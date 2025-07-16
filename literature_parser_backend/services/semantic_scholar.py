"""
Semantic Scholar API client for academic graph data.

This module provides a client for interacting with the Semantic Scholar API
to retrieve paper metadata, author information, and citation networks.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from requests.exceptions import RequestException, Timeout

from ..settings import Settings

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

        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get_metadata(
        self,
        identifier: str,
        id_type: str = "auto",
    ) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a paper by various identifiers.

        Args:
            identifier: Paper identifier (DOI, ArXiv ID, Semantic Scholar ID, etc.)
            id_type: Type of identifier ('doi', 'arxiv', 'paper_id', 'auto')

        Returns:
            dict: Paper metadata if found, None otherwise
        """
        if not identifier:
            raise ValueError("Identifier cannot be empty")

        # Clean identifier
        clean_id = identifier.strip()

        # Auto-detect identifier type if needed
        if id_type == "auto":
            id_type = self._detect_identifier_type(clean_id)

        # Format identifier for API
        if id_type == "doi":
            # The API expects the DOI without the "DOI:" prefix for the paper lookup
            pass
        elif id_type == "arxiv":
            if not clean_id.lower().startswith("arxiv:"):
                clean_id = f"ARXIV:{clean_id}"

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
            response = self.session.get(url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return self._parse_paper_data(data)
            elif response.status_code == 404:
                logger.info(f"Paper {identifier} not found in Semantic Scholar")
                return None
            else:
                response.raise_for_status()
        except Timeout:
            logger.error(f"Semantic Scholar API timeout for: {identifier}")
            raise Exception("Semantic Scholar API request timed out")
        except RequestException as e:
            logger.error(f"Semantic Scholar API error for {identifier}: {e}")
            raise Exception(f"Semantic Scholar API request failed: {e!s}")
        return None

    def get_references(
        self,
        identifier: str,
        id_type: str = "auto",
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
        if not identifier:
            raise ValueError("Identifier cannot be empty")

        clean_id = identifier.strip()

        # Auto-detect identifier type if needed
        if id_type == "auto":
            id_type = self._detect_identifier_type(clean_id)

        # Format identifier for API
        if id_type == "doi":
            if not clean_id.lower().startswith("doi:"):
                clean_id = f"DOI:{clean_id}"
        elif id_type == "arxiv":
            if not clean_id.lower().startswith("arxiv:"):
                clean_id = f"ARXIV:{clean_id}"

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
            response = self.session.get(url, params=params, timeout=self.timeout)
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

    def _detect_identifier_type(self, identifier: str) -> str:
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

    def _parse_paper_data(self, paper_data: Dict) -> Dict[str, Any]:
        """
        Parse paper data from Semantic Scholar API into our format.

        Args:
            paper_data (Dict): The raw paper data from the API.

        Returns:
            Dict[str, Any]: The parsed and structured paper data.
        """
        if not paper_data or not paper_data.get("paperId"):
            return {}

        external_ids = paper_data.get("externalIds", {}) or {}

        return {
            "s2_id": paper_data.get("paperId"),
            "title": paper_data.get("title"),
            "abstract": paper_data.get("abstract"),
            "authors": self._parse_authors(paper_data.get("authors", [])),
            "venue": paper_data.get("venue"),
            "publication_venue": paper_data.get("publicationVenue", {}),
            "year": paper_data.get("year"),
            "reference_count": paper_data.get("referenceCount"),
            "citation_count": paper_data.get("citationCount"),
            "influential_citation_count": paper_data.get("influentialCitationCount"),
            "is_open_access": paper_data.get("isOpenAccess"),
            "open_access_pdf": (paper_data.get("openAccessPdf") or {}).get("url"),
            "fields_of_study": paper_data.get("fieldsOfStudy", []),
            "s2_fields_of_study": paper_data.get("s2FieldsOfStudy", []),
            "publication_types": paper_data.get("publicationTypes", []),
            "publication_date": paper_data.get("publicationDate"),
            "journal": paper_data.get("journal", {}),
            "doi": external_ids.get("DOI"),
            "arxiv_id": external_ids.get("ArXiv"),
            "s2_url": paper_data.get("url"),
            "tldr": (paper_data.get("tldr") or {}).get("text"),
        }

    def _parse_authors(self, authors_data: List[Dict]) -> List[Dict]:
        """
        Parse author data into a simplified format.

        Args:
            authors_data (List[Dict]): Raw author data from API.

        Returns:
            List[Dict]: List of parsed author data.
        """
        if not authors_data:
            return []
        return [
            {"s2_id": author.get("authorId"), "name": author.get("name")}
            for author in authors_data
        ]