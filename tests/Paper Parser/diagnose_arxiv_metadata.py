#!/usr/bin/env python3
"""
诊断arXiv论文元数据获取问题

分析为什么 https://arxiv.org/abs/2301.00001 无法正确获取元数据
"""

import requests
import json
import time
import threading
from typing import Dict, Any


class ArXivMetadataDiagnoser:
    """arXiv元数据诊断器"""
    
    def __init__(self):
        self.events = []
        self.metadata_details = {}
        self.is_connected = False
        self.error = None
        
    def diagnose_arxiv_paper(self, arxiv_url: str):
        """诊断arXiv论文的元数据获取"""
        print(f"🔍 诊断arXiv论文: {arxiv_url}")
        print("=" * 70)
        
        # 1. 首先测试直接的arXiv API
        arxiv_id = self._extract_arxiv_id(arxiv_url)
        if arxiv_id:
            print(f"📋 提取的arXiv ID: {arxiv_id}")
            self._test_arxiv_api(arxiv_id)
        
        # 2. 测试我们的SSE端点
        print(f"\n🧪 测试我们的SSE端点...")
        self._test_our_sse_endpoint(arxiv_url)
        
        # 3. 获取最终的文献数据进行分析
        if hasattr(self, 'literature_id') and self.literature_id:
            print(f"\n📖 分析最终文献数据...")
            self._analyze_final_literature_data(self.literature_id)
    
    def _extract_arxiv_id(self, url: str) -> str:
        """从URL中提取arXiv ID"""
        if 'arxiv.org/abs/' in url:
            return url.split('arxiv.org/abs/')[-1]
        return None
    
    def _test_arxiv_api(self, arxiv_id: str):
        """测试arXiv官方API"""
        print(f"🌐 测试arXiv官方API...")
        
        try:
            # arXiv API URL
            api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                print("✅ arXiv API响应成功")
                
                # 简单解析XML响应
                content = response.text
                if '<title>' in content and '</title>' in content:
                    title_start = content.find('<title>') + 7
                    title_end = content.find('</title>', title_start)
                    title = content[title_start:title_end].strip()
                    print(f"   📝 标题: {title}")
                
                if '<summary>' in content and '</summary>' in content:
                    summary_start = content.find('<summary>') + 9
                    summary_end = content.find('</summary>', summary_start)
                    summary = content[summary_start:summary_end].strip()
                    print(f"   📄 摘要: {summary[:100]}...")
                
                # 检查作者信息
                author_count = content.count('<name>')
                print(f"   👥 作者数量: {author_count}")
                
            else:
                print(f"❌ arXiv API响应失败: {response.status_code}")
                
        except Exception as e:
            print(f"❌ arXiv API测试异常: {e}")
    
    def _test_our_sse_endpoint(self, arxiv_url: str):
        """测试我们的SSE端点"""
        test_data = {
            "source": {
                "url": arxiv_url
            }
        }
        
        try:
            response = requests.post(
                "http://localhost:8000/api/literature/stream",
                json=test_data,
                headers={
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache'
                },
                stream=True,
                timeout=60
            )
            
            if response.status_code != 200:
                self.error = f"HTTP {response.status_code}: {response.text}"
                print(f"❌ SSE连接失败: {self.error}")
                return
            
            self.is_connected = True
            print("✅ SSE连接建立成功")
            print("\n📊 处理过程分析:")
            print("-" * 50)
            
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    self._process_sse_line(line)
                    
        except Exception as e:
            self.error = str(e)
            print(f"❌ SSE测试异常: {e}")
    
    def _process_sse_line(self, line: str):
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
                self._analyze_sse_event(event)
            except json.JSONDecodeError:
                print(f"⚠️ 无法解析JSON数据: {data}")
    
    def _analyze_sse_event(self, event: Dict[str, Any]):
        """分析SSE事件"""
        event_type = event['type']
        data = event['data']
        timestamp = time.strftime('%H:%M:%S', time.localtime(event['timestamp']))
        
        if event_type == 'status':
            execution_status = data.get('execution_status')
            stage = data.get('current_stage', 'N/A')
            progress = data.get('overall_progress', 0)
            
            print(f"[{timestamp}] 📊 {execution_status} - {progress}% - {stage}")
            
            # 分析文献状态详情
            lit_status = data.get('literature_status')
            if lit_status:
                comp_status = lit_status.get('component_status', {})
                
                # 重点关注metadata组件
                metadata_comp = comp_status.get('metadata')
                if metadata_comp:
                    meta_status = metadata_comp.get('status')
                    meta_stage = metadata_comp.get('stage', 'N/A')
                    meta_source = metadata_comp.get('source', 'N/A')
                    meta_error = metadata_comp.get('error_info')
                    
                    print(f"           🔍 元数据: {meta_status} - {meta_stage} - 来源: {meta_source}")
                    if meta_error:
                        print(f"           ❌ 元数据错误: {meta_error}")
                    
                    self.metadata_details = metadata_comp
                
        elif event_type == 'completed':
            literature_id = data.get('literature_id')
            print(f"[{timestamp}] 🎉 任务完成! Literature ID: {literature_id}")
            self.literature_id = literature_id
            
        elif event_type == 'error':
            error_msg = data.get('error', '未知错误')
            error_type = data.get('error_type', 'UnknownError')
            print(f"[{timestamp}] ❌ 错误: {error_type} - {error_msg}")
    
    def _analyze_final_literature_data(self, literature_id: str):
        """分析最终的文献数据"""
        try:
            response = requests.get(f"http://localhost:8000/api/literature/{literature_id}")
            
            if response.status_code == 200:
                lit_data = response.json()
                
                print("📋 最终文献数据分析:")
                print(f"   📝 标题: {lit_data.get('title', 'N/A')}")
                print(f"   👥 作者: {lit_data.get('authors', [])}")
                print(f"   🔗 DOI: {lit_data.get('doi', 'N/A')}")
                print(f"   📄 arXiv ID: {lit_data.get('arxiv_id', 'N/A')}")
                print(f"   📅 发布日期: {lit_data.get('published_date', 'N/A')}")
                print(f"   📖 摘要长度: {len(lit_data.get('abstract', '')) if lit_data.get('abstract') else 0} 字符")
                
                # 分析标识符
                identifiers = lit_data.get('identifiers', {})
                print(f"   🏷️ 标识符: {identifiers}")
                
                # 分析元数据来源
                metadata = lit_data.get('metadata', {})
                if metadata:
                    print(f"   📊 元数据字段数: {len(metadata)}")
                    print(f"   📊 元数据键: {list(metadata.keys())}")
                
                # 检查是否有处理历史
                task_info = lit_data.get('task_info', {})
                if task_info:
                    print(f"   ⚙️ 任务状态: {task_info.get('status', 'N/A')}")
                    print(f"   ⚙️ 完成时间: {task_info.get('completed_at', 'N/A')}")
                
                return lit_data
            else:
                print(f"❌ 无法获取文献数据: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 分析文献数据异常: {e}")
        
        return None
    
    def generate_diagnosis_report(self):
        """生成诊断报告"""
        print("\n" + "=" * 70)
        print("🔬 诊断报告")
        print("=" * 70)
        
        print(f"📊 处理统计:")
        print(f"   - 总事件数: {len(self.events)}")
        print(f"   - SSE连接: {'✅ 成功' if self.is_connected else '❌ 失败'}")
        
        if self.metadata_details:
            print(f"\n🔍 元数据组件详情:")
            print(f"   - 状态: {self.metadata_details.get('status', 'N/A')}")
            print(f"   - 阶段: {self.metadata_details.get('stage', 'N/A')}")
            print(f"   - 来源: {self.metadata_details.get('source', 'N/A')}")
            print(f"   - 尝试次数: {self.metadata_details.get('attempts', 'N/A')}")
            
            if self.metadata_details.get('error_info'):
                print(f"   - 错误信息: {self.metadata_details['error_info']}")
        
        # 问题分析
        print(f"\n🎯 问题分析:")
        
        if self.metadata_details.get('source') == 'fallback':
            print("⚠️ 元数据使用了fallback来源，说明主要API都失败了")
            print("   可能原因:")
            print("   1. CrossRef API无法找到该论文")
            print("   2. Semantic Scholar API无法找到该论文")
            print("   3. GROBID解析PDF失败")
            print("   4. 系统回退到了基础的URL解析")
        
        if hasattr(self, 'literature_id'):
            print(f"✅ 任务完成，但元数据质量可能有问题")
            print(f"   建议检查各个API的响应和错误日志")
        else:
            print(f"❌ 任务未完成或出现严重错误")


def main():
    """主诊断函数"""
    print("🚀 开始arXiv元数据诊断...")
    
    diagnoser = ArXivMetadataDiagnoser()
    
    # 诊断问题论文
    arxiv_url = "https://arxiv.org/abs/2301.00001"
    diagnoser.diagnose_arxiv_paper(arxiv_url)
    
    # 生成诊断报告
    diagnoser.generate_diagnosis_report()


if __name__ == "__main__":
    main()
