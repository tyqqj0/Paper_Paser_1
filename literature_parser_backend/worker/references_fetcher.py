"""
References fetcher module implementing waterfall logic for literature references.

This module implements the intelligent waterfall approach for fetching references,
trying different data sources in priority order.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..models.literature import ReferenceModel
from ..services.grobid import GrobidClient
from ..services.semantic_scholar import SemanticScholarClient
from ..settings import Settings

logger = logging.getLogger(__name__)


class ReferencesFetcher:
    """Fetches references from various sources."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize references fetcher with API clients."""
        self.settings = settings or Settings()
        self.semantic_scholar_client = SemanticScholarClient(settings)
        self.grobid_client = GrobidClient(settings)

    def fetch_references_waterfall(
        self,
        identifiers: Dict[str, Optional[str]],
        pdf_content: Optional[bytes] = None,
    ) -> Tuple[List[ReferenceModel], Dict[str, Any]]:
        """
        Fetch references using waterfall: Semantic Scholar -> GROBID fallback.
        """
        logger.info(f"Starting references fetch for identifiers: {identifiers}")

        references: List[ReferenceModel] = []
        raw_data: Dict[str, Any] = {}

        # 1. Try Semantic Scholar API
        identifier = identifiers.get("doi") or identifiers.get("arxiv_id")
        if identifier:
            logger.info(
                "Attempting to fetch references from Semantic Scholar for "
                f"identifier: {identifier}",
            )
            try:
                s2_refs = self.semantic_scholar_client.get_references(identifier)
                if s2_refs:
                    raw_data["semantic_scholar"] = s2_refs
                    for ref_data in s2_refs:
                        # Ensure 'title' is not None before creating the model
                        if ref_data.get("title"):
                            references.append(
                                ReferenceModel(
                                    raw_text=ref_data.get(
                                        "raw_text",
                                        ref_data.get("title"),
                                    ),
                                    parsed=ref_data,
                                    source="semantic_scholar",
                                ),
                            )
                    logger.info(
                        f"✅ Successfully fetched {len(references)} references.",
                    )
                    # If we get results from S2, we are done.
                    if references:
                        return references, raw_data
            except Exception as e:
                logger.warning(
                    "Semantic Scholar API for references failed: %s. "
                    "Will try GROBID fallback.",
                    e,
                )

        # 2. Fallback to GROBID if we have PDF content
        if not references and pdf_content:
            logger.info("Falling back to GROBID for reference extraction from PDF.")
            try:
                # Use the 'processReferences' service for better performance
                grobid_data = self.grobid_client.process_pdf(
                    pdf_content,
                    service="processReferences",
                )
                if grobid_data and isinstance(grobid_data, list):
                    raw_data["grobid"] = grobid_data
                    # Placeholder for a proper TEI XML to ReferenceModel conversion
                    for ref_text in grobid_data:
                        references.append(
                            ReferenceModel(raw_text=ref_text, source="grobid_fallback"),
                        )
                    logger.info(
                        f"✅ Successfully parsed {len(references)} reference strings from PDF.",
                    )
                else:
                    logger.warning(
                        f"GROBID did not return a list of references. Output: {grobid_data}",
                    )
            except Exception as e:
                logger.error(f"GROBID reference parsing failed: {e}", exc_info=True)

        return references, raw_data
