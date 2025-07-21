"""
CrossRef API client for retrieving bibliographic metadata.

This module provides a client for interacting with the CrossRef REST API
to retrieve metadata for publications by DOI and other identifiers.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from requests.exceptions import RequestException

from ..settings import Settings
from .request_manager import ExternalRequestManager, RequestType

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

        # Use external request manager for all HTTP requests
        self.request_manager = ExternalRequestManager(settings)

        # Set custom headers for CrossRef API
        session = self.request_manager.get_session(RequestType.EXTERNAL)
        session.headers.update(
            {"User-Agent": self.user_agent, "Accept": "application/json"},
        )

    def get_metadata_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
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
            response = self.request_manager.get(
                url=url,
                request_type=RequestType.EXTERNAL,
                params=params,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return self._parse_crossref_work(data.get("message", {}))
            elif response.status_code == 404:
                logger.info(f"DOI {doi} not found in CrossRef")
                return None
            else:
                response.raise_for_status()  # Will raise an HTTPError for other bad statuses

        except RequestException as e:
            logger.error(f"CrossRef API error for DOI {doi}: {e}")
            raise Exception(f"CrossRef API request failed: {e!s}")
        return None  # Should not be reached, but as a fallback

    def search_by_title_author(
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
            response = self.request_manager.get(
                url=url,
                request_type=RequestType.EXTERNAL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            items = data.get("message", {}).get("items", [])

            results = []
            for item in items:
                parsed_item = self._parse_crossref_work(item)
                if parsed_item:
                    results.append(parsed_item)

            return results

        except RequestException as e:
            logger.error(f"CrossRef search error: {e}")
            raise Exception(f"CrossRef search failed: {e!s}")

    def get_multiple_dois(
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
                metadata = self.get_metadata_by_doi(doi)
                results[doi] = metadata
            except Exception as e:
                logger.warning(f"Failed to retrieve metadata for DOI {doi}: {e}")
                results[doi] = None

        return results

    def _parse_crossref_work(self, work_data: Dict[str, Any]) -> Dict[str, Any]:
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
            if work_data.get("page"):
                parsed["pages"] = work_data["page"]

            # Extract ISSN
            if work_data.get("ISSN"):
                parsed["issn"] = work_data["ISSN"]

            # Extract ISBN
            if work_data.get("ISBN"):
                parsed["isbn"] = work_data["ISBN"]

            # Extract license information
            if work_data.get("license"):
                parsed["license"] = work_data["license"]

            # Extract funder information
            if work_data.get("funder"):
                parsed["funder"] = work_data["funder"]

            return parsed

        except Exception as e:
            logger.error(f"Error parsing CrossRef work data: {e}")
            return {}

    def check_doi_agency(self, doi: str) -> Optional[str]:
        """
        Check which agency registered a DOI.

        Args:
            doi: The DOI to check

        Returns:
            The agency ID if found, otherwise None.
        """
        if not doi:
            return None

        encoded_doi = quote(doi.strip(), safe="")
        url = f"{self.base_url}/works/{encoded_doi}/agency"

        try:
            response = self.request_manager.get(
                url=url, request_type=RequestType.EXTERNAL, timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json().get("message", {}).get("agency", {}).get("id")
            return None
        except RequestException as e:
            logger.warning(f"Could not check DOI agency for {doi}: {e}")
            return None

    def get_work_types(self) -> List[Dict[str, Any]]:
        """
        Get a list of all valid work types from CrossRef.

        Returns:
            A list of work types.
        """
        url = f"{self.base_url}/types"
        try:
            response = self.request_manager.get(
                url=url, request_type=RequestType.EXTERNAL, timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("items", [])
        except RequestException as e:
            logger.error(f"Could not retrieve work types from CrossRef: {e}")
            return []
