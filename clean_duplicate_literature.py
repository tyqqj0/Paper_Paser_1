#!/usr/bin/env python3
"""
清理数据库中重复的文献记录
使用修复后的去重逻辑来识别和合并重复文献
"""

import asyncio
import sys
import os
import json
from typing import List, Dict, Set, Tuple
from collections import defaultdict

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from literature_parser_backend.worker.execution.data_pipeline import DataPipeline
from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.db.neo4j import connect_to_mongodb, get_database

async def find_duplicate_groups() -> List[List[Dict]]:
    """找到所有重复文献组"""
    print("🔍 查找重复文献组...")
    
    dao = LiteratureDAO()
    pipeline = DataPipeline(dao)
    
    # 获取所有文献
    all_literature = await dao.find_all()
    print(f"📚 总共找到 {len(all_literature)} 篇文献")
    
    if len(all_literature) < 2:
        print("⚠️ 文献数量不足，无需去重")
        return []
    
    # 用于存储重复组
    duplicate_groups = []
    processed_lids = set()
    
    for i, lit1 in enumerate(all_literature):
        if lit1.lid in processed_lids:
            continue
            
        if not lit1.metadata or not lit1.metadata.title:
            print(f"⚠️ 跳过无效文献: {lit1.lid}")
            continue
        
        # 当前文献的重复组
        current_group = [lit1]
        processed_lids.add(lit1.lid)
        
        # 与后续文献比较
        for j, lit2 in enumerate(all_literature[i+1:], i+1):
            if lit2.lid in processed_lids:
                continue
                
            if not lit2.metadata or not lit2.metadata.title:
                continue
            
            # 检查是否为重复
            try:
                title_match = pipeline._is_title_match(lit1.metadata.title, lit2.metadata.title)
                author_match = pipeline._is_author_match(
                    getattr(lit1.metadata, 'authors', []), 
                    getattr(lit2.metadata, 'authors', [])
                )
                
                if title_match and author_match:
                    current_group.append(lit2)
                    processed_lids.add(lit2.lid)
                    print(f"🔗 发现重复: {lit1.lid} <-> {lit2.lid}")
                    print(f"   标题1: {lit1.metadata.title[:50]}...")
                    print(f"   标题2: {lit2.metadata.title[:50]}...")
                    
            except Exception as e:
                print(f"❌ 比较异常 {lit1.lid} vs {lit2.lid}: {e}")
                continue
        
        # 如果找到重复，添加到重复组
        if len(current_group) > 1:
            duplicate_groups.append(current_group)
            print(f"📋 重复组 {len(duplicate_groups)}: {len(current_group)} 篇文献")
        
        # 显示进度
        if (i + 1) % 10 == 0:
            print(f"📊 已处理: {i + 1}/{len(all_literature)} ({(i + 1)/len(all_literature)*100:.1f}%)")
    
    print(f"\n🎯 总结: 找到 {len(duplicate_groups)} 个重复组")
    return duplicate_groups

def choose_primary_literature(group: List) -> Tuple[dict, List]:
    """选择主要文献，其他作为重复"""
    if not group:
        return None, []
    
    if len(group) == 1:
        return group[0], []
    
    # 选择策略：
    # 1. 优先选择有DOI的文献
    # 2. 优先选择元数据更完整的文献
    # 3. 优先选择较早创建的文献（较短的LID通常表示较早）
    
    scored_literature = []
    
    for lit in group:
        score = 0
        
        # 有DOI加分
        if lit.identifiers and getattr(lit.identifiers, 'doi', None):
            score += 10
        
        # 有ArXiv ID加分
        if lit.identifiers and getattr(lit.identifiers, 'arxiv_id', None):
            score += 5
        
        # 元数据完整性加分
        if lit.metadata:
            if getattr(lit.metadata, 'abstract', None):
                score += 3
            if getattr(lit.metadata, 'authors', None):
                score += len(lit.metadata.authors)
            if getattr(lit.metadata, 'year', None):
                score += 2
            if getattr(lit.metadata, 'journal', None):
                score += 2
        
        # LID长度（较短的LID优先）
        score += max(0, 50 - len(lit.lid))
        
        scored_literature.append((lit, score))
    
    # 按分数排序，选择最高分的作为主要文献
    scored_literature.sort(key=lambda x: x[1], reverse=True)
    
    primary = scored_literature[0][0]
    duplicates = [item[0] for item in scored_literature[1:]]
    
    return primary, duplicates

