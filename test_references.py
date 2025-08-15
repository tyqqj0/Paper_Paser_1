#!/usr/bin/env python3
import requests
import json
import time

def test_reference_parsing():
    # 测试URL - 使用一个新的ArXiv论文
    test_url = "https://arxiv.org/abs/2308.07912"  # 一个新的论文来测试引用解析
    
    print(f"🧪 测试引用解析功能")
    print(f"📄 测试URL: {test_url}")
    
    # 1. 提交论文
    submit_data = {
        "url": test_url,
        "tags": ["reference-test"]
    }
    
    try:
        print("\n📤 提交论文...")
        response = requests.post(
            "http://localhost:8000/api/resolve",
            headers={"Content-Type": "application/json"},
            json=submit_data,
            timeout=10
        )
        
        if response.status_code == 202:
            result = response.json()
            task_id = result.get("task_id")
            print(f"✅ 提交成功! Task ID: {task_id}")
            
            # 等待任务完成获取literature_id
            literature_id = None
            
            # 2. 等待处理完成
            print("\n⏳ 等待处理完成...")
            for i in range(30):  # 等待最多30秒
                time.sleep(2)
                
                # 检查任务状态
                task_response = requests.get(f"http://localhost:8000/api/tasks/{task_id}")
                if task_response.status_code == 200:
                    task_data = task_response.json()
                    task_status = task_data.get("status", "unknown")
                    print(f"📊 任务状态: {task_status}")
                    
                    # 获取literature_id
                    if not literature_id and task_data.get("literature_id"):
                        literature_id = task_data.get("literature_id")
                        print(f"📄 获得 Literature ID: {literature_id}")
                    
                    if task_status in ["completed", "failed"]:
                        break
                else:
                    print(f"❌ 任务状态检查失败: {task_response.status_code}")
            
            # 3. 检查引用数据
            if not literature_id:
                print("❌ 无法获取 Literature ID，任务可能失败")
                return
                
            print(f"\n🔍 检查引用数据 (Literature ID: {literature_id})...")
            lit_response = requests.get(f"http://localhost:8000/api/literature/{literature_id}")
            if lit_response.status_code == 200:
                literature_data = lit_response.json()
                references = literature_data.get("references", [])
                
                print(f"📚 找到 {len(references)} 个引用")
                
                if references:
                    print("\n✅ 引用解析成功!")
                    print("前3个引用:")
                    for i, ref in enumerate(references[:3]):
                        title = ref.get("title", "无标题")[:60]
                        authors = ref.get("authors", [])
                        author_str = ", ".join(authors[:2]) if authors else "无作者"
                        print(f"  {i+1}. {title}... - {author_str}")
                        
                    # 检查组件状态
                    task_info = literature_data.get("task_info", {})
                    component_statuses = task_info.get("component_statuses", {})
                    ref_status = component_statuses.get("references", {})
                    print(f"\n📊 引用组件状态: {ref_status.get('status', 'unknown')}")
                    print(f"🔄 处理阶段: {ref_status.get('stage', 'unknown')}")
                    print(f"📈 进度: {ref_status.get('progress', 0)}%")
                    if ref_status.get('source'):
                        print(f"📡 数据源: {ref_status.get('source')}")
                    
                else:
                    print("\n❌ 引用解析失败 - 没有找到引用")
                    
                    # 检查组件状态详情
                    task_info = literature_data.get("task_info", {})
                    component_statuses = task_info.get("component_statuses", {})
                    ref_status = component_statuses.get("references", {})
                    print(f"📊 引用组件状态: {ref_status}")
                    
            else:
                print(f"❌ 获取文献数据失败: {lit_response.status_code}")
                
        else:
            print(f"❌ 提交失败: {response.status_code}")
            print(f"响应: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试出错: {e}")

if __name__ == "__main__":
    test_reference_parsing()
