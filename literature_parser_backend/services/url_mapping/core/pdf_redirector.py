"""
PDF重定向器

智能检测已知平台的PDF链接，并重定向到对应的标准页面链接，
以提高处理效率和元数据获取质量。
"""

import re
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RedirectRule:
    """重定向规则"""
    name: str
    pattern: str
    template: str
    reason: str
    priority: int = 1


class PDFRedirector:
    """PDF重定向器 - 将已知平台的PDF链接重定向到标准页面链接"""
    
    def __init__(self):
        """初始化重定向器"""
        self.rules = []
        self._register_default_rules()
    
    def _register_default_rules(self):
        """注册默认重定向规则"""
        
        # arXiv PDF → abs链接
        self.rules.append(RedirectRule(
            name="arxiv_pdf_to_abs",
            pattern=r"arxiv\.org/pdf/([^/?]+)\.pdf",
            template="https://arxiv.org/abs/{0}",
            reason="arXiv PDF链接重定向到abs页面以获得更好的元数据",
            priority=1
        ))
        
        # IEEE PDF → 文章页面 (多种格式)
        self.rules.append(RedirectRule(
            name="ieee_pdf_to_article",
            pattern=r"ieeexplore\.ieee\.org/stamp/stamp\.jsp\?(?:.*&)?(?:tp=|arnumber=)(\d+)",
            template="https://ieeexplore.ieee.org/document/{0}",
            reason="IEEE PDF链接重定向到文章页面以获得更好的元数据",
            priority=1
        ))
        
        # ACM PDF → 文章页面
        self.rules.append(RedirectRule(
            name="acm_pdf_to_article", 
            pattern=r"dl\.acm\.org/doi/pdf/([^/?]+)",
            template="https://dl.acm.org/doi/{0}",
            reason="ACM PDF链接重定向到文章页面以获得更好的元数据",
            priority=1
        ))
        
        # Springer PDF → 文章页面
        self.rules.append(RedirectRule(
            name="springer_pdf_to_article",
            pattern=r"link\.springer\.com/content/pdf/([^/?]+)\.pdf",
            template="https://link.springer.com/article/{0}",
            reason="Springer PDF链接重定向到文章页面以获得更好的元数据",
            priority=1
        ))
        
        # Nature PDF → 文章页面
        self.rules.append(RedirectRule(
            name="nature_pdf_to_article",
            pattern=r"nature\.com/articles/([^/?]+)\.pdf",
            template="https://www.nature.com/articles/{0}",
            reason="Nature PDF链接重定向到文章页面以获得更好的元数据",
            priority=1
        ))
        
        logger.info(f"注册了 {len(self.rules)} 个PDF重定向规则")
    
    def check_redirect(self, url: str) -> Optional[Dict[str, Any]]:
        """
        检查URL是否需要重定向
        
        Args:
            url: 要检查的URL
            
        Returns:
            重定向信息字典，如果不需要重定向则返回None
        """
        logger.debug(f"检查PDF重定向: {url}")
        
        # 按优先级排序规则
        sorted_rules = sorted(self.rules, key=lambda r: r.priority)
        
        for rule in sorted_rules:
            match = re.search(rule.pattern, url, re.IGNORECASE)
            if match:
                # 提取匹配的组
                groups = match.groups()
                
                try:
                    # 生成重定向URL
                    canonical_url = rule.template.format(*groups)
                    
                    redirect_info = {
                        "canonical_url": canonical_url,
                        "original_url": url,
                        "redirect_reason": rule.reason,
                        "rule_name": rule.name,
                        "matched_groups": groups
                    }
                    
                    logger.info(f"PDF重定向匹配: {rule.name} - {url} → {canonical_url}")
                    return redirect_info
                    
                except (IndexError, ValueError) as e:
                    logger.warning(f"重定向规则 {rule.name} 处理失败: {e}")
                    continue
        
        logger.debug(f"无需重定向: {url}")
        return None
    
    def add_rule(self, rule: RedirectRule):
        """
        添加新的重定向规则
        
        Args:
            rule: 重定向规则
        """
        self.rules.append(rule)
        logger.info(f"添加重定向规则: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """
        移除重定向规则
        
        Args:
            rule_name: 规则名称
        """
        self.rules = [r for r in self.rules if r.name != rule_name]
        logger.info(f"移除重定向规则: {rule_name}")
    
    def get_rules(self) -> list:
        """获取所有重定向规则"""
        return self.rules.copy()
    
    def is_pdf_url(self, url: str) -> bool:
        """
        检查URL是否为PDF链接
        
        Args:
            url: 要检查的URL
            
        Returns:
            是否为PDF链接
        """
        # 简单的PDF URL检测
        pdf_indicators = [
            '.pdf',
            'pdf/',
            'stamp.jsp',  # IEEE
            '/pdf/',
            'filetype=pdf'
        ]
        
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in pdf_indicators)
    
    def get_supported_domains(self) -> list:
        """获取支持的域名列表"""
        domains = set()
        for rule in self.rules:
            # 从正则表达式中提取域名
            domain_match = re.search(r'([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', rule.pattern)
            if domain_match:
                domains.add(domain_match.group(1))
        
        return sorted(list(domains))


# 全局重定向器实例
_pdf_redirector = None


def get_pdf_redirector() -> PDFRedirector:
    """
    获取PDF重定向器的单例实例
    
    Returns:
        PDFRedirector实例
    """
    global _pdf_redirector
    if _pdf_redirector is None:
        _pdf_redirector = PDFRedirector()
        logger.info("创建PDF重定向器单例实例")
    return _pdf_redirector


def reset_pdf_redirector():
    """重置PDF重定向器单例（主要用于测试）"""
    global _pdf_redirector
    _pdf_redirector = None
    logger.info("重置PDF重定向器单例")
