"""
GROBID service client for PDF processing.

This module provides a client for interacting with GROBID service
to extract metadata and fulltext from PDF documents.
"""

import logging
from typing import Any, Dict, Optional

import httpx
import xmltodict

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

    async def health_check(self) -> bool:
        """
        Check if GROBID service is alive and responding.

        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}{self.endpoints['is_alive']}",
                )
                return (
                    response.status_code == 200
                    and response.text.strip().lower() == "true"
                )
        except Exception as e:
            logger.error(f"GROBID health check failed: {e}")
            return False

    async def get_version(self) -> Optional[str]:
        """
        Get GROBID service version.

        Returns:
            str: Version string if successful, None otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}{self.endpoints['version']}",
                )
                if response.status_code == 200:
                    return response.text.strip()
                return None
        except Exception as e:
            logger.error(f"Failed to get GROBID version: {e}")
            return None

    async def process_pdf(
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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, files=files, data=form_data)

                if response.status_code == 200:
                    # GROBID returns TEI XML format
                    xml_content = response.text
                    return await self._parse_tei_xml(xml_content)
                elif response.status_code == 204:
                    logger.warning(
                        "GROBID processing completed but no content extracted",
                    )
                    return {"status": "no_content", "message": "No content extracted"}
                elif response.status_code == 503:
                    logger.warning("GROBID service temporarily unavailable (503)")
                    raise Exception(
                        "GROBID service temporarily unavailable. Please retry later.",
                    )
                else:
                    error_msg = f"GROBID processing failed with status {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

        except httpx.TimeoutException:
            logger.error("GROBID request timed out")
            raise Exception("GROBID processing timed out")
        except Exception as e:
            logger.error(f"GROBID processing error: {e}")
            raise Exception(f"GROBID processing failed: {e!s}")

    async def process_header_only(self, pdf_file: bytes) -> Dict[str, Any]:
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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, files=files, data=form_data)

                if response.status_code == 200:
                    xml_content = response.text
                    return await self._parse_tei_xml(xml_content)
                else:
                    raise Exception(f"Header processing failed: {response.status_code}")

        except Exception as e:
            logger.error(f"GROBID header processing error: {e}")
            raise Exception(f"Header processing failed: {e!s}")

    async def _parse_tei_xml(self, xml_content: str) -> Dict[str, Any]:
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
                result["metadata"] = await self._extract_header_metadata(tei_header)

            # Extract body text
            text_element = tei_root.get("text", {})
            if text_element:
                result["fulltext"] = await self._extract_fulltext(text_element)
                result["references"] = await self._extract_references(text_element)

            # Store complete parsed structure for advanced usage
            result["parsed_data"] = tei_root

            return result

        except Exception as e:
            logger.error(f"TEI XML parsing error: {e}")
            return {"status": "parse_error", "error": str(e), "raw_xml": xml_content}

    async def _extract_header_metadata(self, tei_header: Dict) -> Dict[str, Any]:
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

            # Extract author information
            source_desc = file_desc.get("sourceDesc", {})
            if source_desc:
                # Extract authors and affiliations
                metadata["authors"] = await self._extract_authors(source_desc)

            # Extract publication info
            publication_stmt = file_desc.get("publicationStmt", {})
            if publication_stmt:
                metadata["publication_info"] = publication_stmt

        except Exception as e:
            logger.warning(f"Error extracting header metadata: {e}")

        return metadata

    async def _extract_authors(self, source_desc: Dict) -> list:
        """Extract author information from source description."""
        authors = []

        try:
            # GROBID places author info in different possible locations
            bibl = source_desc.get("biblStruct", {}).get("analytic", {})
            if "author" in bibl:
                author_data = bibl["author"]
                if not isinstance(author_data, list):
                    author_data = [author_data]

                for author in author_data:
                    author_info = {}
                    pers_name = author.get("persName", {})

                    if "forename" in pers_name:
                        forenames = pers_name["forename"]
                        if not isinstance(forenames, list):
                            forenames = [forenames]
                        author_info["given_names"] = [
                            f.get("#text", f) if isinstance(f, dict) else f
                            for f in forenames
                        ]

                    if "surname" in pers_name:
                        surname = pers_name["surname"]
                        author_info["family_name"] = (
                            surname.get("#text", surname)
                            if isinstance(surname, dict)
                            else surname
                        )

                    # Extract affiliations if present
                    if "affiliation" in author:
                        author_info["affiliations"] = author["affiliation"]

                    authors.append(author_info)

        except Exception as e:
            logger.warning(f"Error extracting authors: {e}")

        return authors

    async def _extract_fulltext(self, text_element: Dict) -> Dict[str, Any]:
        """Extract fulltext content from TEI text element."""
        fulltext = {}

        try:
            body = text_element.get("body", {})
            if body:
                fulltext["body"] = body

            # Extract structured sections if available
            if "div" in body:
                fulltext["sections"] = body["div"]

        except Exception as e:
            logger.warning(f"Error extracting fulltext: {e}")

        return fulltext

    async def _extract_references(self, text_element: Dict) -> list:
        """Extract references from TEI text element."""
        references = []

        try:
            back = text_element.get("back", {})
            if back and "div" in back:
                div_elements = back["div"]
                if not isinstance(div_elements, list):
                    div_elements = [div_elements]

                for div in div_elements:
                    if div.get("@type") == "references":
                        list_bibl = div.get("listBibl", {})
                        if "biblStruct" in list_bibl:
                            bibl_structs = list_bibl["biblStruct"]
                            if not isinstance(bibl_structs, list):
                                bibl_structs = [bibl_structs]

                            for bibl in bibl_structs:
                                ref_data = await self._parse_reference(bibl)
                                if ref_data:
                                    references.append(ref_data)

        except Exception as e:
            logger.warning(f"Error extracting references: {e}")

        return references

    async def _parse_reference(self, bibl_struct: Dict) -> Optional[Dict]:
        """Parse a single bibliographic reference."""
        try:
            ref_data = {"type": "grobid_parsed"}

            # Extract analytic part (article info)
            analytic = bibl_struct.get("analytic", {})
            if analytic:
                if "title" in analytic:
                    title = analytic["title"]
                    ref_data["title"] = (
                        title.get("#text", title) if isinstance(title, dict) else title
                    )

                # Extract authors
                if "author" in analytic:
                    ref_data["authors"] = await self._extract_authors(
                        {"biblStruct": {"analytic": analytic}},
                    )

            # Extract monographic part (journal/book info)
            monogr = bibl_struct.get("monogr", {})
            if monogr:
                if "title" in monogr:
                    title = monogr["title"]
                    container_title = (
                        title.get("#text", title) if isinstance(title, dict) else title
                    )
                    ref_data["container_title"] = container_title

                # Extract publication details
                imprint = monogr.get("imprint", {})
                if imprint:
                    if "date" in imprint:
                        ref_data["publication_date"] = imprint["date"]
                    if "biblScope" in imprint:
                        ref_data["publication_info"] = imprint["biblScope"]

            return (
                ref_data
                if ref_data.get("title") or ref_data.get("container_title")
                else None
            )

        except Exception as e:
            logger.warning(f"Error parsing reference: {e}")
            return None
