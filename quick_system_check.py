#!/usr/bin/env python3
"""
快速系统健康检查脚本

快速验证所有核心服务和API是否正常工作
"""

import asyncio
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

async def check_system_health():
    """检查系统健康状态"""
    
    console.print(Panel.fit("🔍 系统健康检查", style="bold blue"))
    
    base_url = "http://localhost:8000"
    timeout = 10.0
    
    checks = [
        {"name": "Health Check", "url": f"{base_url}/health", "expected": 200},
        {"name": "Resolve API", "url": f"{base_url}/api/resolve", "method": "POST", "expected": [400, 422]},  # 无数据时的预期错误
        {"name": "Tasks API", "url": f"{base_url}/api/tasks/test-task-id", "expected": 404},  # 任务不存在的预期错误
        {"name": "Literatures API", "url": f"{base_url}/api/literatures", "expected": 200},
        {"name": "Graphs API", "url": f"{base_url}/api/graphs?lids=test-lid", "expected": [200, 501]},  # 可能是stub或已实现
    ]
    
    results = []
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        for check in checks:
            try:
                console.print(f"🔍 检查 {check['name']}...")
                
                if check.get("method") == "POST":
                    response = await client.post(check["url"], json={})
                else:
                    response = await client.get(check["url"])
                
                expected = check["expected"]
                if isinstance(expected, list):
                    status_ok = response.status_code in expected
                else:
                    status_ok = response.status_code == expected
                
                results.append({
                    "name": check["name"],
                    "status_code": response.status_code,
                    "ok": status_ok,
                    "url": check["url"]
                })
                
                if status_ok:
                    console.print(f"   ✅ {check['name']}: {response.status_code}")
                else:
                    console.print(f"   ❌ {check['name']}: {response.status_code} (期望: {expected})")
                    
            except Exception as e:
                console.print(f"   ❌ {check['name']}: 连接失败 - {e}")
                results.append({
                    "name": check["name"],
                    "status_code": "ERROR",
                    "ok": False,
                    "error": str(e)
                })
    
    # 生成总结报告
    console.print("\n" + "="*50)
    console.print(Panel.fit("📊 检查结果总结", style="bold green"))
    
    table = Table(title="API检查结果")
    table.add_column("服务", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("状态码", style="yellow")
    table.add_column("结果", style="magenta")
    
    success_count = 0
    for result in results:
        status = "✅ 正常" if result["ok"] else "❌ 异常"
        if result["ok"]:
            success_count += 1
            
        table.add_row(
            result["name"],
            status,
            str(result["status_code"]),
            "通过" if result["ok"] else "失败"
        )
    
    console.print(table)
    console.print(f"\n📈 总体状态: {success_count}/{len(results)} 项检查通过")
    
    if success_count == len(results):
        console.print("🎉 系统运行正常，可以进行端到端测试！")
        console.print("\n运行完整测试:")
        console.print("python test_end_to_end_citation_system.py --mode full")
    else:
        console.print("⚠️ 部分服务异常，请检查Docker服务状态:")
        console.print("sudo docker compose ps")
        console.print("sudo docker compose logs")

async def quick_graphs_test():
    """快速测试graphs API具体功能"""
    console.print(Panel.fit("🌐 Graphs API 功能测试", style="bold magenta"))
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 测试graphs API的具体功能
            response = await client.get(
                f"{base_url}/api/graphs",
                params={"lids": "test-lid-1,test-lid-2", "max_depth": 1, "min_confidence": 0.5}
            )
            
            console.print(f"📊 Graphs API 响应: {response.status_code}")
            
            if response.status_code == 501:
                console.print("ℹ️ Graphs API 当前是stub状态 (501 Not Implemented)")
                result = response.json()
                if "expected_response_format" in result.get("detail", {}):
                    console.print("✅ API结构正确，等待连接到RelationshipDAO")
                    
            elif response.status_code == 200:
                result = response.json()
                console.print("🎉 Graphs API 已完全实现！")
                console.print(f"   返回节点数: {len(result.get('nodes', []))}")
                console.print(f"   返回边数: {len(result.get('edges', []))}")
                console.print(f"   元数据: {result.get('metadata', {})}")
                
            elif response.status_code == 400:
                console.print("⚠️ 参数错误 (这是正常的，因为使用了测试LID)")
                
            else:
                console.print(f"❓ 未预期的响应: {response.status_code}")
                console.print(f"响应内容: {response.text[:200]}")
                
        except Exception as e:
            console.print(f"❌ Graphs API 测试失败: {e}")

async def main():
    """主函数"""
    try:
        await check_system_health()
        console.print("")
        await quick_graphs_test()
        
    except KeyboardInterrupt:
        console.print("\n⚠️ 检查被用户中断")
    except Exception as e:
        console.print(f"\n❌ 检查失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
