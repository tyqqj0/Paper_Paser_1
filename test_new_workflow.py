import requests
import time
import os

# --- 配置 ---
API_BASE_URL = "http://localhost:8000"
# 使用一个公开可访问的PDF URL进行测试 (例如, "Attention Is All You Need")
TEST_PDF_URL = "https://arxiv.org/pdf/1706.03762.pdf"
# 或者使用一个DOI
TEST_DOI = "10.48550/arXiv.1706.03762"


def print_header(title):
    print("\n" + "="*50)
    print(f" {title}")
    print("="*50)

def submit_task(payload):
    """Submits a task to the API."""
    print_header("1. 提交新任务")
    print(f"提交负载: {payload}")
    try:
        # Correct the submission URL
        response = requests.post(f"{API_BASE_URL}/api/literature", json=payload, timeout=30)
        response.raise_for_status()
        task_info = response.json()
        print(f"✅ 任务成功提交: {task_info}")
        return task_info.get("task_id")
    except requests.exceptions.RequestException as e:
        print(f"❌ 任务提交失败: {e}")
        if e.response:
            print(f"响应内容: {e.response.text}")
        return None

def check_task_status(task_id):
    """Checks the status of a task until it's completed."""
    while True:
        try:
            # Construct URL carefully to avoid double slashes
            url = f"{API_BASE_URL.rstrip('/')}/api/task/{task_id}"
            response = requests.get(url)
            response.raise_for_status()
            status_data = response.json()
            current_status = status_data.get("status", "UNKNOWN").lower()
            
            # Make the details extraction more robust
            details_info = status_data.get("details") or {}
            details = details_info.get("stage", current_status)

            print(f"当前状态: {current_status} - {details}")

            if current_status in ["success", "success_duplicate", "success_created", "failure"]:
                print("✅ 任务处理完成")
                return status_data
            
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            print(f"❌ 状态查询失败: {e}")
            return None

def get_literature_details(literature_id):
    """获取文献详情"""
    print_header("3. 获取文献详情")
    try:
        # Fix the URL path for literature details
        url = f"{API_BASE_URL}/api/literature/{literature_id}"
        response = requests.get(url)
        response.raise_for_status()
        literature_data = response.json()
        print(f"✅ 成功获取文献详情")
        print(f"标题: {literature_data.get('metadata', {}).get('title', 'N/A')}")
        print(f"作者: {literature_data.get('metadata', {}).get('authors', [])}")
        return literature_data
    except requests.RequestException as e:
        print(f"❌ 获取详情失败: {e}")
        return None

def run_test(payload):
    task_id = submit_task(payload)
    if not task_id:
        return

    status_data = check_task_status(task_id)
    if not status_data:
        print("❌ 任务状态检查失败")
        return

    final_status = status_data.get("status", "").upper()

    if final_status in ["SUCCESS_CREATED", "SUCCESS_DUPLICATE", "SUCCESS"]:
        literature_id = status_data.get("literature_id")
        
        if literature_id:
            print(f"✅ 任务成功完成，状态: {final_status}, 文献ID: {literature_id}")
            get_literature_details(literature_id)
        else:
            print("❌ 任务成功，但未能在最终结果中找到 literature_id")

    elif final_status == "FAILURE":
        error_details = status_data.get("details", {}).get("error", "未知错误")
        print(f"❌ 任务失败: {error_details}")
    else:
        print(f"ℹ️ 任务以未知状态结束: {status_data.get('status')}")

if __name__ == "__main__":
    # 测试1: 只提交PDF URL
    run_test({"pdf_url": TEST_PDF_URL})
    
    # 测试2: 再次提交相同的PDF URL，测试去重
    run_test({"pdf_url": TEST_PDF_URL})
    
    # 测试3: 提交DOI，测试去重
    run_test({"doi": TEST_DOI}) 