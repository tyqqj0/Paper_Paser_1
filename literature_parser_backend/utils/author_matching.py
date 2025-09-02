#!/usr/bin/env python3
"""
智能作者匹配工具类

解决不同姓名格式的匹配问题：
- "Ashish Vaswani" vs "Vaswani, Ashish"
- 特殊字符处理: "Łukasz" vs "Lukasz"
- 中间名和缩写处理
"""

import re
from typing import List, Dict, Set, Tuple


class AuthorMatchingUtils:
    """智能作者匹配工具类"""
    
    @staticmethod
    def parse_author_name(name: str) -> Dict[str, str]:
        """
        解析作者姓名，返回标准化的姓和名
        
        Args:
            name: 原始姓名字符串
            
        Returns:
            包含 'first', 'last', 'original' 的字典
        """
        if not name:
            return {'first': '', 'last': '', 'original': name}
        
        # 移除多余的空格和无关标点
        clean_name = re.sub(r'[^\w\s,.-]', '', name.strip())
        
        # 检查是否包含逗号（lastname, firstname 格式）
        if ',' in clean_name:
            parts = [p.strip() for p in clean_name.split(',')]
            if len(parts) >= 2:
                last_name = parts[0].strip()
                first_name = ' '.join(parts[1:]).strip()
            else:
                last_name = parts[0].strip()
                first_name = ''
        else:
            # firstname lastname 格式
            parts = clean_name.split()
            if len(parts) >= 2:
                first_name = ' '.join(parts[:-1])
                last_name = parts[-1]
            elif len(parts) == 1:
                first_name = ''
                last_name = parts[0]
            else:
                first_name = ''
                last_name = ''
        
        return {
            'first': AuthorMatchingUtils._normalize_text(first_name),
            'last': AuthorMatchingUtils._normalize_text(last_name),
            'original': name
        }
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        标准化文本（小写，移除特殊字符）
        
        Args:
            text: 要标准化的文本
            
        Returns:
            标准化后的文本
        """
        if not text:
            return ""
        
        # 转换为小写
        normalized = text.lower()
        
        # 处理常见的特殊字符
        char_map = {
            'ł': 'l', 'ä': 'a', 'ü': 'u', 'ö': 'o', 'ñ': 'n',
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
            'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
            'ç': 'c', 'ş': 's', 'ğ': 'g', 'ı': 'i'
        }
        
        for char, replacement in char_map.items():
            normalized = normalized.replace(char, replacement)
        
        # 移除点号、连字符等
        normalized = re.sub(r'[.-]', '', normalized)
        
        return normalized.strip()
    
    @staticmethod
    def create_author_signature(parsed_name: Dict[str, str]) -> str:
        """
        创建作者的唯一签名用于匹配
        
        Args:
            parsed_name: 解析后的姓名信息
            
        Returns:
            作者签名字符串
        """
        first = parsed_name['first']
        last = parsed_name['last']
        
        # 组合姓和名的关键部分
        if first and last:
            # 使用姓 + 名的首字母
            first_initial = first[0] if first else ''
            return f"{last}_{first_initial}"
        elif last:
            return last
        else:
            return first if first else "unknown"
    
    @staticmethod
    def match_authors(authors1: List[Dict], authors2: List[Dict], threshold: float = 0.7) -> Tuple[bool, float]:
        """
        智能作者匹配算法
        
        Args:
            authors1: 第一个作者列表
            authors2: 第二个作者列表
            threshold: 匹配阈值
            
        Returns:
            (是否匹配, 相似度分数) 的元组
        """
        if not authors1 or not authors2:
            return False, 0.0
        
        # 解析所有作者姓名
        parsed1 = [AuthorMatchingUtils.parse_author_name(author.get('name', '')) for author in authors1]
        parsed2 = [AuthorMatchingUtils.parse_author_name(author.get('name', '')) for author in authors2]
        
        # 创建签名集合，过滤掉无效签名
        signatures1 = {AuthorMatchingUtils.create_author_signature(p) for p in parsed1 if p['last']}
        signatures2 = {AuthorMatchingUtils.create_author_signature(p) for p in parsed2 if p['last']}
        
        # 移除无效签名
        signatures1.discard("unknown")
        signatures2.discard("unknown")
        
        if not signatures1 or not signatures2:
            return False, 0.0
        
        # 计算交集和并集
        intersection = signatures1 & signatures2
        union = signatures1 | signatures2
        
        if len(union) == 0:
            return False, 0.0
        
        # 计算相似度
        similarity = len(intersection) / len(union)
        
        return similarity >= threshold, similarity
    
    @staticmethod
    def match_authors_detailed(authors1: List[Dict], authors2: List[Dict], threshold: float = 0.7) -> Dict:
        """
        详细的作者匹配，返回调试信息
        
        Args:
            authors1: 第一个作者列表
            authors2: 第二个作者列表
            threshold: 匹配阈值
            
        Returns:
            包含匹配结果和详细信息的字典
        """
        if not authors1 or not authors2:
            return {
                'is_match': False,
                'similarity': 0.0,
                'reason': 'Empty author lists',
                'details': {}
            }
        
        # 解析所有作者姓名
        parsed1 = [AuthorMatchingUtils.parse_author_name(author.get('name', '')) for author in authors1]
        parsed2 = [AuthorMatchingUtils.parse_author_name(author.get('name', '')) for author in authors2]
        
        # 创建签名集合
        signatures1 = {AuthorMatchingUtils.create_author_signature(p) for p in parsed1 if p['last']}
        signatures2 = {AuthorMatchingUtils.create_author_signature(p) for p in parsed2 if p['last']}
        
        # 移除无效签名
        signatures1.discard("unknown")
        signatures2.discard("unknown")
        
        if not signatures1 or not signatures2:
            return {
                'is_match': False,
                'similarity': 0.0,
                'reason': 'No valid author signatures',
                'details': {
                    'parsed1': parsed1,
                    'parsed2': parsed2,
                    'signatures1': list(signatures1),
                    'signatures2': list(signatures2)
                }
            }
        
        # 计算交集和并集
        intersection = signatures1 & signatures2
        union = signatures1 | signatures2
        similarity = len(intersection) / len(union) if union else 0.0
        
        is_match = similarity >= threshold
        
        return {
            'is_match': is_match,
            'similarity': similarity,
            'threshold': threshold,
            'reason': 'Sufficient overlap' if is_match else 'Insufficient overlap',
            'details': {
                'authors1_count': len(authors1),
                'authors2_count': len(authors2),
                'signatures1': list(signatures1),
                'signatures2': list(signatures2),
                'intersection': list(intersection),
                'union': list(union),
                'intersection_count': len(intersection),
                'union_count': len(union)
            }
        }


