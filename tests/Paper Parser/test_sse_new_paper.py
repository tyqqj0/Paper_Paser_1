#!/usr/bin/env python3
"""
测试SSE处理全新文献的详细状态变化

使用一个全新的、系统中不存在的文献来触发完整的处理流程
"""

import requests
import json
import time
import threading
from typing import Dict, Any


class NewPaperSSEAnalyzer:
    """新文献SSE分析器"""
    
    def __init__(self, url: str, data: Dict[str, Any]):
        self.url = url
        self.data = data
        self.events = []
        self.is_connected = False
        self.error = None
        
    def connect_and_analyze(self):
        """连接SSE并分析"""
        try:
            response = requests.post(
                self.url,
                json=self.data,
                headers={
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache'
                },
                stream=True,
                timeout=120  # 增加超时时间
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
        """分析事件"""
        event_type = event['type']
        data = event['data']
        timestamp = time.strftime('%H:%M:%S', time.localtime(event['timestamp']))
        
        if event_type == 'status':
            execution_status = data.get('execution_status')
            progress = data.get('overall_progress', 0)
            stage = data.get('current_stage', 'N/A')
            
            print(f"[{timestamp}] 📊 {execution_status} - {progress}% - {stage}")
            
            # 分析文献状态详情
            literature_status = data.get('literature_status')
            if literature_status:
                self._print_literature_details(literature_status)
                
        elif event_type == 'completed':
            literature_id = data.get('literature_id')
            print(f"[{timestamp}] 🎉 任务完成! Literature ID: {literature_id}")
            
        elif event_type == 'failed':
            error = data.get('error', '未知错误')
            print(f"[{timestamp}] ❌ 任务失败: {error}")
    
    def _print_literature_details(self, lit_status: Dict[str, Any]):
        """打印文献状态详情"""
        overall_status = lit_status.get('overall_status')
        overall_progress = lit_status.get('overall_progress', 0)
        
        print(f"    📚 文献整体: {overall_status} ({overall_progress}%)")
        
        # 打印各组件状态
        component_status = lit_status.get('component_status', {})
        for comp_name, comp_detail in component_status.items():
            if isinstance(comp_detail, dict):
                status = comp_detail.get('status', 'unknown')
                stage = comp_detail.get('stage', 'N/A')
                progress = comp_detail.get('progress', 0)
                source = comp_detail.get('source')
                error_info = comp_detail.get('error_info')
                
                status_icon = {
                    'pending': '⏳',
                    'processing': '🔄',
                    'success': '✅',
                    'failed': '❌'
                }.get(status, '❓')
                
                print(f"      {status_icon} {comp_name}: {status} ({progress}%) - {stage}")
                if source and source != "未知来源":
                    print(f"         来源: {source}")
                if error_info:
                    print(f"         错误: {error_info}")
    
    def generate_summary(self):
        """生成摘要"""
        print("\n" + "=" * 70)
        print("📋 处理过程摘要")
        print("=" * 70)
        
        print(f"📊 总事件数: {len(self.events)}")
        
        # 统计各阶段
        stages_seen = set()
        components_seen = set()
        error_count = 0
        
        for event in self.events:
            if event['type'] == 'status':
                data = event['data']
                stage = data.get('current_stage')
                if stage:
                    stages_seen.add(stage)
                
                lit_status = data.get('literature_status')
                if lit_status:
                    comp_status = lit_status.get('component_status', {})
                    for comp_name, comp_detail in comp_status.items():
                        if isinstance(comp_detail, dict):
                            components_seen.add(comp_name)
                            if comp_detail.get('error_info'):
                                error_count += 1
        
        print(f"🔄 处理阶段: {len(stages_seen)} 个")
        for stage in sorted(stages_seen):
            print(f"   - {stage}")
        
        print(f"🔧 涉及组件: {len(components_seen)} 个")
        for comp in sorted(components_seen):
            print(f"   - {comp}")
        
        print(f"💥 错误次数: {error_count}")
        
        return {
            'total_events': len(self.events),
            'stages_count': len(stages_seen),
            'components_count': len(components_seen),
            'error_count': error_count
        }


def test_new_paper_processing():
    """测试新文献的完整处理流程"""
    print("🧪 测试新文献的完整SSE处理流程")
    print("=" * 70)
    
    # 使用一个相对较新的arXiv论文，可能系统中还没有
    test_data = {
        "source": {
            "arxiv_id": "2501.12345",  # 使用一个不存在的arXiv ID
            "title": "Test Paper for SSE Analysis",
            "authors": ["Test Author"]
        }
    }
    
    print(f"📝 提交测试数据: {json.dumps(test_data, indent=2)}")
    
    analyzer = NewPaperSSEAnalyzer("http://localhost:8000/api/literature/stream", test_data)
    
    # 在单独线程中运行
    analysis_thread = threading.Thread(target=analyzer.connect_and_analyze)
    analysis_thread.daemon = True
    analysis_thread.start()
    
    print("⏳ 等待处理完成...")
    analysis_thread.join(timeout=120)
    
    if analyzer.error:
        print(f"❌ 处理失败: {analyzer.error}")
        return False
    
    # 生成摘要
    summary = analyzer.generate_summary()
    return summary


def test_with_real_new_arxiv():
    """使用真实的新arXiv论文测试"""
    print("\n🧪 测试真实的新arXiv论文")
    print("=" * 70)
    
    # 使用一个最近的arXiv论文
    test_data = {
        "source": {
            "url": "https://arxiv.org/abs/2501.18585"  # 一个2025年1月的论文
        }
    }
    
    print(f"📝 提交测试数据: {json.dumps(test_data, indent=2)}")
    
    analyzer = NewPaperSSEAnalyzer("http://localhost:8000/api/literature/stream", test_data)
    
    analysis_thread = threading.Thread(target=analyzer.connect_and_analyze)
    analysis_thread.daemon = True
    analysis_thread.start()
    
    print("⏳ 等待处理完成...")
    analysis_thread.join(timeout=120)
    
    if analyzer.error:
        print(f"❌ 处理失败: {analyzer.error}")
        return False
    
    summary = analyzer.generate_summary()
    return summary


def main():
    """主测试函数"""
    print("🚀 开始新文献SSE详细测试...")
    
    # 测试1: 使用不存在的arXiv ID（会触发错误处理）
    # summary1 = test_new_paper_processing()
    
    # 测试2: 使用真实的新arXiv论文
    summary2 = test_with_real_new_arxiv()
    
    print("\n" + "=" * 70)
    print("🎯 测试总结")
    print("=" * 70)
    
    if summary2:
        print("✅ 新文献SSE处理验证:")
        print(f"   - 事件数量: {summary2['total_events']}")
        print(f"   - 处理阶段: {summary2['stages_count']}")
        print(f"   - 涉及组件: {summary2['components_count']}")
        print(f"   - 错误次数: {summary2['error_count']}")
        
        if summary2['stages_count'] > 2:
            print("✅ 包含详细的处理阶段")
        else:
            print("⚠️ 处理阶段较少，可能是重复文献")
            
        if summary2['components_count'] >= 3:
            print("✅ 包含所有主要组件状态")
        else:
            print("⚠️ 组件状态信息不完整")
    else:
        print("❌ 新文献SSE测试失败")


if __name__ == "__main__":
    main()
