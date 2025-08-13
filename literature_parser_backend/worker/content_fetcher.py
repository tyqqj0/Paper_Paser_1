"""
Content fetcher module implementing waterfall logic for literature content/PDF.

This module implements the intelligent waterfall approach for fetching content,
following the three-step process outlined in the architecture document.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests

from ..models.literature import ContentModel
from ..services.grobid import GrobidClient
from ..settings import Settings

logger = logging.getLogger(__name__)


class ContentFetcher:
    """Fetches PDF content from various sources."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize content fetcher with required clients."""
        self.settings = settings or Settings()
        self.timeout = self.settings.external_api_timeout
        self.grobid_client = GrobidClient(settings)

        # Use external request manager for PDF downloads
        from ..services.request_manager import ExternalRequestManager

        self.request_manager = ExternalRequestManager(settings)

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

        # Initialize content model
        content_model = ContentModel(
            pdf_url=pdf_url,
            source_page_url=self._infer_source_page_url(doi=doi, arxiv_id=arxiv_id),
            parsed_fulltext=None,
            grobid_processing_info=None,
            sources_tried=raw_data["sources_tried"],
        )

        # If we have a PDF URL, download and parse it
        if pdf_url:
            pdf_content = self._download_pdf(pdf_url)
            if pdf_content:
                logger.info("PDF downloaded successfully, starting GROBID parsing...")
                parsed_content, processing_info = self._parse_pdf_with_grobid(
                    pdf_content,
                )
                content_model.parsed_fulltext = parsed_content
                content_model.grobid_processing_info = processing_info
                logger.info(
                    f"GROBID parsing completed. Status: {processing_info.get('status', 'unknown')}",
                )
            else:
                logger.warning("Failed to download PDF, skipping GROBID parsing")

        return content_model, raw_data

    def _download_pdf(self, url: str) -> Optional[bytes]:
        """Download a PDF from a given URL."""
        try:
            logger.info(f"Attempting to download PDF from URL: {url}")

            # 检查是否是COS URL，如果是则使用特殊处理
            if self._is_cos_url(url):
                return self._download_pdf_from_cos(url)

            from ..services.request_manager import RequestType

            response = self.request_manager.get(
                url=url, request_type=RequestType.EXTERNAL, timeout=self.timeout,
            )
            response.raise_for_status()
            logger.info(f"Successfully downloaded PDF: {len(response.content)} bytes.")

            # 调试步骤一：保存PDF到临时位置以便检查
            try:
                debug_dir = "/tmp/debug_pdfs"
                os.makedirs(debug_dir, exist_ok=True)

                # 从URL中提取文件名
                import urllib.parse

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
                    # 检查是否是HTML重定向页面
                    if response.content.startswith(
                        b"<!DOCTYPE",
                    ) or response.content.startswith(b"<html"):
                        logger.warning(
                            "DEBUG: Downloaded content appears to be HTML, not PDF",
                        )
                        # 如果是ArXiv DOI，尝试使用ArXiv PDF URL
                        if "arxiv" in url.lower() and "10.48550" in url:
                            arxiv_id = self._extract_arxiv_id_from_url(url)
                            if arxiv_id:
                                logger.info(
                                    f"DEBUG: Attempting to download from ArXiv PDF URL for {arxiv_id}",
                                )
                                return self._download_arxiv_pdf(arxiv_id)
                    return None

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

    def _extract_arxiv_id_from_url(self, url: str) -> Optional[str]:
        """Extract ArXiv ID from URL patterns."""
        import re

        # Pattern for 10.48550/arXiv.XXXX.XXXXX
        pattern = r"10\.48550[/%]arXiv\.(\d{4}\.\d{4,5})"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None

    def _download_arxiv_pdf(self, arxiv_id: str) -> Optional[bytes]:
        """Download PDF directly from ArXiv."""
        arxiv_pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        logger.info(f"Attempting to download ArXiv PDF from: {arxiv_pdf_url}")

        try:
            from ..services.request_manager import RequestType
            response = self.request_manager.get(
                url=arxiv_pdf_url,
                request_type=RequestType.EXTERNAL,
                timeout=self.timeout,
            )
            response.raise_for_status()

            # Verify it's a valid PDF
            if response.content.startswith(b"%PDF-"):
                logger.info(
                    f"✅ Successfully downloaded ArXiv PDF: {len(response.content)} bytes",
                )
                return response.content
            else:
                logger.warning("❌ ArXiv PDF download failed - invalid PDF format")
                return None

        except Exception as e:
            logger.error(f"❌ Failed to download ArXiv PDF: {e}")
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

    def _parse_pdf_with_grobid(
        self,
        pdf_content: bytes,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Parse PDF content using GROBID and structure it for caching.

        Args:
            pdf_content: Raw PDF bytes

        Returns:
            Tuple of (parsed_fulltext_dict, processing_info_dict)
        """
        start_time = datetime.now()
        processing_info = {
            "grobid_version": "0.8.0",  # TODO: Get from GROBID service
            "processed_at": start_time.isoformat(),
            "status": "failed",
            "endpoints_used": [],
            "xml_size_bytes": 0,
            "text_length_chars": 0,
            "processing_time_ms": 0,
        }

        try:
            # Use GROBID to parse the full document
            grobid_result = self.grobid_client.process_pdf(
                pdf_content,
                "process_fulltext",
            )

            if not grobid_result or grobid_result.get("status") != "success":
                logger.error(f"GROBID processing failed: {grobid_result}")
                return None, processing_info

            # Extract structured content from GROBID result
            parsed_fulltext = self._structure_grobid_content(grobid_result)

            # Update processing info
            end_time = datetime.now()
            processing_info.update(
                {
                    "status": "success",
                    "endpoints_used": ["processFulltextDocument"],
                    "xml_size_bytes": len(grobid_result.get("raw_xml", "")),
                    "text_length_chars": len(parsed_fulltext.get("body_text", "")),
                    "processing_time_ms": int(
                        (end_time - start_time).total_seconds() * 1000,
                    ),
                },
            )

            logger.info(
                f"GROBID parsing successful: {processing_info['text_length_chars']} chars extracted",
            )
            return parsed_fulltext, processing_info

        except Exception as e:
            logger.error(f"Error during GROBID parsing: {e}")
            end_time = datetime.now()
            processing_info.update(
                {
                    "status": "error",
                    "error_message": str(e),
                    "processing_time_ms": int(
                        (end_time - start_time).total_seconds() * 1000,
                    ),
                },
            )
            return None, processing_info

    def _structure_grobid_content(
        self,
        grobid_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Structure GROBID parsing result into our standardized format.

        Args:
            grobid_result: Raw GROBID parsing result

        Returns:
            Structured fulltext content dictionary
        """
        structured_content = {
            "body_text": "",
            "sections": [],
            "tables": [],
            "figures": [],
            "acknowledgments": "",
            "appendices": "",
        }

        try:
            # Extract body text
            fulltext = grobid_result.get("fulltext", {})
            if isinstance(fulltext, dict):
                body_text = fulltext.get("body", "")
                if body_text:
                    structured_content["body_text"] = body_text

                back_text = fulltext.get("back", "")
                if back_text:
                    # Try to separate acknowledgments and appendices
                    if "acknowledgment" in back_text.lower():
                        structured_content["acknowledgments"] = back_text
                    elif "appendix" in back_text.lower():
                        structured_content["appendices"] = back_text
                    else:
                        structured_content["appendices"] = back_text

            # TODO: Extract more structured elements like sections, tables, figures
            # This would require more detailed parsing of the TEI XML structure

            logger.info(
                f"Structured content created: {len(structured_content['body_text'])} chars body text",
            )
            return structured_content

        except Exception as e:
            logger.error(f"Error structuring GROBID content: {e}")
            return structured_content

    def _is_cos_url(self, url: str) -> bool:
        """检查URL是否是腾讯云COS URL"""
        cos_domains = [
            self.settings.cos_domain,
            "cos.ap-shanghai.myqcloud.com",
            "cos.myqcloud.com"
        ]
        return any(domain in url for domain in cos_domains)

    def _download_pdf_from_cos(self, url: str) -> Optional[bytes]:
        """从腾讯云COS下载PDF文件"""
        try:
            logger.info(f"从COS下载PDF: {url}")

            # 对于COS公开读的文件，可以直接使用HTTP请求
            # 但为了更好的错误处理和认证，我们使用COS服务
            from ..services.cos import get_cos_service, extract_object_key_from_url

            # 提取对象键名
            object_key = extract_object_key_from_url(url, self.settings.cos_domain)
            if not object_key:
                logger.warning(f"无法从COS URL提取对象键名: {url}")
                # 回退到普通HTTP下载
                return self._download_pdf_fallback(url)

            # 获取COS服务
            cos_service = get_cos_service()

            # 检查文件是否存在
            if not cos_service.check_object_exists(object_key):
                logger.warning(f"COS文件不存在: {object_key}")
                return None

            # 生成下载URL（带认证）
            download_url = cos_service.generate_download_url(object_key, expires=3600)

            # 使用下载URL获取文件
            from ..services.request_manager import RequestType
            response = self.request_manager.get(
                url=download_url,
                request_type=RequestType.EXTERNAL,
                timeout=self.timeout
            )
            response.raise_for_status()

            logger.info(f"成功从COS下载PDF: {len(response.content)} bytes")

            # 验证PDF格式
            if not response.content.startswith(b"%PDF-"):
                logger.warning("从COS下载的文件不是有效的PDF格式")
                return None

            return response.content

        except Exception as e:
            logger.error(f"从COS下载PDF失败: {e}")
            # 回退到普通HTTP下载
            logger.info("尝试回退到普通HTTP下载...")
            return self._download_pdf_fallback(url)

    def _download_pdf_fallback(self, url: str) -> Optional[bytes]:
        """回退的PDF下载方法（普通HTTP请求）"""
        try:
            from ..services.request_manager import RequestType
            response = self.request_manager.get(
                url=url,
                request_type=RequestType.EXTERNAL,
                timeout=self.timeout
            )
            response.raise_for_status()

            if response.content.startswith(b"%PDF-"):
                logger.info(f"回退下载成功: {len(response.content)} bytes")
                return response.content
            else:
                logger.warning("回退下载的文件不是有效的PDF格式")
                return None

        except Exception as e:
            logger.error(f"回退下载也失败: {e}")
            return None
