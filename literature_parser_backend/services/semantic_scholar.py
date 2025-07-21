"""
Semantic Scholar API client for academic graph data.

This module provides a client for interacting with the Semantic Scholar API
to retrieve paper metadata, author information, and citation networks.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from requests.exceptions import RequestException

from ..settings import Settings
from .request_manager import ExternalRequestManager, RequestType

logger = logging.getLogger(__name__)


class SemanticScholarClient:
    """
    Client for Semantic Scholar Academic Graph API.

    Semantic Scholar provides AI-powered academic search with rich metadata
    including citations, references, and semantic information.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize Semantic Scholar client with configuration."""
        self.settings = settings or Settings()
        self.base_url = self.settings.semantic_scholar_api_base_url
        self.timeout = self.settings.external_api_timeout
        self.max_retries = self.settings.external_api_max_retries
        self.api_key = self.settings.semantic_scholar_api_key

        # Common headers for all requests
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "LiteratureParser/1.0",
        }

        # Add API key if available
        if self.api_key:
            self.headers["x-api-key"] = self.api_key

        # Available fields for paper requests
        self.paper_fields = [
            "paperId",
            "title",
            "abstract",
            "venue",
            "year",
            "referenceCount",
            "citationCount",
            "influentialCitationCount",
            "isOpenAccess",
            "openAccessPdf",
            "fieldsOfStudy",
            "s2FieldsOfStudy",
            "publicationTypes",
            "publicationDate",
            "journal",
            "authors",
            "externalIds",
            "url",
            "publicationVenue",
            "references",
            "citations",
            "embedding",
            "tldr",
        ]

        # Available fields for author requests
        self.author_fields = [
            "authorId",
            "name",
            "url",
            "affiliations",
            "paperCount",
            "citationCount",
            "hIndex",
            "papers",
            "externalIds",
        ]

        # Use external request manager for all HTTP requests
        self.request_manager = ExternalRequestManager(settings)

        # Set custom headers for Semantic Scholar API
        session = self.request_manager.get_session(RequestType.EXTERNAL)
        session.headers.update(self.headers)

    def get_metadata(
        self,
        identifier: str,
        id_type: str = "auto",
        fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a single paper.

        Args:
            identifier: DOI or ArXiv ID of the paper.
            id_type: Type of identifier ('doi' or 'arxiv', 'auto' for detection).
            fields: List of fields to return.
            limit: Maximum number of results to return.

        Returns:
            Dictionary containing paper metadata or None if not found.
        """
        clean_id, detected_id_type = self._clean_and_detect_id(identifier)
        id_type = detected_id_type if id_type == "auto" else id_type

        if not id_type:
            raise ValueError("Invalid identifier type provided.")

        # URL encode the identifier
        encoded_id = quote(clean_id, safe=":")
        url = f"{self.base_url}/graph/v1/paper/{encoded_id}"

        # Request comprehensive fields
        params = {
            "fields": ",".join(
                [
                    "paperId",
                    "title",
                    "abstract",
                    "venue",
                    "year",
                    "referenceCount",
                    "citationCount",
                    "influentialCitationCount",
                    "isOpenAccess",
                    "openAccessPdf",
                    "fieldsOfStudy",
                    "s2FieldsOfStudy",
                    "publicationTypes",
                    "publicationDate",
                    "journal",
                    "authors",
                    "externalIds",
                    "url",
                    "publicationVenue",
                    "tldr",
                ],
            ),
        }

        try:
            response = self.request_manager.get(
                url=url,
                request_type=RequestType.EXTERNAL,
                params=params,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                data = response.json()
                return self._parse_paper_data(data)
            elif response.status_code == 404:
                logger.info(f"Paper {identifier} not found in Semantic Scholar")
                return None
            else:
                response.raise_for_status()
        except RequestException as e:
            logger.error(f"Semantic Scholar API error for {identifier}: {e}")
            raise Exception(f"Semantic Scholar API request failed: {e!s}")
        return None

    def get_references(
        self,
        identifier: str,
        id_type: str = "auto",
        fields: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get references for a paper.

        Args:
            identifier: Paper identifier
            id_type: Type of identifier ('doi', 'arxiv', 'paper_id', 'auto')
            limit: Maximum number of references to return

        Returns:
            list: List of referenced papers
        """
        clean_id, detected_id_type = self._clean_and_detect_id(identifier)
        id_type = detected_id_type if id_type == "auto" else id_type

        if not id_type:
            logger.error("Could not determine identifier type for references.")
            return []

        encoded_id = quote(clean_id, safe=":")
        url = f"{self.base_url}/graph/v1/paper/{encoded_id}/references"

        params = {
            "fields": ",".join(
                [
                    "paperId",
                    "title",
                    "abstract",
                    "venue",
                    "year",
                    "authors",
                    "externalIds",
                    "url",
                    "citationCount",
                    "isOpenAccess",
                ],
            ),
            "limit": str(limit),
        }

        try:
            response = self.request_manager.get(
                url=url,
                request_type=RequestType.EXTERNAL,
                params=params,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                data = response.json()
                references = []
                for ref_item in data.get("data", []):
                    cited_paper = ref_item.get("citedPaper", {})
                    if cited_paper:
                        parsed_ref = self._parse_paper_data(cited_paper)
                        if parsed_ref:
                            references.append(parsed_ref)
                return references
            elif response.status_code == 404:
                logger.info(f"No references found for paper: {identifier}")
                return []
            else:
                response.raise_for_status()
        except RequestException as e:
            logger.error(f"Semantic Scholar API error for {identifier}: {e}")
            raise
        return []

    def _clean_and_detect_id(self, identifier: str) -> Tuple[str, Optional[str]]:
        """Clean identifier and detect its type."""
        clean_id = identifier.strip()
        id_type = self._detect_identifier_type(clean_id)
        if id_type == "doi" and not clean_id.lower().startswith("doi:"):
            clean_id = f"DOI:{clean_id}"
        elif id_type == "arxiv" and not clean_id.lower().startswith("arxiv:"):
            clean_id = f"ARXIV:{clean_id}"
        return clean_id, id_type

    def _detect_identifier_type(self, identifier: str) -> Optional[str]:
        """
        Detects the type of a paper identifier.

        Args:
            identifier: The identifier string.

        Returns:
            The detected identifier type ('doi', 'arxiv', 'paper_id', 'unknown').
        """
        if "10." in identifier and "/" in identifier:
            return "doi"
        elif "arxiv" in identifier.lower() or "." in identifier:
            # Basic check for ArXiv ID format (e.g., 1706.03762 or arXiv:1706.03762)
            return "arxiv"
        elif len(identifier) == 40 and identifier.isalnum():
            return "paper_id"  # Semantic Scholar ID
        else:
            return "unknown"

    def _parse_paper_data(self, paper_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a single paper's data from the S2 API response."""
        return {
            "paperId": paper_data.get("paperId"),
            "title": paper_data.get("title"),
            "abstract": paper_data.get("abstract"),
            "authors": self._parse_authors(paper_data.get("authors", [])),
            "venue": paper_data.get("venue"),
            "publication_venue": paper_data.get("publicationVenue", {}),
            "year": paper_data.get("year"),
            "referenceCount": paper_data.get("referenceCount"),
            "citationCount": paper_data.get("citationCount"),
            "influentialCitationCount": paper_data.get("influentialCitationCount"),
            "isOpenAccess": paper_data.get("isOpenAccess"),
            "openAccessPdf": paper_data.get("openAccessPdf"),
            "fieldsOfStudy": paper_data.get("fieldsOfStudy"),
            "s2FieldsOfStudy": paper_data.get("s2FieldsOfStudy"),
            "publicationTypes": paper_data.get("publicationTypes"),
            "publicationDate": paper_data.get("publicationDate"),
            "journal": paper_data.get("journal"),
            "authors": self._parse_authors(paper_data.get("authors", [])),
            "externalIds": paper_data.get("externalIds"),
            "url": paper_data.get("url"),
            "publicationVenue": paper_data.get("publicationVenue"),
            "tldr": paper_data.get("tldr"),
        }

    def _parse_authors(
        self,
        authors_data: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Parse author data from the S2 API response."""
        if not authors_data:
            return []
        parsed_authors = []
        for author in authors_data:
            if author:  # Ensure author is not None
                parsed_authors.append(
                    {
                        "authorId": author.get("authorId"),
                        "name": author.get("name"),
                    },
                )
        return parsed_authors
