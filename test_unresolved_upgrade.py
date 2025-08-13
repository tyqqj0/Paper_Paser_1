#!/usr/bin/env python3
"""
测试未解析节点升级功能
测试流程：
1. 添加文献A（引用文献B）-> 产生未解析节点B
2. 添加文献B本身 -> 验证未解析B是否升级为Literature节点
"""

import asyncio
import httpx
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Dict, Any

console = Console()

class UnresolvedUpgradeTest:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.client = httpx.AsyncClient(timeout=120.0)
        
    async def close(self):
        await self.client.aclose()
    
    async def add_literature(self, data: Dict[str, Any], description: str) -> str:
        """添加文献并等待完成"""
        console.print(f"\n📝 {description}")
        
        # 发起请求
        response = await self.client.post(f"{self.base_url}/api/resolve", json=data)
        response.raise_for_status()
        task_info = response.json()
        task_id = task_info["task_id"]
        
        console.print(f"🔄 任务ID: {task_id}")
        
        # 等待任务完成
        while True:
            response = await self.client.get(f"{self.base_url}/api/tasks/{task_id}")
            response.raise_for_status()
            task_status = response.json()
            
            status = task_status["status"]
            console.print(f"⏳ 状态: {status}")
            
            if status in ["completed", "failed"]:
                if status == "completed":
                    literature_id = task_status.get("result", {}).get("literature_id")
                    console.print(f"✅ 完成！文献ID: {literature_id}")
                    return literature_id
                else:
                    console.print(f"❌ 失败: {task_status.get('message', 'Unknown error')}")
                    return None
            
            await asyncio.sleep(3)
    
    async def query_database_state(self, step: str):
        """查询数据库状态"""
        console.print(f"\n🔍 [{step}] 数据库状态查询")
        
        # 使用Neo4j直接查询
        import subprocess
        
        queries = [
            'MATCH (n:Literature) RETURN count(n) as literature_count',
            'MATCH (n:Unresolved) RETURN count(n) as unresolved_count',
            'MATCH ()-[r:CITES]->(:Literature) RETURN count(r) as literature_citations',
            'MATCH ()-[r:CITES]->(:Unresolved) RETURN count(r) as unresolved_citations'
        ]
        
        results = {}
        for query in queries:
            try:
                cmd = f'sudo docker exec -it literature_parser_neo4j cypher-shell -u neo4j -p literature_parser_neo4j "{query}"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                # 简单解析结果
                lines = result.stdout.split('\n')
                for line in lines:
                    if '|' in line and any(char.isdigit() for char in line):
                        parts = line.split('|')
                        if len(parts) >= 2:
                            value = parts[1].strip()
                            if value.isdigit():
                                key = query.split('as ')[1] if 'as ' in query else 'count'
                                results[key] = int(value)
                                break
            except Exception as e:
                console.print(f"❌ 查询失败: {e}")
        
        # 显示结果表格
        table = Table(title=f"数据库状态 - {step}")
        table.add_column("指标", style="cyan")
        table.add_column("数量", style="magenta")
        
        table.add_row("Literature节点", str(results.get('literature_count', 0)))
        table.add_row("Unresolved节点", str(results.get('unresolved_count', 0)))
        table.add_row("Literature引用", str(results.get('literature_citations', 0)))
        table.add_row("Unresolved引用", str(results.get('unresolved_citations', 0)))
        
        console.print(table)
        return results
    
    async def run_test(self):
        """执行完整测试流程"""
        console.print(Panel.fit(
            "🧪 未解析节点升级测试\n"
            "测试流程：\n"
            "1️⃣ 添加ResNet论文（引用AlexNet） -> 产生未解析AlexNet节点\n"
            "2️⃣ 添加AlexNet论文本身 -> 验证升级功能",
            title="测试开始"
        ))
        
        try:
            # 步骤0：初始状态
            await self.query_database_state("初始状态")
            
            # 步骤1：添加引用ResNet的文献 (使用arXiv版本，更容易获取引用)
            citing_paper = {
                "arxiv_id": "1512.03385",  # ResNet论文
                "title": "Deep Residual Learning for Image Recognition",
                "authors": ["Kaiming He", "Xiangyu Zhang", "Shaoqing Ren", "Jian Sun"]
            }
            
            literature_a_id = await self.add_literature(
                citing_paper, 
                "步骤1: 添加ResNet论文（包含引用信息）"
            )
            
            if not literature_a_id:
                console.print("❌ 文献A添加失败，测试终止")
                return False
            
            # 查询步骤1后的状态
            state_1 = await self.query_database_state("添加文献A后")
            
            # 检查是否产生了未解析节点
            if state_1.get('unresolved_count', 0) == 0:
                console.print("⚠️  警告：没有产生未解析节点，可能引用解析未启动")
            else:
                console.print(f"✅ 成功产生 {state_1.get('unresolved_count', 0)} 个未解析节点")
            
            # 等待一下
            console.print("\n⏳ 等待5秒...")
            await asyncio.sleep(5)
            
            # 步骤2：添加被ResNet引用的AlexNet论文
            alexnet_paper = {
                "arxiv_id": "1404.5997",  # AlexNet论文
                "title": "ImageNet Classification with Deep Convolutional Neural Networks",
                "authors": ["Alex Krizhevsky", "Ilya Sutskever", "Geoffrey E. Hinton"]
            }
            
            literature_b_id = await self.add_literature(
                alexnet_paper,
                "步骤2: 添加AlexNet论文（被引用文献）"
            )
            
            if not literature_b_id:
                console.print("❌ 文献B添加失败")
                return False
            
            # 查询最终状态
            state_2 = await self.query_database_state("添加文献B后")
            
            # 分析结果
            console.print("\n📊 测试结果分析:")
            
            literature_increase = state_2.get('literature_count', 0) - state_1.get('literature_count', 0)
            unresolved_change = state_2.get('unresolved_count', 0) - state_1.get('unresolved_count', 0)
            
            console.print(f"📈 Literature节点增加: {literature_increase}")
            console.print(f"📉 Unresolved节点变化: {unresolved_change}")
            
            # 判断升级是否成功
            if literature_increase == 1 and unresolved_change <= 0:
                console.print("🎉 升级功能测试成功！未解析节点可能已升级为Literature节点")
                return True
            elif literature_increase == 1 and unresolved_change > 0:
                console.print("⚠️  文献B添加成功，但可能有新的未解析节点产生")
                return True
            else:
                console.print("❓ 结果待分析，需要详细检查引用关系")
                return False
                
        except Exception as e:
            console.print(f"❌ 测试执行失败: {e}")
            return False

async def main():
    test = UnresolvedUpgradeTest()
    try:
        success = await test.run_test()
        if success:
            console.print(Panel.fit("✅ 测试完成", style="green"))
        else:
            console.print(Panel.fit("❌ 测试失败", style="red"))
    finally:
        await test.close()

if __name__ == "__main__":
    asyncio.run(main())
