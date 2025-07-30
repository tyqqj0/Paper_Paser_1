#!/usr/bin/env python3
"""
测试SSE的错误处理功能

验证增强后的SSE是否能正确处理和推送各种错误情况
"""

import requests
import json
import time
import threading
from typing import Dict, Any, List


class SSEErrorTester:
    """SSE错误处理测试器"""
    
    def __init__(self, url: str, data: Dict[str, Any], test_name: str):
        self.url = url
        self.data = data
        self.test_name = test_name
        self.events = []
        self.error_events = []
        self.is_connected = False
        self.error = None
        
    def connect_and_test(self):
        """连接SSE并测试错误处理"""
        try:
            response = requests.post(
                self.url,
                json=self.data,
                headers={
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache'
                },
                stream=True,
                timeout=60
            )
            
            if response.status_code != 200:
                self.error = f"HTTP {response.status_code}: {response.text}"
                return
            
            self.is_connected = True
            print(f"✅ {self.test_name} - SSE连接建立成功")
            
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    self._process_line(line)
                    
        except Exception as e:
            self.error = str(e)
            print(f"❌ {self.test_name} - SSE连接错误: {e}")
    
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
                self._analyze_event(event)
            except json.JSONDecodeError:
                print(f"⚠️ 无法解析JSON数据: {data}")
    
    def _analyze_event(self, event: Dict[str, Any]):
        """分析事件"""
        event_type = event['type']
        data = event['data']
        timestamp = time.strftime('%H:%M:%S', time.localtime(event['timestamp']))
        
        if event_type == 'status':
            execution_status = data.get('execution_status')
            progress = data.get('overall_progress', 0)
            stage = data.get('current_stage', 'N/A')
            
            print(f"[{timestamp}] 📊 {execution_status} - {progress}% - {stage}")
            
            # 检查URL验证错误
            if data.get('url_validation_status') == 'failed':
                print(f"[{timestamp}] 🔗 URL验证失败: {data.get('url_validation_error')}")
            
            # 检查组件错误
            lit_status = data.get('literature_status')
            if lit_status:
                comp_status = lit_status.get('component_status', {})
                for comp_name, comp_detail in comp_status.items():
                    if isinstance(comp_detail, dict) and comp_detail.get('status') == 'failed':
                        error_info = comp_detail.get('error_info')
                        print(f"[{timestamp}] 💥 组件 {comp_name} 失败: {error_info}")
                        
        elif event_type == 'error':
            # 错误事件
            error_event = data.get('event', 'unknown_error')
            error_msg = data.get('error', '未知错误')
            print(f"[{timestamp}] ❌ 错误事件: {error_event} - {error_msg}")
            self.error_events.append(event)
            
        elif event_type == 'completed':
            literature_id = data.get('literature_id')
            print(f"[{timestamp}] 🎉 任务完成! Literature ID: {literature_id}")
            
        elif event_type == 'failed':
            error = data.get('error', '未知错误')
            error_type = data.get('error_type', 'UnknownError')
            print(f"[{timestamp}] ❌ 任务失败: {error_type} - {error}")
    
    def get_summary(self):
        """获取测试摘要"""
        return {
            'test_name': self.test_name,
            'total_events': len(self.events),
            'error_events': len(self.error_events),
            'has_errors': len(self.error_events) > 0,
            'connection_success': self.is_connected,
            'connection_error': self.error
        }


def test_invalid_url():
    """测试无效URL的错误处理"""
    print("🧪 测试1: 无效URL错误处理")
    print("=" * 50)
    
    test_data = {
        "source": {
            "url": "https://this-is-definitely-not-a-valid-url-12345.com/paper.pdf"
        }
    }
    
    print(f"📝 提交数据: {json.dumps(test_data, indent=2)}")
    
    tester = SSEErrorTester(
        "http://localhost:8000/api/literature/stream", 
        test_data, 
        "无效URL测试"
    )
    
    test_thread = threading.Thread(target=tester.connect_and_test)
    test_thread.daemon = True
    test_thread.start()
    
    test_thread.join(timeout=30)
    
    return tester.get_summary()


def test_invalid_doi():
    """测试无效DOI的错误处理"""
    print("\n🧪 测试2: 无效DOI错误处理")
    print("=" * 50)
    
    test_data = {
        "source": {
            "doi": "10.9999/invalid.doi.12345"
        }
    }
    
    print(f"📝 提交数据: {json.dumps(test_data, indent=2)}")
    
    tester = SSEErrorTester(
        "http://localhost:8000/api/literature/stream", 
        test_data, 
        "无效DOI测试"
    )
    
    test_thread = threading.Thread(target=tester.connect_and_test)
    test_thread.daemon = True
    test_thread.start()
    
    test_thread.join(timeout=45)
    
    return tester.get_summary()


def test_invalid_arxiv():
    """测试无效ArXiv ID的错误处理"""
    print("\n🧪 测试3: 无效ArXiv ID错误处理")
    print("=" * 50)
    
    test_data = {
        "source": {
            "arxiv_id": "9999.99999"  # 明显无效的ArXiv ID
        }
    }
    
    print(f"📝 提交数据: {json.dumps(test_data, indent=2)}")
    
    tester = SSEErrorTester(
        "http://localhost:8000/api/literature/stream", 
        test_data, 
        "无效ArXiv ID测试"
    )
    
    test_thread = threading.Thread(target=tester.connect_and_test)
    test_thread.daemon = True
    test_thread.start()
    
    test_thread.join(timeout=45)
    
    return tester.get_summary()


def main():
    """主测试函数"""
    print("🚀 开始SSE错误处理测试...")
    
    # 运行各种错误测试
    summaries = []
    
    # 测试1: 无效URL
    summary1 = test_invalid_url()
    summaries.append(summary1)
    
    # 测试2: 无效DOI
    summary2 = test_invalid_doi()
    summaries.append(summary2)
    
    # 测试3: 无效ArXiv ID
    summary3 = test_invalid_arxiv()
    summaries.append(summary3)
    
    # 生成总结报告
    print("\n" + "=" * 70)
    print("📋 SSE错误处理测试总结")
    print("=" * 70)
    
    for summary in summaries:
        print(f"\n🔍 {summary['test_name']}:")
        print(f"   - 连接成功: {'✅' if summary['connection_success'] else '❌'}")
        print(f"   - 总事件数: {summary['total_events']}")
        print(f"   - 错误事件数: {summary['error_events']}")
        print(f"   - 包含错误处理: {'✅' if summary['has_errors'] else '❌'}")
        
        if summary['connection_error']:
            print(f"   - 连接错误: {summary['connection_error']}")
    
    # 评估整体结果
    total_tests = len(summaries)
    successful_connections = sum(1 for s in summaries if s['connection_success'])
    tests_with_errors = sum(1 for s in summaries if s['has_errors'])
    
    print(f"\n🎯 整体评估:")
    print(f"   - 测试总数: {total_tests}")
    print(f"   - 连接成功率: {successful_connections}/{total_tests}")
    print(f"   - 错误处理覆盖: {tests_with_errors}/{total_tests}")
    
    if successful_connections == total_tests:
        print("✅ 所有SSE连接测试通过")
    else:
        print("❌ 部分SSE连接测试失败")
    
    if tests_with_errors > 0:
        print("✅ SSE错误处理功能正常工作")
    else:
        print("⚠️ 未检测到错误处理事件，可能需要进一步验证")


if __name__ == "__main__":
    main()
