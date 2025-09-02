#!/usr/bin/env python3
"""
直接查看数据库中现有文献，并测试对已有文献的重复检测
"""

import asyncio
from literature_parser_backend.db.neo4j import connect_to_mongodb
from literature_parser_backend.db.dao import LiteratureDAO

async def check_existing_literature():
    print("=" * 80)
    print("查看数据库中现有文献")
    print("=" * 80)
    
    try:
        # 连接数据库
        await connect_to_mongodb()
        dao = LiteratureDAO.create_from_global_connection()
        
        # 查找一些现有文献
        print("🔍 搜索现有文献...")
        
        # 使用模糊标题搜索
        candidates = await dao.find_by_title_fuzzy("attention", limit=5)
        
        if candidates:
            print(f"找到 {len(candidates)} 个文献:")
            for i, lit in enumerate(candidates):
                print(f"\n📚 文献 {i+1}:")
                print(f"  LID: {lit.lid}")
                print(f"  标题: {lit.metadata.title if lit.metadata else 'N/A'}")
                print(f"  DOI: {lit.identifiers.doi if lit.identifiers else 'N/A'}")
                print(f"  ArXiv ID: {lit.identifiers.arxiv_id if lit.identifiers else 'N/A'}")
                
                # 选择第一个有DOI的文献进行测试
                if lit.identifiers and lit.identifiers.doi:
                    print(f"\n✅ 选择此文献进行重复测试: {lit.identifiers.doi}")
                    return lit.identifiers.doi
        else:
            print("❌ 没有找到任何文献")
            return None
            
    except Exception as e:
        print(f"❌ 数据库查询失败: {e}")
        return None

async def test_duplicate_with_existing_doi(test_doi):
    """使用已存在的DOI测试重复检测"""
    import aiohttp
    import json
    
    print(f"\n🧪 使用已存在的DOI测试重复检测: {test_doi}")
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        request_data = {"doi": test_doi}
        
        async with session.post(
            f"{base_url}/api/resolve",
            json=request_data,
            headers={"Content-Type": "application/json"}
        ) as response:
            status = response.status
            result = await response.json()
            
            print(f"📊 API响应 (状态码: {status}):")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            if status == 200:
                print("✅ 成功！API正确返回了已存在的文献")
                print("这说明别名系统或前端查重工作正常")
                return True
            elif status == 202:
                print("❌ 失败！API创建了新任务，说明没有检测到已存在的文献")
                return False
            else:
                print(f"❓ 未知状态: {status}")
                return False

async def main():
    # 先查看现有文献
    test_doi = await check_existing_literature()
    
    if test_doi:
        # 使用已存在的DOI测试
        success = await test_duplicate_with_existing_doi(test_doi)
        
        if success:
            print("\n✅ 别名系统工作正常，前端查重有效")
        else:
            print("\n❌ 别名系统可能有问题，需要检查")
    else:
        print("\n⚠️  没有找到合适的测试数据")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