def print_duplicate_summary(duplicate_groups: List[List[Dict]]):
    """打印重复文献摘要"""
    print("\n" + "=" * 80)
    print("重复文献详细摘要")
    print("=" * 80)
    
    total_duplicates = 0
    
    for i, group in enumerate(duplicate_groups, 1):
        print(f"\n📋 重复组 {i}: {len(group)} 篇文献")
        print("-" * 60)
        
        primary, duplicates = choose_primary_literature(group)
        total_duplicates += len(duplicates)
        
        print(f"🏆 主要文献: {primary.lid}")
        print(f"   标题: {primary.metadata.title if primary.metadata else 'N/A'}")
        if primary.identifiers:
            if getattr(primary.identifiers, 'doi', None):
                print(f"   DOI: {primary.identifiers.doi}")
            if getattr(primary.identifiers, 'arxiv_id', None):
                print(f"   ArXiv: {primary.identifiers.arxiv_id}")
        
        print(f"\n🔄 重复文献 ({len(duplicates)} 篇):")
        for dup in duplicates:
            print(f"   - {dup.lid}")
            print(f"     标题: {dup.metadata.title if dup.metadata else 'N/A'}")
            if dup.identifiers:
                if getattr(dup.identifiers, 'doi', None):
                    print(f"     DOI: {dup.identifiers.doi}")
                if getattr(dup.identifiers, 'arxiv_id', None):
                    print(f"     ArXiv: {dup.identifiers.arxiv_id}")
    
    print(f"\n📊 统计摘要:")
    print(f"   重复组数量: {len(duplicate_groups)}")
    print(f"   可删除的重复文献: {total_duplicates}")
    print(f"   节省的存储空间: {total_duplicates} 篇文献")

async def merge_duplicate_literature(duplicate_groups: List[List[Dict]], dry_run: bool = True):
    """合并重复文献（默认为试运行模式）"""
    if dry_run:
        print("\n🔍 试运行模式 - 不会实际删除数据")
    else:
        print("\n⚠️ 实际执行模式 - 将删除重复数据")
    
    dao = LiteratureDAO()
    
    deleted_count = 0
    
    for i, group in enumerate(duplicate_groups, 1):
        print(f"\n处理重复组 {i}/{len(duplicate_groups)}")
        
        primary, duplicates = choose_primary_literature(group)
        
        print(f"保留主要文献: {primary.lid}")
        
        for dup in duplicates:
            print(f"  {'[试运行] ' if dry_run else ''}删除重复文献: {dup.lid}")
            
            if not dry_run:
                try:
                    await dao.delete_by_lid(dup.lid)
                    deleted_count += 1
                    print(f"    ✅ 已删除")
                except Exception as e:
                    print(f"    ❌ 删除失败: {e}")
            else:
                deleted_count += 1
    
    print(f"\n🎯 {'模拟' if dry_run else '实际'}删除了 {deleted_count} 篇重复文献")
    
    if dry_run:
        print("\n⚠️ 这只是试运行，没有实际删除任何数据")
        print("如要实际执行删除，请运行: python3 clean_duplicate_literature.py --execute")

async def main():
    """主函数"""
    print("=" * 80)
    print("文献去重工具")
    print("=" * 80)
    
    # 检查命令行参数
    dry_run = "--execute" not in sys.argv
    
    if dry_run:
        print("🔍 试运行模式（只显示结果，不实际删除）")
    else:
        print("⚠️ 执行模式（将实际删除重复文献）")
        print("请确认您已备份数据库！")
        
        confirm = input("继续执行吗？(yes/no): ")
        if confirm.lower() != 'yes':
            print("操作已取消")
            return
    
    try:
        # 连接数据库
        await connect_to_mongodb()
        
        # 查找重复文献
        duplicate_groups = await find_duplicate_groups()
        
        if not duplicate_groups:
            print("🎉 没有发现重复文献！")
            return
        
        # 显示摘要
        print_duplicate_summary(duplicate_groups)
        
        # 执行合并
        await merge_duplicate_literature(duplicate_groups, dry_run)
        
        print("\n✅ 去重任务完成！")
        
    except Exception as e:
        print(f"❌ 执行异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
