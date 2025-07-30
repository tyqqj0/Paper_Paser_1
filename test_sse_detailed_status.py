#!/usr/bin/env python3
"""
测试SSE中的详细状态信息

验证SSE是否包含了所有的任务状态变化，包括：
1. 各个组件的详细状态（metadata, content, references）
2. 错误处理和失败状态
3. 进度更新和阶段变化
4. URL验证错误等
"""

import requests
import json
import time
import threading
from typing import Dict, Any, List


class DetailedSSEAnalyzer:
    """详细的SSE状态分析器"""
    
    def __init__(self, url: str, data: Dict[str, Any]):
        self.url = url
        self.data = data
        self.events = []
        self.detailed_analysis = {}
        self.is_connected = False
        self.error = None
        
    def connect_and_analyze(self):
        """连接SSE并分析详细状态"""
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
            print(f"✅ SSE连接建立成功")
            
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
                self._analyze_event(event)
            except json.JSONDecodeError:
                print(f"⚠️ 无法解析JSON数据: {data}")
    
    def _analyze_event(self, event: Dict[str, Any]):
        """分析事件内容"""
        event_type = event['type']
        data = event['data']
        
        if event_type == 'status':
            self._analyze_status_event(data)
        elif event_type == 'completed':
            print(f"🎉 任务完成: {data.get('literature_id')}")
        elif event_type == 'failed':
            print(f"❌ 任务失败: {data.get('error')}")
    
    def _analyze_status_event(self, data: Dict[str, Any]):
        """分析状态事件的详细信息"""
        # 基本信息
        task_id = data.get('task_id')
        execution_status = data.get('execution_status')
        overall_progress = data.get('overall_progress', 0)
        current_stage = data.get('current_stage')
        
        print(f"📊 状态更新: {execution_status} - {overall_progress}% - {current_stage}")
        
        # 分析文献状态详情
        literature_status = data.get('literature_status')
        if literature_status:
            self._analyze_literature_status(literature_status)
        
        # 分析URL验证信息
        url_validation_status = data.get('url_validation_status')
        if url_validation_status:
            print(f"🔗 URL验证状态: {url_validation_status}")
            if data.get('url_validation_error'):
                print(f"   错误: {data.get('url_validation_error')}")
        
        # 分析错误信息
        error_info = data.get('error_info')
        if error_info:
            print(f"💥 错误信息: {error_info}")
    
    def _analyze_literature_status(self, lit_status: Dict[str, Any]):
        """分析文献状态的详细信息"""
        overall_status = lit_status.get('overall_status')
        overall_progress = lit_status.get('overall_progress', 0)
        
        print(f"   📚 文献状态: {overall_status} ({overall_progress}%)")
        
        # 分析各组件状态
        component_status = lit_status.get('component_status', {})
        for component_name, component_detail in component_status.items():
            if isinstance(component_detail, dict):
                status = component_detail.get('status', 'unknown')
                stage = component_detail.get('stage', 'N/A')
                progress = component_detail.get('progress', 0)
                error_info = component_detail.get('error_info')
                source = component_detail.get('source')
                attempts = component_detail.get('attempts', 0)
                
                print(f"     🔧 {component_name}: {status} ({progress}%) - {stage}")
                if source:
                    print(f"        来源: {source}")
                if attempts > 1:
                    print(f"        尝试次数: {attempts}")
                if error_info:
                    print(f"        错误: {error_info}")
    
    def generate_analysis_report(self):
        """生成详细分析报告"""
        print("\n" + "=" * 80)
        print("📋 SSE详细状态分析报告")
        print("=" * 80)
        
        print(f"📊 总事件数: {len(self.events)}")
        
        # 事件类型统计
        event_types = {}
        for event in self.events:
            event_type = event['type']
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        print(f"📈 事件类型分布:")
        for event_type, count in event_types.items():
            print(f"   - {event_type}: {count} 次")
        
        # 分析状态变化
        status_events = [e for e in self.events if e['type'] == 'status']
        if status_events:
            print(f"\n🔄 状态变化分析:")
            for i, event in enumerate(status_events, 1):
                data = event['data']
                execution_status = data.get('execution_status')
                progress = data.get('overall_progress', 0)
                stage = data.get('current_stage', 'N/A')
                timestamp = time.strftime('%H:%M:%S', time.localtime(event['timestamp']))
                
                print(f"   {i}. [{timestamp}] {execution_status} - {progress}% - {stage}")
        
        # 检查是否包含详细组件信息
        has_component_details = False
        has_error_details = False
        has_url_validation = False
        
        for event in status_events:
            data = event['data']
            lit_status = data.get('literature_status') or {}
            component_status = lit_status.get('component_status', {})
            
            if component_status:
                has_component_details = True
                
                # 检查是否有错误详情
                for comp_name, comp_detail in component_status.items():
                    if isinstance(comp_detail, dict) and comp_detail.get('error_info'):
                        has_error_details = True
            
            if data.get('url_validation_status'):
                has_url_validation = True
        
        print(f"\n✅ 功能覆盖检查:")
        print(f"   - 组件详细状态: {'✅' if has_component_details else '❌'}")
        print(f"   - 错误详情: {'✅' if has_error_details else '❌'}")
        print(f"   - URL验证信息: {'✅' if has_url_validation else '❌'}")
        
        return {
            'total_events': len(self.events),
            'event_types': event_types,
            'has_component_details': has_component_details,
            'has_error_details': has_error_details,
            'has_url_validation': has_url_validation
        }


