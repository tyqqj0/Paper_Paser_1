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
                f"{self.base_url}{self.endpoints['is_alive']}", timeout=self.timeout,
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
                f"{self.base_url}{self.endpoints['version']}", timeout=self.timeout,
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
                url, files=files, data=form_data, timeout=self.timeout,
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
                url, files=files, data=form_data, timeout=self.timeout,
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
            file_desc = tei_header.get("fileDesc", {})

            # Extract title information
            title_stmt = file_desc.get("titleStmt", {})
            if title_stmt and "title" in title_stmt:
                title = title_stmt["title"]
                metadata["title"] = (
                    title.get("#text", title) if isinstance(title, dict) else title
                )

            # Extract authors
            source_desc = file_desc.get("sourceDesc", {})
            if source_desc:
                bibl_struct = source_desc.get("biblStruct", {})
                if bibl_struct and "analytic" in bibl_struct:
                    metadata["authors"] = self._extract_authors(bibl_struct["analytic"])

            # Extract abstract
            profile_desc = tei_header.get("profileDesc", {})
            if profile_desc and "abstract" in profile_desc:
                abstract_text = profile_desc["abstract"].get("#text", "")
                metadata["abstract"] = abstract_text

            # Extract keywords
            if profile_desc and "textClass" in profile_desc:
                keywords = []
                terms = profile_desc["textClass"].get("keywords", {}).get("term", [])
                if isinstance(terms, list):
                    keywords.extend(terms)
                elif terms:
                    keywords.append(terms)
                metadata["keywords"] = keywords

        except Exception as e:
            logger.error(f"Error extracting header metadata from TEI: {e}")

        return metadata

    def _extract_authors(self, analytic: Dict) -> list:
        """Extract authors from TEI analytic section."""
        authors = []
        author_list = analytic.get("author", [])
        if not isinstance(author_list, list):
            author_list = [author_list]

        for author_node in author_list:
            pers_name = author_node.get("persName", {})
            if not pers_name:
                continue

            author = {
                "full_name": "",
                "given_name": pers_name.get("forename", {}).get("#text", ""),
                "surname": pers_name.get("surname", ""),
                "email": author_node.get("email", ""),
                "affiliations": [],
            }
            author["full_name"] = f"{author['given_name']} {author['surname']}".strip()

            # Extract affiliations
            aff_nodes = author_node.get("affiliation", [])
            if not isinstance(aff_nodes, list):
                aff_nodes = [aff_nodes]

            for aff_node in aff_nodes:
                org_names = aff_node.get("orgName", [])
                if not isinstance(org_names, list):
                    org_names = [org_names]
                author["affiliations"].extend(
                    [org.get("#text", "") for org in org_names if org.get("#text")],
                )
            authors.append(author)
        return authors

    def _extract_fulltext(self, text_element: Dict) -> Dict[str, Any]:
        """Extract fulltext from TEI body."""
        fulltext = {"body": "", "sections": []}
        try:
            body = text_element.get("body", {})
            if body:
                divs = body.get("div", [])
                if not isinstance(divs, list):
                    divs = [divs]

                for div in divs:
                    head = div.get("head", {})
                    title = head.get("#text", f"Section {head.get('@n', '')}")
                    paragraphs = [p for p in div.get("p", [])]
                    fulltext["sections"].append(
                        {"title": title, "paragraphs": paragraphs},
                    )
                    fulltext["body"] += "\n".join(paragraphs) + "\n"
        except Exception as e:
            logger.error(f"Error extracting fulltext from TEI: {e}")
        return fulltext

    def _extract_references(self, text_element: Dict) -> list:
        """Extract references from TEI back section."""
        references = []
        try:
            back = text_element.get("back", {})
            if back:
                div = back.get("div", {})
                if div and div.get("@type") == "references":
                    bibl_list = div.get("listBibl", {}).get("biblStruct", [])
                    if not isinstance(bibl_list, list):
                        bibl_list = [bibl_list]

                    for bibl in bibl_list:
                        ref = self._parse_reference(bibl)
                        if ref:
                            references.append(ref)
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
