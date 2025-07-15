"""
Semantic Scholar API client for academic graph data.

This module provides a client for interacting with the Semantic Scholar API
to retrieve paper metadata, author information, and citation networks.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

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

    async def get_metadata(
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
            if not clean_id.lower().startswith("doi:"):
                clean_id = f"DOI:{clean_id}"
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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    return await self._parse_paper_data(data)
                elif response.status_code == 404:
                    logger.info(f"Paper {identifier} not found in Semantic Scholar")
                    return None
                else:
                    error_msg = f"Semantic Scholar API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

        except httpx.TimeoutException:
            logger.error(f"Semantic Scholar API timeout for: {identifier}")
            raise Exception("Semantic Scholar API request timed out")
        except Exception as e:
            logger.error(f"Semantic Scholar API error for {identifier}: {e}")
            raise Exception(f"Semantic Scholar API request failed: {e!s}")

    async def get_references(
        self,
        identifier: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get references for a paper.

        Args:
            identifier: Paper identifier
            limit: Maximum number of references to return

        Returns:
            list: List of referenced papers
        """
        if not identifier:
            raise ValueError("Identifier cannot be empty")

        clean_id = identifier.strip()
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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    references = []

                    for ref_item in data.get("data", []):
                        cited_paper = ref_item.get("citedPaper", {})
                        if cited_paper:
                            parsed_ref = await self._parse_paper_data(cited_paper)
                            if parsed_ref:
                                references.append(parsed_ref)

                    return references
                elif response.status_code == 404:
                    logger.info(f"No references found for paper: {identifier}")
                    return []
                else:
                    error_msg = f"Semantic Scholar references API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

        except Exception as e:
            logger.error(f"Error getting references for {identifier}: {e}")
            raise Exception(f"Failed to get references: {e!s}")

    def _detect_identifier_type(self, identifier: str) -> str:
        """Detect the type of identifier."""
        identifier_lower = identifier.lower()

        if (
            identifier_lower.startswith("doi:")
            or "/" in identifier
            and "10." in identifier
        ):
            return "doi"
        elif identifier_lower.startswith("arxiv:") or "arxiv" in identifier_lower:
            return "arxiv"
        elif len(identifier) == 40:  # Semantic Scholar paper IDs are 40 characters
            return "paper_id"
        else:
            return "paper_id"  # Default assumption

    async def _parse_paper_data(self, paper_data: Dict) -> Dict[str, Any]:
        """
        Parse Semantic Scholar paper data into our standard format.

        Args:
            paper_data: Raw paper data from Semantic Scholar API

        Returns:
            dict: Parsed metadata in our standard format
        """
        try:
            parsed = {
                "source": "Semantic Scholar API",
                "s2_paper_id": paper_data.get("paperId"),
                "title": paper_data.get("title"),
                "abstract": paper_data.get("abstract"),
                "venue": paper_data.get("venue"),
                "year": paper_data.get("year"),
                "authors": [],
                "external_ids": paper_data.get("externalIds", {}),
                "url": paper_data.get("url"),
                "citation_count": paper_data.get("citationCount", 0),
                "reference_count": paper_data.get("referenceCount", 0),
                "influential_citation_count": paper_data.get(
                    "influentialCitationCount",
                    0,
                ),
                "is_open_access": paper_data.get("isOpenAccess", False),
                "open_access_pdf": paper_data.get("openAccessPdf"),
                "fields_of_study": paper_data.get("fieldsOfStudy", []),
                "s2_fields_of_study": paper_data.get("s2FieldsOfStudy", []),
                "publication_types": paper_data.get("publicationTypes", []),
                "publication_date": paper_data.get("publicationDate"),
                "journal": paper_data.get("journal"),
                "publication_venue": paper_data.get("publicationVenue"),
                "tldr": paper_data.get("tldr"),
                "raw_data": paper_data,  # Keep original data for reference
            }

            # Extract authors
            if paper_data.get("authors"):
                for author in paper_data["authors"]:
                    author_info = {
                        "s2_author_id": author.get("authorId"),
                        "name": author.get("name"),
                        "url": author.get("url"),
                        "affiliations": author.get("affiliations", []),
                        "external_ids": author.get("externalIds", {}),
                    }
                    parsed["authors"].append(author_info)

            # Extract DOI from external IDs
            if parsed["external_ids"] and "DOI" in parsed["external_ids"]:
                parsed["doi"] = parsed["external_ids"]["DOI"]

            # Extract ArXiv ID
            if parsed["external_ids"] and "ArXiv" in parsed["external_ids"]:
                parsed["arxiv_id"] = parsed["external_ids"]["ArXiv"]

            return parsed

        except Exception as e:
            logger.error(f"Error parsing Semantic Scholar paper data: {e}")
            return {
                "source": "Semantic Scholar API",
                "error": str(e),
                "raw_data": paper_data,
            }
