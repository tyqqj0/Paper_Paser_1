from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..db.dao import LiteratureDAO
from ..db.alias_dao import AliasDAO
from ..models.alias import AliasType
from ..models.literature import LiteratureModel, IdentifiersModel
from ..worker.utils import extract_authoritative_identifiers


class WaterfallDeduplicator:
    """Enhanced waterfall deduplication with improved robustness."""

    def __init__(self, dao: LiteratureDAO, task_id: str):
        self.dao = dao
        self.task_id = task_id
        self.alias_dao = AliasDAO(database=dao.driver)

    async def deduplicate_literature(
        self,
        source_data: Dict[str, Any],
    ) -> Tuple[Optional[str], IdentifiersModel, Optional[Dict[str, Any]]]:
        """
        Execute the enhanced waterfall deduplication logic.
        1. Extracts authoritative identifiers (including URL mapping).
        2. Performs fast, low-cost checks for duplicates.
        """
        logger.info(f"Task {self.task_id}: Starting enhanced deduplication waterfall")

        # Phase 1: Extract authoritative identifiers (includes URL mapping)
        identifiers, primary_type, url_validation_info = extract_authoritative_identifiers(source_data)

        # If URL validation failed, stop here and return the info to the main task
        if url_validation_info and url_validation_info.get("status") == "failed":
            logger.warning(f"Task {self.task_id}: Halting deduplication due to URL validation failure.")
            return None, identifiers, url_validation_info

        # Phase 2: Explicit identifier deduplication using extracted identifiers
        existing_id = await self._check_explicit_identifiers(identifiers)
        if existing_id:
            logger.info(f"Task {self.task_id}: Found duplicate by explicit identifier: {existing_id}")
            return existing_id, identifiers, url_validation_info

        # Phase 3: Source URL deduplication
        existing_id = await self._check_source_urls(source_data)
        if existing_id:
            logger.info(f"Task {self.task_id}: Found duplicate by source URL: {existing_id}")
            return existing_id, identifiers, url_validation_info

        # Phase 4: Processing state check
        existing_id = await self._check_processing_state(identifiers)
        if existing_id:
            logger.info(f"Task {self.task_id}: Found duplicate in processing state: {existing_id}")
            return existing_id, identifiers, url_validation_info

        # Phase 5: All initial checks passed
        logger.info(
            f"Task {self.task_id}: No duplicates found in initial checks, proceeding to metadata fetch.",
        )
        return None, identifiers, url_validation_info

    async def _check_explicit_identifiers(
        self, identifiers: IdentifiersModel,
    ) -> Optional[str]:
        """Check for duplicates using extracted explicit identifiers."""

        # Check DOI
        if identifiers.doi:
            logger.info(f"Task {self.task_id}: Checking DOI: {identifiers.doi}")
            if literature := await self.dao.find_by_doi(identifiers.doi):
                if literature.task_info and literature.task_info.status == "failed":
                    logger.info(
                        f"Task {self.task_id}: Cleaning up failed literature with DOI {identifiers.doi}",
                    )
                    await self.dao.delete_literature(literature.lid)
                    return None
                
                if (literature.raw_data and 
                    literature.raw_data.get("placeholder") == True and 
                    literature.metadata.title == "Processing..."):
                    logger.info(f"Task {self.task_id}: Skipping placeholder node with DOI {identifiers.doi}, LID: {literature.lid}")
                    return None
                    
                logger.info(f"Task {self.task_id}: Found existing literature with DOI, LID: {literature.lid}")
                return literature.lid

        # Check ArXiv ID
        if identifiers.arxiv_id:
            logger.info(f"Task {self.task_id}: Checking ArXiv ID: {identifiers.arxiv_id}")
            if literature := await self.dao.find_by_arxiv_id(identifiers.arxiv_id):
                if literature.task_info and literature.task_info.status == "failed":
                    logger.info(
                        f"Task {self.task_id}: Cleaning up failed literature with ArXiv ID {identifiers.arxiv_id}",
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

            # Query database for matching source URLs
            try:
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
        self, identifiers: IdentifiersModel,
    ) -> Optional[str]:
        """Check if same content is currently being processed."""

        if not identifiers.doi and not identifiers.arxiv_id:
            return None

        # Look for processing tasks with same identifiers
        query = {
            "task_info.status": {"$in": ["pending", "processing", "in_progress"]},
            "$or": [],
        }

        if identifiers.doi:
            query["$or"].append({"identifiers.doi": identifiers.doi})
        if identifiers.arxiv_id:
            query["$or"].append({"identifiers.arxiv_id": identifiers.arxiv_id})
        
        # This part still uses MongoDB query syntax. It needs to be refactored for Neo4j.
        # For now, we'll bypass this check to avoid errors.
        # try:
        #     doc = await self.dao.collection.find_one(query)
        #     if doc:
        #         literature = LiteratureModel(**doc)
        #         logger.info(
        #             f"Task {self.task_id}: Found same content being processed in task {literature.task_info.task_id}",
        #         )
        #         return literature.lid
        # except Exception as e:
        #     logger.error(f"Task {self.task_id}: Error checking processing state: {e}")

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
