#!/usr/bin/env python3
"""
统一的标题匹配工具类 - Paper Parser 0.2

整合现有的多个标题匹配实现，提供：
- 标准化的标题预处理
- 简单的严格匹配（用于CrossRef过滤）
- 复杂的相似度计算（用于智能匹配）
- 统一的匹配接口
"""

import re
import hashlib
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class TitleMatchingUtils:
    """统一的标题匹配工具类"""
    
    # 英文停用词
    STOPWORDS = {
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
        'above', 'below', 'between', 'among', 'under', 'over'
    }
    
    @staticmethod
    def normalize_title(title: str) -> str:
        """
        标准化标题用于匹配，移除所有可变因素。
        
        处理步骤：
        1. 转换为小写
        2. 移除标点符号和特殊字符
        3. 统一空格
        4. 移除前后空白
        
        Args:
            title: 原始标题
            
        Returns:
            标准化后的标题字符串
        """
        if not title or not isinstance(title, str):
            return ""
        
        # 1. 转小写
        normalized = title.lower()
        
        # 2. 移除标点符号和特殊字符，保留字母、数字、空格
        normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
        
        # 3. 合并多个空格为单个空格
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # 4. 移除前后空白
        normalized = normalized.strip()
        
        return normalized
    
    @staticmethod
    def is_exact_match(title1: str, title2: str) -> bool:
        """
        判断两个标题是否严格匹配（标准化后完全相同）。
        
        用于CrossRef结果的严格过滤。
        
        Args:
            title1: 第一个标题
            title2: 第二个标题
            
        Returns:
            True if 标题严格匹配
        """
        norm1 = TitleMatchingUtils.normalize_title(title1)
        norm2 = TitleMatchingUtils.normalize_title(title2)
        
        return norm1 == norm2 and len(norm1) > 0
    
    @staticmethod
    def get_title_words(title: str) -> Set[str]:
        """
        提取标题中的有意义词汇（移除停用词和短词）。
        
        Args:
            title: 标准化后的标题
            
        Returns:
            有意义词汇的集合
        """
        if not title:
            return set()
            
        words = [
            word for word in title.split()
            if len(word) >= 2 and word not in TitleMatchingUtils.STOPWORDS
        ]
        
        return set(words)
    
    @staticmethod
    def calculate_jaccard_similarity(title1: str, title2: str) -> float:
        """
        计算基于词汇的Jaccard相似度。
        
        Args:
            title1: 第一个标题
            title2: 第二个标题
            
        Returns:
            Jaccard相似度 (0.0 - 1.0)
        """
        norm1 = TitleMatchingUtils.normalize_title(title1)
        norm2 = TitleMatchingUtils.normalize_title(title2)
        
        words1 = TitleMatchingUtils.get_title_words(norm1)
        words2 = TitleMatchingUtils.get_title_words(norm2)
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
            
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def calculate_sequence_similarity(title1: str, title2: str) -> float:
        """
        计算基于字符序列的相似度。
        
        Args:
            title1: 第一个标题
            title2: 第二个标题
            
        Returns:
            序列相似度 (0.0 - 1.0)
        """
        norm1 = TitleMatchingUtils.normalize_title(title1)
        norm2 = TitleMatchingUtils.normalize_title(title2)
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    @staticmethod
    def calculate_combined_similarity(title1: str, title2: str) -> float:
        """
        计算组合相似度（序列相似度60% + Jaccard相似度40%）。
        
        这是复杂的相似度算法，用于智能匹配系统。
        
        Args:
            title1: 第一个标题
            title2: 第二个标题
            
        Returns:
            组合相似度 (0.0 - 1.0)
        """
        sequence_sim = TitleMatchingUtils.calculate_sequence_similarity(title1, title2)
        jaccard_sim = TitleMatchingUtils.calculate_jaccard_similarity(title1, title2)
        
        # 权重组合：序列相似度60% + Jaccard相似度40%
        combined_similarity = (0.6 * sequence_sim) + (0.4 * jaccard_sim)
        
        return min(combined_similarity, 1.0)
    
    @staticmethod
    def calculate_simple_similarity(title1: str, title2: str) -> float:
        """
        计算简单相似度（仅基于词汇重叠）。
        
        用于CrossRef等场景的快速过滤。
        
        Args:
            title1: 第一个标题
            title2: 第二个标题
            
        Returns:
            简单相似度 (0.0 - 1.0)
        """
        return TitleMatchingUtils.calculate_jaccard_similarity(title1, title2)
    
    @staticmethod
    def filter_crossref_candidates(
        target_title: str, 
        candidates: List[Dict[str, Any]],
        similarity_threshold: float = 0.8
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        过滤CrossRef候选结果，只保留高相似度的结果。
        
        简化的过滤逻辑，替代复杂的评分系统。
        
        Args:
            target_title: 目标标题
            candidates: CrossRef返回的候选列表
            similarity_threshold: 相似度阈值，默认0.8
            
        Returns:
            (候选项, 相似度分数) 的列表，按相似度降序排列
        """
        if not candidates or not target_title:
            return []
            
        target_normalized = TitleMatchingUtils.normalize_title(target_title)
        if not target_normalized:
            return []
            
        logger.info(f"🎯 过滤CrossRef结果: 目标标题='{target_title}'")
        logger.info(f"🎯 标准化后: '{target_normalized}'")
        
        filtered_results = []
        
        for i, candidate in enumerate(candidates):
            # 提取候选标题
            candidate_title = ""
            if candidate.get('title'):
                if isinstance(candidate['title'], list) and candidate['title']:
                    candidate_title = candidate['title'][0]
                elif isinstance(candidate['title'], str):
                    candidate_title = candidate['title']
            
            if not candidate_title:
                logger.debug(f"候选{i+1}: 无标题，跳过")
                continue
                
            candidate_normalized = TitleMatchingUtils.normalize_title(candidate_title)
            
            # 检查严格匹配
            if TitleMatchingUtils.is_exact_match(target_title, candidate_title):
                similarity = 1.0
                logger.info(f"🎯 候选{i+1}: 严格匹配 '{candidate_title}' (1.00)")
            else:
                # 计算相似度
                similarity = TitleMatchingUtils.calculate_simple_similarity(target_title, candidate_title)
                logger.debug(f"候选{i+1}: '{candidate_title}' 相似度={similarity:.3f}")
            
            # 应用阈值过滤
            if similarity >= similarity_threshold:
                filtered_results.append((candidate, similarity))
                logger.info(f"✅ 通过过滤: '{candidate_title}' (相似度={similarity:.3f})")
            else:
                logger.debug(f"❌ 未通过过滤: '{candidate_title}' (相似度={similarity:.3f} < {similarity_threshold})")
        
        # 按相似度降序排列
        filtered_results.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"🎯 过滤结果: {len(filtered_results)}/{len(candidates)} 候选通过阈值 {similarity_threshold}")
        
        return filtered_results
    
    @staticmethod
    def generate_title_based_lid(title: str, prefix: str = "unresolved") -> str:
        """
        基于标准化标题生成稳定的LID。
        
        Args:
            title: 文献标题
            prefix: LID前缀，默认 "unresolved"
            
        Returns:
            格式：{prefix}-{8位哈希}
        """
        normalized_title = TitleMatchingUtils.normalize_title(title)
        
        if not normalized_title:
            # 如果标题为空，使用时间戳作为fallback
            import time
            normalized_title = f"untitled_{int(time.time())}"
        
        # 生成MD5哈希的前8位
        hash_object = hashlib.md5(normalized_title.encode('utf-8'))
        short_hash = hash_object.hexdigest()[:8]
        
        return f"{prefix}-{short_hash}"


# 向后兼容的函数别名
def normalize_title_for_matching(title: str) -> str:
    """向后兼容的函数别名"""
    return TitleMatchingUtils.normalize_title(title)


def are_titles_equivalent(title1: str, title2: str) -> bool:
    """向后兼容的函数别名"""
    return TitleMatchingUtils.is_exact_match(title1, title2)


def get_title_matching_signature(title: str) -> Optional[str]:
    """向后兼容的函数别名"""
    normalized = TitleMatchingUtils.normalize_title(title)
    return normalized if normalized else None


def generate_title_based_lid(title: str, prefix: str = "unresolved") -> str:
    """向后兼容的函数别名"""
    return TitleMatchingUtils.generate_title_based_lid(title, prefix)


# 测试用例
if __name__ == "__main__":
    print("🧪 统一标题匹配工具测试:")
    print("=" * 60)
    
    test_titles = [
        "ImageNet Classification with Deep Convolutional Neural Networks",
        "ImageNet classification with deep convolutional neural networks!",
        "IMAGENET CLASSIFICATION WITH DEEP CONVOLUTIONAL NEURAL NETWORKS",
        "ImageNet Classification using Deep CNNs",
        "A Different Paper Title Entirely"
    ]
    
    base_title = test_titles[0]
    
    print(f"基准标题: {base_title}")
    print(f"标准化后: {TitleMatchingUtils.normalize_title(base_title)}")
    print(f"LID: {TitleMatchingUtils.generate_title_based_lid(base_title)}")
    print()
    
    print("相似度测试:")
    print("-" * 40)
    
    for title in test_titles[1:]:
        is_exact = TitleMatchingUtils.is_exact_match(base_title, title)
        jaccard = TitleMatchingUtils.calculate_jaccard_similarity(base_title, title)
        sequence = TitleMatchingUtils.calculate_sequence_similarity(base_title, title)
        combined = TitleMatchingUtils.calculate_combined_similarity(base_title, title)
        simple = TitleMatchingUtils.calculate_simple_similarity(base_title, title)
        
        print(f"对比标题: {title}")
        print(f"  严格匹配: {is_exact}")
        print(f"  Jaccard: {jaccard:.3f}")
        print(f"  序列相似度: {sequence:.3f}")
        print(f"  组合相似度: {combined:.3f}")
        print(f"  简单相似度: {simple:.3f}")
        print()


