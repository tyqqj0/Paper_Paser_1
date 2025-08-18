#!/usr/bin/env python3
"""
全面测试脚本 - 测试新瀑布流架构对各种学术网站链接的处理能力

测试覆盖：
- ArXiv: 有ID和无ID
- NeurIPS: 不同年份
- ACM Digital Library
- IEEE Xplore  
- SpringerLink
- 各种edge cases

Author: Paper Parser Team
Date: 2025-08-14
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Any
import aiohttp
import sys

# 测试用例配置
TEST_CASES = [
    # {
    #     "name": "ArXiv经典论文 - Transformer",
    #     "url": "https://arxiv.org/abs/1706.03762",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi", "arxiv_id", "high_quality"],
    #     "description": "有ArXiv ID的经典论文，应该优先使用Semantic Scholar"
    # },
    # {
    #     "name": "ArXiv最新论文 - Vision Transformer", 
    #     "url": "https://arxiv.org/abs/2010.11929",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["arxiv_id"],
    #     "description": "较新的ArXiv论文测试"
    # },
    # {
    #     "name": "NeurIPS 2012 - AlexNet",
    #     "url": "https://proceedings.neurips.cc/paper/2012/hash/c399862d3b9d6b76c8436e924a68c45b-Abstract.html",
    #     "expected_processor": "CrossRef",
    #     "expected_features": ["title_match", "no_doi"],
    #     "description": "经典的NeurIPS论文，无DOI，需要标题匹配"
    # },
    {
        "name": "Acceleration of stochastic approximation by averaging",
        "url": "https://doi.org/10.1137/0330046",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["doi"],
        "description": "经典的NeurIPS论文，有DOI"
    },
    # {
    #     "name": "NeurIPS 2017 - Attention论文",
    #     "url": "https://proceedings.neurips.cc/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html",
    #     "expected_processor": "CrossRef",
    #     "expected_features": ["title_match"],
    #     "description": "另一篇重要的NeurIPS论文"
    # },
    # {
    #     "name": "ACM Digital Library - 有DOI",
    #     "url": "https://dl.acm.org/doi/10.1145/3292500.3330958",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi"],
    #     "description": "ACM论文，有明确DOI"
    # },
    # {
    #     "name": "IEEE Xplore论文",
    #     "url": "https://ieeexplore.ieee.org/document/8578335",
    #     "expected_processor": "Site Parser",
    #     "expected_features": ["url_parsing"],
    #     "description": "IEEE论文测试"
    # },
    # {
    #     "name": "ArXiv PDF直链",
    #     "url": "https://arxiv.org/pdf/1706.03762.pdf",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["arxiv_id"],
    #     "description": "ArXiv PDF链接应该能提取ArXiv ID"
    # },
    {
        "name": "ResNet原论文 - 应该有DOI",
        "url": "https://arxiv.org/abs/1512.03385",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["doi", "arxiv_id"],
        "description": "经典ResNet论文，发表在CVPR，应该有DOI"
    },
    {
        "name": "ArXiv论文 - 有DOI和ArXiv ID",
        "url": "https://arxiv.org/abs/1412.6980",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["doi", "arxiv_id"],
        "description": "有DOI和ArXiv ID的论文"
    },
    
    # 🆕 扩展重要论文测试集
    {
        "name": "BERT - 自然语言处理里程碑",
        "url": "https://arxiv.org/abs/1810.04805",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["doi", "arxiv_id"],
        "description": "BERT论文，NLP领域重要突破"
    },
    # {
    #     "name": "GPT-1 原论文",
    #     "url": "https://s3-us-west-2.amazonaws.com/openai-assets/research-covers/language-unsupervised/language_understanding_paper.pdf",
    #     "expected_processor": "Site Parser",
    #     "expected_features": ["pdf_url"],
    #     "description": "GPT-1原论文，直接PDF链接"
    # },
    # {
    #     "name": "AlphaGo论文 - Nature",
    #     "url": "https://www.nature.com/articles/nature16961",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi"],
    #     "description": "AlphaGo突破性论文，发表在Nature"
    # },
    {
        "name": "GAN论文 - Ian Goodfellow",
        "url": "https://arxiv.org/abs/1406.2661",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["doi", "arxiv_id"],
        "description": "生成对抗网络原始论文"
    },
    {
        "name": "U-Net - 医学图像分割",
        "url": "https://arxiv.org/abs/1505.04597",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["doi", "arxiv_id"],
        "description": "U-Net架构，医学图像分割经典"
    },
    {
        "name": "Batch Normalization",
        "url": "https://arxiv.org/abs/1502.03167",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["doi", "arxiv_id"],
        "description": "批标准化论文，深度学习重要技术"
    },
    # {
    #     "name": "Dropout论文",
    #     "url": "https://jmlr.org/papers/v15/srivastava14a.html",
    #     "expected_processor": "Site Parser",
    #     "expected_features": ["title_match"],
    #     "description": "Dropout正则化技术论文"
    # },
    {
        "name": "Word2Vec - 词向量",
        "url": "https://arxiv.org/abs/1301.3781",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["arxiv_id"],
        "description": "Word2Vec词向量表示学习"
    },
    {
        "name": "Seq2Seq - 序列到序列",
        "url": "https://arxiv.org/abs/1409.3215",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["doi", "arxiv_id"],
        "description": "序列到序列学习论文"
    },
    {
        "name": "Adam优化器",
        "url": "https://arxiv.org/abs/1412.6980",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["arxiv_id"],
        "description": "Adam优化算法论文"
    },
    # {
    #     "name": "深度学习Nature综述 - LeCun",
    #     "url": "https://www.nature.com/articles/nature14539",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi"],
    #     "description": "深度学习Nature综述，LeCun等人"
    # },
    # {
    #     "name": "ImageNet大规模视觉识别",
    #     "url": "https://www.cv-foundation.org/openaccess/content_cvpr_2015/html/Russakovsky_ImageNet_Large_Scale_2015_CVPR_paper.html",
    #     "expected_processor": "Site Parser",
    #     "expected_features": ["title_match"],
    #     "description": "ImageNet数据集和竞赛的重要论文"
    # },
    {
        "name": "YOLO目标检测",
        "url": "https://arxiv.org/abs/1506.02640",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["doi", "arxiv_id"],
        "description": "YOLO实时目标检测算法"
    },
    {
        "name": "LSTM - 长短期记忆网络",
        "url": "https://www.bioinf.jku.at/publications/older/2604.pdf",
        "expected_processor": "Site Parser",
        "expected_features": ["pdf_url"],
        "description": "LSTM原始论文，1997年经典"
    },
    # {
    #     "name": "imagenet",
    #     "url": "https://doi.org/10.1145/3065386",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi"],
    #     "description": "ReLU激活函数的深入研究"
    # },
    # {
    #     "name": "ReLU激活函数研究",
    #     "url": "https://proceedings.mlr.press/v15/glorot11a.html",
    #     "expected_processor": "Site Parser",
    #     "expected_features": ["title_match"],
    #     "description": "ReLU激活函数的深入研究"
    # }
]

class TestResult:
    """测试结果数据类"""
    def __init__(self, test_case: Dict[str, Any]):
        self.test_case = test_case
        self.success = False
        self.literature_id = None
        self.processor_used = None
        self.metadata_quality = None
        self.processing_time = None
        self.error_message = None
        self.raw_response = None
        self.analysis = {}

class ComprehensiveTester:
    """全面测试器类"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[TestResult] = []
        self.session = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def test_single_url(self, test_case: Dict[str, Any]) -> TestResult:
        """测试单个URL"""
        result = TestResult(test_case)
        url = test_case["url"]
        
        print(f"\n🧪 测试: {test_case['name']}")
        print(f"   URL: {url}")
        print(f"   预期处理器: {test_case['expected_processor']}")
        
        start_time = time.time()
        
        try:
            # 发送解析请求
            async with self.session.post(
                f"{self.base_url}/api/resolve",
                json={"url": url},
                timeout=60
            ) as response:
                response_data = await response.json()
                
                if response.status == 202:
                    # 异步任务已创建，需要轮询状态
                    task_id = response_data.get("task_id")
                    if not task_id:
                        result.error_message = "No task_id in 202 response"
                        print(f"   ❌ 失败: {result.error_message}")
                        return result
                    
                    print(f"   ⏳ 任务已创建: {task_id}, 等待处理完成...")
                    
                    # 轮询任务状态直到完成
                    result = await self._poll_task_completion(result, task_id)
                    
                elif response.status == 200:
                    # 同步响应（如果有的话）
                    result.success = True
                    result.raw_response = response_data
                    
                    if isinstance(response_data, dict):
                        result.literature_id = response_data.get("lid")
                        if result.literature_id:
                            result = await self._get_literature_details(result)
                    
                    print(f"   ✅ 成功: LID={result.literature_id}")
                else:
                    result.error_message = f"HTTP {response.status}: {response_data}"
                    print(f"   ❌ 失败: {result.error_message}")
                    
        except Exception as e:
            result.error_message = str(e)
            print(f"   ❌ 异常: {result.error_message}")
        
        result.processing_time = time.time() - start_time
        return result
    
    async def _poll_task_completion(self, result: TestResult, task_id: str, max_wait: int = 60) -> TestResult:
        """轮询任务状态直到完成"""
        poll_start = time.time()
        
        while time.time() - poll_start < max_wait:
            try:
                async with self.session.get(
                    f"{self.base_url}/api/tasks/{task_id}"
                ) as response:
                    if response.status == 200:
                        task_status = await response.json()
                        status = task_status.get("status", "").lower()
                        
                        if status == "completed":
                            result_type = task_status.get("result_type")
                            result.literature_id = task_status.get("lid")
                            result.raw_response = task_status
                            result.success = True  # Mark as success regardless of type

                            if result_type == "duplicate":
                                print(f"   ✅ 成功 (副本): LID={result.literature_id}")
                            else:
                                print(f"   ✅ 成功 (创建): LID={result.literature_id}")

                            if result.literature_id:
                                result = await self._get_literature_details(result)
                            
                            return result
                            
                        elif status == "failed":
                            # 任务失败
                            error_msg = task_status.get("error_message", "Unknown error")
                            result.error_message = f"Task failed: {error_msg}"
                            print(f"   ❌ 任务失败: {error_msg}")
                            return result
                            
                        elif status in ["pending", "processing"]:
                            # 仍在处理中，继续等待
                            print(f"   ⏳ 处理中... ({status})")
                            await asyncio.sleep(2)
                            continue
                        else:
                            print(f"   ⚠️  未知状态: {status}")
                            await asyncio.sleep(2)
                            continue
                    else:
                        try:
                            error_json = await response.json()
                            print(f"   ⚠️  查询状态失败: HTTP {response.status}, 响应: {json.dumps(error_json, indent=2)}")
                            print(f"   ⚠️  完整响应: {await response.text()}")
                        except Exception:
                            error_text = await response.text()
                            print(f"   ⚠️  查询状态失败: HTTP {response.status}, 响应: {error_text}")
                        await asyncio.sleep(2)
                        continue
                        
            except Exception as e:
                print(f"   ⚠️  轮询异常: {e}")
                await asyncio.sleep(2)
                continue
        
        # 超时
        result.error_message = f"Task timeout after {max_wait}s"
        print(f"   ❌ 超时: 任务在{max_wait}秒内未完成")
        return result
    
    async def _get_literature_details(self, result: TestResult) -> TestResult:
        """获取文献详细信息并分析"""
        if not result.literature_id:
            return result
            
        try:
            async with self.session.get(
                f"{self.base_url}/api/literatures/{result.literature_id}"
            ) as response:
                if response.status == 200:
                    details = await response.json()
                    result = self._analyze_literature_details(result, details)
                else:
                    result.analysis["detail_fetch_error"] = f"HTTP {response.status}"
                    
        except Exception as e:
            result.analysis["detail_fetch_error"] = str(e)
            
        return result
    
    def _analyze_literature_details(self, result: TestResult, details: Dict[str, Any]) -> TestResult:
        """分析文献详细信息"""
        metadata = details.get("metadata", {})
        task_info = details.get("task_info", {})
        component_status = task_info.get("component_status", {})
        metadata_status = component_status.get("metadata", {})
        
        # 提取处理器信息
        result.processor_used = metadata_status.get("source", "Unknown")
        
        # 计算元数据质量分数
        result.metadata_quality = self._calculate_quality_score(metadata)
        
        # 验证预期特性
        result.analysis = self._verify_expected_features(result.test_case, details)
        
        # 打印分析结果
        print(f"   📊 处理器: {result.processor_used}")
        print(f"   📊 质量分数: {result.metadata_quality}/100")
        print(f"   📊 处理时间: {result.processing_time:.2f}s")
        
        # 验证预期
        expected_processor = result.test_case["expected_processor"]
        if result.processor_used == expected_processor:
            print(f"   ✅ 处理器匹配预期: {expected_processor}")
        else:
            print(f"   ⚠️  处理器不匹配: 预期{expected_processor}, 实际{result.processor_used}")
        
        return result
    
    def _calculate_quality_score(self, metadata: Dict[str, Any]) -> int:
        """计算元数据质量分数"""
        score = 0
        
        # 标题 (必须)
        title = metadata.get("title", "")
        if title and title != "Unknown Title":
            score += 25
        
        # 作者
        authors = metadata.get("authors", [])
        if authors:
            score += 20
        
        # 年份
        year = metadata.get("year")
        if year and year > 1900:
            score += 15
        
        # 期刊/会议
        journal = metadata.get("journal", "")
        if journal:
            score += 15
        
        # 摘要
        abstract = metadata.get("abstract", "")
        if abstract and len(abstract) > 50:
            score += 15
        
        # 关键词
        keywords = metadata.get("keywords", [])
        if keywords:
            score += 10
        
        return min(score, 100)
    
    def _verify_expected_features(self, test_case: Dict[str, Any], details: Dict[str, Any]) -> Dict[str, Any]:
        """验证预期特性"""
        analysis = {}
        expected_features = test_case.get("expected_features", [])
        
        identifiers = details.get("identifiers", {})
        metadata = details.get("metadata", {})
        
        for feature in expected_features:
            if feature == "doi":
                analysis["has_doi"] = bool(identifiers.get("doi"))
            elif feature == "arxiv_id":
                analysis["has_arxiv_id"] = bool(identifiers.get("arxiv_id"))
            elif feature == "high_quality":
                analysis["is_high_quality"] = self._calculate_quality_score(metadata) >= 80
            elif feature == "title_match":
                analysis["title_available"] = bool(metadata.get("title") and metadata["title"] != "Unknown Title")
            elif feature == "no_doi":
                analysis["correctly_no_doi"] = not bool(identifiers.get("doi"))
            elif feature == "url_parsing":
                analysis["url_processed"] = bool(details.get("identifiers", {}).get("source_urls"))
        
        return analysis
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("🚀 开始全面测试新瀑布流架构")
        print("=" * 60)
        
        start_time = time.time()
        
        # 运行所有测试用例
        for test_case in TEST_CASES:
            result = await self.test_single_url(test_case)
            self.results.append(result)
            
            # 添加延迟避免API限制
            await asyncio.sleep(1)
        
        total_time = time.time() - start_time
        
        # 生成测试报告
        report = self._generate_report(total_time)
        
        return report
    
    def _generate_report(self, total_time: float) -> Dict[str, Any]:
        """生成测试报告"""
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        
        processor_usage = {}
        quality_scores = []
        
        for result in self.results:
            if result.success:
                processor = result.processor_used or "Unknown"
                processor_usage[processor] = processor_usage.get(processor, 0) + 1
                if result.metadata_quality is not None:
                    quality_scores.append(result.metadata_quality)
        
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": f"{(successful_tests/total_tests)*100:.1f}%",
                "total_time": f"{total_time:.2f}s",
                "avg_quality_score": f"{avg_quality:.1f}/100"
            },
            "processor_usage": processor_usage,
            "detailed_results": []
        }
        
        # 添加详细结果
        for result in self.results:
            detailed = {
                "test_name": result.test_case["name"],
                "url": result.test_case["url"],
                "success": result.success,
                "lid": result.literature_id,
                "processor_used": result.processor_used,
                "metadata_quality": result.metadata_quality,
                "processing_time": f"{result.processing_time:.2f}s" if result.processing_time else None,
                "error_message": result.error_message,
                "analysis": result.analysis
            }
            report["detailed_results"].append(detailed)
        
        return report
    
    def print_report(self, report: Dict[str, Any]):
        """打印测试报告"""
        print("\n" + "=" * 60)
        print("📊 测试报告总结")
        print("=" * 60)
        
        summary = report["summary"]
        print(f"\n📈 总体统计:")
        print(f"   总测试数: {summary['total_tests']}")
        print(f"   成功测试: {summary['successful_tests']}")
        print(f"   成功率: {summary['success_rate']}")
        print(f"   总耗时: {summary['total_time']}")
        print(f"   平均质量分数: {summary['avg_quality_score']}")
        
        print(f"\n🔧 处理器使用统计:")
        for processor, count in report["processor_usage"].items():
            print(f"   {processor}: {count}次")
        
        print(f"\n📋 详细结果:")
        for result in report["detailed_results"]:
            status = "✅" if result["success"] else "❌"
            is_duplicate = result.get("raw_response", {}).get("result_type") == "duplicate"
            duplicate_marker = " (副本)" if is_duplicate else ""
            print(f"   {status} {result['test_name']}{duplicate_marker}")
            if result["success"]:
                print(f"      处理器: {result['processor_used']}")
                print(f"      质量: {result['metadata_quality']}/100")
                print(f"      时间: {result['processing_time']}")
            else:
                print(f"      错误: {result['error_message']}")

async def main():
    """主函数"""
    print("🎯 Paper Parser 新瀑布流架构全面测试")
    print("=" * 60)
    
    async with ComprehensiveTester() as tester:
        report = await tester.run_all_tests()
        tester.print_report(report)
        
        # 保存报告到文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"test_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 详细报告已保存到: {report_file}")

if __name__ == "__main__":
    # 检查Python版本
    if sys.version_info < (3, 7):
        print("❌ 需要Python 3.7或更高版本")
        sys.exit(1)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生错误: {e}")
        sys.exit(1)
