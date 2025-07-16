"""
GROBID service client for PDF processing.

This module provides a client for interacting with GROBID service
to extract metadata and fulltext from PDF documents.
"""

import logging
from typing import Any, Dict, Optional

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
        pdf_file: bytes,
        include_raw_citations: bool = True,
        include_raw_affiliations: bool = True,
        consolidate_header: int = 1,
        consolidate_citations: int = 0,
        tei_coordinates: Optional[list] = None,
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
        if not pdf_file:
            raise ValueError("PDF file content cannot be empty")

        # Prepare form data for GROBID request
        files = {"input": ("document.pdf", pdf_file, "application/pdf")}

        # Form parameters based on GROBID API documentation
        form_data = {
            "includeRawCitations": "1" if include_raw_citations else "0",
            "includeRawAffiliations": "1" if include_raw_affiliations else "0",
            "consolidateHeader": str(consolidate_header),
            "consolidateCitations": str(consolidate_citations),
        }

        # Add coordinates parameters if specified
        if tei_coordinates:
            for coord_type in tei_coordinates:
                form_data["teiCoordinates"] = coord_type

        url = f"{self.base_url}{self.endpoints['process_fulltext']}"

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

            result = {
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
                result["references"] = self._extract_references(text_element)

            # Store complete parsed structure for advanced usage
            result["parsed_data"] = tei_root

            return result

        except Exception as e:
            logger.error(f"TEI XML parsing error: {e}")
            return {"status": "parse_error", "error": str(e), "raw_xml": xml_content}

    def _extract_header_metadata(self, tei_header: Dict) -> Dict[str, Any]:
        """Extract metadata from TEI header."""
        metadata = {}
        try:
            file_desc_list = tei_header.get("fileDesc", [])
            file_desc = file_desc_list[0] if isinstance(file_desc_list, list) else file_desc_list
            if not file_desc:
                return {}

            # Extract title information
            title_stmt_list = file_desc.get("titleStmt", [])
            title_stmt = title_stmt_list[0] if isinstance(title_stmt_list, list) else title_stmt_list
            if title_stmt and "title" in title_stmt:
                title_info = title_stmt["title"]
                if isinstance(title_info, list):
                    title_info = title_info[0]
                metadata["title"] = title_info.get("#text") if isinstance(title_info, dict) else title_info

            # Extract publication information
            publication_stmt_list = file_desc.get("publicationStmt", [])
            publication_stmt = publication_stmt_list[0] if isinstance(publication_stmt_list, list) else publication_stmt_list
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
            source_desc = source_desc_list[0] if isinstance(source_desc_list, list) else source_desc_list
            if source_desc:
                bibl_struct = source_desc.get("biblStruct", {})
                if bibl_struct:
                    analytic = bibl_struct.get("analytic", {})
                    if analytic:
                        metadata["authors"] = self._extract_authors(analytic)

        except Exception as e:
            logger.error(f"Error extracting header metadata from TEI: {e}")
        return metadata

    def _extract_authors(self, analytic: Dict) -> list:
        """Extract authors from TEI analytic section."""
        authors = []
        author_list = analytic.get("author", [])
        if not isinstance(author_list, list):
            author_list = [author_list]

        for author_entry in author_list:
            if not isinstance(author_entry, dict):
                continue
            pers_name = author_entry.get("persName", {})
            if not pers_name:
                continue

            forenames = pers_name.get("forename", [])
            if not isinstance(forenames, list):
                forenames = [forenames]

            given_names = " ".join(
                [
                    name.get("#text") if isinstance(name, dict) else name
                    for name in forenames
                ],
            )

            surname = pers_name.get("surname", "")
            if isinstance(surname, dict):
                surname = surname.get("#text", "")

            full_name = f"{given_names} {surname}".strip()
            if full_name:
                authors.append({"name": full_name})
        return authors

    def _extract_fulltext(self, text_element: Dict) -> Dict[str, Any]:
        """Extract abstract and body from TEI text element."""
        fulltext = {}
        try:
            # Handle abstract
            front_element_list = text_element.get("front", [])
            front_element = front_element_list[0] if isinstance(front_element_list, list) else front_element_list
            if front_element:
                div_abstract = front_element.get("div", {})
                if isinstance(div_abstract, list):
                    div_abstract = next(
                        (item for item in div_abstract if item.get("@type") == "abstract"),
                        {},
                    )
                if div_abstract.get("@type") == "abstract":
                    abstract_p = div_abstract.get("p")
                    if isinstance(abstract_p, dict):
                        fulltext["abstract"] = abstract_p.get("#text")
                    elif isinstance(abstract_p, str):
                        fulltext["abstract"] = abstract_p

            # Handle body
            body_element = text_element.get("body", {})
            if body_element:
                sections = []
                divs = body_element.get("div", [])
                if not isinstance(divs, list):
                    divs = [divs]
                for div in divs:
                    if not isinstance(div, dict):
                        continue
                    section_title = div.get("head", {}).get("#text", "")
                    paragraphs = []
                    ps = div.get("p", [])
                    if not isinstance(ps, list):
                        ps = [ps]
                    for p in ps:
                        if isinstance(p, dict):
                            paragraphs.append(p.get("#text", ""))
                        elif isinstance(p, str):
                            paragraphs.append(p)
                    sections.append(
                        {"title": section_title, "text": "\n".join(paragraphs)},
                    )
                fulltext["body"] = sections

        except Exception as e:
            logger.error(f"Error extracting fulltext from TEI: {e}")
        return fulltext

    def _extract_references(self, text_element: Dict) -> list:
        """Extract references from TEI back element."""
        references = []
        try:
            back_element_list = text_element.get("back", [])
            back_element = back_element_list[0] if isinstance(back_element_list, list) else back_element_list
            if not back_element:
                return []

            div_element_list = back_element.get("div", [])
            div_element = div_element_list[0] if isinstance(div_element_list, list) else div_element_list
            if not div_element or div_element.get("@type") != "references":
                return []

            list_bibl = div_element.get("listBibl", {})
            bibl_structs = list_bibl.get("biblStruct", [])
            if not isinstance(bibl_structs, list):
                bibl_structs = [bibl_structs]

            for bibl in bibl_structs:
                if not isinstance(bibl, dict):
                    continue
                parsed_ref = self._parse_reference(bibl)
                if parsed_ref:
                    references.append(
                        {"raw_text": str(bibl), "parsed": parsed_ref, "source": "GROBID"},
                    )
        except Exception as e:
            logger.error(f"Error extracting references from TEI: {e}")
        return references

    def _parse_reference(self, bibl_struct: Dict) -> Optional[Dict]:
        """Parse a single biblStruct into a structured reference."""
        if not bibl_struct:
            return None

        ref = {"raw_text": bibl_struct.get("@id", "")}

        analytic = bibl_struct.get("analytic", {})
        if analytic:
            ref["title"] = analytic.get("title", {}).get("#text")
            ref["authors"] = self._extract_authors(analytic)

        monogr = bibl_struct.get("monogr", {})
        if monogr:
            ref["journal"] = monogr.get("title", {}).get("#text")
            imprint = monogr.get("imprint", {})
            if imprint:
                ref["year"] = imprint.get("date", {}).get("@when")
                ref["volume"] = imprint.get("biblScope", {"@unit": "volume"}).get(
                    "#text",
                )
                ref["issue"] = imprint.get("biblScope", {"@unit": "issue"}).get("#text")
                ref["pages"] = imprint.get("biblScope", {"@unit": "page"}).get("#text")

        return ref
