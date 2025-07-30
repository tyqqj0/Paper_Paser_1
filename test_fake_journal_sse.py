#!/usr/bin/env python3
"""
测试假文献URL的SSE错误处理

验证系统对fake-journal.com这样的假URL的错误处理能力
"""

import requests
import json
import time
import threading
from typing import Dict, Any


class FakeJournalTester:
    """假文献URL测试器"""
    
    def __init__(self):
        self.events = []
        self.error_events = []
        self.status_events = []
        self.is_connected = False
        self.error = None
        
    def test_fake_journal_url(self, url: str):
        """测试假的期刊URL"""
        print(f"🧪 测试假文献URL: {url}")
        print("=" * 70)
        
        test_data = {
            "source": {
                "url": url
            }
        }
        
        print(f"📝 提交数据: {json.dumps(test_data, indent=2)}")
        print("⏳ 等待SSE响应...")
        
        try:
            response = requests.post(
                "http://localhost:8000/api/literature/stream",
                json=test_data,
                headers={
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache'
                },
                stream=True,
                timeout=30
            )
            
            if response.status_code != 200:
                self.error = f"HTTP {response.status_code}: {response.text}"
                print(f"❌ 连接失败: {self.error}")
                return False
            
            self.is_connected = True
            print("✅ SSE连接建立成功")
            print("\n📊 实时事件流:")
            print("-" * 50)
            
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    self._process_line(line)
                    
        except Exception as e:
            self.error = str(e)
            print(f"❌ 连接异常: {e}")
            return False
        
        return True
    
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
                self._display_event(event)
            except json.JSONDecodeError:
                print(f"⚠️ 无法解析JSON数据: {data}")
    
    def _display_event(self, event: Dict[str, Any]):
        """显示事件内容"""
        event_type = event['type']
        data = event['data']
        timestamp = time.strftime('%H:%M:%S', time.localtime(event['timestamp']))
        
        if event_type == 'status':
            self.status_events.append(event)
            execution_status = data.get('execution_status')
            progress = data.get('overall_progress', 0)
            stage = data.get('current_stage', 'N/A')
            
            # 状态图标
            status_icon = {
                'pending': '⏳',
                'processing': '🔄',
                'completed': '✅',
                'failed': '❌'
            }.get(execution_status, '❓')
            
            print(f"[{timestamp}] {status_icon} 状态: {execution_status} - {progress}% - {stage}")
            
            # 检查URL验证状态
            url_validation_status = data.get('url_validation_status')
            if url_validation_status == 'failed':
                url_error = data.get('url_validation_error')
                original_url = data.get('original_url')
                print(f"           🔗 URL验证失败: {url_error}")
                print(f"           📍 原始URL: {original_url}")
                
        elif event_type == 'error':
            self.error_events.append(event)
            error_event = data.get('event', 'unknown_error')
            error_msg = data.get('error', '未知错误')
            error_type = data.get('error_type', 'UnknownError')
            
            print(f"[{timestamp}] 💥 错误事件: {error_event}")
            print(f"           📋 错误类型: {error_type}")
            print(f"           📝 错误信息: {error_msg}")
            
            if data.get('original_url'):
                print(f"           🔗 问题URL: {data.get('original_url')}")
                
        elif event_type == 'failed':
            error = data.get('error', '未知错误')
            error_type = data.get('error_type', 'UnknownError')
            print(f"[{timestamp}] ❌ 任务失败: {error_type}")
            print(f"           📝 失败原因: {error}")
            
        elif event_type == 'completed':
            literature_id = data.get('literature_id')
            print(f"[{timestamp}] 🎉 任务完成! Literature ID: {literature_id}")
    
    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 70)
        print("📋 测试结果报告")
        print("=" * 70)
        
        print(f"📊 事件统计:")
        print(f"   - 总事件数: {len(self.events)}")
        print(f"   - 状态事件: {len(self.status_events)}")
        print(f"   - 错误事件: {len(self.error_events)}")
        
        # 分析状态变化
        if self.status_events:
            print(f"\n🔄 状态变化序列:")
            for i, event in enumerate(self.status_events, 1):
                data = event['data']
                status = data.get('execution_status')
                stage = data.get('current_stage', 'N/A')
                print(f"   {i}. {status} - {stage}")
        
        # 分析错误处理
        if self.error_events:
            print(f"\n💥 错误处理详情:")
            for i, event in enumerate(self.error_events, 1):
                data = event['data']
                error_event = data.get('event', 'unknown')
                error_type = data.get('error_type', 'Unknown')
                print(f"   {i}. 事件: {error_event}")
                print(f"      类型: {error_type}")
                print(f"      信息: {data.get('error', 'N/A')}")
        
        # 评估结果
        print(f"\n✅ 功能验证:")
        print(f"   - SSE连接: {'✅ 成功' if self.is_connected else '❌ 失败'}")
        print(f"   - URL验证: {'✅ 检测到失败' if any('url_validation_failed' in str(e) for e in self.error_events) else '❌ 未检测到'}")
        print(f"   - 错误推送: {'✅ 正常' if self.error_events else '❌ 无错误事件'}")
        print(f"   - 任务失败: {'✅ 正确处理' if any(e['data'].get('execution_status') == 'failed' for e in self.status_events) else '❌ 未正确处理'}")
        
        return {
            'total_events': len(self.events),
            'error_events': len(self.error_events),
            'connection_success': self.is_connected,
            'url_validation_detected': any('url_validation_failed' in str(e) for e in self.error_events),
            'task_failed_correctly': any(e['data'].get('execution_status') == 'failed' for e in self.status_events)
        }


def main():
    """主测试函数"""
    print("🚀 开始假文献URL的SSE错误处理测试")
    
    tester = FakeJournalTester()
    
    # 测试假的期刊URL
    fake_url = "https://fake-journal.com/article/123456"
    success = tester.test_fake_journal_url(fake_url)
    
    if success:
        report = tester.generate_report()
        
        print(f"\n🎯 测试总结:")
        if (report['connection_success'] and 
            report['url_validation_detected'] and 
            report['error_events'] > 0 and 
            report['task_failed_correctly']):
            print("🎉 所有错误处理功能正常工作！")
            print("✅ SSE能够正确检测和推送假URL的错误信息")
        else:
            print("⚠️ 部分功能可能需要进一步检查")
    else:
        print("❌ 测试失败，无法建立SSE连接")


if __name__ == "__main__":
    main()
