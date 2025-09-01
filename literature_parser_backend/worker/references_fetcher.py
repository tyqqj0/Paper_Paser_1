"""
References fetcher module implementing waterfall logic for literature references.

This module implements the intelligent waterfall approach for fetching references,
trying different data sources in priority order.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..models.literature import ReferenceModel
from ..services.grobid import GrobidClient
from ..services.semantic_scholar import SemanticScholarClient
from ..services.crossref import CrossRefClient
from ..settings import Settings

logger = logging.getLogger(__name__)


class ReferencesFetcher:
    """Fetches references from various sources."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize references fetcher with API clients."""
        self.settings = settings or Settings()
        self.semantic_scholar_client = SemanticScholarClient(settings)
        self.crossref_client = CrossRefClient(settings)
        self.grobid_client = GrobidClient(settings)

    def fetch_references_waterfall(
        self,
        identifiers: Dict[str, Optional[str]],
        pdf_content: Optional[bytes] = None,
    ) -> Tuple[List[ReferenceModel], Dict[str, Any]]:
        """
        Fetch references using waterfall: Semantic Scholar -> CrossRef -> GROBID fallback.
        
        🆕 支持可选DOI策略：即使没有DOI/ArXiv ID也会尝试其他方法获取引用
        """
        logger.info(f"Starting references fetch for identifiers: {identifiers}")

        references: List[ReferenceModel] = []
        raw_data: Dict[str, Any] = {}

        # 🆕 可选DOI策略：检查是否有理想标识符
        identifier = identifiers.get("doi") or identifiers.get("arxiv_id")
        has_ideal_identifiers = bool(identifier)
        
        logger.info(f"📋 标识符分析: DOI={identifiers.get('doi')}, ArXiv={identifiers.get('arxiv_id')}, 有理想标识符={has_ideal_identifiers}")

        # 1. Try Semantic Scholar API (仅当有理想标识符时)
        if has_ideal_identifiers:
            logger.info(
                "Attempting to fetch references from Semantic Scholar for "
                f"identifier: {identifier}",
            )
            try:
                s2_refs = self.semantic_scholar_client.get_references(identifier)
                if s2_refs:
                    raw_data["semantic_scholar"] = s2_refs
                    for ref_data in s2_refs:
                        # Ensure 'title' is not None before creating the model
                        if ref_data.get("title"):
                            references.append(
                                ReferenceModel(
                                    raw_text=ref_data.get(
                                        "raw_text",
                                        ref_data.get("title"),
                                    ),
                                    parsed=ref_data,
                                    source="semantic_scholar",
                                ),
                            )
                    logger.info(
                        f"✅ Successfully fetched {len(references)} references.",
                    )
                    # If we get results from S2, we are done.
                    if references:
                        return references, raw_data
            except Exception as e:
                logger.warning(
                    "Semantic Scholar API for references failed: %s. "
                    "Will try GROBID fallback.",
                    e,
                )

                # Try extracting ArXiv ID from DOI if DOI lookup failed due to exception
                if not references and identifiers.get("doi"):
                    extracted_arxiv_id = self._extract_arxiv_id_from_doi(
                        identifiers.get("doi"),
                    )
                    if extracted_arxiv_id:
                        logger.info(
                            f"Extracted ArXiv ID {extracted_arxiv_id} from DOI for references, retrying...",
                        )
                        try:
                            s2_refs = self.semantic_scholar_client.get_references(
                                extracted_arxiv_id,
                            )
                            if s2_refs:
                                raw_data["semantic_scholar"] = s2_refs
                                for ref_data in s2_refs:
                                    # Ensure 'title' is not None before creating the model
                                    if ref_data.get("title"):
                                        references.append(
                                            ReferenceModel(
                                                raw_text=ref_data.get(
                                                    "raw_text",
                                                    ref_data.get("title"),
                                                ),
                                                parsed=ref_data,
                                                source="semantic_scholar",
                                            ),
                                        )
                                logger.info(
                                    f"✅ Successfully fetched {len(references)} references using extracted ArXiv ID.",
                                )
                                if references:
                                    return references, raw_data
                        except Exception as e2:
                            logger.warning(
                                f"ArXiv ID retry for references also failed: {e2}",
                            )

        # 2. Fallback to CrossRef if we have DOI
        if not references and identifiers.get("doi"):
            logger.info("Falling back to CrossRef for reference extraction.")
            try:
                crossref_refs = self.crossref_client.get_references(identifiers["doi"])
                if crossref_refs:
                    raw_data["crossref"] = crossref_refs
                    for ref_data in crossref_refs:
                        # 确保标题存在才创建ReferenceModel
                        if ref_data.get("title"):
                            # 生成原始文本
                            raw_text = self._generate_raw_text_from_crossref(ref_data)
                            references.append(
                                ReferenceModel(
                                    raw_text=raw_text,
                                    parsed=ref_data,
                                    source="crossref",
                                ),
                            )
                    logger.info(
                        f"✅ Successfully fetched {len(references)} references from CrossRef.",
                    )
                    if references:
                        return references, raw_data
            except Exception as e:
                logger.warning(
                    f"CrossRef API for references failed: {e}. Will try GROBID fallback.",
                )

        # 3. Fallback to GROBID if we have PDF content
        if not references and pdf_content:
            logger.info("Falling back to GROBID for reference extraction from PDF.")
            try:
                # Use the 'processReferences' service for better performance
                grobid_data = self.grobid_client.process_pdf(
                    pdf_content,
                    service="processReferences",
                )
                if grobid_data and isinstance(grobid_data, list):
                    raw_data["grobid"] = grobid_data
                    # Placeholder for a proper TEI XML to ReferenceModel conversion
                    for ref_text in grobid_data:
                        references.append(
                            ReferenceModel(raw_text=ref_text, source="grobid_fallback"),
                        )
                    logger.info(
                        f"✅ Successfully parsed {len(references)} reference strings from PDF.",
                    )
                else:
                    logger.warning(
                        f"GROBID did not return a list of references. Output: {grobid_data}",
                    )
            except Exception as e:
                logger.error(f"GROBID reference parsing failed: {e}", exc_info=True)

        # 🆕 可选DOI策略：如果没有理想标识符，记录并优雅返回
        if not has_ideal_identifiers:
            logger.info(f"📋 可选DOI策略: 没有理想标识符(DOI/ArXiv)，但引用获取流程正常完成")
            raw_data["strategy"] = "optional_doi_strategy"
            raw_data["no_ideal_identifiers"] = True
            raw_data["attempted_methods"] = ["grobid_fallback"] if pdf_content else ["none_available"]
            
        # 🎯 添加统计信息
        raw_data["source"] = "references_fetcher"
        raw_data["references_count"] = len(references)
        raw_data["has_ideal_identifiers"] = has_ideal_identifiers
        
        if references:
            logger.info(f"✅ 引用获取成功: {len(references)} 个引用")
        else:
            logger.info(f"📋 引用获取完成: 0 个引用（可选DOI策略 - 非错误状态）")

        return references, raw_data

    def _extract_arxiv_id_from_doi(self, doi: str) -> Optional[str]:
        """Extract ArXiv ID from DOI patterns like 10.48550/arXiv.1706.03762."""
        import re

        # Pattern 1: 10.48550/arXiv.XXXX.XXXXX
        pattern1 = r"10\.48550/arXiv\.(\d{4}\.\d{4,5})"
        match1 = re.search(pattern1, doi)
        if match1:
            return match1.group(1)

        # Pattern 2: 10.48550/arXiv.XXXX.XXXXX vN (with version)
        pattern2 = r"10\.48550/arXiv\.(\d{4}\.\d{4,5})v\d+"
        match2 = re.search(pattern2, doi)
        if match2:
            return match2.group(1)

        # Pattern 3: Direct arXiv in DOI like arxiv.org/abs/XXXX.XXXXX
        pattern3 = r"arxiv\.org/abs/(\d{4}\.\d{4,5})"
        match3 = re.search(pattern3, doi)
        if match3:
            return match3.group(1)

        return None

    def _generate_raw_text_from_crossref(self, ref_data: Dict[str, Any]) -> str:
        """
        从CrossRef参考文献数据生成原始文本格式

        Args:
            ref_data: CrossRef参考文献数据

        Returns:
            str: 格式化的原始参考文献文本
        """
        parts = []

        # 作者
        if ref_data.get("authors"):
            author_names = [author["full_name"] for author in ref_data["authors"]]
            if len(author_names) > 3:
                # 如果作者太多，只显示前3个加"et al."
                authors_str = ", ".join(author_names[:3]) + ", et al."
            else:
                authors_str = ", ".join(author_names)
            parts.append(authors_str)

        # 标题
        if ref_data.get("title"):
            parts.append(f'"{ref_data["title"]}"')

        # 期刊/会议
        if ref_data.get("venue"):
            parts.append(ref_data["venue"])

        # 年份
        if ref_data.get("year"):
            parts.append(f"({ref_data['year']})")

        # 页码
        if ref_data.get("pages"):
            parts.append(f"pp. {ref_data['pages']}")

        # DOI
        if ref_data.get("doi"):
            parts.append(f"DOI: {ref_data['doi']}")

        return ". ".join(parts) + "."
