"""
GROBID service client for PDF processing.

This module provides a client for interacting with GROBID service
to extract metadata and fulltext from PDF documents.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
import xmltodict
from requests.exceptions import RequestException, Timeout

from ..settings import Settings

logger = logging.getLogger(__name__)


class GrobidClient:
    """
    Client for GROBID PDF processing service.

    GROBID (GeneRation Of BibliogRaphic Data) is a machine learning library
    for extracting and parsing bibliographic information from scholarly documents.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize GROBID client with configuration."""
        self.settings = settings or Settings()
        self.base_url = self.settings.grobid_base_url
        self.timeout = self.settings.external_api_timeout
        self.max_retries = self.settings.external_api_max_retries

        # GROBID API endpoints
        self.endpoints = {
            "process_fulltext": "/api/processFulltextDocument",
            "process_header": "/api/processHeaderDocument",
            "process_references": "/api/processReferences",
            "version": "/api/version",
            "is_alive": "/api/isalive",
        }
        self.session = requests.Session()

    def health_check(self) -> bool:
        """
        Check if GROBID service is alive and responding.

        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.base_url}{self.endpoints['is_alive']}",
                timeout=self.timeout,
            )
            return (
                response.status_code == 200 and response.text.strip().lower() == "true"
            )
        except RequestException as e:
            logger.error(f"GROBID health check failed: {e}")
            return False

    def get_version(self) -> Optional[str]:
        """
        Get GROBID service version.

        Returns:
            str: Version string if successful, None otherwise
        """
        try:
            response = self.session.get(
                f"{self.base_url}{self.endpoints['version']}",
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.text.strip()
            return None
        except RequestException as e:
            logger.error(f"Failed to get GROBID version: {e}")
            return None

    def process_pdf(
        self,
        pdf_content: bytes,
        service: str = "processFulltextDocument",
        consolidate_header: bool = True,
        consolidate_citations: bool = False,
        include_raw_citations: bool = False,
        include_raw_affiliations: bool = False,
        tei_coordinates: Optional[List[str]] = None,
        segment_sentences: bool = False,
    ) -> Dict[str, Any]:
        """
        Process a PDF file to extract fulltext and metadata using GROBID.

        Args:
            pdf_file: PDF file content as bytes
            include_raw_citations: Include raw citation strings in result
            include_raw_affiliations: Include raw affiliation strings
            consolidate_header: Consolidation level for header (0-3)
            consolidate_citations: Consolidation level for citations (0-2)
            tei_coordinates: List of elements to include coordinates for

        Returns:
            dict: Parsed document data with metadata and fulltext

        Raises:
            Exception: If processing fails
        """
        if not pdf_content:
            raise ValueError("PDF file content cannot be empty")

        # Prepare form data for GROBID request
        files = {"input": ("document.pdf", pdf_content, "application/pdf")}

        # Form parameters based on GROBID API documentation
        form_data = {
            "includeRawCitations": "1" if include_raw_citations else "0",
            "includeRawAffiliations": "1" if include_raw_affiliations else "0",
            "consolidateHeader": str(consolidate_header),
            "consolidateCitations": str(consolidate_citations),
        }

        # Add coordinates parameters if specified
        if tei_coordinates is None:
            tei_coordinates = []
        for coord_type in tei_coordinates:
            form_data["teiCoordinates"] = coord_type

        url = f"{self.base_url}{self.endpoints[service]}"

        try:
            response = self.session.post(
                url,
                files=files,
                data=form_data,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                # GROBID returns TEI XML format
                xml_content = response.text
                return self._parse_tei_xml(xml_content)
            elif response.status_code == 204:
                logger.warning(
                    "GROBID processing completed but no content extracted",
                )
                return {"status": "no_content", "message": "No content extracted"}
            else:
                response.raise_for_status()

        except Timeout:
            logger.error("GROBID request timed out")
            raise Exception("GROBID processing timed out")
        except RequestException as e:
            logger.error(f"GROBID processing error: {e}")
            raise Exception(f"GROBID processing failed: {e!s}")
        return {}

    def process_header_only(self, pdf_file: bytes) -> Dict[str, Any]:
        """
        Extract only header metadata from PDF using GROBID.

        Args:
            pdf_file: PDF file content as bytes

        Returns:
            dict: Parsed header metadata
        """
        if not pdf_file:
            raise ValueError("PDF file content cannot be empty")

        files = {"input": ("document.pdf", pdf_file, "application/pdf")}
        form_data = {"consolidateHeader": "1", "includeRawAffiliations": "1"}

        url = f"{self.base_url}{self.endpoints['process_header']}"

        try:
            response = self.session.post(
                url,
                files=files,
                data=form_data,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                xml_content = response.text
                return self._parse_tei_xml(xml_content)
            else:
                response.raise_for_status()

        except RequestException as e:
            logger.error(f"GROBID header processing error: {e}")
            raise Exception(f"Header processing failed: {e!s}")
        return {}

    def _parse_tei_xml(self, xml_content: str) -> Dict[str, Any]:
        """
        Parse TEI XML response from GROBID into structured data.

        Args:
            xml_content: TEI XML string from GROBID

        Returns:
            dict: Structured document data
        """
        try:
            # Convert XML to dictionary using xmltodict
            parsed_xml = xmltodict.parse(xml_content)

            # Extract key information from TEI structure
            tei_root = parsed_xml.get("TEI", {})

            result: Dict[str, Any] = {
                "status": "success",
                "raw_xml": xml_content,  # Keep original XML for reference
                "parsed_data": {},
                "metadata": {},
                "fulltext": {},
                "references": [],
            }

            # Extract header information
            tei_header = tei_root.get("teiHeader", {})
            if tei_header:
                result["metadata"] = self._extract_header_metadata(tei_header)

            # Extract body text
            text_element = tei_root.get("text", {})
            if text_element:
                result["fulltext"] = self._extract_fulltext(text_element)
                references = self._extract_references(text_element)
                result["references"] = references if references else []

            # Store complete parsed structure for advanced usage
            result["parsed_data"] = tei_root

            return result

        except Exception as e:
            logger.error(f"TEI XML parsing error: {e}")
            return {"status": "parse_error", "error": str(e), "raw_xml": xml_content}

    def _extract_header_metadata(self, tei_header: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from TEI header."""
        metadata = {}
        file_desc = tei_header.get("fileDesc", {})
        if not file_desc:
            return {}

        # Extract title information
        title_stmt_list = file_desc.get("titleStmt", [])
        title_stmt = (
            title_stmt_list[0] if isinstance(title_stmt_list, list) else title_stmt_list
        )
        if title_stmt and "title" in title_stmt:
            title_info = title_stmt["title"]
            if isinstance(title_info, list):
                title_info = title_info[0]
            metadata["title"] = (
                title_info.get("#text") if isinstance(title_info, dict) else title_info
            )

        # Extract publication information
        publication_stmt_list = file_desc.get("publicationStmt", [])
        publication_stmt = (
            publication_stmt_list[0]
            if isinstance(publication_stmt_list, list)
            else publication_stmt_list
        )
        if publication_stmt:
            publisher = publication_stmt.get("publisher")
            if publisher:
                metadata["publisher"] = publisher

            date_info = publication_stmt.get("date")
            if date_info:
                if isinstance(date_info, list):
                    date_info = date_info[0]
                if isinstance(date_info, dict):
                    metadata["year"] = date_info.get("@when")

        # Extract source description for authors
        source_desc_list = file_desc.get("sourceDesc", [])
        source_desc = (
            source_desc_list[0]
            if isinstance(source_desc_list, list)
            else source_desc_list
        )
        if source_desc:
            bibl_struct = source_desc.get("biblStruct", {})
            if bibl_struct:
                analytic = bibl_struct.get("analytic", {})
                if analytic:
                    metadata["authors"] = self._extract_authors(analytic)

        # Abstract
        profile_desc = file_desc.get("profileDesc", {})
        if profile_desc:
            abstract_data = profile_desc.get("abstract")
            if abstract_data:
                # Handle cases where abstract is a list of paragraphs or a simple dict
                if isinstance(abstract_data, list):
                    abstract_text = " ".join(
                        p.get("#text", "")
                        for p in abstract_data
                        if p and p.get("#text")
                    )
                elif isinstance(abstract_data, dict):
                    abstract_text = abstract_data.get("#text") or ""
                else:
                    abstract_text = str(abstract_data)
                metadata["abstract"] = abstract_text.strip()

        return metadata

    def _extract_authors(self, analytic: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract authors from analytic section."""
        authors = []
        author_list = analytic.get("author", [])
        if not isinstance(author_list, list):
            author_list = [author_list]

        for author_node in author_list:
            pers_name = author_node.get("persName", {})
            if not pers_name:
                continue

            first_name = pers_name.get("forename", {"#text": ""})
            if isinstance(first_name, list):
                first_name = first_name[0]
            first_name_text = (
                first_name.get("#text") if isinstance(first_name, dict) else ""
            )

            last_name = pers_name.get("surname", "")
            full_name = f"{first_name_text} {last_name}".strip()
            authors.append({"full_name": full_name})
        return authors

    def _extract_fulltext(self, text_element: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and structure the fulltext from the TEI body."""
        fulltext = {"body": None, "back": None}
        if not text_element or not isinstance(text_element, dict):
            return fulltext

        # Extract body
        body = text_element.get("body", {})
        if body and isinstance(body, dict):
            fulltext["body"] = self._stringify_divs(body.get("div", []))

        # Extract back matter (references, etc.)
        back = text_element.get("back", {})
        if back and isinstance(back, dict):
            fulltext["back"] = self._stringify_divs(back.get("div", []))

        return fulltext

    def _extract_references(self, text_element: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and parse references from the TEI back matter."""
        references = []
        back_element = text_element.get("back", {})
        if not back_element or not isinstance(back_element, dict):
            return references

        ref_div = None
        # Find the div that contains the list of references
        for div in back_element.get("div", []):
            if div.get("listBibl"):
                ref_div = div
                break

        if not ref_div:
            return references

        list_bibl = ref_div.get("listBibl", {}).get("biblStruct", [])
        if not isinstance(list_bibl, list):
            list_bibl = [list_bibl]

        for bibl_struct in list_bibl:
            parsed_ref = self._parse_reference(bibl_struct)
            if parsed_ref:
                references.append(parsed_ref)
        return references

    def _parse_reference(self, bibl_struct: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a single biblStruct into a structured reference."""
        if not bibl_struct or not isinstance(bibl_struct, dict):
            return None

        analytic = bibl_struct.get("analytic", {})
        monogr = bibl_struct.get("monogr", {})

        title = analytic.get("title", {}).get("#text")
        year = monogr.get("imprint", {}).get("date", {}).get("@when")
        authors = self._extract_authors_from_reference(analytic.get("author", []))

        return {
            "title": title,
            "year": year,
            "authors": authors,
            "journal": monogr.get("title"),
        }

    def _extract_authors_from_reference(
        self,
        authors_data: List[Dict[str, Any]],
    ) -> List[str]:
        """Extract author names from a reference's author list."""
        if not isinstance(authors_data, list):
            authors_data = [authors_data]

        names = []
        for author in authors_data:
            pers_name = author.get("persName", {})
            if not pers_name:
                continue
            # Simplified name extraction for references
            name_parts = []
            forenames = pers_name.get("forename", [])
            if not isinstance(forenames, list):
                forenames = [forenames]
            for fname in forenames:
                name_parts.append(fname.get("#text", ""))
            surname = pers_name.get("surname")
            if surname:
                name_parts.append(surname)
            if name_parts:
                names.append(" ".join(filter(None, name_parts)))
        return names

    def _stringify_divs(self, divs: List[Dict[str, Any]]) -> str:
        """Recursively stringify divs into a single text block."""
        if not isinstance(divs, list):
            divs = [divs]

        text_parts = []
        for div in divs:
            head = div.get("head", "")
            if isinstance(head, dict):
                head = head.get("#text", "")
            if head:
                text_parts.append(head)

            paragraphs = div.get("p", [])
            if not isinstance(paragraphs, list):
                paragraphs = [paragraphs]
            for p in paragraphs:
                if isinstance(p, str):
                    text_parts.append(p)
                elif isinstance(p, dict):
                    text_parts.append(p.get("#text", ""))
        return "\n".join(text_parts)
