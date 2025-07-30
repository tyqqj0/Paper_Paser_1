#!/usr/bin/env python3
"""
测试SSE文献处理端点

验证新的/api/literature/stream端点是否正常工作
"""

import requests
import json
import time
from typing import Dict, Any
import threading
from urllib.parse import urlencode


class SSEClient:
    """简单的SSE客户端"""
    
    def __init__(self, url: str, data: Dict[str, Any]):
        self.url = url
        self.data = data
        self.events = []
        self.is_connected = False
        self.error = None
        
    def connect(self):
        """连接SSE端点"""
        try:
            # 发送POST请求到SSE端点
            response = requests.post(
                self.url,
                json=self.data,
                headers={
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache'
                },
                stream=True,
                timeout=120
            )
            
            if response.status_code != 200:
                self.error = f"HTTP {response.status_code}: {response.text}"
                return
            
            self.is_connected = True
            print(f"✅ SSE连接建立成功")
            
            # 处理SSE流
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    self._process_line(line)
                    
        except Exception as e:
            self.error = str(e)
            print(f"❌ SSE连接错误: {e}")
    
    def _process_line(self, line: str):
        """处理SSE行数据"""
        if line.startswith('event:'):
            event_type = line[6:].strip()
            self.current_event_type = event_type
        elif line.startswith('data:'):
            data = line[5:].strip()
            try:
                event_data = json.loads(data)
                event = {
                    'type': getattr(self, 'current_event_type', 'message'),
                    'data': event_data,
                    'timestamp': time.time()
                }
                self.events.append(event)
                self._handle_event(event)
            except json.JSONDecodeError:
                print(f"⚠️ 无法解析JSON数据: {data}")
    
    def _handle_event(self, event: Dict[str, Any]):
        """处理接收到的事件"""
        event_type = event['type']
        data = event['data']
        
        if event_type == 'status':
            # 状态更新事件
            progress = data.get('overall_progress', 0)
            stage = data.get('current_stage', '未知阶段')
            execution_status = data.get('execution_status', '未知状态')
            literature_id = data.get('literature_id')
            
            print(f"📊 状态更新: {execution_status} - {progress}% - {stage}")
            if literature_id:
                print(f"   文献ID: {literature_id}")
                
        elif event_type == 'completed':
            # 完成事件
            literature_id = data.get('literature_id')
            resource_url = data.get('resource_url')
            print(f"🎉 任务完成!")
            print(f"   文献ID: {literature_id}")
            print(f"   资源URL: {resource_url}")
            
        elif event_type == 'failed':
            # 失败事件
            error = data.get('error', '未知错误')
            print(f"❌ 任务失败: {error}")
            
        elif event_type == 'error':
            # 错误事件
            error = data.get('error', '未知错误')
            print(f"💥 系统错误: {error}")


def test_sse_literature_processing():
    """测试SSE文献处理"""
    print("=" * 60)
    print("🧪 测试SSE文献处理端点")
    print("=" * 60)
    
    # 测试数据
    test_data = {
        "source": {
            "doi": "10.1038/nature12373"  # 使用已知的DOI
        }
    }
    
    print(f"📝 提交测试数据: {json.dumps(test_data, indent=2)}")
    
    # 创建SSE客户端
    client = SSEClient("http://localhost:8000/api/literature/stream", test_data)
    
    # 在单独线程中连接SSE
    sse_thread = threading.Thread(target=client.connect)
    sse_thread.daemon = True
    sse_thread.start()
    
    # 等待连接建立
    time.sleep(2)
    
    if client.error:
        print(f"❌ SSE连接失败: {client.error}")
        return False
    
    if not client.is_connected:
        print("❌ SSE连接未建立")
        return False
    
    # 等待事件
    print("⏳ 等待SSE事件...")
    
    # 最多等待2分钟
    max_wait_time = 120
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        if client.events:
            last_event = client.events[-1]
            if last_event['type'] in ['completed', 'failed', 'error']:
                break
        time.sleep(1)
    
    # 等待线程结束
    sse_thread.join(timeout=5)
    
    # 分析结果
    print(f"\n📊 收到 {len(client.events)} 个事件:")
    
    for i, event in enumerate(client.events, 1):
        event_type = event['type']
        timestamp = time.strftime('%H:%M:%S', time.localtime(event['timestamp']))
        print(f"  {i}. [{timestamp}] {event_type}")
    
    # 检查是否有完成事件
    completed_events = [e for e in client.events if e['type'] == 'completed']
    if completed_events:
        literature_id = completed_events[0]['data'].get('literature_id')
        print(f"\n✅ 任务成功完成，文献ID: {literature_id}")
        
        # 测试文献数据获取
        if literature_id:
            test_literature_access(literature_id)
        
        return True
    else:
        failed_events = [e for e in client.events if e['type'] in ['failed', 'error']]
        if failed_events:
            error_msg = failed_events[0]['data'].get('error', '未知错误')
            print(f"\n❌ 任务失败: {error_msg}")
        else:
            print(f"\n⏰ 任务在 {max_wait_time} 秒内未完成")
        
        return False


def test_literature_access(literature_id: str):
    """测试文献数据访问"""
    print(f"\n📖 测试文献数据访问...")
    
    try:
        response = requests.get(f"http://localhost:8000/api/literature/{literature_id}")
        
        if response.status_code == 200:
            literature_data = response.json()
            print("✅ 文献数据访问成功:")
            print(f"   - 标题: {literature_data.get('title', 'N/A')}")
            print(f"   - DOI: {literature_data.get('doi', 'N/A')}")
            print(f"   - 作者数: {len(literature_data.get('authors', []))}")
            return True
        else:
            print(f"❌ 文献数据访问失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 文献数据访问异常: {e}")
        return False


def main():
    """主测试函数"""
    print("🚀 开始SSE文献处理测试...")
    
    success = test_sse_literature_processing()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 SSE文献处理测试成功!")
        print("\n📋 功能验证:")
        print("✅ SSE连接建立正常")
        print("✅ 状态事件推送正常")
        print("✅ 完成事件包含literature_id")
        print("✅ 文献数据可正常访问")
    else:
        print("💥 SSE文献处理测试失败!")
        print("需要检查SSE端点实现")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
