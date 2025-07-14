"""
External API services package for literature parser backend.

This package contains clients for interacting with external academic
and research services to retrieve and process literature data.
"""

from .crossref import CrossRefClient
from .grobid import GrobidClient
from .semantic_scholar import SemanticScholarClient

__all__ = [
    "GrobidClient",
    "CrossRefClient",
    "SemanticScholarClient",
]
