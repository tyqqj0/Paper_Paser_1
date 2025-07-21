"""
Metadata fetcher module implementing waterfall logic for literature metadata.

This module implements the intelligent waterfall approach described in the
architecture document, trying different data sources in priority order.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..models.literature import AuthorModel, MetadataModel
from ..services.crossref import CrossRefClient
from ..services.grobid import GrobidClient
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
        identifiers: Dict[str, Any],
        source_data: Dict[str, Any],
        pre_fetched_metadata: Optional[MetadataModel] = None,
        pdf_content: Optional[bytes] = None,
    ) -> Tuple[Optional[MetadataModel], Dict[str, Any]]:
        """
        Fetch metadata using a waterfall approach.
        Priority: Pre-fetched > CrossRef > Semantic Scholar > GROBID > Fallback
        """
        logger.info(f"Starting metadata fetch for identifiers: {identifiers}")

        # 1. Use pre-fetched metadata if available
        if pre_fetched_metadata and pre_fetched_metadata.title != "Unknown Title":
            logger.info("Using pre-fetched metadata from initial GROBID parse.")
            return pre_fetched_metadata, {"source": "pre-fetched"}

        metadata: Optional[MetadataModel] = None
        raw_data: Dict[str, Any] = {}
        source_priority: List[str] = []

        # 2. Try CrossRef if DOI is available
        if identifiers.get("doi"):
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

        # 3. Try Semantic Scholar
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

                        # Try extracting ArXiv ID from DOI if DOI lookup failed
                        if id_type == "doi":
                            extracted_arxiv_id = self._extract_arxiv_id_from_doi(
                                identifier,
                            )
                            if extracted_arxiv_id:
                                logger.info(
                                    f"Extracted ArXiv ID {extracted_arxiv_id} from DOI, retrying...",
                                )
                                (
                                    s2_metadata,
                                    s2_raw_data,
                                ) = self._fetch_from_semantic_scholar(
                                    extracted_arxiv_id, "arxiv",
                                )
                                if s2_metadata:
                                    metadata = s2_metadata
                                    raw_data["semantic_scholar"] = s2_raw_data
                                    source_priority.append(
                                        "Semantic Scholar API (ArXiv ID extracted from DOI)",
                                    )
                                    logger.info(
                                        "✅ Successfully fetched metadata using extracted ArXiv ID",
                                    )
            except Exception as e:
                logger.warning(f"Semantic Scholar lookup failed: {e}")

                # Try extracting ArXiv ID from DOI if DOI lookup failed due to exception
                if not metadata and identifiers.get("doi"):
                    extracted_arxiv_id = self._extract_arxiv_id_from_doi(
                        identifiers.get("doi"),
                    )
                    if extracted_arxiv_id:
                        logger.info(
                            f"Extracted ArXiv ID {extracted_arxiv_id} from DOI after exception, retrying...",
                        )
                        try:
                            (
                                s2_metadata,
                                s2_raw_data,
                            ) = self._fetch_from_semantic_scholar(
                                extracted_arxiv_id, "arxiv",
                            )
                            if s2_metadata:
                                metadata = s2_metadata
                                raw_data["semantic_scholar"] = s2_raw_data
                                source_priority.append(
                                    "Semantic Scholar API (ArXiv ID extracted from DOI after exception)",
                                )
                                logger.info(
                                    "✅ Successfully fetched metadata using extracted ArXiv ID after exception",
                                )
                        except Exception as e2:
                            logger.warning(f"ArXiv ID retry also failed: {e2}")

        # 4. Fallback to GROBID if we have PDF content
        if not metadata and pdf_content:
            logger.info("Attempting metadata extraction from PDF using GROBID.")
            try:
                grobid_client = GrobidClient(self.settings)
                header_data = grobid_client.process_header_only(pdf_content)
                if header_data:
                    from ..worker.utils import convert_grobid_to_metadata

                    metadata = convert_grobid_to_metadata(header_data)
                    raw_data["grobid"] = header_data
                    source_priority.append("GROBID")
                    logger.info("✅ Successfully fetched metadata from GROBID.")
            except Exception as e:
                logger.warning(f"GROBID metadata extraction failed: {e}")

        # 5. Fallback to source data if all else fails
        if not metadata:
            logger.info("All API lookups failed, creating metadata from source data...")
            metadata = self._create_fallback_metadata(source_data)
            source_priority.append("Source data fallback")
            raw_data = {"source": "fallback", "original_source": source_data}

        if metadata:
            metadata.source_priority = source_priority
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

    def _extract_arxiv_id_from_doi(self, doi: str) -> Optional[str]:
        """Extract ArXiv ID from DOI patterns like 10.48550/arXiv.1706.03762."""
        import re

        # Pattern 1: 10.48550/arXiv.XXXX.XXXXX
        pattern1 = r"10\.48550/arXiv\.(\d{4}\.\d{4,5})"
        match1 = re.search(pattern1, doi)
        if match1:
            return match1.group(1)

        # Pattern 2: 10.48550/arXiv.XXXX.XXXXX vN (with version)
        pattern2 = r"10\.48550/arXiv\.(\d{4}\.\d{4,5})v\d+"
        match2 = re.search(pattern2, doi)
        if match2:
            return match2.group(1)

        # Pattern 3: Direct arXiv in DOI like arxiv.org/abs/XXXX.XXXXX
        pattern3 = r"arxiv\.org/abs/(\d{4}\.\d{4,5})"
        match3 = re.search(pattern3, doi)
        if match3:
            return match3.group(1)

        return None

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
