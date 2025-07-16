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
        Fetch references using waterfall approach.

        Args:
            identifiers: IdentifiersModel object containing doi, arxiv_id, fingerprint
            primary_type: Primary identifier type ('doi', 'arxiv', 'fingerprint')
            pdf_content: Optional PDF content for GROBID processing

        Returns:
            Tuple of (List[ReferenceModel], raw_data_dict)
        """
        logger.info(f"Starting references fetch with primary type: {primary_type}")

        references: List[ReferenceModel] = []
        raw_data: Dict[str, Any] = {}

        # Strategy 1: Use Semantic Scholar API if an identifier is available
        identifier = identifiers.get("arxiv_id") or identifiers.get("doi")
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
                    # If we get results from S2, we can consider it done.
                    return references, raw_data
            except Exception as e:
                logger.warning(
                    "Semantic Scholar API for references failed: %s. "
                    "Will try GROBID fallback.",
                    e,
                )

        # Strategy 2: Fallback to GROBID if we have PDF content
        if pdf_content:
            logger.info("Attempting to parse references from PDF using GROBID.")
            try:
                grobid_data = self.grobid_client.process_pdf(
                    pdf_content,
                    service="processReferences",
                )
                if grobid_data:
                    raw_data["grobid"] = grobid_data
                    for ref_data in grobid_data:
                        references.append(
                            ReferenceModel(
                                raw_text=ref_data.get("raw_text", ""),
                                parsed=ref_data,
                                source="grobid",
                            ),
                        )
                    logger.info(
                        f"✅ Successfully parsed {len(references)} references from PDF.",
                    )
            except Exception as e:
                logger.error(f"GROBID reference parsing failed: {e}")

        return references, raw_data
