#!/usr/bin/env python3
"""端到端测试references功能"""

import asyncio
import httpx
import time
import json

BASE_URL = "http://127.0.0.1:8000/api"

async def test_references_end_to_end():
    """端到端测试references功能"""
    print("=== References端到端测试 ===")
    
    # 使用一个新的论文URL，确保不会与已存在的冲突
    test_url = "http://arxiv.org/abs/2103.00020"  # DALL-E论文
    print(f"提交新的文献解析任务: {test_url}")
    
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            # 1. 提交任务
            response = await client.post(
                f"{BASE_URL}/literature",
                json={"source": {"url": test_url}}
            )
            print(f"响应状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "exists":
                    print(f"文献已存在，ID: {result.get('literatureId')}")
                    # 检查已存在文献的references
                    await check_literature_references(client, result.get('literatureId'))
                    return result.get('literatureId')
                    
            elif response.status_code == 202:
                task_data = response.json()
                task_id = task_data["taskId"]
                print(f"任务ID: {task_id}")
                
                # 2. 监控任务进度
                print("\n=== 监控任务进度 ===")
                max_wait = 300  # 5分钟超时
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    try:
                        status_response = await client.get(f"{BASE_URL}/task/{task_id}")
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            print(f"\n时间: {time.time() - start_time:.1f}s")
                            print(f"任务状态: {status_data.get('status')}")
                            print(f"当前阶段: {status_data.get('stage', 'N/A')}")
                            print(f"进度: {status_data.get('progress_percentage', 0)}%")
                            
                            # 检查组件状态
                            if "component_status" in status_data:
                                comp_status = status_data["component_status"]
                                print("组件状态:")
                                for component, status in comp_status.items():
                                    print(f"  {component}: {status.get('status')} - {status.get('stage', 'N/A')}")
                            
                            # 检查是否完成
                            if status_data.get("status") == "success":
                                literature_id = status_data.get("literature_id")
                                if literature_id:
                                    print(f"\n✅ 任务完成! 文献ID: {literature_id}")
                                    await check_literature_references(client, literature_id)
                                    return literature_id
                                break
                            elif status_data.get("status") == "failure":
                                error_info = status_data.get('error_info', {})
                                print(f"❌ 任务失败: {error_info}")
                                break
                                
                        else:
                            print(f"状态查询失败: {status_response.status_code}")
                            
                    except Exception as e:
                        print(f"检查状态时出错: {e}")
                    
                    await asyncio.sleep(10)  # 等待10秒后再检查
                else:
                    print("❌ 任务超时")
            else:
                print(f"提交失败: {response.text}")
                
        except Exception as e:
            print(f"请求失败: {e}")
            import traceback
            traceback.print_exc()

async def check_literature_references(client, literature_id):
    """检查文献的references"""
    print(f"\n=== 检查文献 {literature_id} 的References ===")
    
    try:
        lit_response = await client.get(f"{BASE_URL}/literature/{literature_id}")
        if lit_response.status_code == 200:
            lit_data = lit_response.json()
            
            # 基本信息
            metadata = lit_data.get('metadata', {})
            print(f"标题: {metadata.get('title', 'N/A')}")
            print(f"年份: {metadata.get('year', 'N/A')}")
            print(f"作者数量: {len(metadata.get('authors', []))}")
            
            # References详细分析
            refs = lit_data.get('references', [])
            print(f"\n📚 References数量: {len(refs)}")
            
            if refs:
                print("\n=== References详情 ===")
                for i, ref in enumerate(refs[:5], 1):  # 显示前5个
                    print(f"\n📄 Reference {i}:")
                    raw_text = ref.get('raw_text', 'N/A')
                    if len(raw_text) > 120:
                        raw_text = raw_text[:120] + '...'
                    print(f"  Raw: {raw_text}")
                    print(f"  Source: {ref.get('source', 'N/A')}")
                    
                    parsed = ref.get('parsed')
                    if parsed:
                        print(f"  ✅ 已解析:")
                        print(f"    Title: {parsed.get('title', 'N/A')}")
                        print(f"    Year: {parsed.get('year', 'N/A')}")
                        authors = parsed.get('authors', [])
                        if authors:
                            author_names = [a.get('name', 'N/A') for a in authors[:3]]
                            print(f"    Authors: {', '.join(author_names)}")
                            if len(authors) > 3:
                                print(f"    ... 还有 {len(authors) - 3} 位作者")
                        print(f"    Journal: {parsed.get('journal', 'N/A')}")
                        
                        # 检查identifiers
                        identifiers = parsed.get('identifiers', {})
                        if identifiers:
                            doi = identifiers.get('doi')
                            arxiv = identifiers.get('arxiv_id')
                            if doi:
                                print(f"    DOI: {doi}")
                            if arxiv:
                                print(f"    ArXiv: {arxiv}")
                    else:
                        print(f"  ❌ 未解析")
                
                if len(refs) > 5:
                    print(f"\n... 还有 {len(refs) - 5} 个references")
                
                # 统计分析
                print(f"\n=== 统计分析 ===")
                
                # 来源统计
                sources = {}
                for ref in refs:
                    source = ref.get('source', 'Unknown')
                    sources[source] = sources.get(source, 0) + 1
                
                print(f"📊 References来源统计:")
                for source, count in sources.items():
                    print(f"  {source}: {count} 个 ({count/len(refs)*100:.1f}%)")
                
                # 解析统计
                parsed_count = sum(1 for ref in refs if ref.get('parsed'))
                print(f"\n📈 解析统计:")
                print(f"  已解析: {parsed_count}/{len(refs)} ({parsed_count/len(refs)*100:.1f}%)")
                print(f"  未解析: {len(refs) - parsed_count}/{len(refs)} ({(len(refs) - parsed_count)/len(refs)*100:.1f}%)")
                
                # 质量检查
                print(f"\n🔍 质量检查:")
                title_count = sum(1 for ref in refs if ref.get('parsed', {}).get('title'))
                year_count = sum(1 for ref in refs if ref.get('parsed', {}).get('year'))
                author_count = sum(1 for ref in refs if ref.get('parsed', {}).get('authors'))
                
                print(f"  有标题: {title_count}/{parsed_count} ({title_count/parsed_count*100:.1f}%)" if parsed_count > 0 else "  有标题: 0/0")
                print(f"  有年份: {year_count}/{parsed_count} ({year_count/parsed_count*100:.1f}%)" if parsed_count > 0 else "  有年份: 0/0")
                print(f"  有作者: {author_count}/{parsed_count} ({author_count/parsed_count*100:.1f}%)" if parsed_count > 0 else "  有作者: 0/0")
                
            else:
                print("❌ 没有找到references数据")
                
            # 检查其他信息
            print(f"\n=== 其他信息 ===")
            content = lit_data.get('content', {})
            print(f"PDF URL: {content.get('pdf_url', 'N/A')}")
            print(f"有全文内容: {bool(content.get('fulltext'))}")
            
        else:
            print(f"获取文献详情失败: {lit_response.status_code}")
            print(f"错误信息: {lit_response.text}")
            
    except Exception as e:
        print(f"检查references时出错: {e}")
        import traceback
        traceback.print_exc()

async def check_database_directly():
    """直接检查数据库中的references数据"""
    print(f"\n=== 直接检查数据库 ===")
    
    import subprocess
    try:
        # 使用docker exec直接查询MongoDB
        cmd = [
            'docker', 'exec', 'paper_paser_1-db-1', 'mongosh', '--eval',
            '''
            use literature_parser;
            print("=== 数据库统计 ===");
            var total = db.literatures.countDocuments({});
            var withRefs = db.literatures.countDocuments({"references": {$exists: true, $not: {$size: 0}}});
            print("总文献数: " + total);
            print("有references的文献数: " + withRefs);
            print("比例: " + (withRefs/total*100).toFixed(1) + "%");
            
            print("\\n=== 最新文献的references ===");
            db.literatures.find({}, {_id: 1, "metadata.title": 1, references: 1})
              .sort({created_at: -1})
              .limit(2)
              .forEach(function(doc) {
                print("文献ID: " + doc._id);
                print("标题: " + (doc.metadata && doc.metadata.title ? doc.metadata.title : "N/A"));
                print("References数量: " + (doc.references ? doc.references.length : 0));
                if (doc.references && doc.references.length > 0) {
                  print("第一个reference source: " + (doc.references[0].source || "N/A"));
                  print("第一个reference parsed: " + (doc.references[0].parsed ? "Yes" : "No"));
                }
                print("---");
              });
            '''
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"数据库查询失败: {result.stderr}")
            
    except Exception as e:
        print(f"数据库查询出错: {e}")

if __name__ == '__main__':
    asyncio.run(test_references_end_to_end())
    asyncio.run(check_database_directly()) 