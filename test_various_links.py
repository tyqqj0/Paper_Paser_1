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
    {
        "name": "ArXiv经典论文 - Transformer",
        "url": "https://arxiv.org/abs/1706.03762",
        "expected_processor": "Semantic Scholar",
        "expected_features": ["doi", "arxiv_id", "high_quality"],
        "description": "有ArXiv ID的经典论文，应该优先使用Semantic Scholar"
    },
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
    # {
    #     "name": "Acceleration of stochastic approximation by averaging",
    #     "url": "https://doi.org/10.1137/0330046",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi"],
    #     "description": "经典的NeurIPS论文，有DOI"
    # },
    {
        "name": "NeurIPS 2017 - Attention论文",
        "url": "https://proceedings.neurips.cc/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html",
        "expected_processor": "CrossRef",
        "expected_features": ["title_match"],
        "description": "另一篇重要的NeurIPS论文"
    },
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
    #     "name": "ResNet原论文 - 应该有DOI",
    #     "url": "https://arxiv.org/abs/1512.03385",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi", "arxiv_id"],
    #     "description": "经典ResNet论文，发表在CVPR，应该有DOI"
    # },
    # {
    #     "name": "ArXiv论文 - 有DOI和ArXiv ID",
    #     "url": "https://arxiv.org/abs/1412.6980",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi", "arxiv_id"],
    #     "description": "有DOI和ArXiv ID的论文"
    # },
    
    # # 🆕 扩展重要论文测试集
    # {
    #     "name": "BERT - 自然语言处理里程碑",
    #     "url": "https://arxiv.org/abs/1810.04805",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi", "arxiv_id"],
    #     "description": "BERT论文，NLP领域重要突破"
    # },

    # {
    #     "name": "AlphaGo论文 - Nature",
    #     "url": "https://www.nature.com/articles/nature16961",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi"],
    #     "description": "AlphaGo突破性论文，发表在Nature"
    # },
    # {
    #     "name": "GAN论文 - Ian Goodfellow",
    #     "url": "https://arxiv.org/abs/1406.2661",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi", "arxiv_id"],
    #     "description": "生成对抗网络原始论文"
    # },
    # {
    #     "name": "U-Net - 医学图像分割",
    #     "url": "https://arxiv.org/abs/1505.04597",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi", "arxiv_id"],
    #     "description": "U-Net架构，医学图像分割经典"
    # },
    # {
    #     "name": "Batch Normalization",
    #     "url": "https://arxiv.org/abs/1502.03167",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi", "arxiv_id"],
    #     "description": "批标准化论文，深度学习重要技术"
    # },
    # {
    #     "name": "Word2Vec - 词向量",
    #     "url": "https://arxiv.org/abs/1301.3781",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["arxiv_id"],
    #     "description": "Word2Vec词向量表示学习"
    # },
    # {
    #     "name": "Seq2Seq - 序列到序列",
    #     "url": "https://arxiv.org/abs/1409.3215",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi", "arxiv_id"],
    #     "description": "序列到序列学习论文"
    # },
    # {
    #     "name": "Adam优化器",
    #     "url": "https://arxiv.org/abs/1412.6980",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["arxiv_id"],
    #     "description": "Adam优化算法论文"
    # },
    # {
    #     "name": "深度学习Nature综述 - LeCun",
    #     "url": "https://www.nature.com/articles/nature14539",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi"],
    #     "description": "深度学习Nature综述，LeCun等人"
    # },

    # {
    #     "name": "YOLO目标检测",
    #     "url": "https://arxiv.org/abs/1506.02640",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["doi", "arxiv_id"],
    #     "description": "YOLO实时目标检测算法"
    # },
    # {
    #     "name": "LSTM - 长短期记忆网络",
    #     "url": "https://ieeexplore.ieee.org/abstract/document/6795963",
    #     "expected_processor": "Site Parser",
    #     "expected_features": ["pdf_url"],
    #     "description": "LSTM原始论文，1997年经典"
    # },
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
    # },
    ############################## 暂时有问题的测试用例 ##############################
    #     {
    #     "name": "LSTM - 长短期记忆网络",
    #     "url": "https://www.bioinf.jku.at/publications/older/2604.pdf",
    #     "expected_processor": "Site Parser",
    #     "expected_features": ["pdf_url"],
    #     "description": "LSTM原始论文，1997年经典"
    # },
    #     {
    #     "name": "ImageNet大规模视觉识别",
    #     "url": "https://www.cv-foundation.org/openaccess/content_cvpr_2015/html/Russakovsky_ImageNet_Large_Scale_2015_CVPR_paper.html",
    #     "expected_processor": "Site Parser",
    #     "expected_features": ["title_match"],
    #     "description": "ImageNet数据集和竞赛的重要论文"
    # },
    #     {
    #     "name": "Dropout论文",
    #     "url": "https://jmlr.org/papers/v15/srivastava14a.html",
    #     "expected_processor": "Site Parser",
    #     "expected_features": ["title_match"],
    #     "description": "Dropout正则化技术论文"
    # },
    #     {
    #     "name": "GPT-1 原论文",
    #     "url": "https://s3-us-west-2.amazonaws.com/openai-assets/research-covers/language-unsupervised/language_understanding_paper.pdf",
    #     "expected_processor": "Site Parser",
    #     "expected_features": ["pdf_url"],
    #     "description": "GPT-1原论文，直接PDF链接"
    # },
        # {
    #     "name": "ArXiv PDF直链",
    #     "url": "https://arxiv.org/pdf/1706.03762.pdf",
    #     "expected_processor": "Semantic Scholar",
    #     "expected_features": ["arxiv_id"],
    #     "description": "ArXiv PDF链接应该能提取ArXiv ID"
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
        """测试单个URL - 使用SSE流式传输"""
        result = TestResult(test_case)
        url = test_case["url"]
        
        print(f"\n🧪 测试: {test_case['name']}")
        print(f"   URL: {url}")
        # print(f"   预期处理器: {test_case['expected_processor']}")
        
        start_time = time.time()
        
        try:
            # 首先提交解析请求获取task_id
            async with self.session.post(
                f"{self.base_url}/api/resolve",
                json={"url": url},
                timeout=30
            ) as response:
                response_data = await response.json()
                
                if response.status == 202:
                    # 获取任务ID
                    task_id = response_data.get("task_id")
                    if not task_id:
                        result.error_message = "No task_id in 202 response"
                        print(f"   ❌ 失败: {result.error_message}")
                        return result
                    
                    print(f"   ⏳ 任务已创建: {task_id}, 开始SSE流式监听...")
                    
                    # 使用SSE监听任务状态
                    result = await self._stream_task_completion(result, task_id)
                    
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
    
    async def _stream_task_completion(self, result: TestResult, task_id: str, max_wait: int = 60) -> TestResult:
        """使用SSE流式监听任务状态直到完成"""
        stream_start = time.time()
        
        try:
            # 建立SSE连接
            async with self.session.get(
                f"{self.base_url}/api/tasks/{task_id}/stream",
                headers={
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache",
                },
                timeout=aiohttp.ClientTimeout(total=max_wait+10)
            ) as response:
                
                if response.status != 200:
                    result.error_message = f"SSE连接失败: HTTP {response.status}"
                    print(f"   ❌ SSE连接失败: {result.error_message}")
                    return result
                
                print(f"   📡 SSE连接已建立，开始接收实时状态...")
                
                # 读取SSE流
                current_event_type = None
                async for line in response.content:
                    # 检查是否超时
                    if time.time() - stream_start > max_wait:
                        result.error_message = f"Task timeout after {max_wait}s"
                        print(f"   ❌ 超时: 任务在{max_wait}秒内未完成")
                        return result
                    
                    line_str = line.decode('utf-8').strip()
                    if not line_str:
                        continue
                    
                    # print(f"   🔍 SSE原始数据: {repr(line_str)}")
                    
                    # 解析SSE事件
                    if line_str.startswith('event:'):
                        current_event_type = line_str[6:].strip()
                        print(f"   📝 SSE事件类型: {current_event_type}")
                        continue
                    elif line_str.startswith('data:'):
                        data_str = line_str[5:].strip()
                        # print(f"   📝 SSE数据: {data_str}")
                        
                        try:
                            data = json.loads(data_str)
                            # print(f"   📝 SSE解析后数据: {data}")
                        except json.JSONDecodeError as e:
                            print(f"   ⚠️  SSE JSON解析失败: {e}")
                            continue
                        
                        # 处理不同类型的事件 - 使用从event行解析的类型
                        if current_event_type:
                            
                            if current_event_type == 'completed':
                                # 任务完成
                                result.literature_id = data.get('literature_id')
                                result.raw_response = data
                                
                                if result.literature_id:
                                    result.success = True
                                    print(f"   ✅ 成功完成: LID={result.literature_id}")
                                    result = await self._get_literature_details(result)
                                else:
                                    result.success = False
                                    result.error_message = "任务完成但未生成有效的文献ID"
                                    print(f"   ❌ 失败: 未生成有效LID")
                                
                                return result
                                
                            elif current_event_type in ['url_validation_failed', 'component_failed', 'task_failed', 'failed']:
                                # 任务失败
                                error_msg = data.get('error', data.get('error_message', 'Unknown error'))
                                error_type = data.get('error_type', 'Unknown')
                                result.error_message = f"Task failed: {error_msg}"
                                result.raw_response = data
                                
                                print(f"   ❌ 任务失败: {error_msg}")
                                print(f"   🔍 错误类型: {error_type}")
                                
                                # 根据错误类型提供更多信息
                                self._analyze_error_type(error_type, error_msg)
                                
                                return result
                                
                            elif current_event_type == 'progress':
                                # 进度更新事件
                                progress = data.get('progress', 0)
                                stage = data.get('stage', '')
                                print(f"   🔄 {stage} ({progress}%)")
                                # 重置事件类型，继续等待下一个事件
                                current_event_type = None
                                continue
                                
                        # 处理状态更新事件（带进度信息）- 兼容旧格式
                        elif 'task_id' in data and 'execution_status' in data:
                            execution_status = data.get('execution_status', '').lower()
                            overall_progress = data.get('overall_progress', 0)
                            current_stage = data.get('current_stage', '')
                            
                            print(f"   🔄 {current_stage} ({overall_progress}%)")
                            
                            if execution_status == 'completed':
                                # 从完整状态信息中提取结果
                                literature_status = data.get('literature_status', {})
                                if 'literature_id' in literature_status:
                                    result.literature_id = literature_status['literature_id']
                                    result.success = True
                                    result.raw_response = data
                                    print(f"   ✅ 成功完成: LID={result.literature_id}")
                                    result = await self._get_literature_details(result)
                                    return result
                            
                            elif execution_status == 'failed':
                                error_info = data.get('error_info', {})
                                error_msg = error_info.get('error_message', 'Unknown error')
                                error_type = error_info.get('error_type', 'Unknown')
                                result.error_message = f"Task failed: {error_msg}"
                                result.raw_response = data
                                
                                print(f"   ❌ 任务失败: {error_msg}")
                                print(f"   🔍 错误类型: {error_type}")
                                self._analyze_error_type(error_type, error_msg)
                                
                                return result
                        
        except asyncio.TimeoutError:
            result.error_message = f"SSE stream timeout after {max_wait}s"
            print(f"   ❌ SSE流超时: {result.error_message}")
            return result
        except Exception as e:
            result.error_message = f"SSE stream error: {e}"
            print(f"   ❌ SSE流异常: {result.error_message}")
            return result
        
        # 如果流结束但没有明确的完成或失败事件
        result.error_message = "SSE stream ended without completion"
        print(f"   ❌ SSE流异常结束")
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
        # print(f"   📊 处理器: {result.processor_used}")
        print(f"   📊 质量分数: {result.metadata_quality}/100")
        print(f"   📊 处理时间: {result.processing_time:.2f}s")
        
        # 验证预期
        expected_processor = result.test_case["expected_processor"]
        if result.processor_used == expected_processor:
            print(f"   ✅ 处理器匹配预期: {expected_processor}")
        else:
            print(f"   ⚠️  处理器不匹配: 预期{expected_processor}, 实际{result.processor_used}")
        
        return result
    
    def _analyze_error_type(self, error_type: str, error_msg: str):
        """根据错误类型提供详细分析和建议"""
        if error_type == "HTTPError":
            print(f"   💡 HTTP错误分析: 可能是URL无效、服务器不可达或权限问题")
            if "404" in error_msg:
                print(f"   📝 建议: 检查URL是否正确，文件是否存在")
            elif "403" in error_msg:
                print(f"   📝 建议: 可能需要访问权限或反爬虫限制")
            elif "timeout" in error_msg.lower():
                print(f"   📝 建议: 网络连接问题，可以稍后重试")
        
        elif error_type == "GROBIDConnectionError":
            print(f"   💡 GROBID服务错误: PDF解析服务不可用")
            print(f"   📝 建议: 检查GROBID服务状态，可能需要重启服务")
        
        elif error_type == "URLValidationError":
            print(f"   💡 URL格式错误: 输入的链接格式不正确")
            print(f"   📝 建议: 确保URL以http://或https://开头")
        
        elif error_type == "ParseError":
            print(f"   💡 解析错误: PDF内容无法正确解析")
            print(f"   📝 建议: 可能是扫描版PDF或格式特殊，尝试其他处理器")
        
        elif error_type == "TaskExecutionError":
            print(f"   💡 任务执行错误: Celery任务执行过程中出现问题")
            print(f"   📝 建议: 检查任务队列和worker状态")
        
        elif error_type == "Unknown":
            print(f"   💡 未知错误类型: 可能是新的错误类型或系统问题")
            print(f"   📝 建议: 检查完整错误日志，联系技术支持")
        
        else:
            print(f"   💡 错误类型 '{error_type}': 需要进一步分析")
            print(f"   📝 建议: 查看详细日志获取更多信息")
    
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
            
            # 添加错误类型信息（如果有的话）
            if not result.success and result.raw_response:
                detailed["error_type"] = result.raw_response.get("error_type", "Unknown")
            
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
                if "error_type" in result:
                    print(f"      类型: {result['error_type']}")
                    
        # 添加错误类型统计
        error_types = {}
        failed_results = [r for r in report["detailed_results"] if not r["success"]]
        
        if failed_results:
            print(f"\n🔍 错误类型统计:")
            for result in failed_results:
                error_type = result.get("error_type", "Unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            for error_type, count in error_types.items():
                print(f"   {error_type}: {count}次")

async def main():
    """主函数"""
    print("🎯 Paper Parser 新瀑布流架构全面测试")
    print("=" * 60)
    
    async with ComprehensiveTester() as tester:
        report = await tester.run_all_tests()
        tester.print_report(report)
        
        # 保存报告到文件
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # report_file = f"test_report_{timestamp}.json"
        
        # with open(report_file, 'w', encoding='utf-8') as f:
        #     json.dump(report, f, ensure_ascii=False, indent=2)
        
        # print(f"\n💾 详细报告已保存到: {report_file}")

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
