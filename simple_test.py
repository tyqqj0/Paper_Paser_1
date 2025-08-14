#!/usr/bin/env python3
"""
简化版测试脚本 - 逐个手动测试新瀑布流架构

先测试基本功能，确保各个处理器正常工作
"""

import json
import time
import subprocess
import sys

# 测试用例 - 先从简单的开始
TEST_URLS = [
    {
        "name": "ArXiv经典论文 - Transformer",
        "url": "https://arxiv.org/abs/1706.03762",
        "expected": "Semantic Scholar处理器，高质量元数据"
    },
    {
        "name": "NeurIPS 2012 - AlexNet", 
        "url": "https://proceedings.neurips.cc/paper/2012/hash/c399862d3b9d6b76c8436e924a68c45b-Abstract.html",
        "expected": "CrossRef处理器，标题匹配"
    },
    {
        "name": "ArXiv ResNet论文",
        "url": "https://arxiv.org/abs/1512.03385", 
        "expected": "Semantic Scholar处理器，有DOI"
    }
]

def run_curl_command(cmd):
    """运行curl命令并返回结果"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"

def test_single_url(test_case):
    """测试单个URL"""
    print(f"\n🧪 测试: {test_case['name']}")
    print(f"   URL: {test_case['url']}")
    print(f"   预期: {test_case['expected']}")
    
    # 1. 发送请求
    print("   📤 发送解析请求...")
    url = test_case["url"]
    curl_cmd = f'curl -s -X POST "http://localhost:8000/api/resolve" -H "Content-Type: application/json" -d \'{{"url": "{url}"}}\''
    
    returncode, stdout, stderr = run_curl_command(curl_cmd)
    
    if returncode != 0:
        print(f"   ❌ curl命令失败: {stderr}")
        return False
    
    try:
        response = json.loads(stdout)
        print(f"   📨 响应: {response}")
        
        # 提取task_id
        task_id = response.get("task_id")
        if not task_id:
            print("   ❌ 未获取到task_id")
            return False
        
        print(f"   🆔 任务ID: {task_id}")
        
        # 2. 等待一段时间
        print("   ⏳ 等待10秒让任务完成...")
        time.sleep(10)
        
        # 3. 查看worker日志确认处理完成
        print("   📋 检查worker日志:")
        log_cmd = f'sudo docker logs paper_paser_1-worker-1 --tail=20 | grep "{task_id[:8]}"'
        log_returncode, log_stdout, log_stderr = run_curl_command(log_cmd)
        
        if log_stdout:
            print("   📝 相关日志:")
            for line in log_stdout.strip().split('\n'):
                if task_id[:8] in line:
                    print(f"      {line}")
        
        # 4. 查看数据库中的文献
        print("   📚 查看数据库中的文献:")
        list_cmd = 'curl -s "http://localhost:8000/api/literatures" | python3 -c "import sys,json; data=json.load(sys.stdin); print(f\\"共{len(data)}篇文献:\\"); [print(f\\"  - {lit[\'id\']}: {lit[\'title\'][:50]}...\\") for lit in data[-3:]]"'
        
        list_returncode, list_stdout, list_stderr = run_curl_command(list_cmd)
        if list_returncode == 0:
            print(f"   {list_stdout}")
        else:
            print(f"   ⚠️  查询文献列表失败: {list_stderr}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"   ❌ JSON解析失败: {e}")
        print(f"   原始响应: {stdout}")
        return False

def main():
    """主函数"""
    print("🎯 Paper Parser 新瀑布流架构简化测试")
    print("=" * 50)
    
    # 清空数据库
    print("\n🗑️  清空数据库...")
    clear_cmd = 'curl -s -X DELETE "http://localhost:8000/api/literature/clear-database"'
    returncode, stdout, stderr = run_curl_command(clear_cmd)
    
    if returncode == 0:
        print(f"   ✅ 数据库清空完成: {stdout}")
    else:
        print(f"   ⚠️  清空可能失败: {stderr}")
    
    time.sleep(2)
    
    # 逐个测试
    success_count = 0
    for i, test_case in enumerate(TEST_URLS, 1):
        print(f"\n{'='*20} 测试 {i}/{len(TEST_URLS)} {'='*20}")
        
        success = test_single_url(test_case)
        if success:
            success_count += 1
        
        # 测试间隔
        if i < len(TEST_URLS):
            print("\n   ⏸️  等待5秒后进行下一个测试...")
            time.sleep(5)
    
    # 总结
    print(f"\n" + "=" * 50)
    print(f"📊 测试总结:")
    print(f"   总测试数: {len(TEST_URLS)}")
    print(f"   成功数: {success_count}")
    print(f"   成功率: {success_count/len(TEST_URLS)*100:.1f}%")

if __name__ == "__main__":
    main()
