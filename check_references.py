#!/usr/bin/env python3
"""检查数据库中references的数据情况"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'literature_parser_backend'))

from db.mongodb import get_mongodb_client
from datetime import datetime

def check_references():
    try:
        client = get_mongodb_client()
        db = client['literature_parser']
        collection = db['literatures']
        
        # 查找最近的几个文献记录
        docs = list(collection.find().sort('created_at', -1).limit(3))
        print(f'最近的{len(docs)}个文献记录:')
        
        for i, doc in enumerate(docs, 1):
            print(f'\n=== 文献 {i} ===')
            print(f'ID: {doc.get("_id")}')
            print(f'标题: {doc.get("metadata", {}).get("title", "N/A")}')
            print(f'创建时间: {doc.get("created_at")}')
            print(f'References数量: {len(doc.get("references", []))}')
            
            # 显示references详情
            refs = doc.get('references', [])
            if refs:
                print('References详情:')
                for j, ref in enumerate(refs[:3], 1):  # 只显示前3个
                    raw_text = ref.get('raw_text', 'N/A')
                    if len(raw_text) > 100:
                        raw_text = raw_text[:100] + '...'
                    print(f'  {j}. Raw: {raw_text}')
                    print(f'     Source: {ref.get("source", "N/A")}')
                    print(f'     Parsed: {bool(ref.get("parsed"))}')
                    if ref.get('parsed'):
                        parsed = ref.get('parsed')
                        print(f'     Parsed Title: {parsed.get("title", "N/A")}')
                        print(f'     Parsed Year: {parsed.get("year", "N/A")}')
                if len(refs) > 3:
                    print(f'  ... 还有 {len(refs) - 3} 个references')
            else:
                print('没有references数据')
                
        # 统计有references的文献数量
        total_count = collection.count_documents({})
        with_refs_count = collection.count_documents({'references': {'$exists': True, '$not': {'$size': 0}}})
        print(f'\n=== 统计信息 ===')
        print(f'总文献数量: {total_count}')
        print(f'有references的文献数量: {with_refs_count}')
        print(f'有references的比例: {with_refs_count/total_count*100:.1f}%' if total_count > 0 else '无文献')
        
    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_references() 