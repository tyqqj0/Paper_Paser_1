import asyncio
import sys
from datetime import datetime
from bson import ObjectId
from literature_parser_backend.db.mongodb import get_database, connect_to_mongodb

async def main():
    print("🔍 数据库状态检查...")
    print("=" * 50)
    
    try:
        # 先连接数据库
        await connect_to_mongodb()
        # 获取数据库实例
        db = await get_database()
        print("✅ 数据库连接成功!")
        
        # 获取集合列表
        collections = await db.list_collection_names()
        print(f"📚 集合列表: {collections}")
        
        # 检查文献集合
        if 'literature' in collections:
            count = await db.literature.count_documents({})
            print(f"📄 文献总数量: {count}")
            
            if count > 0:
                # 获取最近的文档
                recent_docs = await db.literature.find({}).sort("created_at", -1).limit(3).to_list(3)
                print(f"\n📋 最近 {len(recent_docs)} 个文档:")
                
                for i, doc in enumerate(recent_docs, 1):
                    print(f"\n  {i}. 文档ID: {doc.get('_id')}")
                    print(f"     标题: {doc.get('title', 'N/A')}")
                    print(f"     DOI: {doc.get('doi', 'N/A')}")
                    print(f"     作者数量: {len(doc.get('authors', []))}")
                    print(f"     参考文献数量: {len(doc.get('references', []))}")
                    print(f"     创建时间: {doc.get('created_at', 'N/A')}")
                    print(f"     状态: {doc.get('processing_status', 'N/A')}")
                    
                    # 检查内容字段
                    content = doc.get('content')
                    if content:
                        print(f"     内容状态: {content.get('status', 'N/A')}")
                        print(f"     PDF URL: {content.get('pdf_url', 'N/A')}")
                        print(f"     文本长度: {len(content.get('full_text', '')) if content.get('full_text') else 0}")
            else:
                print("📭 暂无文献数据")
        else:
            print("❌ 未找到 literature 集合")
        
        # 检查任务集合
        if 'tasks' in collections:
            task_count = await db.tasks.count_documents({})
            print(f"\n🔧 任务总数量: {task_count}")
            
            if task_count > 0:
                recent_tasks = await db.tasks.find({}).sort("created_at", -1).limit(3).to_list(3)
                print(f"\n📋 最近 {len(recent_tasks)} 个任务:")
                
                for i, task in enumerate(recent_tasks, 1):
                    print(f"\n  {i}. 任务ID: {task.get('_id')}")
                    print(f"     状态: {task.get('status', 'N/A')}")
                    print(f"     阶段: {task.get('stage', 'N/A')}")
                    print(f"     进度: {task.get('progress', 'N/A')}%")
                    print(f"     文献ID: {task.get('literature_id', 'N/A')}")
                    print(f"     创建时间: {task.get('created_at', 'N/A')}")
        else:
            print("❌ 未找到 tasks 集合")
            
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 