def test_sse_with_new_literature():
    """测试SSE处理新文献的详细状态"""
    print("🧪 测试SSE处理新文献的详细状态")
    print("=" * 60)
    
    # 使用一个不太常见的DOI来触发完整的处理流程
    test_data = {
        "source": {
            "doi": "10.1145/3025453.3025718"  # 一个ACM的论文
        }
    }
    
    print(f"📝 提交测试数据: {json.dumps(test_data, indent=2)}")
    
    analyzer = DetailedSSEAnalyzer("http://localhost:8000/api/literature/stream", test_data)
    
    # 在单独线程中运行分析
    analysis_thread = threading.Thread(target=analyzer.connect_and_analyze)
    analysis_thread.daemon = True
    analysis_thread.start()
    
    # 等待分析完成
    analysis_thread.join(timeout=60)
    
    if analyzer.error:
        print(f"❌ 分析失败: {analyzer.error}")
        return False
    
    # 生成分析报告
    report = analyzer.generate_analysis_report()
    
    return report


def test_sse_with_url_error():
    """测试SSE处理URL错误的情况"""
    print("\n🧪 测试SSE处理URL错误")
    print("=" * 60)
    
    # 使用一个无效的URL来触发URL验证错误
    test_data = {
        "source": {
            "url": "https://invalid-url-that-does-not-exist.com/paper.pdf"
        }
    }
    
    print(f"📝 提交测试数据: {json.dumps(test_data, indent=2)}")
    
    analyzer = DetailedSSEAnalyzer("http://localhost:8000/api/literature/stream", test_data)
    
    analysis_thread = threading.Thread(target=analyzer.connect_and_analyze)
    analysis_thread.daemon = True
    analysis_thread.start()
    
    analysis_thread.join(timeout=30)
    
    if analyzer.error:
        print(f"❌ 分析失败: {analyzer.error}")
        return False
    
    report = analyzer.generate_analysis_report()
    return report


def main():
    """主测试函数"""
    print("🚀 开始SSE详细状态测试...")
    
    # 测试1: 正常文献处理
    report1 = test_sse_with_new_literature()
    
    # 测试2: URL错误处理
    # report2 = test_sse_with_url_error()
    
    print("\n" + "=" * 80)
    print("🎯 总结")
    print("=" * 80)
    
    if report1:
        print("✅ SSE详细状态功能验证:")
        print(f"   - 事件推送: {report1['total_events']} 个事件")
        print(f"   - 组件详情: {'包含' if report1['has_component_details'] else '缺失'}")
        print(f"   - 错误处理: {'包含' if report1['has_error_details'] else '缺失'}")
        print(f"   - URL验证: {'包含' if report1['has_url_validation'] else '缺失'}")
    else:
        print("❌ SSE详细状态测试失败")


if __name__ == "__main__":
    main()
