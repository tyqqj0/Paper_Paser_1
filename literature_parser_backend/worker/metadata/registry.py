"""
Processor registry for managing and discovering metadata processors.

Provides centralized registration and discovery of all available processors.
"""

import logging
from typing import Dict, List, Type
from .base import MetadataProcessor, IdentifierData, ProcessorType

logger = logging.getLogger(__name__)


class ProcessorRegistry:
    """
    Central registry for all metadata processors.
    
    Manages processor registration, discovery, and selection based on
    identifiers and processor capabilities.
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._processors: Dict[str, Type[MetadataProcessor]] = {}
        self._instances: Dict[str, MetadataProcessor] = {}
    
    def register(self, processor_class: Type[MetadataProcessor]) -> None:
        """
        Register a processor class.
        
        Args:
            processor_class: Class that implements MetadataProcessor
        """
        # Create a temporary instance to get the name
        temp_instance = processor_class()
        name = temp_instance.name
        
        if name in self._processors:
            logger.warning(f"Processor '{name}' already registered, overwriting")
        
        self._processors[name] = processor_class
        logger.debug(f"Registered processor: {name}")
    
    def get_processor(self, name: str, settings=None) -> MetadataProcessor:
        """
        Get processor instance by name.
        
        Args:
            name: Processor name
            settings: Optional settings for processor initialization
            
        Returns:
            Processor instance
            
        Raises:
            KeyError: If processor not found
        """
        if name not in self._processors:
            raise KeyError(f"Processor '{name}' not registered")
        
        # Cache instances with default settings
        if settings is None and name in self._instances:
            return self._instances[name]
        
        processor = self._processors[name](settings)
        
        if settings is None:
            self._instances[name] = processor
        
        return processor
    
    def get_available_processors(
        self, 
        identifiers: IdentifierData,
        processor_type: ProcessorType = None,
        settings=None
    ) -> List[MetadataProcessor]:
        """
        Get all processors that can handle the given identifiers.
        
        Args:
            identifiers: Standardized identifier data
            processor_type: Optional filter by processor type
            settings: Optional settings for processor initialization
            
        Returns:
            List of processors sorted by priority (highest first)
        """
        available = []
        
        for name, processor_class in self._processors.items():
            try:
                processor = self.get_processor(name, settings)
                
                # Filter by type if specified
                if processor_type and processor.processor_type != processor_type:
                    continue
                
                # Check if processor can handle these identifiers
                if processor.can_handle(identifiers):
                    available.append(processor)
                    
            except Exception as e:
                logger.warning(f"Error checking processor '{name}': {e}")
                continue
        
        # Sort by priority (lower number = higher priority)
        available.sort(key=lambda p: p.priority)
        
        logger.debug(
            f"Found {len(available)} available processors: "
            f"{[p.name for p in available]}"
        )
        
        return available
    
    def list_processors(self) -> List[str]:
        """
        List all registered processor names.
        
        Returns:
            List of processor names
        """
        return list(self._processors.keys())
    
    def get_processors_by_type(self, processor_type: ProcessorType) -> List[str]:
        """
        Get processor names filtered by type.
        
        Args:
            processor_type: Type to filter by
            
        Returns:
            List of processor names of the specified type
        """
        names = []
        for name in self._processors:
            try:
                processor = self.get_processor(name)
                if processor.processor_type == processor_type:
                    names.append(name)
            except Exception as e:
                logger.warning(f"Error checking processor type for '{name}': {e}")
        
        return names


# Global registry instance
_global_registry = ProcessorRegistry()


def register_processor(processor_class: Type[MetadataProcessor]) -> None:
    """
    Register a processor in the global registry.
    
    Args:
        processor_class: Class that implements MetadataProcessor
    """
    _global_registry.register(processor_class)


def get_global_registry() -> ProcessorRegistry:
    """
    Get the global processor registry.
    
    Returns:
        Global ProcessorRegistry instance
    """
    return _global_registry


