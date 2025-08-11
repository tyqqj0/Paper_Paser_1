#!/usr/bin/env python3
"""
简单的LID生成功能测试

这是一个独立的测试脚本，用于验证LID生成逻辑的基本功能。
"""

import hashlib
import re
import secrets


class SimpleLIDGenerator:
    """简化的LID生成器，用于测试"""
    
    STOP_WORDS = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", 
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "can", "shall"
    }
    
    def generate_lid(self, title: str, author_name: str, year: int) -> str:
        """生成LID"""
        try:
            year_part = str(year) if year else "unkn"
            author_part = self._extract_author_surname(author_name)
            title_part = self._extract_title_initials(title)
            hash_part = secrets.token_hex(2)
            
            return f"{year_part}-{author_part}-{title_part}-{hash_part}"
        except:
            # 备选方案
            content = f"{title}{author_name}{year}"
            hash_value = hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
            return f"lit-{hash_value}"
    
    def _extract_author_surname(self, name: str) -> str:
        """提取作者姓氏"""
        if not name:
            return "noauthor"
        
        name_parts = name.strip().split()
        if len(name_parts) == 0:
            return "noauthor"
        
        surname = name_parts[-1] if len(name_parts) > 1 else name_parts[0]
        surname = re.sub(r'[^a-zA-Z]', '', surname)
        surname = surname.lower()
        
        return surname[:8] if len(surname) > 8 else surname
    
    def _extract_title_initials(self, title: str) -> str:
        """提取标题首字母"""
        if not title:
            return "untitl"
        
        title = title.lower()
        words = re.findall(r'\b[a-zA-Z]+\b', title)
        
        meaningful_words = [
            word for word in words 
            if word not in self.STOP_WORDS and len(word) >= 3
        ]
        
        initials = ''.join(word[0] for word in meaningful_words[:6])
        
        if len(initials) < 3:
            all_words = [word for word in words if len(word) >= 2]
            initials = ''.join(word[0] for word in all_words[:6])
        
        if len(initials) < 3:
            initials = "title"
        
        return initials[:6].lower()
    
    def validate_lid_format(self, lid: str) -> bool:
        """验证LID格式"""
        primary_pattern = r'^(\d{4}|unkn)-[a-z]{1,8}-[a-z]{3,6}-[a-f0-9]{4}$'
        fallback_pattern = r'^lit-[a-f0-9]{12}$'
        
        return (re.match(primary_pattern, lid) is not None or 
                re.match(fallback_pattern, lid) is not None)


def run_tests():
    """运行测试用例"""
    generator = SimpleLIDGenerator()
    
    print("=== LID生成功能测试 ===\n")
    
    # 测试1: 完整数据
    print("测试1: 完整元数据")
    lid1 = generator.generate_lid("Attention Is All You Need", "Ashish Vaswani", 2017)
    print(f"  输入: 'Attention Is All You Need', 'Ashish Vaswani', 2017")
    print(f"  生成LID: {lid1}")
    print(f"  格式验证: {'通过' if generator.validate_lid_format(lid1) else '失败'}")
    
    # 测试2: 缺少年份
    print("\n测试2: 缺少年份")
    lid2 = generator.generate_lid("Machine Learning Paper", "John Smith", None)
    print(f"  输入: 'Machine Learning Paper', 'John Smith', None")
    print(f"  生成LID: {lid2}")
    print(f"  格式验证: {'通过' if generator.validate_lid_format(lid2) else '失败'}")
    
    # 测试3: 特殊字符
    print("\n测试3: 带特殊字符")
    lid3 = generator.generate_lid("The AI Revolution: How ML Changes Everything!", "María García-López", 2023)
    print(f"  输入: 'The AI Revolution: How ML Changes Everything!', 'María García-López', 2023")
    print(f"  生成LID: {lid3}")
    print(f"  格式验证: {'通过' if generator.validate_lid_format(lid3) else '失败'}")
    
    # 测试4: 短标题
    print("\n测试4: 短标题")
    lid4 = generator.generate_lid("AI", "Bob Wilson", 2024)
    print(f"  输入: 'AI', 'Bob Wilson', 2024")
    print(f"  生成LID: {lid4}")
    print(f"  格式验证: {'通过' if generator.validate_lid_format(lid4) else '失败'}")
    
    # 测试5: 空数据（备选方案）
    print("\n测试5: 空数据（备选方案）")
    lid5 = generator.generate_lid("", "", None)
    print(f"  输入: '', '', None")
    print(f"  生成LID: {lid5}")
    print(f"  格式验证: {'通过' if generator.validate_lid_format(lid5) else '失败'}")
    
    # 测试6: 唯一性测试
    print("\n测试6: 唯一性验证")
    lids = []
    for i in range(5):
        lid = generator.generate_lid("Same Title", "Same Author", 2024)
        lids.append(lid)
    
    unique_lids = len(set(lids))
    print(f"  生成5个相同元数据的LID")
    print(f"  唯一LID数量: {unique_lids}/5")
    print(f"  样本: {lids[0]}, {lids[1]}")
    
    # 测试7: 格式验证
    print("\n测试7: 格式验证")
    valid_cases = [
        "2017-vaswani-aiaynu-a8c4",
        "unkn-noauthor-title-ff00", 
        "lit-abcdef123456"
    ]
    invalid_cases = [
        "invalid-lid",
        "2017-vaswani",
        "2017_vaswani_title_hash"
    ]
    
    for case in valid_cases:
        result = generator.validate_lid_format(case)
        print(f"  '{case}': {'有效' if result else '无效'} (预期: 有效)")
    
    for case in invalid_cases:
        result = generator.validate_lid_format(case)
        print(f"  '{case}': {'有效' if result else '无效'} (预期: 无效)")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    run_tests()
