"""
Content fetcher module implementing waterfall logic for literature content/PDF.

This module implements the intelligent waterfall approach for fetching content,
following the three-step process outlined in the architecture document.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.exceptions import RequestException, Timeout

from ..models.literature import ContentModel, IdentifiersModel
from ..services.grobid import GrobidClient
from ..settings import Settings

logger = logging.getLogger(__name__)


class ContentFetcher:
    """
    Intelligent content fetcher using waterfall approach.

    Follows the three-step process:
    1. Direct download from user-provided PDF link
    2. Attempt auto-download from inferred URLs (ArXiv, etc.)
    3. Return status indicating PDF unavailable for frontend handling
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize content fetcher with required clients."""
        self.settings = settings or Settings()
        self.grobid_client = GrobidClient(self.settings)

    def fetch_content_waterfall(
        self,
        identifiers: IdentifiersModel,
        source_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ContentModel, Optional[bytes], Dict[str, Any]]:
        """
        Fetch content using waterfall approach.

        Args:
            identifiers: IdentifiersModel object containing doi, arxiv_id, fingerprint
            source_data: Original source data from user request
            metadata: Previously fetched metadata (may contain URLs)

        Returns:
            Tuple of (ContentModel, pdf_bytes, raw_data_dict)
        """
        logger.info("Starting content fetch using waterfall approach")

        content_model = ContentModel()
        pdf_content = None
        sources_tried: List[str] = []
        raw_data: Dict[str, Any] = {
            "sources_tried": sources_tried,
            "download_status": "pending",
        }

        # Step 1: Try user-provided PDF URL
        user_pdf_url = source_data.get("pdf_url")
        if user_pdf_url:
            logger.info(
                f"Step 1: Attempting download from user-provided PDF URL: {user_pdf_url}",
            )
            sources_tried.append(f"user_pdf_url: {user_pdf_url}")

            pdf_content = self._download_pdf(user_pdf_url)
            if pdf_content:
                content_model.pdf_url = user_pdf_url
                content_model.source_page_url = None
                raw_data["download_status"] = "success_user_pdf"
                logger.info("✅ Successfully downloaded from user-provided PDF URL")

                # Parse with GROBID if we have PDF content
                self._parse_with_grobid(content_model, pdf_content, raw_data)
                content_model.sources_tried = sources_tried
                return content_model, pdf_content, raw_data
            else:
                logger.warning("❌ Failed to download from user-provided PDF URL")

        # Step 2: Try auto-download from inferred URLs
        inferred_urls = self._infer_pdf_urls(identifiers, source_data, metadata)

        for url_info in inferred_urls:
            url = url_info["url"]
            source_type = url_info["type"]
            logger.info(f"Step 2: Attempting auto-download from {source_type}: {url}")
            sources_tried.append(f"{source_type}: {url}")

            pdf_content = self._download_pdf(url)
            if pdf_content:
                content_model.pdf_url = url
                content_model.source_page_url = (
                    source_data.get("url")
                    if not source_data.get("url", "").endswith(".pdf")
                    else None
                )
                raw_data["download_status"] = f"success_auto_{source_type}"
                logger.info(f"✅ Successfully downloaded from {source_type}")

                # Parse with GROBID if we have PDF content
                self._parse_with_grobid(content_model, pdf_content, raw_data)
                content_model.sources_tried = sources_tried
                return content_model, pdf_content, raw_data
            else:
                logger.warning(f"❌ Failed to download from {source_type}: {url}")

        # Step 3: No PDF available - return status for frontend handling
        logger.info("Step 3: No PDF available for download")
        content_model.pdf_url = None
        content_model.source_page_url = (
            source_data.get("url")
            if source_data.get("url")
            and not source_data.get("url", "").endswith(".pdf")
            else None
        )
        raw_data["download_status"] = "pdf_unavailable"
        content_model.sources_tried = sources_tried

        return content_model, None, raw_data

    def _infer_pdf_urls(
        self,
        identifiers: IdentifiersModel,
        source_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        """
        Infer possible PDF URLs from available information.

        Returns:
            List of {"url": str, "type": str} dictionaries
        """
        urls = []

        # ArXiv PDF URL
        if identifiers.arxiv_id:
            arxiv_pdf_url = f"https://arxiv.org/pdf/{identifiers.arxiv_id}.pdf"
            urls.append({"url": arxiv_pdf_url, "type": "arxiv"})

        # DOI-based URLs (some publishers provide direct PDF access)
        if identifiers.doi:
            # Try common publisher PDF patterns
            doi_part = identifiers.doi.replace("10.", "").replace("/", "_")

            # Nature papers
            if "nature" in identifiers.doi.lower():
                nature_pdf = f"https://www.nature.com/articles/{identifiers.doi}.pdf"
                urls.append({"url": nature_pdf, "type": "nature_publisher"})

        # Check if source URL is already a PDF
        source_url = source_data.get("url")
        if source_url and source_url.endswith(".pdf"):
            urls.append({"url": source_url, "type": "source_pdf"})

        # Look for PDF URLs in metadata (from CrossRef, etc.)
        if metadata and isinstance(metadata, dict):
            # CrossRef sometimes provides PDF URLs
            links = metadata.get("link", [])
            for link in links:
                if (
                    isinstance(link, dict)
                    and link.get("content-type") == "application/pdf"
                ):
                    pdf_url = link.get("URL")
                    if pdf_url:
                        urls.append({"url": pdf_url, "type": "crossref_link"})

        return urls

    def _download_pdf(self, url: str) -> Optional[bytes]:
        """
        Download PDF from URL with proper error handling and timeouts.

        Args:
            url: PDF URL to download

        Returns:
            PDF content as bytes or None if failed
        """
        try:
            response = requests.get(url, timeout=self.settings.external_api_timeout)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            content_type = response.headers.get("content-type", "").lower()
            if "application/pdf" in content_type:
                content = response.content
                if content.startswith(b"%PDF"):
                    logger.info(
                        f"Successfully downloaded PDF: {len(content)} bytes from {url}",
                    )
                    return content
                else:
                    logger.warning(f"Downloaded content from {url} is not a valid PDF.")
            else:
                logger.warning(f"Content type from {url} is not PDF: {content_type}")

        except Timeout:
            logger.error(f"Timeout downloading PDF from: {url}")
        except RequestException as e:
            logger.error(f"Error downloading PDF from {url}: {e}")

        return None

    def _parse_with_grobid(
        self,
        content_model: ContentModel,
        pdf_content: bytes,
        raw_data: Dict[str, Any],
    ) -> None:
        """
        Parse PDF content with GROBID to extract fulltext.

        Args:
            content_model: ContentModel to update
            pdf_content: PDF bytes to parse
            raw_data: Raw data dictionary to update
        """
        try:
            logger.info("Parsing PDF content with GROBID...")

            # This now calls the synchronous version of the grobid client method
            grobid_result = self.grobid_client.process_pdf(
                pdf_content,
                include_raw_citations=True,
            )

            if grobid_result:
                # Extract fulltext from GROBID result
                fulltext = self._extract_fulltext_from_grobid(grobid_result)
                # Store as structured data (model expects Dict[str, Any])
                content_model.parsed_fulltext = (
                    {
                        "text": fulltext,
                        "source": "grobid",
                        "parsed_at": datetime.now().isoformat(),
                    }
                    if fulltext
                    else None
                )
                raw_data["grobid_parsing"] = "success"
                raw_data["grobid_fulltext_length"] = len(fulltext) if fulltext else 0

                logger.info(
                    f"Successfully parsed PDF with GROBID: {len(fulltext)} characters",
                )
            else:
                logger.warning("GROBID parsing returned no results")
                raw_data["grobid_parsing"] = "failed"

        except Exception as e:
            logger.error(f"Error parsing PDF with GROBID: {e}")
            raw_data["grobid_parsing"] = f"error: {e}"

    def fetch_pdf_from_arxiv_id(self, arxiv_id: str) -> Tuple[Optional[str], Optional[bytes]]:
        """
        Fetch a PDF directly from an ArXiv ID.

        Args:
            arxiv_id: The ArXiv identifier.

        Returns:
            A tuple of (pdf_url, pdf_content_bytes) or (None, None) if failed.
        """
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        logger.info(f"Attempting to download PDF from ArXiv URL: {pdf_url}")
        pdf_content = self._download_pdf(pdf_url)
        if pdf_content:
            return pdf_url, pdf_content
        return None, None

    def _extract_fulltext_from_grobid(self, grobid_data: Dict[str, Any]) -> str:
        """
        Extract structured fulltext from GROBID's TEI XML output.

        Args:
            grobid_data: GROBID parsing result

        Returns:
            Extracted fulltext as string
        """
        try:
            # GROBID typically returns structured data
            # This is a simplified extraction - real implementation would need
            # to handle the XML structure properly

            sections = []

            # Extract abstract
            header = grobid_data.get("header", {})
            abstract = header.get("abstract", "")
            if abstract:
                sections.append(f"Abstract\n{abstract}\n")

            # Extract body sections
            body = grobid_data.get("body", [])
            for section in body:
                if isinstance(section, dict):
                    title = section.get("title", "")
                    content = section.get("content", "")
                    if title and content:
                        sections.append(f"{title}\n{content}\n")
                    elif content:
                        sections.append(f"{content}\n")

            # Join all sections
            fulltext = "\n".join(sections)
            return fulltext.strip()

        except Exception as e:
            logger.error(f"Error extracting fulltext from GROBID data: {e}")
            return ""
