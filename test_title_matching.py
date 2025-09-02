#!/usr/bin/env python3
"""
测试标题匹配逻辑，检查为什么两个相同的论文没有被检测为重复
"""

import re
from difflib import SequenceMatcher
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def normalize_title(title: str) -> str:
    """标题规范化函数（复制自data_pipeline.py）"""
    # 去除常见的标点符号和特殊字符
    normalized = re.sub(r'[^\w\s]', ' ', title.lower())
    # 去除多余空格
    normalized = ' '.join(normalized.split())
    return normalized

def is_title_match(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """标题匹配检查（复制自data_pipeline.py）"""
    if not title1 or not title2:
        return False
    
    norm_title1 = normalize_title(title1)
    norm_title2 = normalize_title(title2)
    
    print(f"原标题1: {title1}")
    print(f"规范化1: {norm_title1}")
    print(f"原标题2: {title2}")
    print(f"规范化2: {norm_title2}")
    
    # 1. 完全匹配（预处理后）
    if norm_title1 == norm_title2:
        print(f"✅ 完全匹配!")
        return True
    
    # 2. 高相似度匹配
    similarity = SequenceMatcher(None, norm_title1, norm_title2).ratio()
    print(f"相似度: {similarity:.4f} (阈值: {threshold})")
    
    if similarity >= threshold:
        print(f"✅ 高相似度匹配 ({similarity:.3f})")
        return True
    
    print(f"❌ 不匹配 (相似度 {similarity:.3f} < {threshold})")
    return False

def normalize_author_name(name: str) -> str:
    """作者姓名规范化"""
    if not name:
        return ""
    
    # 去除多余空格和标点
    name = re.sub(r'[^\w\s]', ' ', name)
    name = ' '.join(name.split()).lower()
    
    # 处理 "姓, 名" 格式，转换为统一的 "名 姓" 格式
    if ',' in name:
        parts = [part.strip() for part in name.split(',')]
        if len(parts) == 2:
            # 转换为 "名 姓" 格式
            return f"{parts[1]} {parts[0]}"
    
    return name

def get_author_name_variants(name: str) -> set:
    """生成作者姓名的所有可能变体"""
    if not name:
        return set()
    
    normalized = normalize_author_name(name)
    variants = {normalized}
    
    # 如果包含空格，尝试交换姓名顺序
    parts = normalized.split()
    if len(parts) == 2:
        # 添加反向顺序
        variants.add(f"{parts[1]} {parts[0]}")
    
    return variants

def is_author_match(authors1, authors2, threshold: float = 0.5) -> bool:
    """作者匹配检查"""
    if not authors1 or not authors2:
        return False
    
    # 提取作者姓名列表
    names1 = []
    names2 = []
    
    if isinstance(authors1, list):
        names1 = [author.get('name', '') if isinstance(author, dict) else str(author) for author in authors1]
    
    if isinstance(authors2, list):
        names2 = [author.get('name', '') if isinstance(author, dict) else str(author) for author in authors2]
    
    print(f"原始作者1: {names1}")
    print(f"原始作者2: {names2}")
    
    # 生成所有作者姓名变体
    variants1 = [get_author_name_variants(name) for name in names1]
    variants2 = [get_author_name_variants(name) for name in names2]
    
    print(f"变体1: {variants1}")
    print(f"变体2: {variants2}")
    
    # 计算匹配作者数量
    matched_count = 0
    total_authors = max(len(variants1), len(variants2))
    
    for i, var_set1 in enumerate(variants1):
        best_match = None
        best_similarity = 0
        
        for j, var_set2 in enumerate(variants2):
            # 检查是否有任何变体匹配
            for var1 in var_set1:
                for var2 in var_set2:
                    if var1 and var2:
                        # 完全匹配
                        if var1 == var2:
                            matched_count += 1
                            print(f"  ✅ 完全匹配: {names1[i]} ≈ {names2[j]} ({var1} = {var2})")
                            best_match = (names1[i], names2[j], 1.0)
                            break
                        
                        # 高相似度匹配
                        similarity = SequenceMatcher(None, var1, var2).ratio()
                        if similarity >= 0.8 and similarity > best_similarity:
                            best_similarity = similarity
                            best_match = (names1[i], names2[j], similarity)
                
                if best_match and best_match[2] == 1.0:  # 如果找到完全匹配，停止搜索
                    break
            
            if best_match and best_match[2] == 1.0:
                break
        
        # 如果找到高相似度匹配但不是完全匹配
        if best_match and best_match[2] < 1.0 and best_match[2] >= 0.8:
            matched_count += 1
            print(f"  ✅ 高相似度匹配: {best_match[0]} ≈ {best_match[1]} (相似度: {best_match[2]:.3f})")
    
    match_ratio = matched_count / total_authors if total_authors > 0 else 0
    print(f"作者匹配率: {matched_count}/{total_authors} = {match_ratio:.3f} (阈值: {threshold})")
    
    return match_ratio >= threshold

def main():
    print("=" * 60)
    print("测试标题匹配逻辑")
    print("=" * 60)
    
    # 从数据库查询结果中提取的实际数据
    title1 = "Attention Is All You Need"  # 2017-vaswani-aayn-f14e
    title2 = "Attention is All you Need"  # 2017-ashish-aayn-93f6
    
    authors1 = [
        {"name": "Ashish Vaswani"},
        {"name": "Noam Shazeer"},
        {"name": "Niki Parmar"},
        {"name": "Jakob Uszkoreit"},
        {"name": "Llion Jones"}
    ]
    
    authors2 = [
        {"name": "Vaswani, Ashish"},
        {"name": "Shazeer, Noam"},
        {"name": "Parmar, Niki"},
        {"name": "Uszkoreit, Jakob"},
        {"name": "Jones, Llion"}
    ]
    
    print("\n📋 标题匹配测试:")
    print("-" * 40)
    title_match = is_title_match(title1, title2)
    
    print("\n👥 作者匹配测试:")
    print("-" * 40)
    author_match = is_author_match(authors1, authors2)
    
    print("\n🎯 最终结果:")
    print("-" * 40)
    print(f"标题匹配: {'✅' if title_match else '❌'}")
    print(f"作者匹配: {'✅' if author_match else '❌'}")
    
    if title_match and author_match:
        print("🔄 结论: 应该被检测为重复!")
    else:
        print("🆕 结论: 不会被检测为重复")
        if not title_match:
            print("   - 标题匹配失败")
        if not author_match:
            print("   - 作者匹配失败")

if __name__ == "__main__":
    main()
