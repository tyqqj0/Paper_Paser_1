"""
CrossRef API client for retrieving bibliographic metadata.

This module provides a client for interacting with the CrossRef REST API
to retrieve metadata for publications by DOI and other identifiers.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from ..settings import Settings

logger = logging.getLogger(__name__)


class CrossRefClient:
    """
    Client for CrossRef REST API.

    CrossRef provides open access to bibliographic metadata for millions
    of scholarly publications through their REST API.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize CrossRef client with configuration."""
        self.settings = settings or Settings()
        self.base_url = self.settings.crossref_api_base_url
        self.timeout = self.settings.external_api_timeout
        self.max_retries = self.settings.external_api_max_retries
        self.mailto = self.settings.crossref_mailto

        # User-Agent for polite pool access
        self.user_agent = f"LiteratureParser/1.0 (mailto:{self.mailto})"

        # Common headers for all requests
        self.headers = {"User-Agent": self.user_agent, "Accept": "application/json"}

    async def get_metadata_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve metadata for a publication by DOI.

        Args:
            doi: Digital Object Identifier (DOI) of the publication

        Returns:
            dict: Publication metadata if found, None otherwise

        Raises:
            Exception: If API request fails
        """
        if not doi:
            raise ValueError("DOI cannot be empty")

        # Clean and URL-encode the DOI
        clean_doi = doi.strip()
        if clean_doi.lower().startswith("doi:"):
            clean_doi = clean_doi[4:]

        encoded_doi = quote(clean_doi, safe="")
        url = f"{self.base_url}/works/{encoded_doi}"

        # Add polite pool parameter
        params = {"mailto": self.mailto}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    return await self._parse_crossref_work(data.get("message", {}))
                elif response.status_code == 404:
                    logger.info(f"DOI {doi} not found in CrossRef")
                    return None
                else:
                    error_msg = (
                        f"CrossRef API error {response.status_code}: {response.text}"
                    )
                    logger.error(error_msg)
                    raise Exception(error_msg)

        except httpx.TimeoutException:
            logger.error(f"CrossRef API timeout for DOI: {doi}")
            raise Exception("CrossRef API request timed out")
        except Exception as e:
            logger.error(f"CrossRef API error for DOI {doi}: {e}")
            raise Exception(f"CrossRef API request failed: {e!s}")

    async def search_by_title_author(
        self,
        title: str,
        author: Optional[str] = None,
        year: Optional[int] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search for publications by title and optionally author/year.

        Args:
            title: Publication title to search for
            author: Author name (optional)
            year: Publication year (optional)
            limit: Maximum number of results to return

        Returns:
            list: List of matching publications
        """
        if not title:
            raise ValueError("Title cannot be empty")

        url = f"{self.base_url}/works"

        # Build query string
        query_parts = [f'title:"{title}"']
        if author:
            query_parts.append(f'author:"{author}"')

        params = {
            "query": " AND ".join(query_parts),
            "rows": str(limit),
            "mailto": self.mailto,
        }

        # Add year filter if provided
        if year:
            params["filter"] = f"from-pub-date:{year},until-pub-date:{year}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("message", {}).get("items", [])

                    results = []
                    for item in items:
                        parsed_item = await self._parse_crossref_work(item)
                        if parsed_item:
                            results.append(parsed_item)

                    return results
                else:
                    error_msg = (
                        f"CrossRef search error {response.status_code}: {response.text}"
                    )
                    logger.error(error_msg)
                    raise Exception(error_msg)

        except Exception as e:
            logger.error(f"CrossRef search error: {e}")
            raise Exception(f"CrossRef search failed: {e!s}")

    async def get_multiple_dois(
        self,
        dois: List[str],
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Retrieve metadata for multiple DOIs in batch.

        Args:
            dois: List of DOIs to retrieve

        Returns:
            dict: Mapping of DOI to metadata (None if not found)
        """
        results = {}

        # Process DOIs individually (CrossRef doesn't have a true batch endpoint)
        for doi in dois:
            try:
                metadata = await self.get_metadata_by_doi(doi)
                results[doi] = metadata
            except Exception as e:
                logger.warning(f"Failed to retrieve metadata for DOI {doi}: {e}")
                results[doi] = None

        return results

    async def _parse_crossref_work(self, work_data: Dict) -> Dict[str, Any]:
        """
        Parse CrossRef work data into our standard format.

        Args:
            work_data: Raw work data from CrossRef API

        Returns:
            dict: Parsed metadata in our standard format
        """
        try:
            parsed = {
                "source": "CrossRef API",
                "doi": work_data.get("DOI"),
                "title": None,
                "authors": [],
                "journal": None,
                "year": None,
                "volume": work_data.get("volume"),
                "issue": work_data.get("issue"),
                "pages": None,
                "abstract": work_data.get("abstract"),
                "type": work_data.get("type"),
                "publisher": work_data.get("publisher"),
                "issn": [],
                "isbn": [],
                "url": work_data.get("URL"),
                "references_count": work_data.get("references-count", 0),
                "is_referenced_by_count": work_data.get("is-referenced-by-count", 0),
                "license": [],
                "funder": [],
                "raw_data": work_data,  # Keep original data for reference
            }

            # Extract title
            if work_data.get("title"):
                parsed["title"] = work_data["title"][0]

            # Extract authors
            if "author" in work_data:
                for author in work_data["author"]:
                    author_info = {
                        "family_name": author.get("family", ""),
                        "given_names": (
                            author.get("given", "").split()
                            if author.get("given")
                            else []
                        ),
                        "sequence": author.get("sequence", ""),
                        "orcid": author.get("ORCID", ""),
                        "affiliations": [],
                    }

                    # Extract affiliations if present
                    if "affiliation" in author:
                        for affil in author["affiliation"]:
                            author_info["affiliations"].append(affil.get("name", ""))

                    parsed["authors"].append(author_info)

            # Extract journal/container title
            if work_data.get("container-title"):
                parsed["journal"] = work_data["container-title"][0]

            # Extract publication year
            if "published-print" in work_data:
                date_parts = work_data["published-print"].get("date-parts", [])
                if date_parts and date_parts[0]:
                    parsed["year"] = date_parts[0][0]
            elif "published-online" in work_data:
                date_parts = work_data["published-online"].get("date-parts", [])
                if date_parts and date_parts[0]:
                    parsed["year"] = date_parts[0][0]

            # Extract page information
            if "page" in work_data:
                parsed["pages"] = work_data["page"]

            # Extract ISSN/ISBN
            if "ISSN" in work_data:
                parsed["issn"] = work_data["ISSN"]
            if "ISBN" in work_data:
                parsed["isbn"] = work_data["ISBN"]

            # Extract license information
            if "license" in work_data:
                for license_info in work_data["license"]:
                    parsed["license"].append(
                        {
                            "url": license_info.get("URL"),
                            "start_date": license_info.get("start", {}).get(
                                "date-time",
                            ),
                            "delay_in_days": license_info.get("delay-in-days"),
                        },
                    )

            # Extract funder information
            if "funder" in work_data:
                for funder in work_data["funder"]:
                    funder_info = {
                        "name": funder.get("name"),
                        "doi": funder.get("DOI"),
                        "awards": [],
                    }

                    if "award" in funder:
                        funder_info["awards"] = funder["award"]

                    parsed["funder"].append(funder_info)

            return parsed

        except Exception as e:
            logger.error(f"Error parsing CrossRef work data: {e}")
            return {"source": "CrossRef API", "error": str(e), "raw_data": work_data}

    async def check_doi_agency(self, doi: str) -> Optional[str]:
        """
        Check which registration agency manages a DOI.

        Args:
            doi: DOI to check

        Returns:
            str: Agency name if found, None otherwise
        """
        if not doi:
            return None

        clean_doi = doi.strip()
        if clean_doi.lower().startswith("doi:"):
            clean_doi = clean_doi[4:]

        encoded_doi = quote(clean_doi, safe="")
        url = f"{self.base_url}/works/{encoded_doi}/agency"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    params={"mailto": self.mailto},
                )

                if response.status_code == 200:
                    data = response.json()
                    agency = data.get("message", {}).get("agency", {})
                    return agency.get("id")

                return None

        except Exception as e:
            logger.warning(f"Failed to check DOI agency for {doi}: {e}")
            return None

    async def get_work_types(self) -> List[Dict[str, Any]]:
        """
        Get list of available work types from CrossRef.

        Returns:
            list: List of work type definitions
        """
        url = f"{self.base_url}/types"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    params={"mailto": self.mailto},
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("message", {}).get("items", [])

                return []

        except Exception as e:
            logger.warning(f"Failed to get work types: {e}")
            return []
