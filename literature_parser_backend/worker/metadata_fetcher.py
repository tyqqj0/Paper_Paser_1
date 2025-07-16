"""
Metadata fetcher module implementing waterfall logic for literature metadata.

This module implements the intelligent waterfall approach described in the
architecture document, trying different data sources in priority order.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..models.literature import AuthorModel, IdentifiersModel, MetadataModel
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

    def fetch_metadata_waterfall(
        self,
        identifiers: IdentifiersModel,
        primary_type: str,
        source_data: Dict[str, Any],
    ) -> Tuple[Optional[MetadataModel], Dict[str, Any]]:
        """
        Fetch metadata using a waterfall approach.

        Args:
            identifiers: Dictionary containing doi, arxiv_id, etc.
            primary_type: The primary identifier type ('doi', 'arxiv').
            source_data: Original data from the user request.

        Returns:
            A tuple of (MetadataModel, raw_data_dict).
        """
        logger.info(f"Starting metadata fetch with primary type: {primary_type}")

        metadata: Optional[MetadataModel] = None
        raw_data: Dict[str, Any] = {}
        source_priority: List[str] = []

        # Strategy 1: Try CrossRef if we have a DOI
        if identifiers.get("doi") and primary_type == "doi":
            logger.info("Attempting CrossRef lookup...")
            try:
                crossref_metadata, crossref_raw_data = self._fetch_from_crossref(
                    identifiers["doi"],
                )
                if crossref_metadata:
                    metadata = crossref_metadata
                    raw_data["crossref"] = crossref_raw_data
                    source_priority.append("CrossRef API")
                    logger.info("✅ Successfully fetched metadata from CrossRef")
            except Exception as e:
                logger.warning(f"CrossRef lookup failed: {e}")

        # Strategy 2: Try Semantic Scholar if CrossRef failed or we have ArXiv ID
        if not metadata and (identifiers.get("arxiv_id") or identifiers.get("doi")):
            logger.info("Attempting Semantic Scholar lookup...")
            try:
                identifier = identifiers.get("arxiv_id") or identifiers.get("doi")
                id_type = "arxiv" if identifiers.get("arxiv_id") else "doi"

                if identifier:
                    (
                        s2_metadata,
                        s2_raw_data,
                    ) = self._fetch_from_semantic_scholar(identifier, id_type)
                    if s2_metadata:
                        metadata = s2_metadata
                        raw_data["semantic_scholar"] = s2_raw_data
                        source_priority.append("Semantic Scholar API")
                        logger.info(
                            "✅ Successfully fetched metadata from Semantic Scholar",
                        )
                    else:
                        logger.info("❌ No metadata found in Semantic Scholar")
            except Exception as e:
                logger.warning(f"Semantic Scholar lookup failed: {e}")

        # Strategy 3: Fallback to source data if all APIs failed
        if not metadata:
            logger.info("All API lookups failed, creating metadata from source data...")
            metadata = self._create_fallback_metadata(source_data)
            source_priority.append("Source data fallback")
            raw_data = {"source": "fallback", "original_source": source_data}

        # Update source priority in metadata
        if hasattr(metadata, "source_priority"):
            metadata.source_priority = source_priority

        logger.info(f"Final metadata source priority: {source_priority}")
        return metadata, raw_data

    def _fetch_from_crossref(
        self,
        doi: str,
    ) -> Tuple[Optional[MetadataModel], Dict[str, Any]]:
        """Fetch and parse metadata from CrossRef."""
        try:
            crossref_data = self.crossref_client.get_metadata_by_doi(doi)
            if not crossref_data:
                return None, {}

            metadata = self._convert_crossref_to_metadata(crossref_data)
            return metadata, crossref_data

        except Exception as e:
            logger.error(f"Error fetching from CrossRef: {e}")
            return None, {"error": str(e)}

    def _fetch_from_semantic_scholar(
        self,
        identifier: str,
        id_type: str,
    ) -> Tuple[Optional[MetadataModel], Dict[str, Any]]:
        """Fetch and parse metadata from Semantic Scholar."""
        try:
            s2_data = self.semantic_scholar_client.get_metadata(
                identifier,
                id_type=id_type,
            )
            if not s2_data:
                return None, {}

            metadata = self._convert_semantic_scholar_to_metadata(s2_data)
            return metadata, s2_data

        except Exception as e:
            logger.error(f"Error fetching from Semantic Scholar: {e}")
            return None, {"error": str(e)}

    def _convert_crossref_to_metadata(
        self,
        crossref_data: Dict[str, Any],
    ) -> MetadataModel:
        """Convert CrossRef API response to a standardized MetadataModel."""
        authors = []
        for author_data in crossref_data.get("author", []):
            name = (
                f"{author_data.get('given', '')} "
                f"{author_data.get('family', '')}".strip()
            )
            if name:
                authors.append(AuthorModel(name=name))

        year = None
        published = crossref_data.get("published", {})
        if published and "date-parts" in published:
            year = int(published["date-parts"][0][0])

        metadata = MetadataModel(
            title=crossref_data.get("title", [None])[0] or "Unknown Title",
            authors=authors,
            year=year,
            journal=crossref_data.get("container-title", [None])[0],
            abstract=crossref_data.get("abstract"),
        )
        return metadata

    def _convert_semantic_scholar_to_metadata(
        self,
        s2_data: Dict[str, Any],
    ) -> MetadataModel:
        """Convert Semantic Scholar API response to a standardized MetadataModel."""
        authors = []
        for author_data in s2_data.get("authors", []):
            authors.append(
                AuthorModel(
                    name=author_data.get("name"),
                    s2_id=author_data.get("authorId"),
                ),
            )

        metadata = MetadataModel(
            title=s2_data.get("title") or "Unknown Title",
            authors=authors,
            year=s2_data.get("year"),
            journal=s2_data.get("venue"),
            abstract=s2_data.get("abstract"),
        )
        return metadata

    def _create_fallback_metadata(self, source_data: Dict[str, Any]) -> MetadataModel:
        """Create a fallback MetadataModel from the initial user-provided source."""
        authors = []
        for author_name in source_data.get("authors", []):
            if isinstance(author_name, str):
                authors.append(AuthorModel(name=author_name))

        metadata = MetadataModel(
            title=source_data.get("title") or "Unknown Title",
            authors=authors,
            year=None,
            journal=None,
            abstract=None,
        )
        return metadata
