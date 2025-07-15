#!/usr/bin/env python3
"""
数据库迁移脚本
将现有数据从admin数据库迁移到literature_parser数据库
"""

import pymongo
from bson import ObjectId
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """执行数据库迁移"""
    
    # 连接MongoDB
    client = pymongo.MongoClient(
        "mongodb://literature_parser_backend:literature_parser_backend@localhost:27017/admin"
    )
    
    try:
        # 源数据库和集合
        source_db = client["admin"]
        target_db = client["literature_parser"]
        
        # 检查源数据
        source_collections = ["literature", "literatures"]
        total_migrated = 0
        
        for collection_name in source_collections:
            if collection_name in source_db.list_collection_names():
                source_collection = source_db[collection_name]
                count = source_collection.count_documents({})
                
                if count > 0:
                    logger.info(f"发现 {count} 个文档在 admin.{collection_name}")
                    
                    # 目标集合（统一使用literatures）
                    target_collection = target_db["literatures"]
                    
                    # 迁移数据
                    documents = list(source_collection.find({}))
                    
                    for doc in documents:
                        # 检查目标数据库中是否已存在相同的文档
                        existing = target_collection.find_one({"_id": doc["_id"]})
                        
                        if not existing:
                            # 插入到目标数据库
                            target_collection.insert_one(doc)
                            logger.info(f"迁移文档: {doc['_id']}")
                            total_migrated += 1
                        else:
                            logger.info(f"跳过已存在的文档: {doc['_id']}")
        
        # 验证迁移结果
        target_count = target_db["literatures"].count_documents({})
        logger.info(f"✅ 迁移完成！迁移了 {total_migrated} 个文档")
        logger.info(f"📊 目标数据库现在有 {target_count} 个文档")
        
        # 创建索引
        logger.info("🔧 创建索引...")
        target_collection = target_db["literatures"]
        
        indexes = [
            ("identifiers.doi", 1),
            ("identifiers.arxiv_id", 1),
            ("identifiers.fingerprint", 1),
            ("task_info.task_id", 1),
            ("created_at", -1),
        ]
        
        for index_spec in indexes:
            try:
                target_collection.create_index(index_spec)
                logger.info(f"创建索引: {index_spec}")
            except Exception as e:
                logger.warning(f"索引创建失败 {index_spec}: {e}")
        
        # 创建文本搜索索引
        try:
            target_collection.create_index([
                ("metadata.title", "text"),
                ("metadata.authors.full_name", "text")
            ])
            logger.info("创建文本搜索索引")
        except Exception as e:
            logger.warning(f"文本索引创建失败: {e}")
        
        logger.info("✅ 数据库迁移和索引创建完成！")
        
    except Exception as e:
        logger.error(f"❌ 迁移失败: {e}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    migrate_database() 