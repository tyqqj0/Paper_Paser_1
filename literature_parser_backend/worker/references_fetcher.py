"""
References fetcher module implementing waterfall logic for literature references.

This module implements the intelligent waterfall approach for fetching references,
trying different data sources in priority order.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..models.literature import ReferenceModel
from ..services.semantic_scholar import SemanticScholarClient
from ..settings import Settings

logger = logging.getLogger(__name__)


class ReferencesFetcher:
    """
    Intelligent references fetcher using waterfall approach.

    Tries different data sources in priority order:
    1. Semantic Scholar API (for paper references)
    2. GROBID (for PDF-extracted references)
    3. Fallback to empty references
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize references fetcher with API clients."""
        self.settings = settings or Settings()
        self.semantic_scholar_client = SemanticScholarClient(self.settings)

    def fetch_references_waterfall(
        self,
        identifiers,  # IdentifiersModel object
        primary_type: str,
        pdf_content: Optional[bytes] = None,
    ) -> Tuple[List[ReferenceModel], Dict[str, Any]]:
        """
        Fetch references using waterfall approach.

        Args:
            identifiers: IdentifiersModel object containing doi, arxiv_id, fingerprint
            primary_type: Primary identifier type ('doi', 'arxiv', 'fingerprint')
            pdf_content: Optional PDF content for GROBID processing

        Returns:
            Tuple of (List[ReferenceModel], raw_data_dict)
        """
        logger.info(f"Starting references fetch with primary type: {primary_type}")

        references = []
        raw_data = {}

        # Strategy 1: Try Semantic Scholar if we have a DOI or ArXiv ID
        if identifiers.doi or identifiers.arxiv_id:
            logger.info("Attempting Semantic Scholar references lookup...")
            try:
                references, raw_data = self._fetch_from_semantic_scholar(
                    identifiers.doi or identifiers.arxiv_id,
                    "doi" if identifiers.doi else "arxiv",
                )
                if references:
                    logger.info(
                        f"✅ Successfully fetched {len(references)} references from Semantic Scholar",
                    )
                else:
                    logger.info("❌ No references found in Semantic Scholar")
            except Exception as e:
                logger.warning(f"Semantic Scholar references lookup failed: {e}")

        # Strategy 2: Try GROBID if we have PDF content and no references yet
        if not references and pdf_content:
            logger.info("Attempting GROBID references extraction...")
            try:
                references, raw_data = self._fetch_from_grobid(pdf_content)
                if references:
                    logger.info(
                        f"✅ Successfully extracted {len(references)} references from GROBID",
                    )
                else:
                    logger.info("❌ No references extracted from GROBID")
            except Exception as e:
                logger.warning(f"GROBID references extraction failed: {e}")

        # Strategy 3: Fallback to empty references with explanation
        if not references:
            logger.info(
                "All references fetching methods failed, using empty references",
            )
            references = []
            raw_data = {
                "source": "fallback",
                "message": "No references found through available methods",
                "attempted_sources": (
                    ["Semantic Scholar", "GROBID"]
                    if pdf_content
                    else ["Semantic Scholar"]
                ),
            }

        return references, raw_data

    def _fetch_from_semantic_scholar(
        self,
        identifier: str,
        id_type: str,
    ) -> Tuple[List[ReferenceModel], Dict[str, Any]]:
        """
        Fetch references from Semantic Scholar API.

        Args:
            identifier: DOI or ArXiv ID
            id_type: Type of identifier ('doi' or 'arxiv')

        Returns:
            Tuple of (List[ReferenceModel], raw_data_dict)
        """
        try:
            # Use the get_references method directly
            references_data = self.semantic_scholar_client.get_references(
                identifier,
                limit=50,
            )

            if not references_data:
                return [], {"source": "Semantic Scholar", "references_count": 0}

            references = []
            for ref_data in references_data:
                # Extract reference information
                title = ref_data.get("title", "")
                authors = [
                    author.get("name", "") for author in ref_data.get("authors", [])
                ]
                year = ref_data.get("year")
                venue = ref_data.get("venue", "")

                # Create parsed reference data
                parsed_data = {
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "venue": venue,
                    "doi": (
                        ref_data.get("externalIds", {}).get("DOI")
                        if ref_data.get("externalIds")
                        else None
                    ),
                    "arxiv": (
                        ref_data.get("externalIds", {}).get("ArXiv")
                        if ref_data.get("externalIds")
                        else None
                    ),
                    "semantic_scholar_id": ref_data.get("paperId"),
                    "citation_count": ref_data.get("citationCount", 0),
                    "is_open_access": ref_data.get("isOpenAccess", False),
                    "url": ref_data.get("url"),
                }

                # Create raw text representation
                authors_str = ", ".join(authors[:3])  # First 3 authors
                if len(authors) > 3:
                    authors_str += " et al."

                year_str = f" ({year})" if year else ""
                venue_str = f" {venue}." if venue else ""

                raw_text = f"{authors_str}{year_str} {title}.{venue_str}"

                reference = ReferenceModel(
                    raw_text=raw_text,
                    parsed=parsed_data,
                    source="Semantic Scholar API",
                )

                references.append(reference)

            raw_data = {
                "source": "Semantic Scholar",
                "total_references": len(references_data),
                "processed_references": len(references),
            }

            return references, raw_data

        except Exception as e:
            logger.error(f"Error fetching references from Semantic Scholar: {e}")
            return [], {}

    def _fetch_from_grobid(
        self,
        pdf_content: bytes,
    ) -> Tuple[List[ReferenceModel], Dict[str, Any]]:
        """
        Extract references from PDF using GROBID.

        Args:
            pdf_content: PDF file content as bytes

        Returns:
            Tuple of (List[ReferenceModel], raw_data_dict)
        """
        try:
            # This would require GROBID client integration
            # For now, return empty results as placeholder
            logger.info("GROBID references extraction not yet implemented")
            return [], {"source": "GROBID", "status": "not_implemented"}

        except Exception as e:
            logger.error(f"Error extracting references from GROBID: {e}")
            return [], {}

    def _create_fallback_references(
        self,
        source_data: Dict[str, Any],
    ) -> List[ReferenceModel]:
        """
        Create fallback references from source data if available.

        Args:
            source_data: Original source data from user request

        Returns:
            List of fallback ReferenceModel objects
        """
        # Currently no fallback references logic
        return []
