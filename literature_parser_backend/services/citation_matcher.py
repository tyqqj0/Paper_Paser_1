"""
Citation matching service for building literature relationships.

This service implements algorithms to match literature references to existing
LIDs in the system and build citation relationships.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..db.dao import LiteratureDAO
from ..db.alias_dao import AliasDAO
from ..db.relationship_dao import RelationshipDAO
from ..models.relationship import (
    LiteratureRelationshipModel, 
    RelationshipType, 
    MatchingSource
)

logger = logging.getLogger(__name__)


class CitationMatcher:
    """Service for matching literature references to existing LIDs."""

    def __init__(self):
        """Initialize the citation matcher with DAOs."""
        self.literature_dao = LiteratureDAO()
        self.alias_dao = AliasDAO.create_from_global_connection()
        self.relationship_dao = RelationshipDAO.create_from_global_connection()

    async def match_reference_to_lid(
        self, 
        reference_parsed: Dict[str, Any]
    ) -> Optional[tuple[str, MatchingSource, float]]:
        """
        Try to match a parsed reference to an existing LID.
        
        Args:
            reference_parsed: Parsed reference data from semantic scholar or crossref
            
        Returns:
            Tuple of (lid, matching_source, confidence) if match found, None otherwise
        """
        # Strategy 1: Exact ID matching (highest confidence)
        exact_match = await self._exact_id_match(reference_parsed)
        if exact_match:
            return exact_match
        
        # Strategy 2: Semantic Scholar paperId matching
        s2_match = await self._semantic_scholar_id_match(reference_parsed)
        if s2_match:
            return s2_match
            
        # Strategy 3: Title + Author fuzzy matching (lower confidence)
        fuzzy_match = await self._fuzzy_title_author_match(reference_parsed)
        if fuzzy_match:
            return fuzzy_match
            
        return None

    async def _exact_id_match(
        self, 
        reference_parsed: Dict[str, Any]
    ) -> Optional[tuple[str, MatchingSource, float]]:
        """Match using exact external IDs (DOI, ArXiv, etc.)."""
        try:
            external_ids = reference_parsed.get('externalIds', {})
            if not external_ids:
                return None
                
            # Build search data for alias system
            search_data = {}
            matching_source = None
            
            if external_ids.get('DOI'):
                search_data['doi'] = external_ids['DOI']
                matching_source = MatchingSource.EXACT_DOI
                
            elif external_ids.get('ArXiv'):
                search_data['arxiv_id'] = external_ids['ArXiv']
                matching_source = MatchingSource.EXACT_ARXIV
                
            elif external_ids.get('PubMed'):
                search_data['pmid'] = external_ids['PubMed']
                matching_source = MatchingSource.EXACT_PMID
                
            if search_data:
                existing_lid = await self.alias_dao.resolve_to_lid(search_data)
                if existing_lid:
                    logger.info(f"Exact ID match: {search_data} -> {existing_lid}")
                    return existing_lid, matching_source, 0.95
                    
        except Exception as e:
            logger.warning(f"Exact ID match failed: {e}")
            
        return None

    async def _semantic_scholar_id_match(
        self, 
        reference_parsed: Dict[str, Any]
    ) -> Optional[tuple[str, MatchingSource, float]]:
        """Match using Semantic Scholar paperId."""
        try:
            paper_id = reference_parsed.get('paperId')
            if not paper_id:
                return None
                
            # Search in references for matching paperId
            # This is a simplified implementation - in practice you might want 
            # to index paperId separately
            pipeline = [
                {"$match": {"references.parsed.paperId": paper_id}},
                {"$project": {"lid": 1}}
            ]
            
            collection = self.literature_dao.collection
            async for doc in collection.aggregate(pipeline):
                lid = doc.get('lid')
                if lid:
                    logger.info(f"Semantic Scholar ID match: {paper_id} -> {lid}")
                    return lid, MatchingSource.SEMANTIC_SCHOLAR_ID, 0.8
                    
        except Exception as e:
            logger.warning(f"Semantic Scholar ID match failed: {e}")
            
        return None

    async def _fuzzy_title_author_match(
        self, 
        reference_parsed: Dict[str, Any]
    ) -> Optional[tuple[str, MatchingSource, float]]:
        """Match using fuzzy title and author matching."""
        try:
            title = reference_parsed.get('title', '').strip()
            authors = reference_parsed.get('authors', [])
            
            if not title or len(title) < 10:  # Skip very short titles
                return None
                
            # MongoDB text search on title
            collection = self.literature_dao.collection
            cursor = collection.find(
                {"$text": {"$search": title}},
                {"score": {"$meta": "textScore"}, "lid": 1, "metadata.title": 1, "metadata.authors": 1}
            ).sort([("score", {"$meta": "textScore"})]).limit(5)
            
            async for doc in cursor:
                # Simple title similarity check
                doc_title = doc.get('metadata', {}).get('title', '')
                if self._title_similarity(title, doc_title) > 0.8:
                    
                    # Author verification if available
                    if authors:
                        doc_authors = doc.get('metadata', {}).get('authors', [])
                        if self._author_overlap(authors, doc_authors) > 0.5:
                            lid = doc.get('lid')
                            if lid:
                                logger.info(f"Fuzzy match: {title[:50]}... -> {lid}")
                                return lid, MatchingSource.TITLE_AUTHOR_FUZZY, 0.75
                    else:
                        # No authors to verify, rely on title similarity
                        lid = doc.get('lid')
                        if lid:
                            logger.info(f"Title-only fuzzy match: {title[:50]}... -> {lid}")
                            return lid, MatchingSource.TITLE_AUTHOR_FUZZY, 0.7
                            
        except Exception as e:
            logger.warning(f"Fuzzy title/author match failed: {e}")
            
        return None

    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate simple title similarity score."""
        if not title1 or not title2:
            return 0.0
            
        # Simple word-based similarity
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())
        
        if not words1 or not words2:
            return 0.0
            
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0

    def _author_overlap(self, authors1: List[Dict], authors2: List[Dict]) -> float:
        """Calculate author name overlap."""
        if not authors1 or not authors2:
            return 0.0
            
        # Extract author names (handling different formats)
        names1 = set()
        for author in authors1:
            if isinstance(author, dict):
                name = author.get('name') or author.get('full_name', '')
            else:
                name = str(author)
            if name:
                # Use last name for comparison (simple heuristic)
                last_name = name.split()[-1].lower() if name else ''
                if last_name:
                    names1.add(last_name)
                    
        names2 = set()
        for author in authors2:
            if isinstance(author, dict):
                name = author.get('name') or author.get('full_name', '')
            else:
                name = str(author)
            if name:
                last_name = name.split()[-1].lower() if name else ''
                if last_name:
                    names2.add(last_name)
        
        if not names1 or not names2:
            return 0.0
            
        intersection = names1 & names2
        return len(intersection) / min(len(names1), len(names2))

    async def build_citations_for_literature(self, lid: str) -> int:
        """
        Build citation relationships for a single literature.
        
        This is the main entry point for processing a literature's references
        and building citation relationships.
        
        Args:
            lid: Literature ID to process
            
        Returns:
            Number of relationships created
        """
        try:
            logger.info(f"Building citations for literature: {lid}")
            
            # Get the literature
            literature = await self.literature_dao.find_by_lid(lid)
            if not literature:
                logger.warning(f"Literature not found: {lid}")
                return 0
                
            references = literature.references or []
            if not references:
                logger.info(f"No references found for literature: {lid}")
                return 0
                
            logger.info(f"Processing {len(references)} references for {lid}")
            
            relationships_to_create = []
            processed = 0
            matched = 0
            
            for i, reference in enumerate(references):
                processed += 1
                
                if not reference.parsed:
                    continue
                    
                # Try to match this reference to an existing LID
                match_result = await self.match_reference_to_lid(reference.parsed)
                
                if match_result:
                    target_lid, source, confidence = match_result
                    matched += 1
                    
                    # Create relationship model
                    relationship = LiteratureRelationshipModel(
                        from_lid=lid,
                        to_lid=target_lid,
                        relationship_type=RelationshipType.CITES,
                        confidence=confidence,
                        source=source,
                        metadata={
                            "reference_index": i,
                            "raw_reference": reference.raw_text[:200] if reference.raw_text else "",
                            "reference_title": reference.parsed.get('title', ''),
                            "processed_at": datetime.now().isoformat()
                        }
                    )
                    
                    relationships_to_create.append(relationship)
                    
                # Log progress for large reference lists
                if processed % 10 == 0:
                    logger.info(f"Progress: {processed}/{len(references)} references processed, {matched} matched")
            
            # Batch create all relationships
            if relationships_to_create:
                created_ids = await self.relationship_dao.batch_create_relationships(relationships_to_create)
                created_count = len(created_ids)
            else:
                created_count = 0
                
            logger.info(
                f"Citation processing complete for {lid}: "
                f"{processed} references processed, {matched} matched, "
                f"{created_count} relationships created"
            )
            
            return created_count
            
        except Exception as e:
            logger.error(f"Failed to build citations for literature {lid}: {e}")
            return 0

    async def cleanup_relationships_for_literature(self, lid: str) -> int:
        """
        Clean up all relationships when a literature is deleted.
        
        Args:
            lid: Literature ID being deleted
            
        Returns:
            Number of relationships deleted
        """
        try:
            logger.info(f"Cleaning up relationships for deleted literature: {lid}")
            
            deleted_count = await self.relationship_dao.delete_relationships_for_literature(lid)
            
            logger.info(f"Cleaned up {deleted_count} relationships for literature {lid}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup relationships for {lid}: {e}")
            return 0


