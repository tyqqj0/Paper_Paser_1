"""
Metadata fetcher module implementing waterfall logic for literature metadata.

This module implements the intelligent waterfall approach described in the
architecture document, trying different data sources in priority order.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..models.literature import AuthorModel, MetadataModel
from ..services.crossref import CrossRefClient
from ..services.semantic_scholar import SemanticScholarClient
from ..settings import Settings

logger = logging.getLogger(__name__)


class MetadataFetcher:
    """
    Intelligent metadata fetcher using waterfall approach.

    Tries different data sources in priority order:
    1. CrossRef API (for DOI-based lookups)
    2. Semantic Scholar API (for ArXiv and general search)
    3. GROBID (as fallback for PDF parsing)
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize metadata fetcher with API clients."""
        self.settings = settings or Settings()
        self.crossref_client = CrossRefClient(self.settings)
        self.semantic_scholar_client = SemanticScholarClient(self.settings)

    async def fetch_metadata_waterfall(
        self,
        identifiers: Dict[str, Any],
        primary_type: str,
        source_data: Dict[str, Any],
    ) -> Tuple[MetadataModel, Dict[str, Any]]:
        """
        Fetch metadata using waterfall approach.

        Args:
            identifiers: Dictionary containing doi, arxiv_id, fingerprint
            primary_type: Primary identifier type ('doi', 'arxiv', 'fingerprint')
            source_data: Original source data from user request

        Returns:
            Tuple of (MetadataModel, raw_data_dict)
        """
        logger.info(f"Starting metadata fetch with primary type: {primary_type}")

        metadata = None
        raw_data = {}
        source_priority = []

        # Strategy 1: Try CrossRef if we have a DOI
        if identifiers.doi and primary_type == "doi":
            logger.info("Attempting CrossRef lookup...")
            try:
                metadata, raw_data = await self._fetch_from_crossref(identifiers.doi)
                if metadata:
                    source_priority.append("CrossRef API")
                    logger.info("✅ Successfully fetched metadata from CrossRef")
                else:
                    logger.info("❌ No metadata found in CrossRef")
            except Exception as e:
                logger.warning(f"CrossRef lookup failed: {e}")

        # Strategy 2: Try Semantic Scholar if CrossRef failed or we have ArXiv ID
        if not metadata and (identifiers.arxiv_id or identifiers.doi):
            logger.info("Attempting Semantic Scholar lookup...")
            try:
                identifier = identifiers.arxiv_id or identifiers.doi
                id_type = "arxiv" if identifiers.arxiv_id else "doi"

                metadata, raw_data = await self._fetch_from_semantic_scholar(
                    identifier, id_type
                )
                if metadata:
                    source_priority.append("Semantic Scholar API")
                    logger.info(
                        "✅ Successfully fetched metadata from Semantic Scholar"
                    )
                else:
                    logger.info("❌ No metadata found in Semantic Scholar")
            except Exception as e:
                logger.warning(f"Semantic Scholar lookup failed: {e}")

        # Strategy 3: Fallback to source data if all APIs failed
        if not metadata:
            logger.info("All API lookups failed, creating metadata from source data...")
            metadata = self._create_fallback_metadata(source_data, identifiers)
            source_priority.append("Source data fallback")
            raw_data = {"source": "fallback", "original_source": source_data}

        # Update source priority in metadata
        if hasattr(metadata, "source_priority"):
            metadata.source_priority = source_priority

        logger.info(f"Final metadata source priority: {source_priority}")
        return metadata, raw_data

    async def _fetch_from_crossref(
        self, doi: str
    ) -> Tuple[Optional[MetadataModel], Dict]:
        """Fetch metadata from CrossRef API."""
        try:
            crossref_data = await self.crossref_client.get_metadata_by_doi(doi)
            if not crossref_data:
                return None, {}

            # Convert CrossRef data to our MetadataModel
            metadata = self._convert_crossref_to_metadata(crossref_data)
            return metadata, crossref_data

        except Exception as e:
            logger.error(f"CrossRef fetch error: {e}")
            return None, {}

    async def _fetch_from_semantic_scholar(
        self, identifier: str, id_type: str
    ) -> Tuple[Optional[MetadataModel], Dict]:
        """Fetch metadata from Semantic Scholar API."""
        try:
            s2_data = await self.semantic_scholar_client.get_metadata(
                identifier, id_type
            )
            if not s2_data:
                return None, {}

            # Convert Semantic Scholar data to our MetadataModel
            metadata = self._convert_semantic_scholar_to_metadata(s2_data)
            return metadata, s2_data

        except Exception as e:
            logger.error(f"Semantic Scholar fetch error: {e}")
            return None, {}

    def _convert_crossref_to_metadata(self, crossref_data: Dict) -> MetadataModel:
        """Convert CrossRef data to MetadataModel."""
        try:
            # Extract authors
            authors = []
            for author_data in crossref_data.get("authors", []):
                author = AuthorModel(
                    full_name=f"{author_data.get('given_names', [])} {author_data.get('family_name', '')}".strip(),
                    sequence=author_data.get("sequence", "additional"),
                )
                authors.append(author)

            # Create metadata model
            metadata = MetadataModel(
                title=crossref_data.get("title", "Unknown Title"),
                authors=authors,
                year=crossref_data.get("year"),
                journal=crossref_data.get("journal"),
                abstract=crossref_data.get("abstract"),
                keywords=[],  # CrossRef doesn't typically provide keywords
                source_priority=["CrossRef API"],
            )

            return metadata

        except Exception as e:
            logger.error(f"Error converting CrossRef data: {e}")
            return self._create_minimal_metadata("CrossRef conversion error")

    def _convert_semantic_scholar_to_metadata(self, s2_data: Dict) -> MetadataModel:
        """Convert Semantic Scholar data to MetadataModel."""
        try:
            # Extract authors
            authors = []
            for author_data in s2_data.get("authors", []):
                author = AuthorModel(
                    full_name=author_data.get("name", "Unknown Author"),
                    sequence="first" if len(authors) == 0 else "additional",
                )
                authors.append(author)

            # Extract fields of study as keywords
            keywords = []
            for field in s2_data.get("fields_of_study", []):
                if isinstance(field, str):
                    keywords.append(field)

            # Create metadata model
            metadata = MetadataModel(
                title=s2_data.get("title", "Unknown Title"),
                authors=authors,
                year=s2_data.get("year"),
                journal=s2_data.get("venue"),
                abstract=s2_data.get("abstract"),
                keywords=keywords,
                source_priority=["Semantic Scholar API"],
            )

            return metadata

        except Exception as e:
            logger.error(f"Error converting Semantic Scholar data: {e}")
            return self._create_minimal_metadata("Semantic Scholar conversion error")

    def _create_fallback_metadata(
        self, source_data: Dict[str, Any], identifiers: Dict[str, Any]
    ) -> MetadataModel:
        """Create minimal metadata from source data when all APIs fail."""
        # Try to extract title from various sources
        title = source_data.get("title") or source_data.get("url", "Unknown Title")

        if not title or title == "":
            title = "Unknown Title"

        # Create minimal metadata
        metadata = MetadataModel(
            title=title,
            authors=[],
            year=source_data.get("year", 2024),
            journal=source_data.get("journal"),
            abstract=source_data.get("abstract"),
            keywords=source_data.get("keywords", []),
            source_priority=["Source data fallback"],
        )

        return metadata

    def _create_minimal_metadata(self, error_context: str) -> MetadataModel:
        """Create minimal metadata when conversion fails."""
        return MetadataModel(
            title=f"Error: {error_context}",
            authors=[],
            year=2024,
            journal=None,
            abstract=None,
            keywords=[],
            source_priority=["Error fallback"],
        )
