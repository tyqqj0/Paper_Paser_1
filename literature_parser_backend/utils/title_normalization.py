#!/usr/bin/env python3
"""
标题标准化工具模块 - Paper Parser 0.2

用于解决同一文献不同版本的匹配问题：
- 移除年份、作者等变动因素
- 基于标准化标题生成稳定的匹配标识符
- 支持版本合并策略
"""

import re
import hashlib
from typing import Optional


def normalize_title_for_matching(title: str) -> str:
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
        
    Example:
        >>> normalize_title_for_matching("ImageNet Classification with Deep CNNs!")
        "imagenet classification with deep cnns"
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


def generate_title_based_lid(title: str, prefix: str = "unresolved") -> str:
    """
    基于标准化标题生成稳定的LID。
    
    这个LID不依赖年份、作者等变动信息，确保同一文献的不同版本
    能够生成相同的匹配标识符。
    
    Args:
        title: 文献标题
        prefix: LID前缀，默认 "unresolved"
        
    Returns:
        格式：{prefix}-{8位哈希}
        
    Example:
        >>> generate_title_based_lid("ImageNet Classification with Deep CNNs")
        "unresolved-a1b2c3d4"
    """
    normalized_title = normalize_title_for_matching(title)
    
    if not normalized_title:
        # 如果标题为空，使用时间戳作为fallback
        import time
        normalized_title = f"untitled_{int(time.time())}"
    
    # 生成MD5哈希的前8位
    hash_object = hashlib.md5(normalized_title.encode('utf-8'))
    short_hash = hash_object.hexdigest()[:8]
    
    return f"{prefix}-{short_hash}"


def are_titles_equivalent(title1: str, title2: str) -> bool:
    """
    判断两个标题是否表示同一文献。
    
    Args:
        title1: 第一个标题
        title2: 第二个标题
        
    Returns:
        True if 标题相同（标准化后）
        
    Example:
        >>> are_titles_equivalent("ImageNet Classification!", "imagenet classification")
        True
    """
    norm1 = normalize_title_for_matching(title1)
    norm2 = normalize_title_for_matching(title2)
    
    return norm1 == norm2 and len(norm1) > 0


def get_title_matching_signature(title: str) -> Optional[str]:
    """
    获取标题的匹配签名，用于数据库查询。
    
    Args:
        title: 文献标题
        
    Returns:
        标准化后的标题字符串，如果标题无效则返回None
    """
    normalized = normalize_title_for_matching(title)
    return normalized if normalized else None


# 测试用例
if __name__ == "__main__":
    test_titles = [
        "ImageNet Classification with Deep Convolutional Neural Networks",
        "ImageNet classification with deep convolutional neural networks!",
        "IMAGENET CLASSIFICATION WITH DEEP CONVOLUTIONAL NEURAL NETWORKS",
        "ImageNet   Classification    with Deep CNNs"
    ]
    
    print("🧪 标题标准化测试:")
    for title in test_titles:
        normalized = normalize_title_for_matching(title)
        lid = generate_title_based_lid(title)
        print(f"原标题: {title}")
        print(f"标准化: {normalized}")
        print(f"LID: {lid}")
        print("-" * 50)
    
    print("🔍 标题等价性测试:")
    print(f"相同性检查: {are_titles_equivalent(test_titles[0], test_titles[1])}")  # 应该是True
