#!/usr/bin/env python3
"""
批量URL测试脚本
测试各种学术期刊URL的识别和处理能力
"""

import sys
import json
import time
import requests
from typing import List, Dict, Any
from dataclasses import dataclass, asdict

@dataclass
class TestResult:
    """测试结果数据类"""
    url: str
    adapter: str = "无"
    strategy: str = "无"
    doi: str = "无"
    venue: str = "无"
    confidence: float = 0.0
    mapping_success: bool = False
    crossref_valid: bool = False
    processing_success: bool = False
    processing_time: float = 0.0
    title: str = "无"
    year: str = "无"
    authors_count: int = 0
    references_count: int = 0
    error_message: str = ""

class URLBatchTester:
    """URL批量测试器"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.test_urls = [
            'https://arxiv.org/abs/2301.00001',
            'https://www.nature.com/articles/s41586-023-00001-0',
            'https://science.sciencemag.org/content/379/6628/123',
            'https://ieeexplore.ieee.org/document/10000001',
            'https://dl.acm.org/doi/10.1145/3000001.3000002',
            'https://link.springer.com/article/10.1007/s00000-023-00001-0',
            'https://www.cell.com/cell/fulltext/S0092-8674(23)00001-0',
            'https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0000001'
        ]
    
    def test_url_mapping(self, url: str) -> TestResult:
        """测试单个URL的映射能力"""
        result = TestResult(url=url)
        
        try:
            # 调用Docker容器内的URL映射服务
            import subprocess
            
            test_script = f'''
import sys
sys.path.insert(0, '/app')
from literature_parser_backend.services.url_mapper import get_url_mapping_service
import json

service = get_url_mapping_service()
mapping_result = service.map_url_sync("{url}")

output = {{
    "adapter": mapping_result.source_adapter or "无",
    "strategy": mapping_result.strategy_used or "无", 
    "doi": mapping_result.doi or "无",
    "venue": mapping_result.venue or "无",
    "confidence": mapping_result.confidence,
    "success": bool(mapping_result.doi or mapping_result.venue)
}}

print(json.dumps(output))
'''
            
            cmd = ['sudo', 'docker', 'exec', '-i', 'paper_paser_1-worker-1', 'python3', '-c', test_script]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if proc.returncode == 0:
                mapping_data = json.loads(proc.stdout.strip())
                result.adapter = mapping_data.get("adapter", "无")
                result.strategy = mapping_data.get("strategy", "无")
                result.doi = mapping_data.get("doi", "无")
                result.venue = mapping_data.get("venue", "无")
                result.confidence = mapping_data.get("confidence", 0.0)
                result.mapping_success = mapping_data.get("success", False)
            else:
                result.error_message = f"映射测试失败: {proc.stderr}"
                
        except Exception as e:
            result.error_message = f"映射测试异常: {str(e)}"
        
        return result
    
    def test_crossref_validity(self, doi: str) -> bool:
        """测试DOI在CrossRef中的有效性"""
        if doi == "无" or not doi:
            return False
            
        try:
            url = f"https://api.crossref.org/works/{doi}"
            response = requests.get(url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def test_full_processing(self, url: str) -> Dict[str, Any]:
        """测试完整的文献处理流程"""
        try:
            # 提交处理任务
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_base_url}/api/literature",
                json={"url": url},
                timeout=30
            )
            
            if response.status_code != 202:
                return {
                    "success": False,
                    "error": f"提交失败: HTTP {response.status_code}",
                    "processing_time": time.time() - start_time
                }
            
            task_data = response.json()
            task_id = task_data.get("task_id")
            
            if not task_id:
                return {
                    "success": False,
                    "error": "未获取到任务ID",
                    "processing_time": time.time() - start_time
                }
            
            # 等待处理完成
            max_wait = 60  # 最多等待60秒
            wait_time = 0
            
            while wait_time < max_wait:
                time.sleep(5)
                wait_time += 5
                
                status_response = requests.get(
                    f"{self.api_base_url}/api/task/{task_id}",
                    timeout=10
                )
                
                if status_response.status_code != 200:
                    continue
                
                status_data = status_response.json()
                execution_status = status_data.get("execution_status")
                
                if execution_status == "completed":
                    literature_id = status_data.get("literature_id")
                    
                    if literature_id:
                        # 获取文献详细信息
                        lit_response = requests.get(
                            f"{self.api_base_url}/api/literature/{literature_id}",
                            timeout=10
                        )
                        
                        if lit_response.status_code == 200:
                            lit_data = lit_response.json()
                            return {
                                "success": True,
                                "processing_time": time.time() - start_time,
                                "title": lit_data.get("title", "无"),
                                "year": lit_data.get("year", "无"),
                                "doi": lit_data.get("doi", "无"),
                                "authors_count": len(lit_data.get("authors", [])),
                                "references_count": len(lit_data.get("references", []))
                            }
                    
                    return {
                        "success": False,
                        "error": "处理完成但未获取到文献ID",
                        "processing_time": time.time() - start_time
                    }
                
                elif execution_status == "failed":
                    return {
                        "success": False,
                        "error": f"处理失败: {status_data.get('error_info', '未知错误')}",
                        "processing_time": time.time() - start_time
                    }
            
            return {
                "success": False,
                "error": "处理超时",
                "processing_time": time.time() - start_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"处理异常: {str(e)}",
                "processing_time": time.time() - start_time
            }
    
    def run_batch_test(self, test_full_processing: bool = False) -> List[TestResult]:
        """运行批量测试"""
        results = []
        
        print("🔍 开始批量URL测试...")
        print(f"📋 测试URL数量: {len(self.test_urls)}")
        print(f"🔧 完整处理测试: {'是' if test_full_processing else '否'}")
        print("=" * 80)
        
        for i, url in enumerate(self.test_urls, 1):
            print(f"\n测试 {i}/{len(self.test_urls)}: {url}")
            
            # 1. URL映射测试
            result = self.test_url_mapping(url)
            print(f"  📍 适配器: {result.adapter}")
            print(f"  🔧 策略: {result.strategy}")
            print(f"  📄 DOI: {result.doi}")
            print(f"  🏛️ 期刊: {result.venue}")
            print(f"  📊 置信度: {result.confidence}")
            
            # 2. CrossRef有效性测试
            if result.doi != "无":
                result.crossref_valid = self.test_crossref_validity(result.doi)
                print(f"  ✅ CrossRef有效: {'是' if result.crossref_valid else '否'}")
            
            # 3. 完整处理测试（可选）
            if test_full_processing and result.mapping_success:
                print(f"  🔄 开始完整处理测试...")
                processing_result = self.test_full_processing(url)
                
                result.processing_success = processing_result.get("success", False)
                result.processing_time = processing_result.get("processing_time", 0.0)
                
                if result.processing_success:
                    result.title = processing_result.get("title", "无")
                    result.year = str(processing_result.get("year", "无"))
                    result.authors_count = processing_result.get("authors_count", 0)
                    result.references_count = processing_result.get("references_count", 0)
                    
                    print(f"  📚 标题: {result.title[:50]}...")
                    print(f"  📅 年份: {result.year}")
                    print(f"  👥 作者数: {result.authors_count}")
                    print(f"  📖 参考文献数: {result.references_count}")
                    print(f"  ⏱️ 处理时间: {result.processing_time:.1f}秒")
                else:
                    result.error_message = processing_result.get("error", "未知错误")
                    print(f"  ❌ 处理失败: {result.error_message}")
            
            results.append(result)
        
        return results
    
    def generate_report(self, results: List[TestResult]) -> str:
        """生成测试报告"""
        total = len(results)
        mapping_success = sum(1 for r in results if r.mapping_success)
        crossref_valid = sum(1 for r in results if r.crossref_valid)
        processing_success = sum(1 for r in results if r.processing_success)
        
        report = f"""
