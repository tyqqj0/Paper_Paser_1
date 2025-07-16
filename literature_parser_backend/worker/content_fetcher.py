"""
Content fetcher module implementing waterfall logic for literature content/PDF.

This module implements the intelligent waterfall approach for fetching content,
following the three-step process outlined in the architecture document.
"""

import logging
import os
from typing import Any, Dict, Optional, Tuple

import requests

from ..models.literature import ContentModel
from ..settings import Settings

logger = logging.getLogger(__name__)


class ContentFetcher:
    """Fetches PDF content from various sources."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize content fetcher with required clients."""
        self.settings = settings or Settings()
        self.client = requests.Session()
        self.client.proxies = self.settings.get_proxy_dict()
        self.client.timeout = self.settings.external_api_timeout

    def fetch_content_waterfall(
        self,
        doi: Optional[str] = None,
        arxiv_id: Optional[str] = None,
        user_pdf_url: Optional[str] = None,
    ) -> Tuple[ContentModel, Dict[str, Any]]:
        """
        Attempt to fetch PDF content using a waterfall approach.

        Args:
            doi: The DOI of the literature.
            arxiv_id: The ArXiv ID of the literature.
            user_pdf_url: A direct PDF URL provided by the user.

        Returns:
            A tuple containing the ContentModel and a dictionary of raw data.
        """
        pdf_url: Optional[str] = None
        raw_data: Dict[str, Any] = {"sources_tried": []}

        # Strategy 1: Use the user-provided direct PDF URL if available
        if user_pdf_url:
            raw_data["sources_tried"].append(f"user_pdf_url: {user_pdf_url}")
            pdf_url = user_pdf_url

        # Strategy 2: Infer PDF URL from identifiers
        if not pdf_url:
            inferred_urls = self._infer_pdf_urls(doi=doi, arxiv_id=arxiv_id)
            for source_type, url in inferred_urls.items():
                raw_data["sources_tried"].append(f"{source_type}: {url}")
                pdf_url = url
                break  # Use the first one found

        content_model = ContentModel(
            pdf_url=pdf_url,
            source_page_url=self._infer_source_page_url(doi=doi, arxiv_id=arxiv_id),
            parsed_fulltext=None,
            sources_tried=raw_data["sources_tried"],
        )

        return content_model, raw_data

    def _download_pdf(self, url: str) -> Optional[bytes]:
        """Download a PDF from a given URL."""
        try:
            logger.info(f"Attempting to download PDF from URL: {url}")
            response = self.client.get(url)
            response.raise_for_status()
            logger.info(f"Successfully downloaded PDF: {len(response.content)} bytes.")

            # 调试步骤一：保存PDF到临时位置以便检查
            try:
                debug_dir = "/tmp/debug_pdfs"
                os.makedirs(debug_dir, exist_ok=True)

                # 从URL中提取文件名
                import urllib.parse
                from datetime import datetime

                parsed_url = urllib.parse.urlparse(url)
                filename = os.path.basename(parsed_url.path) or "unknown.pdf"
                if not filename.endswith(".pdf"):
                    filename += ".pdf"

                # 添加时间戳避免冲突
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_filename = f"{timestamp}_{filename}"
                debug_path = os.path.join(debug_dir, debug_filename)

                with open(debug_path, "wb") as f:
                    f.write(response.content)

                logger.info(f"DEBUG: PDF saved to {debug_path} for inspection")
                logger.info(f"DEBUG: File size: {len(response.content)} bytes")

                # 简单验证PDF头部
                if response.content.startswith(b"%PDF-"):
                    logger.info("DEBUG: PDF header verification PASSED")
                else:
                    logger.warning(
                        "DEBUG: PDF header verification FAILED - not a valid PDF",
                    )

            except Exception as e:
                logger.error(f"DEBUG: Failed to save PDF for debugging: {e}")

            return response.content
        except requests.HTTPError as e:
            logger.error(
                f"HTTP error downloading PDF from {url}: "
                f"Status {e.response.status_code}",
            )
        except requests.RequestException as e:
            logger.error(f"Request error downloading PDF from {url}: {e}")
        return None

    def _infer_pdf_urls(
        self,
        doi: Optional[str] = None,
        arxiv_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Infer potential PDF URLs from identifiers."""
        urls = {}
        if arxiv_id:
            urls["arxiv"] = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        if doi:
            # This is a generic pattern; it might not always work.
            urls["doi"] = f"https://doi.org/{doi}"
        return urls

    def _infer_source_page_url(
        self,
        doi: Optional[str] = None,
        arxiv_id: Optional[str] = None,
    ) -> Optional[str]:
        """Infer the source page URL from identifiers."""
        if arxiv_id:
            return f"https://arxiv.org/abs/{arxiv_id}"
        if doi:
            return f"https://doi.org/{doi}"
        return None
