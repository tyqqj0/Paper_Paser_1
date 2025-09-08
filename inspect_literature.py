#!/usr/bin/env python3
"""
查看特定LID文献的详细数据
"""

import asyncio
import json
import sys
from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.db.neo4j import connect_to_neo4j
from literature_parser_backend.settings import Settings

def print_json_pretty(data, indent=0):
    """美化打印JSON数据"""
    if isinstance(data, dict):
        for key, value in data.items():
            print("  " * indent + f"📌 {key}:")
            if isinstance(value, (dict, list)):
                print_json_pretty(value, indent + 1)
            else:
                print("  " * (indent + 1) + f"{value}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            print("  " * indent + f"[{i}]")
            print_json_pretty(item, indent + 1)
    else:
        print("  " * indent + f"{data}")

async def inspect_literature(lid: str):
    """查看特定LID的文献详细数据"""
    
    # 初始化连接
    settings = Settings()
    await connect_to_neo4j()
    
    # 初始化DAO
    literature_dao = LiteratureDAO()
    
    try:
        print(f"🔍 查询LID: {lid}")
        print("=" * 80)
        
        # 查找文献
        literature = await literature_dao.find_by_lid(lid)
        
        if not literature:
            print(f"❌ 未找到LID为 {lid} 的文献")
            return
            
        print(f"✅ 找到文献: {lid}")
        print()
        
        # 基本信息
        print("📋 基本信息:")
        print(f"  LID: {literature.lid}")
        print(f"  创建时间: {literature.created_at}")
        print(f"  更新时间: {literature.updated_at}")
        print()
        
        # 标识符
        print("🏷️ 标识符:")
        if literature.identifiers:
            if literature.identifiers.doi:
                print(f"  DOI: {literature.identifiers.doi}")
            if literature.identifiers.arxiv_id:
                print(f"  ArXiv ID: {literature.identifiers.arxiv_id}")
            if literature.identifiers.pmid:
                print(f"  PMID: {literature.identifiers.pmid}")
        else:
            print("  无标识符数据")
        print()
        
        # 元数据
        print("📄 元数据:")
        if literature.metadata:
            print(f"  标题: {literature.metadata.title or 'N/A'}")
            print(f"  期刊: {literature.metadata.journal or 'N/A'}")
            print(f"  发表年份: {literature.metadata.publication_year or 'N/A'}")
            print(f"  作者数量: {len(literature.metadata.authors) if literature.metadata.authors else 0}")
            if literature.metadata.authors:
                print("  作者:")
                for i, author in enumerate(literature.metadata.authors[:3]):  # 只显示前3个作者
                    print(f"    {i+1}. {author}")
                if len(literature.metadata.authors) > 3:
                    print(f"    ... 还有 {len(literature.metadata.authors) - 3} 个作者")
            if literature.metadata.abstract:
                abstract_preview = literature.metadata.abstract[:200] + "..." if len(literature.metadata.abstract) > 200 else literature.metadata.abstract
                print(f"  摘要预览: {abstract_preview}")
        else:
            print("  无元数据")
        print()
        
        # 任务信息
        print("⚙️ 任务信息:")
        if literature.task_info:
            print(f"  任务ID: {literature.task_info.task_id}")
            print(f"  状态: {literature.task_info.status}")
            print(f"  开始时间: {literature.task_info.start_time}")
            print(f"  结束时间: {literature.task_info.end_time}")
            
            if literature.task_info.components:
                print("  组件状态:")
                print(f"    元数据: {literature.task_info.components.metadata.status}")
                print(f"    PDF提取: {literature.task_info.components.pdf_extraction.status}")
                print(f"    关系提取: {literature.task_info.components.relationship_extraction.status}")
            
            if literature.task_info.error_info:
                print("  错误信息:")
                for error in literature.task_info.error_info:
                    print(f"    - {error}")
        else:
            print("  无任务信息")
        print()
        
        # PDF信息
        print("📑 PDF信息:")
        if literature.pdf_info:
            print(f"  是否有PDF: {literature.pdf_info.has_pdf}")
            print(f"  文件路径: {literature.pdf_info.file_path or 'N/A'}")
            print(f"  页数: {literature.pdf_info.page_count or 'N/A'}")
            print(f"  文件大小: {literature.pdf_info.file_size or 'N/A'} bytes")
            print(f"  抽取状态: {literature.pdf_info.extraction_status or 'N/A'}")
        else:
            print("  无PDF信息")
        print()
        
        # 关系信息
        print("🔗 关系信息:")
        if literature.relationships:
            print(f"  引用数量: {len(literature.relationships.citations) if literature.relationships.citations else 0}")
            print(f"  参考文献数量: {len(literature.relationships.references) if literature.relationships.references else 0}")
            print(f"  作者关系数量: {len(literature.relationships.author_relationships) if literature.relationships.author_relationships else 0}")
        else:
            print("  无关系信息")
        print()
        
        # 原始数据（可选）
        answer = input("是否查看完整原始数据? (y/N): ").strip().lower()
        if answer in ['y', 'yes']:
            print("\n" + "=" * 80)
            print("🗂️ 完整原始数据:")
            print("=" * 80)
            # 转换为字典并美化打印
            data_dict = literature.model_dump()
            print_json_pretty(data_dict)
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("用法: python inspect_literature.py <LID>")
        print("例如: python inspect_literature.py LIT_001")
        print()
        print("提示: 先运行 python list_all_lids.py 查看所有可用的LID")
        sys.exit(1)
    
    lid = sys.argv[1]
    await inspect_literature(lid)

if __name__ == "__main__":
    asyncio.run(main())


