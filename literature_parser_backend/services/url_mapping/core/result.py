"""
URL映射结果模型

定义URL映射操作的结果数据结构。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class URLMappingResult:
    """
    URL映射结果
    
    包含从URL中提取的各种标识符和元信息。
    """
    
    # 标识符
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    pmid: Optional[str] = None
    
    # 元信息
    venue: Optional[str] = None
    year: Optional[int] = None
    title: Optional[str] = None
    authors: Optional[list] = None  # 🆕 添加作者字段支持
    
    # URL信息
    source_page_url: Optional[str] = None
    pdf_url: Optional[str] = None

    # PDF重定向信息
    canonical_url: Optional[str] = None  # 建议的标准URL
    original_url: Optional[str] = None   # 原始URL
    redirect_reason: Optional[str] = None # 重定向原因

    # 处理信息
    source_adapter: Optional[str] = None
    strategy_used: Optional[str] = None
    confidence: float = 1.0
    
    # 额外标识符和元数据
    identifiers: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_identifiers(self) -> bool:
        """检查是否有有效的标识符"""
        return bool(self.doi or self.arxiv_id or self.pmid)
    
    def has_useful_info(self) -> bool:
        """检查是否有有用的信息"""
        return bool(
            self.venue or
            self.source_page_url or
            self.pdf_url or
            self.title or
            self.authors or  # 🆕 包含作者信息
            self.canonical_url
        )
    
    def is_successful(self) -> bool:
        """检查映射是否成功"""
        return self.has_identifiers() or self.has_useful_info()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "pmid": self.pmid,
            "venue": self.venue,
            "year": self.year,
            "title": self.title,
            "authors": self.authors,  # 🆕 包含作者信息
            "source_page_url": self.source_page_url,
            "pdf_url": self.pdf_url,
            "canonical_url": self.canonical_url,
            "original_url": self.original_url,
            "redirect_reason": self.redirect_reason,
            "source_adapter": self.source_adapter,
            "strategy_used": self.strategy_used,
            "confidence": self.confidence,
            "identifiers": self.identifiers,
            "metadata": self.metadata,
        }

    def should_use_canonical(self) -> bool:
        """检查是否应该使用标准URL"""
        return self.canonical_url is not None
