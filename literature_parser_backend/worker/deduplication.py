"""
Enhanced waterfall deduplication logic for literature processing.

This module implements the new waterfall deduplication strategy:
1. Explicit identifier checks (DOI, ArXiv ID) - most reliable
2. Source URL checks - handles same source submissions
3. Content fingerprint checks - requires metadata parsing
4. Processing state management - handles concurrent submissions
"""

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..db.dao import LiteratureDAO
from ..db.alias_dao import AliasDAO
from ..models.alias import AliasType
from ..models.literature import LiteratureModel, MetadataModel
from ..services.grobid import GrobidClient
from ..worker.content_fetcher import ContentFetcher


class WaterfallDeduplicator:
    """Enhanced waterfall deduplication with improved robustness."""

    def __init__(self, dao: LiteratureDAO, task_id: str):
        self.dao = dao
        self.task_id = task_id
        self.grobid_client = GrobidClient()
        self.content_fetcher = ContentFetcher()
        # 0.2.1 Hotfix: Initialize AliasDAO for URL deduplication
        self.alias_dao = AliasDAO.create_from_global_connection()

    async def deduplicate_literature(
        self,
        source_data: Dict[str, Any],
    ) -> Tuple[Optional[str], Optional[MetadataModel], Optional[bytes]]:
        """
        Execute the enhanced waterfall deduplication logic.

        Args:
            source_data: Original submission data

        Returns:
            Tuple of (existing_literature_id, prefetched_metadata, pdf_content)
        """
        logger.info(f"Task {self.task_id}: Starting waterfall deduplication")

        # Phase 1: Explicit identifier deduplication
        existing_id = await self._check_explicit_identifiers(source_data)
        if existing_id:
            logger.info(f"Task {self.task_id}: Found duplicate by explicit identifier")
            return existing_id, None, None

        # Phase 2: Source URL deduplication
        existing_id = await self._check_source_urls(source_data)
        if existing_id:
            logger.info(f"Task {self.task_id}: Found duplicate by source URL")
            return existing_id, None, None

        # Phase 3: Processing state check
        existing_id = await self._check_processing_state(source_data)
        if existing_id:
            logger.info(f"Task {self.task_id}: Found duplicate in processing state")
            return existing_id, None, None

        # Phase 4: Content fingerprint deduplication (requires metadata parsing)
        existing_id, metadata, pdf_content = await self._check_content_fingerprint(
            source_data,
        )
        if existing_id:
            logger.info(f"Task {self.task_id}: Found duplicate by content fingerprint")
            return existing_id, metadata, pdf_content

        logger.info(
            f"Task {self.task_id}: No duplicates found, proceeding with new literature",
        )
        return None, metadata, pdf_content

    async def _check_explicit_identifiers(
        self, source_data: Dict[str, Any],
    ) -> Optional[str]:
        """Check for duplicates using explicit identifiers (LID, DOI, ArXiv ID)."""

        # Extract and check LID (highest priority)
        lid = source_data.get("lid")
        if lid:
            logger.info(f"Task {self.task_id}: Checking LID: {lid}")
            if literature := await self.dao.find_by_lid(lid):
                # Clean up failed literature
                if literature.task_info and literature.task_info.status == "failed":
                    logger.info(
                        f"Task {self.task_id}: Cleaning up failed literature with LID {lid}",
                    )
                    await self.dao.delete_literature(literature.lid)
                    return None
                return literature.lid

        # Extract and check DOI
        doi = self._extract_doi(source_data)
        if doi:
            logger.info(f"Task {self.task_id}: Checking DOI: {doi}")
            if literature := await self.dao.find_by_doi(doi):
                # Clean up failed literature
                if literature.task_info and literature.task_info.status == "failed":
                    logger.info(
                        f"Task {self.task_id}: Cleaning up failed literature with DOI {doi}",
                    )
                    await self.dao.delete_literature(literature.lid)
                    return None
                
                # Skip placeholder nodes - they are not complete literature
                if (literature.raw_data and 
                    literature.raw_data.get("placeholder") == True and 
                    literature.metadata.title == "Processing..."):
                    logger.info(f"Task {self.task_id}: Skipping placeholder node with DOI {doi}, LID: {literature.lid}")
                    return None
                    
                logger.info(f"Task {self.task_id}: Found existing literature with DOI, LID: {literature.lid}")
                return literature.lid

        # Extract and check ArXiv ID
        arxiv_id = self._extract_arxiv_id(source_data)
        if arxiv_id:
            logger.info(f"Task {self.task_id}: Checking ArXiv ID: {arxiv_id}")
            if literature := await self.dao.find_by_arxiv_id(arxiv_id):
                # Clean up failed literature
                if literature.task_info and literature.task_info.status == "failed":
                    logger.info(
                        f"Task {self.task_id}: Cleaning up failed literature with ArXiv ID {arxiv_id}",
                    )
                    await self.dao.delete_literature(literature.lid)
                    return None
                return literature.lid

        return None

    async def _check_source_urls(self, source_data: Dict[str, Any]) -> Optional[str]:
        """Check for duplicates based on source URLs."""

        # Extract all possible URLs
        urls = []
        for key in ["url", "pdf_url", "source_url"]:
            if url := source_data.get(key):
                urls.append(self._normalize_url(url))

        if not urls:
            return None

        # Check each URL
        for url in urls:
            logger.info(f"Task {self.task_id}: Checking source URL: {url}")

            # Query database for matching source URLs - 0.2.1 Hotfix
            try:
                # Use the new AliasDAO for checking source URLs
                existing_lid = await self.alias_dao._lookup_single_alias(AliasType.SOURCE_PAGE, url)
                if existing_lid:
                    literature = await self.dao.find_by_lid(existing_lid)
                    if not literature: # Should not happen, but handle defensively
                        continue

                    # Clean up failed literature
                    if literature.task_info and literature.task_info.status == "failed":
                        logger.info(
                            f"Task {self.task_id}: Cleaning up failed literature with URL {url}",
                        )
                        await self.dao.delete_literature(literature.lid)
                        continue

                    return literature.lid
            except Exception as e:
                logger.error(
                    f"Task {self.task_id}: Error checking source URL {url} via AliasDAO: {e}",
                )

        return None

    async def _check_processing_state(
        self, source_data: Dict[str, Any],
    ) -> Optional[str]:
        """Check if same content is currently being processed."""

        # Extract identifiers for processing state check
        doi = self._extract_doi(source_data)
        arxiv_id = self._extract_arxiv_id(source_data)

        if not doi and not arxiv_id:
            return None

        # Look for processing tasks with same identifiers
        query = {
            "task_info.status": {"$in": ["pending", "processing", "in_progress"]},
            "$or": [],
        }

        if doi:
            query["$or"].append({"identifiers.doi": doi})
        if arxiv_id:
            query["$or"].append({"identifiers.arxiv_id": arxiv_id})

        try:
            doc = await self.dao.collection.find_one(query)
            if doc:
                literature = LiteratureModel(**doc)
                logger.info(
                    f"Task {self.task_id}: Found same content being processed in task {literature.task_info.task_id}",
                )
                return literature.lid
        except Exception as e:
            logger.error(f"Task {self.task_id}: Error checking processing state: {e}")

        return None

    async def _check_content_fingerprint(
        self, source_data: Dict[str, Any],
    ) -> Tuple[Optional[str], Optional[MetadataModel], Optional[bytes]]:
        """Check for duplicates using content fingerprint (requires metadata parsing)."""

        # Try to get PDF content for fingerprint generation
        pdf_content = None
        metadata = None

        # Attempt to fetch PDF content
        try:
            pdf_content = await self._fetch_pdf_content(source_data)
            if pdf_content:
                logger.info(
                    f"Task {self.task_id}: Successfully fetched PDF content for fingerprint check",
                )

                # Generate content fingerprint
                content_fingerprint = self._generate_content_fingerprint(pdf_content)

                # Check for existing literature with same fingerprint
                if literature := await self.dao.find_by_fingerprint(
                    content_fingerprint,
                ):
                    # Clean up failed literature
                    if literature.task_info and literature.task_info.status == "failed":
                        logger.info(
                            f"Task {self.task_id}: Cleaning up failed literature with fingerprint {content_fingerprint}",
                        )
                        await self.dao.delete_literature(literature.lid)
                    else:
                        return literature.lid, None, pdf_content

                # Try to parse metadata for title-based deduplication
                try:
                    metadata = await self._parse_metadata_from_pdf(pdf_content)
                    if (
                        metadata
                        and metadata.title
                        and metadata.title != "Unknown Title"
                    ):
                        logger.info(
                            f"Task {self.task_id}: Checking title-based deduplication: {metadata.title}",
                        )

                        # Generate title fingerprint for more robust matching
                        title_fingerprint = self._generate_title_fingerprint(
                            metadata.title, metadata.authors,
                        )

                        # Check for existing literature with similar title fingerprint
                        if literature := await self._find_by_title_fingerprint(
                            title_fingerprint,
                        ):
                            # Clean up failed literature
                            if (
                                literature.task_info
                                and literature.task_info.status == "failed"
                            ):
                                logger.info(
                                    f"Task {self.task_id}: Cleaning up failed literature with title fingerprint",
                                )
                                await self.dao.delete_literature(literature.lid)
                            else:
                                return literature.lid, metadata, pdf_content

                except Exception as e:
                    logger.warning(
                        f"Task {self.task_id}: Failed to parse metadata from PDF: {e}",
                    )

        except Exception as e:
            logger.warning(
                f"Task {self.task_id}: Failed to fetch PDF content for fingerprint check: {e}",
            )

        return None, metadata, pdf_content

    async def _fetch_pdf_content(self, source_data: Dict[str, Any]) -> Optional[bytes]:
        """Fetch PDF content from various sources."""

        # Try PDF URL first
        if pdf_url := source_data.get("pdf_url"):
            try:
                content_model, _ = self.content_fetcher.fetch_content_waterfall(
                    user_pdf_url=pdf_url,
                )
                if content_model and content_model.pdf_content:
                    return content_model.pdf_content
            except Exception as e:
                logger.warning(
                    f"Task {self.task_id}: Failed to fetch from pdf_url: {e}",
                )

        # Try general URL
        if url := source_data.get("url"):
            try:
                content_model, _ = self.content_fetcher.fetch_content_waterfall(
                    user_pdf_url=url,
                )
                if content_model and content_model.pdf_content:
                    return content_model.pdf_content
            except Exception as e:
                logger.warning(f"Task {self.task_id}: Failed to fetch from url: {e}")

        return None

    async def _parse_metadata_from_pdf(
        self, pdf_content: bytes,
    ) -> Optional[MetadataModel]:
        """Parse metadata from PDF content using GROBID."""
        try:
            parsed_data = self.grobid_client.process_header_only(pdf_content)
            if parsed_data:
                from ..worker.utils import convert_grobid_to_metadata

                return convert_grobid_to_metadata(parsed_data)
        except Exception as e:
            logger.warning(
                f"Task {self.task_id}: Failed to parse metadata with GROBID: {e}",
            )

        return None

    def _extract_doi(self, source_data: Dict[str, Any]) -> Optional[str]:
        """Extract DOI from source data."""
        # Direct DOI field
        if doi := source_data.get("doi"):
            return doi

        # Extract from URL
        if url := source_data.get("url"):
            if "doi.org" in url:
                match = re.search(r"10\.\d{4,}/[^\s]+", url)
                if match:
                    return match.group()

        return None

    def _extract_arxiv_id(self, source_data: Dict[str, Any]) -> Optional[str]:
        """Extract ArXiv ID from source data."""
        # Direct ArXiv ID field
        if arxiv_id := source_data.get("arxiv_id"):
            return arxiv_id

        # Extract from URL
        if url := source_data.get("url"):
            if "arxiv.org" in url:
                match = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?]+)", url)
                if match:
                    return match.group(1).replace(".pdf", "")

        return None

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        # Remove protocol
        url = re.sub(r"^https?://", "", url)
        # Remove trailing slash
        url = url.rstrip("/")
        # Remove common query parameters
        url = re.sub(r"[?&](utm_|ref=|source=)[^&]*", "", url)
        return url.lower()

    def _generate_content_fingerprint(self, pdf_content: bytes) -> str:
        """Generate content fingerprint from PDF content."""
        return hashlib.md5(pdf_content).hexdigest()

    def _generate_title_fingerprint(self, title: str, authors: List[Any]) -> str:
        """Generate robust title fingerprint for deduplication."""
        # Normalize title
        normalized_title = self._normalize_title(title)

        # Normalize authors
        normalized_authors = self._normalize_authors(authors)

        # Combine for fingerprint
        content = f"{normalized_title}|{normalized_authors}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _normalize_title(self, title: str) -> str:
        """Normalize title for consistent fingerprint generation."""
        if not title:
            return ""

        # Convert to lowercase
        title = title.lower()

        # Remove common punctuation and extra spaces
        title = re.sub(r"[^\w\s]", "", title)
        title = re.sub(r"\s+", " ", title)

        # Remove common stop words
        stop_words = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }
        words = title.split()
        words = [word for word in words if word not in stop_words]

        return " ".join(words).strip()

    def _normalize_authors(self, authors: List[Any]) -> str:
        """Normalize authors for consistent fingerprint generation."""
        if not authors:
            return ""

        normalized = []
        for author in authors:
            if isinstance(author, dict):
                name = author.get("name", "")
            elif hasattr(author, "name"):
                name = author.name
            else:
                name = str(author)

            # Normalize name
            name = name.lower().strip()
            name = re.sub(r"[^\w\s]", "", name)
            name = re.sub(r"\s+", " ", name)

            if name:
                normalized.append(name)

        return "|".join(sorted(normalized))

    async def _find_by_title_fingerprint(
        self, title_fingerprint: str,
    ) -> Optional[LiteratureModel]:
        """Find literature by title fingerprint."""
        try:
            # We'll store title fingerprints in a computed field
            # For now, do a broader search and check manually
            query = {
                "metadata.title": {"$exists": True, "$ne": None},
                "task_info.status": {"$ne": "failed"},
            }

            cursor = self.dao.collection.find(query)
            async for doc in cursor:
                try:
                    literature = LiteratureModel(**doc)

                    # Generate fingerprint for comparison
                    if literature.metadata and literature.metadata.title:
                        existing_fingerprint = self._generate_title_fingerprint(
                            literature.metadata.title, literature.metadata.authors or [],
                        )

                        if existing_fingerprint == title_fingerprint:
                            return literature

                except Exception as e:
                    logger.warning(
                        f"Task {self.task_id}: Error processing document for title fingerprint: {e}",
                    )
                    continue

        except Exception as e:
            logger.error(
                f"Task {self.task_id}: Error finding by title fingerprint: {e}",
            )

        return None
