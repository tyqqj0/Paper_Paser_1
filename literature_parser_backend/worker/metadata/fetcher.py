"""
Modern metadata fetcher with unified processor architecture.

Implements the waterfall approach using modular, registered processors
for clean separation of concerns and easy extensibility.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ...models.literature import MetadataModel
from ...settings import Settings
from .base import IdentifierData, MetadataProcessor, ProcessorResult, ProcessorType
from .registry import get_global_registry

# 自动导入所有处理器以触发注册
from . import processors

logger = logging.getLogger(__name__)


class MetadataFetcher:
    """
    Modern metadata fetcher using unified processor architecture.
    
    This fetcher automatically discovers and uses all registered processors
    in priority order, providing a clean waterfall approach with modular
    processor components.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize fetcher with settings."""
        self.settings = settings or Settings()
        self.registry = get_global_registry()
    
    async def fetch_metadata_waterfall(
        self,
        identifiers: Dict[str, Any],
        source_data: Dict[str, Any],
        pre_fetched_metadata: Optional[MetadataModel] = None,
        pdf_content: Optional[bytes] = None,
    ) -> Tuple[Optional[MetadataModel], Dict[str, Any]]:
        """
        Fetch metadata using the waterfall approach with registered processors.
        
        Args:
            identifiers: Raw identifier data from task
            source_data: Additional source context
            pre_fetched_metadata: Optional pre-fetched metadata
            pdf_content: Optional PDF content for parsing
            
        Returns:
            Tuple of (MetadataModel, raw_data) or (None, error_info)
        """
        logger.info(f"Starting metadata fetch with {len(self.registry.list_processors())} registered processors")
        
        # 1. Check pre-fetched metadata first
        if pre_fetched_metadata and pre_fetched_metadata.title != "Unknown Title":
            logger.info("✅ Using pre-fetched metadata")
            return pre_fetched_metadata, {"source": "pre-fetched"}
        
        # 2. Preprocess and standardize identifiers
        identifier_data = self._preprocess_identifiers(
            identifiers, source_data, pdf_content
        )
        
        logger.info(f"Preprocessed identifiers: DOI={bool(identifier_data.doi)}, "
                   f"ArXiv={bool(identifier_data.arxiv_id)}, URL={bool(identifier_data.url)}, "
                   f"Title={bool(identifier_data.title)}")
        
        # 3. Get all available processors for these identifiers
        available_processors = self.registry.get_available_processors(
            identifier_data, settings=self.settings
        )
        
        if not available_processors:
            logger.warning("No processors available for these identifiers")
            return None, {"error": "No suitable processors found"}
        
        logger.info(f"Found {len(available_processors)} available processors: "
                   f"{[p.name for p in available_processors]}")
        
        # 4. Try processors in priority order (waterfall approach)
        attempted_sources = []
        last_error = None
        
        for processor in available_processors:
            try:
                logger.info(f"🔍 Trying processor: {processor.name} (priority: {processor.priority})")
                
                result = await processor.process(identifier_data)
                attempted_sources.append(processor.name)
                
                if result.is_valid:
                    logger.info(f"✅ Success with {processor.name} (confidence: {result.confidence:.2f})")
                    
                    # Add source priority information
                    if result.metadata:
                        if hasattr(result.metadata, 'source_priority'):
                            result.metadata.source_priority = [result.source]
                        else:
                            # For backward compatibility
                            pass
                    
                    return result.metadata, result.raw_data or {}
                else:
                    logger.info(f"❌ {processor.name} failed: {result.error}")
                    last_error = result.error
                    
            except Exception as e:
                logger.warning(f"❌ {processor.name} exception: {e}")
                attempted_sources.append(processor.name)
                last_error = str(e)
                continue
        
        # 5. All processors failed
        logger.warning(f"All {len(attempted_sources)} processors failed")
        
        return None, {
            "error": "All metadata sources failed",
            "attempted_sources": attempted_sources,
            "last_error": last_error
        }
    
    def _preprocess_identifiers(
        self,
        identifiers: Dict[str, Any],
        source_data: Dict[str, Any],
        pdf_content: Optional[bytes] = None
    ) -> IdentifierData:
        """
        Preprocess and standardize identifier data.
        
        Extracts and enriches identifiers from various sources into
        a standardized format for processors.
        """
        # Extract basic identifiers
        identifier_data = IdentifierData(
            doi=identifiers.get("doi"),
            arxiv_id=identifiers.get("arxiv_id"),
            pmid=identifiers.get("pmid"),
            pdf_content=pdf_content,
            source_data=source_data
        )
        
        # Extract URL-based identifiers
        if source_data:
            identifier_data.url = source_data.get("url")
            identifier_data.pdf_url = source_data.get("pdf_url")
            
            # Extract enriched metadata from URL mapping
            url_mapping = source_data.get("url_mapping_result", {})
            if url_mapping:
                identifier_data.title = url_mapping.get("title")
                identifier_data.year = url_mapping.get("year")
                identifier_data.venue = url_mapping.get("venue")
                
                logger.debug(f"Extracted from URL mapping: title='{identifier_data.title}', "
                           f"year={identifier_data.year}, venue='{identifier_data.venue}'")
        
        return identifier_data
    
    def get_available_processors(self, identifiers: Dict[str, Any], source_data: Dict[str, Any]) -> List[str]:
        """
        Get list of processor names that can handle the given identifiers.
        
        Useful for debugging and status reporting.
        """
        identifier_data = self._preprocess_identifiers(identifiers, source_data)
        processors = self.registry.get_available_processors(identifier_data, settings=self.settings)
        return [p.name for p in processors]


