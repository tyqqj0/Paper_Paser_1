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

# TODO: 现在的api层在为元数据解析提供原始数据，但是为引文解析提供解析后数据，比较混乱，包括其他的api层，需要统一
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
                # 🆕 直接返回原始CrossRef数据，不做转换
                return data.get("message", {})
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

            # 🆕 直接返回原始CrossRef数据列表，不做转换
            results = items

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
        🚫 DEPRECATED: Parse CrossRef work data into our standard format.
        
        📝 NOTE: 数据转换逻辑已迁移到 CrossRefProcessor._convert_crossref_to_metadata()
        此方法保留仅为兼容性，建议使用处理器层的统一转换。

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

    def get_references(self, doi: str) -> List[Dict[str, Any]]:
        """
        获取论文的参考文献列表

        Args:
            doi: 论文的DOI

        Returns:
            List[Dict]: 参考文献列表，每个元素包含解析后的参考文献信息
        """
        logger.info(f"获取CrossRef参考文献: {doi}")

        try:
            # 获取论文的完整元数据
            work_data = self._get_work_by_doi(doi)
            if not work_data:
                logger.warning(f"无法获取DOI {doi} 的元数据")
                return []

            # 提取参考文献
            references = work_data.get("reference", [])
            if not references:
                logger.info(f"DOI {doi} 没有参考文献数据")
                return []

            logger.info(f"找到 {len(references)} 个参考文献")

            # 处理每个参考文献
            processed_refs = []
            for i, ref in enumerate(references):
                try:
                    processed_ref = self._process_reference(ref, i + 1)
                    if processed_ref:
                        processed_refs.append(processed_ref)
                except Exception as e:
                    logger.warning(f"处理参考文献 {i+1} 失败: {e}")
                    continue

            logger.info(f"成功处理 {len(processed_refs)} 个参考文献")
            return processed_refs

        except Exception as e:
            logger.error(f"获取CrossRef参考文献失败: {e}")
            return []

    def _get_work_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        通过DOI获取完整的work数据

        Args:
            doi: DOI标识符

        Returns:
            Dict: CrossRef work数据，如果失败返回None
        """
        try:
            encoded_doi = quote(doi, safe="")
            url = f"{self.base_url}/works/{encoded_doi}"

            response = self.request_manager.get(
                url=url,
                request_type=RequestType.EXTERNAL,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("message")
            else:
                logger.warning(f"CrossRef API返回状态码 {response.status_code} for DOI: {doi}")
                return None

        except Exception as e:
            logger.error(f"获取CrossRef work数据失败: {e}")
            return None

    def _process_reference(self, ref: Dict[str, Any], ref_number: int) -> Optional[Dict[str, Any]]:
        """
        处理单个参考文献

        Args:
            ref: CrossRef原始参考文献数据
            ref_number: 参考文献编号

        Returns:
            Dict: 处理后的参考文献数据，如果质量不合格返回None
        """
        logger.debug(f"处理参考文献 {ref_number}: {ref}")

        # 情况1: 已有标题，直接使用
        if ref.get("article-title"):
            logger.debug(f"参考文献 {ref_number} 已有标题，直接使用")
            return self._create_reference_from_crossref(ref)

        # 情况2: 只有DOI，尝试补全
        if ref.get("DOI"):
            doi = ref["DOI"]
            logger.debug(f"参考文献 {ref_number} 只有DOI，尝试补全: {doi}")

            enhanced_data = self._enhance_reference_with_doi(doi)
            if enhanced_data and enhanced_data.get("title"):
                logger.debug(f"参考文献 {ref_number} DOI补全成功")
                # 合并原始数据和补全数据
                merged_ref = {**ref, **enhanced_data}
                return self._create_reference_from_crossref(merged_ref)
            else:
                logger.debug(f"参考文献 {ref_number} DOI补全失败，跳过")
                return None

        # 情况3: 数据不完整，跳过
        logger.debug(f"参考文献 {ref_number} 数据不完整，跳过")
        return None

    def _enhance_reference_with_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        通过DOI补全参考文献信息

        Args:
            doi: DOI标识符

        Returns:
            Dict: 补全后的参考文献信息，如果失败返回None
        """
        try:
            work_data = self._get_work_by_doi(doi)
            if not work_data:
                return None

            # 提取关键信息
            enhanced_data = {}

            # 标题 (必须)
            if work_data.get("title"):
                enhanced_data["title"] = work_data["title"][0]

            # 作者 (可选)
            if work_data.get("author"):
                authors = []
                for author in work_data["author"]:
                    given = author.get("given", "")
                    family = author.get("family", "")
                    if given or family:
                        authors.append(f"{given} {family}".strip())
                if authors:
                    enhanced_data["authors"] = authors

            # 年份 (可选)
            if work_data.get("published-print"):
                date_parts = work_data["published-print"].get("date-parts", [])
                if date_parts and date_parts[0]:
                    enhanced_data["year"] = date_parts[0][0]

            # 期刊/会议 (可选)
            if work_data.get("container-title"):
                enhanced_data["venue"] = work_data["container-title"][0]

            return enhanced_data

        except Exception as e:
            logger.warning(f"DOI补全失败 {doi}: {e}")
            return None

    def _create_reference_from_crossref(self, ref_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从CrossRef数据创建标准化的参考文献格式

        Args:
            ref_data: CrossRef参考文献数据 (可能是原始的或补全后的)

        Returns:
            Dict: 标准化的参考文献数据
        """
        # 构建标准化格式
        result = {}

        # 标题 (优先使用补全的title，其次使用article-title)
        title = ref_data.get("title") or ref_data.get("article-title")
        if title:
            result["title"] = title

        # 作者
        if ref_data.get("authors"):
            # 补全后的格式
            result["authors"] = [{"full_name": author} for author in ref_data["authors"]]
        elif ref_data.get("author"):
            # 原始CrossRef格式
            if isinstance(ref_data["author"], str):
                result["authors"] = [{"full_name": ref_data["author"]}]
            else:
                result["authors"] = [{"full_name": str(ref_data["author"])}]

        # 年份
        if ref_data.get("year"):
            result["year"] = ref_data["year"]

        # 期刊/会议
        venue = ref_data.get("venue") or ref_data.get("volume-title")
        if venue:
            result["venue"] = venue

        # DOI
        if ref_data.get("DOI"):
            result["doi"] = ref_data["DOI"]

        # 页码
        if ref_data.get("first-page"):
            result["pages"] = ref_data["first-page"]

        return result
