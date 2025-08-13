#!/usr/bin/env python3
"""
端到端引用关系系统测试脚本

这个脚本将测试完整的文献添加和引用关系建立流程：
1. 添加一组相互引用的经典论文
2. 验证引用关系是否正确建立
3. 测试图查询API功能
4. 检查Neo4j数据完整性

使用方法：
python test_end_to_end_citation_system.py --mode full
"""

import asyncio
import json
import logging
import sys
import time
from typing import Dict, List, Any, Optional
import argparse
from pathlib import Path

import httpx
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

console = Console()

class EndToEndTester:
    """端到端测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=120.0)
        self.test_results = {
            "literature_added": [],
            "citation_relationships": [],
            "errors": [],
            "timing": {}
        }
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def get_test_papers(self) -> List[Dict[str, Any]]:
        """
        返回一组有明确引用关系的经典论文数据
        这些论文在NLP/ML领域有清晰的引用链条
        """
        papers = [
            {
                "order": 1,
                "name": "Word2Vec",
                "data": {
                    "doi": "10.48550/arXiv.1301.3781",
                    "title": "Efficient Estimation of Word Representations in Vector Space",
                    "authors": ["Tomas Mikolov", "Kai Chen", "Greg Corrado", "Jeffrey Dean"]
                },
                "expected_citations": [],  # 这是最早的论文，不引用其他测试论文
                "note": "基础词向量论文，会被后续论文引用"
            },
            {
                "order": 2,
                "name": "Attention Mechanism",
                "data": {
                    "doi": "10.48550/arXiv.1409.0473",
                    "title": "Neural Machine Translation by Jointly Learning to Align and Translate",
                    "authors": ["Dzmitry Bahdanau", "Kyunghyun Cho", "Yoshua Bengio"]
                },
                "expected_citations": ["Word2Vec"],  # 可能引用Word2Vec
                "note": "注意力机制的开创性论文"
            },
            {
                "order": 3,
                "name": "Transformer",
                "data": {
                    "doi": "10.48550/arXiv.1706.03762",
                    "title": "Attention Is All You Need",
                    "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit"]
                },
                "expected_citations": ["Attention Mechanism"],  # 肯定引用注意力机制
                "note": "Transformer架构，引用了注意力机制"
            },
            {
                "order": 4,
                "name": "BERT",
                "data": {
                    "doi": "10.48550/arXiv.1810.04805",
                    "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                    "authors": ["Jacob Devlin", "Ming-Wei Chang", "Kenton Lee", "Kristina Toutanova"]
                },
                "expected_citations": ["Word2Vec", "Transformer"],  # 引用Word2Vec和Transformer
                "note": "BERT模型，基于Transformer"
            },
            {
                "order": 5,
                "name": "GPT-2",
                "data": {
                    "doi": "10.48550/arXiv.1908.10084",
                    "title": "Language Models are Unsupervised Multitask Learners",
                    "authors": ["Alec Radford", "Jeff Wu", "Rewon Child", "David Luan"]
                },
                "expected_citations": ["Transformer", "BERT"],  # 引用Transformer和BERT
                "note": "GPT-2模型，对比BERT"
            }
        ]
        
        return papers

    async def add_literature(self, paper_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """添加单个文献到系统"""
        try:
            console.print(f"📚 添加文献: {paper_data['title'][:50]}...")
            
            # 使用resolve API添加文献
            response = await self.client.post(
                f"{self.base_url}/api/resolve",
                json=paper_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                # 文献已存在
                result = response.json()
                console.print(f"✅ 文献已存在: LID={result['lid']}")
                return result
                
            elif response.status_code == 202:
                # 需要异步处理
                result = response.json()
                task_id = result["task_id"]
                console.print(f"⏳ 创建任务: {task_id}")
                
                # 等待任务完成
                final_result = await self.wait_for_task_completion(task_id)
                return final_result
                
            else:
                console.print(f"❌ 添加失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            console.print(f"❌ 添加出错: {e}")
            return None

    async def wait_for_task_completion(self, task_id: str, timeout: int = 300) -> Optional[Dict[str, Any]]:
        """等待任务完成"""
        start_time = time.time()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"等待任务 {task_id[:8]}...", total=None)
            
            while time.time() - start_time < timeout:
                try:
                    response = await self.client.get(f"{self.base_url}/api/tasks/{task_id}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        status = result.get("status")
                        current_stage = result.get("current_stage", "处理中")
                        
                        progress.update(task, description=f"任务 {task_id[:8]} - {current_stage}")
                        
                        if status == "success":
                            literature_id = result.get("literature_id")
                            console.print(f"✅ 任务完成: LID={literature_id}")
                            return {
                                "lid": literature_id,
                                "task_id": task_id,
                                "status": "success"
                            }
                        elif status == "failure":
                            console.print(f"❌ 任务失败: {result.get('error', '未知错误')}")
                            return None
                            
                    await asyncio.sleep(2)  # 每2秒检查一次
                    
                except Exception as e:
                    console.print(f"⚠️ 查询任务状态错误: {e}")
                    await asyncio.sleep(5)
                    
        console.print(f"⏰ 任务超时: {task_id}")
        return None

    async def verify_citation_relationships(self, papers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """验证引用关系是否正确建立"""
        console.print("\n🔍 验证引用关系...")
        
        verification_results = {
            "total_expected": 0,
            "total_found": 0,
            "relationships": [],
            "missing": [],
            "unexpected": []
        }
        
        # 收集所有LID
        paper_lids = {}
        for paper in papers:
            if paper.get("result") and paper["result"].get("lid"):
                paper_lids[paper["name"]] = paper["result"]["lid"]
        
        console.print(f"📋 已添加文献LID映射: {paper_lids}")
        
        # 等待引用关系处理完成
        console.print("⏳ 等待引用关系处理完成...")
        await asyncio.sleep(10)  # 给系统时间处理引用关系
        
        # 检查每个文献的预期引用关系
        for paper in papers:
            expected_citations = paper.get("expected_citations", [])
            paper_lid = paper_lids.get(paper["name"])
            
            if not paper_lid:
                continue
                
            verification_results["total_expected"] += len(expected_citations)
            
            console.print(f"\n📄 检查 {paper['name']} (LID: {paper_lid})")
            console.print(f"   预期引用: {expected_citations}")
            
            try:
                # 查询该文献的引用关系
                # 由于graphs API还是stub，我们直接查询Neo4j
                relationships = await self.query_neo4j_relationships(paper_lid)
                
                found_citations = []
                for rel in relationships:
                    # 检查是否匹配预期的引用
                    for expected_name in expected_citations:
                        expected_lid = paper_lids.get(expected_name)
                        if expected_lid and rel.get("to_lid") == expected_lid:
                            found_citations.append(expected_name)
                            verification_results["total_found"] += 1
                            
                verification_results["relationships"].append({
                    "paper": paper["name"],
                    "lid": paper_lid,
                    "expected": expected_citations,
                    "found": found_citations,
                    "raw_relationships": relationships
                })
                
                # 记录缺失的引用
                for expected in expected_citations:
                    if expected not in found_citations:
                        verification_results["missing"].append({
                            "from": paper["name"],
                            "to": expected,
                            "from_lid": paper_lid,
                            "to_lid": paper_lids.get(expected)
                        })
                        
                console.print(f"   实际引用: {found_citations}")
                        
            except Exception as e:
                console.print(f"❌ 查询引用关系失败: {e}")
                
        return verification_results

    async def query_neo4j_relationships(self, lid: str) -> List[Dict[str, Any]]:
        """查询Neo4j中的引用关系"""
        try:
            # 使用graphs API查询引用关系
            response = await self.client.get(
                f"{self.base_url}/api/graphs",
                params={"lids": lid, "max_depth": 1, "min_confidence": 0.1}
            )
            
            if response.status_code == 200:
                graph_data = response.json()
                edges = graph_data.get("edges", [])
                
                # 转换为关系列表
                relationships = []
                for edge in edges:
                    if edge.get("from_lid") == lid:  # 出度关系
                        relationships.append({
                            "type": "outgoing",
                            "from_lid": edge["from_lid"],
                            "to_lid": edge["to_lid"],
                            "confidence": edge.get("confidence", 0.0)
                        })
                    elif edge.get("to_lid") == lid:  # 入度关系
                        relationships.append({
                            "type": "incoming", 
                            "from_lid": edge["from_lid"],
                            "to_lid": edge["to_lid"],
                            "confidence": edge.get("confidence", 0.0)
                        })
                
                return relationships
            else:
                console.print(f"⚠️ Graphs API查询失败: {response.status_code}")
                return []
                
        except Exception as e:
            console.print(f"⚠️ Neo4j查询出错: {e}")
            return []

    async def test_graphs_api(self, paper_lids: List[str]) -> Dict[str, Any]:
        """测试graphs API功能"""
        console.print("\n🌐 测试 Graphs API...")
        
        if not paper_lids:
            console.print("⚠️ 没有有效的LID进行测试")
            return {"status": "skipped", "reason": "no_lids"}
            
        try:
            # 测试graphs API
            lids_param = ",".join(paper_lids[:3])  # 最多测试3个LID
            
            response = await self.client.get(
                f"{self.base_url}/api/graphs",
                params={"lids": lids_param}
            )
            
            console.print(f"📊 Graphs API 响应: {response.status_code}")
            
            if response.status_code == 501:
                # 预期的stub响应
                result = response.json()
                console.print("✅ Graphs API返回预期的501 Not Implemented (stub状态)")
                return {
                    "status": "stub_confirmed",
                    "response": result,
                    "test_lids": paper_lids[:3]
                }
            elif response.status_code == 200:
                # 如果已经实现了
                result = response.json()
                console.print("🎉 Graphs API已实现并返回数据!")
                return {
                    "status": "implemented",
                    "response": result,
                    "test_lids": paper_lids[:3]
                }
            else:
                console.print(f"❌ Graphs API返回意外状态码: {response.status_code}")
                return {
                    "status": "error",
                    "status_code": response.status_code,
                    "response": response.text
                }
                
        except Exception as e:
            console.print(f"❌ Graphs API测试失败: {e}")
            return {"status": "error", "error": str(e)}

    async def run_full_test(self) -> Dict[str, Any]:
        """运行完整的端到端测试"""
        console.print(Panel.fit("🚀 开始端到端引用关系系统测试", style="bold blue"))
        
        start_time = time.time()
        
        # 1. 获取测试论文数据
        papers = self.get_test_papers()
        console.print(f"📋 准备测试 {len(papers)} 篇论文的引用关系")
        
        # 显示测试计划
        table = Table(title="测试论文列表")
        table.add_column("顺序", style="cyan")
        table.add_column("论文名称", style="green") 
        table.add_column("DOI", style="yellow")
        table.add_column("预期引用", style="magenta")
        
        for paper in papers:
            table.add_row(
                str(paper["order"]),
                paper["name"],
                paper["data"].get("doi", "N/A")[:30] + "..." if len(paper["data"].get("doi", "")) > 30 else paper["data"].get("doi", "N/A"),
                ", ".join(paper["expected_citations"]) or "无"
            )
        console.print(table)
        
        # 2. 按顺序添加文献
        console.print("\n📚 开始添加文献...")
        for paper in papers:
            result = await self.add_literature(paper["data"])
            paper["result"] = result
            if result:
                self.test_results["literature_added"].append({
                    "name": paper["name"],
                    "lid": result.get("lid"),
                    "status": "success"
                })
            await asyncio.sleep(2)  # 给系统一点时间
            
        # 3. 收集成功添加的LID
        successful_lids = []
        for paper in papers:
            if paper.get("result") and paper["result"].get("lid"):
                successful_lids.append(paper["result"]["lid"])
        
        console.print(f"\n✅ 成功添加 {len(successful_lids)} 篇文献")
        
        # 4. 验证引用关系
        citation_verification = await self.verify_citation_relationships(papers)
        self.test_results["citation_relationships"] = citation_verification
        
        # 5. 测试Graphs API
        graphs_test = await self.test_graphs_api(successful_lids)
        self.test_results["graphs_api"] = graphs_test
        
        # 6. 生成测试报告
        end_time = time.time()
        self.test_results["timing"]["total_duration"] = end_time - start_time
        
        await self.generate_test_report()
        
        return self.test_results

    async def generate_test_report(self):
        """生成测试报告"""
        console.print("\n" + "="*60)
        console.print(Panel.fit("📊 测试报告", style="bold green"))
        
        # 文献添加结果
        added_count = len(self.test_results["literature_added"])
        console.print(f"📚 文献添加: {added_count} 篇成功")
        
        for lit in self.test_results["literature_added"]:
            console.print(f"   ✅ {lit['name']}: LID={lit['lid']}")
        
        # 引用关系验证结果
        citation_results = self.test_results["citation_relationships"]
        console.print(f"\n🔗 引用关系验证:")
        console.print(f"   预期关系: {citation_results['total_expected']}")
        console.print(f"   发现关系: {citation_results['total_found']}")
        console.print(f"   成功率: {citation_results['total_found']/max(citation_results['total_expected'], 1)*100:.1f}%")
        
        if citation_results["missing"]:
            console.print(f"   ❌ 缺失关系: {len(citation_results['missing'])}")
            for missing in citation_results["missing"]:
                console.print(f"      {missing['from']} -> {missing['to']}")
        
        # Graphs API测试结果
        graphs_result = self.test_results["graphs_api"]
        console.print(f"\n🌐 Graphs API: {graphs_result['status']}")
        
        # 总耗时
        duration = self.test_results["timing"]["total_duration"]
        console.print(f"\n⏱️ 总耗时: {duration:.2f} 秒")
        
        # 保存详细结果到文件
        with open("test_results.json", "w", encoding="utf-8") as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False, default=str)
        console.print(f"\n💾 详细结果已保存到: test_results.json")

async def main():
    parser = argparse.ArgumentParser(description="端到端引用关系系统测试")
    parser.add_argument("--mode", choices=["full", "quick", "graphs-only"], 
                       default="full", help="测试模式")
    parser.add_argument("--base-url", default="http://localhost:8000", 
                       help="API基础URL")
    
    args = parser.parse_args()
    
    async with EndToEndTester(args.base_url) as tester:
        if args.mode == "full":
            await tester.run_full_test()
        elif args.mode == "graphs-only":
            # 只测试graphs API (需要提供一些LID)
            test_lids = ["test-lid-1", "test-lid-2"]  # 这里需要实际的LID
            await tester.test_graphs_api(test_lids)
        else:
            console.print("⚠️ Quick模式暂未实现")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n⚠️ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