📊 批量URL测试报告
{'=' * 50}

📈 总体统计:
  • 测试URL总数: {total}
  • URL映射成功: {mapping_success}/{total} ({mapping_success/total*100:.1f}%)
  • CrossRef有效: {crossref_valid}/{total} ({crossref_valid/total*100:.1f}%)
  • 完整处理成功: {processing_success}/{total} ({processing_success/total*100:.1f}%)

📋 详细结果:
"""
        
        for i, result in enumerate(results, 1):
            status_icons = []
            if result.mapping_success:
                status_icons.append("🔍")
            if result.crossref_valid:
                status_icons.append("✅")
            if result.processing_success:
                status_icons.append("📚")
            
            status = "".join(status_icons) if status_icons else "❌"
            
            report += f"""
{i}. {status} {result.url}
   适配器: {result.adapter} | 策略: {result.strategy}
   DOI: {result.doi}
   期刊: {result.venue} | 置信度: {result.confidence}
"""
            
            if result.processing_success:
                report += f"   标题: {result.title[:60]}...\n"
                report += f"   年份: {result.year} | 作者: {result.authors_count} | 参考文献: {result.references_count}\n"
            
            if result.error_message:
                report += f"   错误: {result.error_message}\n"
        
        return report

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="批量URL测试脚本")
    parser.add_argument("--full", action="store_true", help="执行完整处理测试")
    parser.add_argument("--output", type=str, help="输出报告到文件")
    
    args = parser.parse_args()
    
    tester = URLBatchTester()
    results = tester.run_batch_test(test_full_processing=args.full)
    report = tester.generate_report(results)
    
    print("\n" + report)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n📄 报告已保存到: {args.output}")

if __name__ == "__main__":
    main()
