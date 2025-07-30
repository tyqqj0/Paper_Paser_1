#!/usr/bin/env python3
"""
测试arXiv API修复效果

验证新增的arXiv Official API是否能正确获取元数据
"""

import requests
import json
import time
import threading
from typing import Dict, Any


class ArXivAPIFixTester:
    """arXiv API修复测试器"""
    
    def __init__(self):
        self.events = []
        self.metadata_sources = []
        self.final_literature_data = None
        self.is_connected = False
        self.error = None
        
    def test_arxiv_api_fix(self, arxiv_url: str):
        """测试arXiv API修复效果"""
        print(f"🧪 测试arXiv API修复: {arxiv_url}")
        print("=" * 70)
        
        # 1. 首先测试arXiv官方API直接调用
        print("🔍 步骤1: 测试arXiv官方API直接调用")
        self._test_direct_arxiv_api(arxiv_url)
        
        # 2. 测试我们的SSE端点
        print(f"\n🔍 步骤2: 测试我们的SSE端点处理")
        self._test_our_sse_endpoint(arxiv_url)
        
        # 3. 分析最终结果
        print(f"\n🔍 步骤3: 分析处理结果")
        self._analyze_results()
    
    def _test_direct_arxiv_api(self, arxiv_url: str):
        """直接测试arXiv API"""
        # 提取arXiv ID
        arxiv_id = None
        if 'arxiv.org/abs/' in arxiv_url:
            arxiv_id = arxiv_url.split('arxiv.org/abs/')[-1]
        
        if not arxiv_id:
            print("❌ 无法从URL中提取arXiv ID")
            return
        
        print(f"📋 arXiv ID: {arxiv_id}")
        
        try:
            # 调用arXiv官方API
            api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                print("✅ arXiv官方API响应成功")
                
                # 解析响应
                content = response.text
                
                # 提取标题
                if '<title>' in content:
                    title_start = content.find('<title>') + 7
                    title_end = content.find('</title>', title_start)
                    title = content[title_start:title_end].strip()
                    print(f"   📝 标题: {title}")
                
                # 提取作者数量
                author_count = content.count('<name>')
                print(f"   👥 作者数量: {author_count}")
                
                # 提取摘要长度
                if '<summary>' in content:
                    summary_start = content.find('<summary>') + 9
                    summary_end = content.find('</summary>', summary_start)
                    summary = content[summary_start:summary_end].strip()
                    print(f"   📄 摘要长度: {len(summary)} 字符")
                
                print("✅ arXiv官方API能够正常获取元数据")
            else:
                print(f"❌ arXiv官方API响应失败: {response.status_code}")
                
        except Exception as e:
            print(f"❌ arXiv官方API测试异常: {e}")
    
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
                timeout=90  # 增加超时时间
            )
            
            if response.status_code != 200:
                self.error = f"HTTP {response.status_code}: {response.text}"
                print(f"❌ SSE连接失败: {self.error}")
                return
            
            self.is_connected = True
            print("✅ SSE连接建立成功")
            print("\n📊 处理过程监控:")
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
            
            # 重点关注元数据组件
            lit_status = data.get('literature_status')
            if lit_status:
                comp_status = lit_status.get('component_status', {})
                metadata_comp = comp_status.get('metadata')
                
                if metadata_comp:
                    meta_status = metadata_comp.get('status')
                    meta_stage = metadata_comp.get('stage', 'N/A')
                    meta_source = metadata_comp.get('source')
                    
                    if meta_source and meta_source not in self.metadata_sources:
                        self.metadata_sources.append(meta_source)
                        print(f"           🔍 元数据来源: {meta_source}")
                    
                    if meta_status == 'success' and meta_source:
                        print(f"           ✅ 元数据获取成功，来源: {meta_source}")
                        
        elif event_type == 'completed':
            literature_id = data.get('literature_id')
            print(f"[{timestamp}] 🎉 任务完成! Literature ID: {literature_id}")
            self.literature_id = literature_id
            
        elif event_type == 'error':
            error_msg = data.get('error', '未知错误')
            error_type = data.get('error_type', 'UnknownError')
            print(f"[{timestamp}] ❌ 错误: {error_type} - {error_msg}")
    
    def _analyze_results(self):
        """分析最终结果"""
        if not hasattr(self, 'literature_id'):
            print("❌ 任务未完成，无法分析结果")
            return
        
        try:
            # 获取最终的文献数据
            response = requests.get(f"http://localhost:8000/api/literature/{self.literature_id}")
            
            if response.status_code == 200:
                self.final_literature_data = response.json()
                
                print("📋 最终文献数据分析:")
                print(f"   📝 标题: {self.final_literature_data.get('title', 'N/A')}")
                print(f"   👥 作者数量: {len(self.final_literature_data.get('authors', []))}")
                print(f"   🔗 DOI: {self.final_literature_data.get('doi', 'N/A')}")
                print(f"   📄 arXiv ID: {self.final_literature_data.get('arxiv_id', 'N/A')}")
                print(f"   📅 年份: {self.final_literature_data.get('year', 'N/A')}")
                
                abstract = self.final_literature_data.get('abstract', '')
                print(f"   📖 摘要长度: {len(abstract) if abstract else 0} 字符")
                
                # 检查标题质量
                title = self.final_literature_data.get('title', '')
                if title.startswith('Processing:') or title.startswith('https://'):
                    print("   ❌ 标题质量差，仍然是URL格式")
                else:
                    print("   ✅ 标题质量良好")
                
            else:
                print(f"❌ 无法获取文献数据: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 分析结果异常: {e}")
    
    def generate_fix_report(self):
        """生成修复效果报告"""
        print("\n" + "=" * 70)
        print("🔬 arXiv API修复效果报告")
        print("=" * 70)
        
        print(f"📊 处理统计:")
        print(f"   - 总事件数: {len(self.events)}")
        print(f"   - SSE连接: {'✅ 成功' if self.is_connected else '❌ 失败'}")
        print(f"   - 元数据来源: {self.metadata_sources}")
        
        # 评估修复效果
        fix_success = False
        
        if self.final_literature_data:
            title = self.final_literature_data.get('title', '')
            authors = self.final_literature_data.get('authors', [])
            abstract = self.final_literature_data.get('abstract', '')
            
            # 检查是否使用了arXiv API
            used_arxiv_api = 'arXiv Official API' in self.metadata_sources or 'arxiv_api' in self.metadata_sources
            
            # 检查数据质量
            good_title = not (title.startswith('Processing:') or title.startswith('https://'))
            has_authors = len(authors) > 0
            has_abstract = len(abstract) > 100  # 至少100字符的摘要
            
            print(f"\n🎯 修复效果评估:")
            print(f"   - 使用arXiv API: {'✅' if used_arxiv_api else '❌'}")
            print(f"   - 标题质量: {'✅' if good_title else '❌'}")
            print(f"   - 包含作者: {'✅' if has_authors else '❌'}")
            print(f"   - 包含摘要: {'✅' if has_abstract else '❌'}")
            
            fix_success = used_arxiv_api and good_title and has_authors and has_abstract
            
            if fix_success:
                print("\n🎉 arXiv API修复成功！")
                print("   系统现在能够正确获取arXiv论文的完整元数据")
            else:
                print("\n⚠️ arXiv API修复部分成功")
                print("   仍有一些问题需要进一步调试")
        else:
            print("\n❌ 无法评估修复效果，任务未完成")
        
        return fix_success


def main():
    """主测试函数"""
    print("🚀 开始arXiv API修复效果测试...")
    
    tester = ArXivAPIFixTester()
    
    # 测试一个新的arXiv论文
    arxiv_url = "https://arxiv.org/abs/2301.00003"  # 使用一个不同的ID
    tester.test_arxiv_api_fix(arxiv_url)
    
    # 生成修复报告
    success = tester.generate_fix_report()
    
    if success:
        print("\n✅ arXiv元数据获取问题已修复！")
    else:
        print("\n⚠️ 需要进一步调试arXiv API集成")


if __name__ == "__main__":
    main()
