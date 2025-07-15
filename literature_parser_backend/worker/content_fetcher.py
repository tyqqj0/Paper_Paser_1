"""
Content fetcher module implementing waterfall logic for literature content/PDF.

This module implements the intelligent waterfall approach for fetching content,
following the three-step process outlined in the architecture document.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp

from ..models.literature import ContentModel
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
        
    async def fetch_content_waterfall(
        self,
        identifiers,  # IdentifiersModel object
        source_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
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
        raw_data = {"sources_tried": [], "download_status": "pending"}
        
        # Step 1: Try user-provided PDF URL
        user_pdf_url = source_data.get("pdf_url")
        if user_pdf_url:
            logger.info(f"Step 1: Attempting download from user-provided PDF URL: {user_pdf_url}")
            raw_data["sources_tried"].append(f"user_pdf_url: {user_pdf_url}")
            
            pdf_content = await self._download_pdf(user_pdf_url)
            if pdf_content:
                content_model.pdf_url = user_pdf_url
                content_model.source_page_url = None
                raw_data["download_status"] = "success_user_pdf"
                logger.info("✅ Successfully downloaded from user-provided PDF URL")
                
                # Parse with GROBID if we have PDF content
                await self._parse_with_grobid(content_model, pdf_content, raw_data)
                return content_model, pdf_content, raw_data
            else:
                logger.warning("❌ Failed to download from user-provided PDF URL")
        
        # Step 2: Try auto-download from inferred URLs
        inferred_urls = self._infer_pdf_urls(identifiers, source_data, metadata)
        
        for url_info in inferred_urls:
            url = url_info["url"]
            source_type = url_info["type"]
            logger.info(f"Step 2: Attempting auto-download from {source_type}: {url}")
            raw_data["sources_tried"].append(f"{source_type}: {url}")
            
            pdf_content = await self._download_pdf(url)
            if pdf_content:
                content_model.pdf_url = url
                content_model.source_page_url = source_data.get("url") if not source_data.get("url", "").endswith(".pdf") else None
                raw_data["download_status"] = f"success_auto_{source_type}"
                logger.info(f"✅ Successfully downloaded from {source_type}")
                
                # Parse with GROBID if we have PDF content
                await self._parse_with_grobid(content_model, pdf_content, raw_data)
                return content_model, pdf_content, raw_data
            else:
                logger.warning(f"❌ Failed to download from {source_type}: {url}")
        
        # Step 3: No PDF available - return status for frontend handling
        logger.info("Step 3: No PDF available for download")
        content_model.pdf_url = None
        content_model.source_page_url = source_data.get("url") if source_data.get("url") and not source_data.get("url", "").endswith(".pdf") else None
        raw_data["download_status"] = "pdf_unavailable"
        
        return content_model, None, raw_data
    
    def _infer_pdf_urls(
        self,
        identifiers,
        source_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
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
                if isinstance(link, dict) and link.get("content-type") == "application/pdf":
                    pdf_url = link.get("URL")
                    if pdf_url:
                        urls.append({"url": pdf_url, "type": "crossref_link"})
        
        return urls
    
    async def _download_pdf(self, url: str) -> Optional[bytes]:
        """
        Download PDF from URL with proper error handling and timeouts.
        
        Args:
            url: PDF URL to download
            
        Returns:
            PDF content as bytes or None if failed
        """
        try:
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content_type = response.headers.get("content-type", "").lower()
                        
                        # Verify it's actually a PDF
                        if "application/pdf" in content_type:
                            content = await response.read()
                            
                            # Verify PDF magic number
                            if content.startswith(b"%PDF"):
                                logger.info(f"Successfully downloaded PDF: {len(content)} bytes")
                                return content
                            else:
                                logger.warning(f"Downloaded content is not a valid PDF: {url}")
                        else:
                            logger.warning(f"Content type is not PDF: {content_type}")
                    else:
                        logger.warning(f"HTTP {response.status} when downloading: {url}")
                        
        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading PDF from: {url}")
        except Exception as e:
            logger.error(f"Error downloading PDF from {url}: {e}")
            
        return None
    
    async def _parse_with_grobid(
        self,
        content_model: ContentModel,
        pdf_content: bytes,
        raw_data: Dict[str, Any]
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
            
            grobid_result = await self.grobid_client.process_pdf(
                pdf_content,
                include_raw_citations=True
            )
            
            if grobid_result:
                # Extract fulltext from GROBID result
                fulltext = self._extract_fulltext_from_grobid(grobid_result)
                content_model.parsed_fulltext = fulltext
                raw_data["grobid_parsing"] = "success"
                raw_data["grobid_fulltext_length"] = len(fulltext) if fulltext else 0
                
                logger.info(f"Successfully parsed PDF with GROBID: {len(fulltext)} characters")
            else:
                logger.warning("GROBID parsing returned no results")
                raw_data["grobid_parsing"] = "failed"
                
        except Exception as e:
            logger.error(f"Error parsing PDF with GROBID: {e}")
            raw_data["grobid_parsing"] = f"error: {e}"
    
    def _extract_fulltext_from_grobid(self, grobid_data: Dict[str, Any]) -> str:
        """
        Extract readable fulltext from GROBID parsing result.
        
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