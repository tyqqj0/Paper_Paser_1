"""
Citation Relationship Resolver

Analyzes reference data to build citation relationships between literature.
Creates :CITES relationships and :Unresolved placeholder nodes.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from literature_parser_backend.services.literature_matcher import FuzzyMatcher, MatchType
from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.db.relationship_dao import RelationshipDAO

logger = logging.getLogger(__name__)


class UnresolvedReference:
    """Represents an unresolved reference that will become a placeholder node."""
    
    def __init__(self, raw_text: str, parsed_data: Dict[str, Any]):
        self.raw_text = raw_text
        self.parsed_data = parsed_data
        self.placeholder_lid: Optional[str] = None


class ResolvedCitation:
    """Represents a successfully resolved citation relationship."""
    
    def __init__(self, citing_lid: str, cited_lid: str, confidence: float, raw_reference: str):
        self.citing_lid = citing_lid
        self.cited_lid = cited_lid
        self.confidence = confidence
        self.raw_reference = raw_reference


class CitationResolver:
    """
    Resolves literature references into citation relationships.
    
    Core workflow:
    1. Analyze references from a literature
    2. Attempt to match each reference to existing literature
    3. Create :CITES relationships for successful matches
    4. Create :Unresolved placeholder nodes for failed matches
    """
    
    def __init__(self, task_id: str = None):
        """
        Initialize citation resolver.
        
        Args:
            task_id: Task ID for logging context
        """
        self.task_id = task_id
        self.matcher = None  # Will be initialized with DAO
        self.literature_dao = None
        self.relationship_dao = None
        
    async def initialize_with_dao(self, literature_dao: LiteratureDAO):
        """
        Initialize resolver with data access objects.
        
        Args:
            literature_dao: Literature DAO for querying existing literature
        """
        self.literature_dao = literature_dao
        self.relationship_dao = RelationshipDAO.create_from_task_connection(
            literature_dao.driver if hasattr(literature_dao, 'driver') else None
        )
        self.matcher = FuzzyMatcher(dao=literature_dao)
        
    async def resolve_citations_for_literature(
        self, 
        citing_literature_lid: str, 
        references: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Resolve all citations for a literature and create relationships.
        
        Args:
            citing_literature_lid: LID of the literature doing the citing
            references: List of reference data from the literature
            
        Returns:
            Dictionary with resolution statistics and results
        """
        if not self.matcher or not self.literature_dao or not self.relationship_dao:
            raise ValueError("CitationResolver not properly initialized. Call initialize_with_dao first.")
            
        logger.info(f"Task {self.task_id}: Starting citation resolution for {citing_literature_lid} with {len(references)} references")
        
        resolved_citations = []
        unresolved_references = []
        
        # Process each reference
        for i, reference in enumerate(references):
            try:
                logger.debug(f"Task {self.task_id}: Processing reference {i+1}/{len(references)}")
                
                # Attempt to resolve the reference
                result = await self._resolve_single_reference(
                    citing_literature_lid, 
                    reference, 
                    reference_index=i
                )
                
                if result["resolved"]:
                    resolved_citations.append(result["citation"])
                else:
                    unresolved_references.append(result["unresolved"])
                    
            except Exception as e:
                logger.error(f"Task {self.task_id}: Error processing reference {i+1}: {e}")
                # Continue processing other references
                continue
        
        # Create relationships in Neo4j
        await self._create_citation_relationships(resolved_citations)
        await self._create_unresolved_placeholders(citing_literature_lid, unresolved_references)
        
        stats = {
            "total_references": len(references),
            "resolved_citations": len(resolved_citations),
            "unresolved_references": len(unresolved_references),
            "resolution_rate": len(resolved_citations) / len(references) if references else 0.0
        }
        
        logger.info(f"Task {self.task_id}: Citation resolution completed: {stats}")
        return {
            "statistics": stats,
            "resolved_citations": resolved_citations,
            "unresolved_references": unresolved_references
        }
    
    async def _resolve_single_reference(
        self, 
        citing_lid: str, 
        reference: Dict[str, Any], 
        reference_index: int
    ) -> Dict[str, Any]:
        """
        Attempt to resolve a single reference to an existing literature.
        
        Args:
            citing_lid: LID of the citing literature
            reference: Reference data to resolve
            reference_index: Index of reference in the list
            
        Returns:
            Dictionary with resolution result
        """
        try:
            # Extract structured data from reference
            parsed_ref = self._parse_reference_data(reference)
            
            if not parsed_ref:
                logger.debug(f"Task {self.task_id}: Could not parse reference {reference_index + 1}")
                return {
                    "resolved": False,
                    "unresolved": UnresolvedReference(
                        raw_text=str(reference),
                        parsed_data={}
                    )
                }
            
            # Attempt fuzzy matching
            matches = await self.matcher.find_matches(
                source=parsed_ref,
                match_type=MatchType.CITATION,  # Use citation-specific matching
                threshold=0.6,  # Lower threshold for citations
                max_candidates=3
            )
            
            if matches:
                best_match = matches[0]
                logger.debug(f"Task {self.task_id}: Reference {reference_index + 1} matched to {best_match.lid} (confidence: {best_match.confidence:.2f})")
                
                return {
                    "resolved": True,
                    "citation": ResolvedCitation(
                        citing_lid=citing_lid,
                        cited_lid=best_match.lid,
                        confidence=best_match.confidence,
                        raw_reference=str(reference)
                    )
                }
            else:
                logger.debug(f"Task {self.task_id}: Reference {reference_index + 1} could not be matched")
                return {
                    "resolved": False,
                    "unresolved": UnresolvedReference(
                        raw_text=str(reference),
                        parsed_data=parsed_ref
                    )
                }
                
        except Exception as e:
            logger.error(f"Task {self.task_id}: Error resolving reference {reference_index + 1}: {e}")
            return {
                "resolved": False,
                "unresolved": UnresolvedReference(
                    raw_text=str(reference),
                    parsed_data={}
                )
            }
    
    def _parse_reference_data(self, reference) -> Optional[Dict[str, Any]]:
        """
        Parse reference data into standardized format for matching.
        
        Args:
            reference: ReferenceModel object or dict
            
        Returns:
            Parsed reference data or None if parsing fails
        """
        try:
            parsed = {}
            
            # Handle both ReferenceModel objects and dictionaries
            if hasattr(reference, 'parsed') and reference.parsed:
                # ReferenceModel object - use the parsed field
                reference_data = reference.parsed
            elif isinstance(reference, dict):
                # Already a dictionary
                reference_data = reference
            else:
                # Unknown format, try to access as dict
                reference_data = reference
            
            # Extract title
            title = reference_data.get("title", "").strip()
            if title:
                parsed["title"] = title
            
            # Extract authors
            authors = reference_data.get("authors") or reference_data.get("author", [])
            if authors:
                parsed["authors"] = authors
            
            # Extract DOI
            doi = reference_data.get("doi", "").strip()
            if doi:
                parsed["doi"] = doi
                parsed["identifiers"] = {"doi": doi}
            
            # Extract year
            year = reference_data.get("year")
            if year:
                try:
                    parsed["year"] = int(year)
                except (ValueError, TypeError):
                    pass
            
            # Extract journal
            journal = reference_data.get("journal") or reference_data.get("venue", "")
            if journal:
                parsed["journal"] = journal.strip()
            
            # Require at least title or DOI for meaningful matching
            if not parsed.get("title") and not parsed.get("doi"):
                return None
                
            return parsed
            
        except Exception as e:
            logger.warning(f"Task {self.task_id}: Error parsing reference data: {e}")
            return None
    
    async def _create_citation_relationships(self, resolved_citations: List[ResolvedCitation]):
        """
        Create :CITES relationships in Neo4j for resolved citations.
        
        Args:
            resolved_citations: List of successfully resolved citations
        """
        if not resolved_citations:
            return
            
        logger.info(f"Task {self.task_id}: Creating {len(resolved_citations)} citation relationships")
        
        try:
            for citation in resolved_citations:
                await self.relationship_dao.create_citation_relationship(
                    citing_lid=citation.citing_lid,
                    cited_lid=citation.cited_lid,
                    relationship_data={
                        "confidence": citation.confidence,
                        "raw_reference": citation.raw_reference,
                        "created_at": datetime.now().isoformat(),
                        "source": "citation_resolver"
                    }
                )
                
            logger.info(f"Task {self.task_id}: Successfully created {len(resolved_citations)} citation relationships")
            
        except Exception as e:
            logger.error(f"Task {self.task_id}: Error creating citation relationships: {e}")
            raise
    
    async def _create_unresolved_placeholders(
        self, 
        citing_lid: str, 
        unresolved_refs: List[UnresolvedReference]
    ):
        """
        Create :Unresolved placeholder nodes for unmatched references.
        
        Args:
            citing_lid: LID of the citing literature
            unresolved_refs: List of unresolved references
        """
        if not unresolved_refs:
            return
            
        logger.info(f"Task {self.task_id}: Creating {len(unresolved_refs)} unresolved placeholder nodes")
        
        try:
            for unresolved in unresolved_refs:
                # Generate placeholder LID
                placeholder_lid = self._generate_placeholder_lid(unresolved.parsed_data)
                unresolved.placeholder_lid = placeholder_lid
                
                # Create placeholder node and relationship
                await self.relationship_dao.create_unresolved_citation(
                    citing_lid=citing_lid,
                    placeholder_lid=placeholder_lid,
                    reference_data={
                        "raw_text": unresolved.raw_text,
                        "parsed_data": unresolved.parsed_data,
                        "created_at": datetime.now().isoformat(),
                        "source": "citation_resolver"
                    }
                )
                
            logger.info(f"Task {self.task_id}: Successfully created {len(unresolved_refs)} placeholder nodes")
            
        except Exception as e:
            logger.error(f"Task {self.task_id}: Error creating placeholder nodes: {e}")
            raise
    
    def _generate_placeholder_lid(self, parsed_data: Dict[str, Any]) -> str:
        """
        Generate a placeholder LID for an unresolved reference.
        
        Args:
            parsed_data: Parsed reference data
            
        Returns:
            Generated placeholder LID
        """
        import hashlib
        
        # Create a hash from available reference data
        reference_string = ""
        
        if parsed_data.get("title"):
            reference_string += parsed_data["title"]
        if parsed_data.get("doi"):
            reference_string += parsed_data["doi"]
        if parsed_data.get("authors"):
            reference_string += str(parsed_data["authors"])
        if parsed_data.get("year"):
            reference_string += str(parsed_data["year"])
            
        if not reference_string:
            reference_string = f"unresolved_{datetime.now().timestamp()}"
            
        # Generate short hash
        hash_object = hashlib.md5(reference_string.encode())
        short_hash = hash_object.hexdigest()[:8]
        
        return f"unresolved-{short_hash}"

