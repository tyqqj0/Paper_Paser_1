#!/usr/bin/env python3
"""
Worker execution exceptions.

Custom exceptions for literature processing pipeline.
"""

import logging

logger = logging.getLogger(__name__)


class ProcessingException(Exception):
    """Base exception for processing errors."""
    pass


class URLNotFoundException(ProcessingException):
    """Exception raised when URL is not found or doesn't exist."""
    pass


class URLAccessFailedException(ProcessingException):
    """Exception raised when URL cannot be accessed due to network/permission issues."""
    pass


class ParsingFailedException(ProcessingException):
    """Exception raised when content parsing fails."""
    pass


class ContentFetchException(ProcessingException):
    """Exception raised when content fetching fails."""
    pass


class MetadataExtractionException(ProcessingException):
    """Exception raised when metadata extraction fails."""
    pass
