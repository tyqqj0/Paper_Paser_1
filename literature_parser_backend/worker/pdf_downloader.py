"""
PDF downloader for literature processing.

This module provides functionality to download PDF files from various sources
including ArXiv, DOI URLs, and direct PDF links.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)


class PDFDownloader:
    """Downloads PDF files from various academic sources."""

    def __init__(self, timeout: int = 30, max_size: int = 50 * 1024 * 1024):
        """
        Initialize PDF downloader.
        
        :param timeout: Request timeout in seconds
        :param max_size: Maximum file size in bytes (default: 50MB)
        """
        self.timeout = ClientTimeout(total=timeout)
        self.max_size = max_size
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            headers={
                "User-Agent": "Literature Parser Bot/1.0 (academic research)"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    def _extract_arxiv_id(self, url: str) -> Optional[str]:
        """
        Extract ArXiv ID from various ArXiv URL formats.
        
        :param url: ArXiv URL
        :return: ArXiv ID or None if not found
        """
        # Common ArXiv URL patterns
        patterns = [
            r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})",
            r"arxiv\.org/pdf/([0-9]{4}\.[0-9]{4,5})",
            r"arxiv\.org/abs/([a-z-]+/[0-9]{7})",
            r"arxiv\.org/pdf/([a-z-]+/[0-9]{7})",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url.lower())
            if match:
                return match.group(1)
        
        return None

    def _get_arxiv_pdf_url(self, arxiv_id: str) -> str:
        """
        Get direct PDF URL for ArXiv paper.
        
        :param arxiv_id: ArXiv identifier
        :return: Direct PDF URL
        """
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    async def download_from_arxiv(self, arxiv_url: str, output_path: Path) -> bool:
        """
        Download PDF from ArXiv URL.
        
        :param arxiv_url: ArXiv URL (abs or pdf)
        :param output_path: Path to save the PDF
        :return: True if successful, False otherwise
        """
        try:
            # Extract ArXiv ID
            arxiv_id = self._extract_arxiv_id(arxiv_url)
            if not arxiv_id:
                logger.error(f"Could not extract ArXiv ID from URL: {arxiv_url}")
                return False

            # Get direct PDF URL
            pdf_url = self._get_arxiv_pdf_url(arxiv_id)
            logger.info(f"Downloading ArXiv PDF from: {pdf_url}")

            # Download the PDF
            return await self._download_pdf(pdf_url, output_path)

        except Exception as e:
            logger.error(f"Failed to download ArXiv PDF: {e}")
            return False

    async def download_from_url(self, pdf_url: str, output_path: Path) -> bool:
        """
        Download PDF from direct URL.
        
        :param pdf_url: Direct PDF URL
        :param output_path: Path to save the PDF
        :return: True if successful, False otherwise
        """
        try:
            logger.info(f"Downloading PDF from: {pdf_url}")
            return await self._download_pdf(pdf_url, output_path)

        except Exception as e:
            logger.error(f"Failed to download PDF from URL: {e}")
            return False

    async def _download_pdf(self, url: str, output_path: Path) -> bool:
        """
        Internal method to download PDF from URL.
        
        :param url: PDF URL
        :param output_path: Path to save the PDF
        :return: True if successful, False otherwise
        """
        if not self.session:
            raise RuntimeError("PDFDownloader must be used as async context manager")

        try:
            # Create output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Download the file
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"HTTP {response.status} when downloading {url}")
                    return False

                # Check content type
                content_type = response.headers.get("content-type", "").lower()
                if "pdf" not in content_type and "application/octet-stream" not in content_type:
                    logger.warning(f"Unexpected content type: {content_type}")

                # Check file size
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > self.max_size:
                    logger.error(f"File too large: {content_length} bytes")
                    return False

                # Download and save
                total_size = 0
                async with aiofiles.open(output_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        total_size += len(chunk)
                        if total_size > self.max_size:
                            logger.error(f"File too large during download: {total_size} bytes")
                            output_path.unlink(missing_ok=True)
                            return False
                        await f.write(chunk)

                logger.info(f"Successfully downloaded PDF: {output_path} ({total_size} bytes)")
                return True

        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading PDF from {url}")
            return False
        except Exception as e:
            logger.error(f"Error downloading PDF from {url}: {e}")
            return False

    async def try_download_from_sources(
        self, 
        arxiv_url: Optional[str] = None,
        pdf_url: Optional[str] = None,
        doi: Optional[str] = None,
        output_path: Optional[Path] = None
    ) -> Tuple[bool, Optional[Path]]:
        """
        Try to download PDF from multiple sources in priority order.
        
        :param arxiv_url: ArXiv URL (highest priority)
        :param pdf_url: Direct PDF URL
        :param doi: DOI (will try to resolve to PDF)
        :param output_path: Custom output path, or auto-generate if None
        :return: (success, file_path) tuple
        """
        if not output_path:
            # Generate output path based on available identifiers
            if arxiv_url:
                arxiv_id = self._extract_arxiv_id(arxiv_url)
                if arxiv_id:
                    filename = f"arxiv_{arxiv_id.replace('/', '_')}.pdf"
                else:
                    filename = "downloaded_paper.pdf"
            elif doi:
                filename = f"doi_{doi.replace('/', '_').replace('.', '_')}.pdf"
            else:
                filename = "downloaded_paper.pdf"
            
            output_path = Path("temp_pdfs") / filename

        # Try ArXiv first (most reliable)
        if arxiv_url:
            logger.info("Trying ArXiv download...")
            if await self.download_from_arxiv(arxiv_url, output_path):
                return True, output_path

        # Try direct PDF URL
        if pdf_url:
            logger.info("Trying direct PDF URL...")
            if await self.download_from_url(pdf_url, output_path):
                return True, output_path

        # Try DOI resolution (basic implementation)
        if doi:
            logger.info("Trying DOI resolution...")
            # This is a basic implementation - could be expanded
            # to use DOI resolution services
            doi_url = f"https://doi.org/{doi}"
            if await self.download_from_url(doi_url, output_path):
                return True, output_path

        logger.warning("All PDF download attempts failed")
        return False, None


# Convenience function for single-use downloads
async def download_pdf(
    arxiv_url: Optional[str] = None,
    pdf_url: Optional[str] = None,
    doi: Optional[str] = None,
    output_path: Optional[Path] = None,
    timeout: int = 30
) -> Tuple[bool, Optional[Path]]:
    """
    Convenience function to download PDF from various sources.
    
    :param arxiv_url: ArXiv URL
    :param pdf_url: Direct PDF URL
    :param doi: DOI
    :param output_path: Output file path
    :param timeout: Request timeout
    :return: (success, file_path) tuple
    """
    async with PDFDownloader(timeout=timeout) as downloader:
        return await downloader.try_download_from_sources(
            arxiv_url=arxiv_url,
            pdf_url=pdf_url,
            doi=doi,
            output_path=output_path
        ) 