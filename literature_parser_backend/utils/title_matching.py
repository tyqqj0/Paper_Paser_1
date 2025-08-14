#!/usr/bin/env python3
"""
统一的标题匹配工具类 - Paper Parser 0.2

提供分级匹配策略：
- 精确模式（CrossRef）：严格匹配，避免错误关联
- 标准模式（一般情况）：平衡精度和召回率
- 模糊模式（Semantic Scholar）：宽松匹配，提高召回率
- 统一的标准化和接口
"""

import re
import hashlib
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MatchingMode(Enum):
    """标题匹配模式枚举"""
    STRICT = "strict"      # 精确模式 - CrossRef等权威数据库
    STANDARD = "standard"  # 标准模式 - 一般场景
    FUZZY = "fuzzy"       # 模糊模式 - Semantic Scholar等


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
    def calculate_similarity_by_mode(title1: str, title2: str, mode: MatchingMode = MatchingMode.STANDARD) -> float:
        """
        根据匹配模式计算相似度。
        
        Args:
            title1: 第一个标题
            title2: 第二个标题
            mode: 匹配模式
            
        Returns:
            相似度分数 (0.0 - 1.0)
        """
        if mode == MatchingMode.STRICT:
            # 精确模式：严格匹配优先，然后是极高相似度
            if TitleMatchingUtils.is_exact_match(title1, title2):
                return 1.0
            else:
                # 对于精确模式，只有序列相似度>0.95的才认为可能匹配
                sequence_sim = TitleMatchingUtils.calculate_sequence_similarity(title1, title2)
                return sequence_sim if sequence_sim > 0.95 else 0.0
                
        elif mode == MatchingMode.FUZZY:
            # 模糊模式：使用组合相似度，但权重向Jaccard倾斜
            sequence_sim = TitleMatchingUtils.calculate_sequence_similarity(title1, title2)
            jaccard_sim = TitleMatchingUtils.calculate_jaccard_similarity(title1, title2)
            
            # 权重组合：序列相似度40% + Jaccard相似度60%（模糊模式更重视词汇重叠）
            return (0.4 * sequence_sim) + (0.6 * jaccard_sim)
            
        else:  # STANDARD
            # 标准模式：平衡的组合相似度
            return TitleMatchingUtils.calculate_combined_similarity(title1, title2)
    
    @staticmethod
    def is_acceptable_match(title1: str, title2: str, mode: MatchingMode = MatchingMode.STANDARD, 
                           custom_threshold: Optional[float] = None) -> bool:
        """
        判断两个标题是否为可接受的匹配。
        
        Args:
            title1: 第一个标题
            title2: 第二个标题
            mode: 匹配模式
            custom_threshold: 自定义阈值，如果不提供则使用模式默认值
            
        Returns:
            True if 匹配可接受
        """
        similarity = TitleMatchingUtils.calculate_similarity_by_mode(title1, title2, mode)
        
        # 根据模式设定不同的默认阈值
        if custom_threshold is not None:
            threshold = custom_threshold
        elif mode == MatchingMode.STRICT:
            threshold = 0.98  # 精确模式：只接受极高相似度
        elif mode == MatchingMode.FUZZY:
            threshold = 0.6   # 模糊模式：较低阈值
        else:  # STANDARD
            threshold = 0.8   # 标准模式：中等阈值
        
        return similarity >= threshold
    
    @staticmethod
    def filter_crossref_candidates(
        target_title: str, 
        candidates: List[Dict[str, Any]],
        mode: MatchingMode = MatchingMode.STRICT,
        custom_threshold: Optional[float] = None
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        过滤CrossRef候选结果，使用分级匹配策略。
        
        Args:
            target_title: 目标标题
            candidates: CrossRef返回的候选列表
            mode: 匹配模式，默认STRICT（精确模式）
            custom_threshold: 自定义阈值，如果不提供则使用模式默认值
            
        Returns:
            (候选项, 相似度分数) 的列表，按相似度降序排列
        """
        if not candidates or not target_title:
            return []
            
        target_normalized = TitleMatchingUtils.normalize_title(target_title)
        if not target_normalized:
            return []
            
        # 根据模式确定阈值
        if custom_threshold is not None:
            threshold = custom_threshold
        elif mode == MatchingMode.STRICT:
            threshold = 0.98  # 精确模式：极高阈值
        elif mode == MatchingMode.FUZZY:
            threshold = 0.6   # 模糊模式：低阈值
        else:  # STANDARD
            threshold = 0.8   # 标准模式：中等阈值
            
        logger.info(f"🎯 过滤CrossRef结果: 目标标题='{target_title}'")
        logger.info(f"🎯 标准化后: '{target_normalized}'")
        logger.info(f"🎯 匹配模式: {mode.value}, 阈值: {threshold}")
        
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
                
            # 使用新的匹配模式计算相似度
            similarity = TitleMatchingUtils.calculate_similarity_by_mode(target_title, candidate_title, mode)
            
            # 特殊处理严格匹配
            if TitleMatchingUtils.is_exact_match(target_title, candidate_title):
                similarity = 1.0
                logger.info(f"🎯 候选{i+1}: 严格匹配 '{candidate_title}' (1.00)")
            else:
                logger.debug(f"候选{i+1}: '{candidate_title}' 相似度={similarity:.3f} (模式: {mode.value})")
            
            # 应用阈值过滤
            if similarity >= threshold:
                filtered_results.append((candidate, similarity))
                logger.info(f"✅ 通过过滤: '{candidate_title}' (相似度={similarity:.3f})")
            else:
                logger.debug(f"❌ 未通过过滤: '{candidate_title}' (相似度={similarity:.3f} < {threshold})")
        
        # 按相似度降序排列
        filtered_results.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"🎯 过滤结果: {len(filtered_results)}/{len(candidates)} 候选通过阈值 {threshold} (模式: {mode.value})")
        
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
        "Is ImageNet Classification All You Need?",  # 相似但错误的标题
        "A Different Paper Title Entirely"
    ]
    
    base_title = test_titles[0]
    
    print(f"基准标题: {base_title}")
    print(f"标准化后: {TitleMatchingUtils.normalize_title(base_title)}")
    print(f"LID: {TitleMatchingUtils.generate_title_based_lid(base_title)}")
    print()
    
    print("分级匹配模式测试:")
    print("-" * 60)
    
    for title in test_titles[1:]:
        print(f"对比标题: {title}")
        
        # 测试不同模式
        for mode in [MatchingMode.STRICT, MatchingMode.STANDARD, MatchingMode.FUZZY]:
            similarity = TitleMatchingUtils.calculate_similarity_by_mode(base_title, title, mode)
            is_acceptable = TitleMatchingUtils.is_acceptable_match(base_title, title, mode)
            
            print(f"  {mode.value:8}: 相似度={similarity:.3f}, 可接受={is_acceptable}")
        
        print()


