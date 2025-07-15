#!/usr/bin/env python3
"""
测试真实URL的脚本 - ArXiv论文
"""

import requests
import json
import time

def test_arxiv_url():
    """测试ArXiv URL处理"""
    
    # 测试数据 - 您提供的ArXiv URL
    test_data = {
        "source": {
            "url": "http://arxiv.org/abs/2205.14217"
        }
    }
    
    print("🚀 开始测试真实ArXiv URL...")
    print(f"📄 测试URL: {test_data['source']['url']}")
    print("=" * 60)
    
    try:
        # 1. 提交文献处理请求
        print("1️⃣ 提交文献处理请求...")
        response = requests.post(
            "http://localhost:8000/api/literature", 
            json=test_data, 
            timeout=30
        )
        
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            # 文献已存在
            result = response.json()
            print("   ✅ 文献已存在于数据库中")
            print(f"   📚 文献ID: {result.get('literatureId')}")
            return result.get('literatureId'), None
            
        elif response.status_code == 202:
            # 创建了新任务
            result = response.json()
            print("   ✅ 创建了新的处理任务")
            print(f"   🆔 任务ID: {result.get('taskId')}")
            print(f"   📝 消息: {result.get('message')}")
            return None, result.get('taskId')
            
        else:
            print(f"   ❌ 请求失败: {response.status_code}")
            print(f"   📄 响应: {response.text}")
            return None, None
            
    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
        return None, None

def monitor_task(task_id, max_wait_time=300):
    """监控任务状态"""
    if not task_id:
        return None
    
    print(f"\n2️⃣ 监控任务进度 (任务ID: {task_id})")
    print("   ⏱️ 最大等待时间: 5分钟")
    
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        try:
            response = requests.get(f"http://localhost:8000/api/task/{task_id}", timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                status = result.get('status')
                stage = result.get('stage', '未知阶段')
                progress = result.get('progress_percentage', 0)
                
                print(f"   📊 状态: {status} | 阶段: {stage} | 进度: {progress}%")
                
                if status == 'success':
                    literature_id = result.get('literature_id')
                    print(f"   🎉 任务成功完成！文献ID: {literature_id}")
                    return literature_id
                    
                elif status == 'failure':
                    error_msg = result.get('error_message', '未知错误')
                    print(f"   ❌ 任务失败: {error_msg}")
                    return None
                    
                elif status in ['pending', 'processing']:
                    print(f"   ⏳ 任务进行中...")
                    time.sleep(5)  # 等待5秒后再次检查
                    
            else:
                print(f"   ❌ 查询任务状态失败: {response.status_code}")
                break
                
        except Exception as e:
            print(f"   ❌ 查询任务异常: {e}")
            break
    
    print("   ⏰ 任务监控超时")
    return None

def get_literature_info(literature_id):
    """获取文献详细信息"""
    if not literature_id:
        return
    
    print(f"\n3️⃣ 获取文献详细信息 (ID: {literature_id})")
    
    try:
        response = requests.get(f"http://localhost:8000/api/literature/{literature_id}", timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print("   ✅ 成功获取文献信息")
            
            # 显示关键信息
            metadata = result.get('metadata', {})
            print(f"   📰 标题: {metadata.get('title', '未知')}")
            print(f"   👥 作者: {', '.join([a.get('full_name', '') for a in metadata.get('authors', [])])}")
            print(f"   📅 年份: {metadata.get('year', '未知')}")
            print(f"   📖 期刊: {metadata.get('journal', '未知')}")
            
            # 显示摘要 (截断显示)
            abstract = metadata.get('abstract', '')
            if abstract:
                abstract_preview = abstract[:200] + "..." if len(abstract) > 200 else abstract
                print(f"   📄 摘要: {abstract_preview}")
            
            # 显示引用数量
            references = result.get('references', [])
            print(f"   📚 参考文献数量: {len(references)}")
            
            return result
            
        else:
            print(f"   ❌ 获取文献信息失败: {response.status_code}")
            print(f"   📄 响应: {response.text}")
            
    except Exception as e:
        print(f"   ❌ 获取文献信息异常: {e}")

def main():
    """主函数"""
    print("🎯 ArXiv URL 真实测试")
    print("=" * 60)
    
    # 测试URL处理
    literature_id, task_id = test_arxiv_url()
    
    # 如果是新任务，监控进度
    if task_id:
        literature_id = monitor_task(task_id)
    
    # 获取最终结果
    if literature_id:
        literature_info = get_literature_info(literature_id)
        
        print("\n" + "=" * 60)
        print("🎉 测试成功完成！")
        print("✅ 系统成功处理了ArXiv URL并提取了文献信息")
    else:
        print("\n" + "=" * 60)
        print("❌ 测试未能完成")
        print("💡 建议检查服务日志: docker logs literature_parser_backend-worker-1")

if __name__ == "__main__":
    main() 