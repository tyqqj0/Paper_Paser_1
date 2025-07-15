#!/usr/bin/env python3
"""
调试参考文献获取
"""

import requests
import json
import time

def test_references():
    """测试参考文献获取"""
    
    # 提交一个新任务
    test_data = {
        'doi': '10.1038/nature12373',
        'title': None,
        'authors': None
    }
    
    print('🔍 提交新任务测试参考文献获取...')
    response = requests.post('http://localhost:8000/api/literature', json=test_data)
    print(f'状态码: {response.status_code}')
    
    if response.status_code == 202:
        result = response.json()
        task_id = result.get('taskId')
        print(f'任务ID: {task_id}')
        
        # 等待任务完成
        time.sleep(8)
        
        # 检查任务状态
        status_response = requests.get(f'http://localhost:8000/api/task/{task_id}')
        if status_response.status_code == 200:
            task_info = status_response.json()
            lit_id = task_info.get('literature_id')
            print(f'文献ID: {lit_id}')
            
            if lit_id:
                # 获取文献详情
                lit_response = requests.get(f'http://localhost:8000/api/literature/{lit_id}')
                if lit_response.status_code == 200:
                    lit_data = lit_response.json()
                    references = lit_data.get('references', [])
                    print(f'参考文献数量: {len(references)}')
                    if references:
                        print(f'第一个参考文献来源: {references[0].get("source", "N/A")}')
                        print(f'第一个参考文献内容: {references[0].get("raw_text", "N/A")[:100]}...')
                        
                        # 显示详细信息
                        print("\n参考文献详情:")
                        for i, ref in enumerate(references[:3]):
                            print(f"  {i+1}. 来源: {ref.get('source', 'N/A')}")
                            print(f"     原文: {ref.get('raw_text', 'N/A')[:80]}...")
                            parsed = ref.get('parsed', {})
                            print(f"     标题: {parsed.get('title', 'N/A')[:60]}...")
                            print()
                    else:
                        print('❌ 没有找到参考文献')
                else:
                    print(f'获取文献详情失败: {lit_response.status_code}')
                    print(f'错误: {lit_response.text}')
        else:
            print(f'获取任务状态失败: {status_response.status_code}')
    else:
        print(f'提交任务失败: {response.text}')

if __name__ == "__main__":
    test_references() 