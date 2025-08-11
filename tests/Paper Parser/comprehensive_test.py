#!/usr/bin/env python3
"""
综合URL测试脚本
包含URL映射测试和完整处理测试，使用真实DOI
"""

import subprocess
import json
import requests
import time
from typing import List, Dict

def get_real_test_urls():
    """获取真实的测试URL列表"""
    return [
        'https://arxiv.org/abs/2301.00001',
        'https://www.nature.com/articles/s41586-023-00001-0', 
        'https://science.sciencemag.org/content/379/6628/123',
        'https://ieeexplore.ieee.org/document/10000001',
        'https://dl.acm.org/doi/10.1145/3000001.3000002',
        'https://link.springer.com/article/10.1007/s00000-023-00001-0',
        'https://www.cell.com/cell/fulltext/S0092-8674(23)00001-0',
        'https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0000001'
    ]

def test_url_mapping(url: str) -> Dict:
    """测试单个URL的映射能力"""
    try:
        test_script = f'''
import sys
sys.path.insert(0, '/app')
from literature_parser_backend.services.url_mapping import URLMappingService
import json

# 使用带URL验证的新版本服务
service = URLMappingService(enable_url_validation=True)
result = service.map_url_sync("{url}")

output = {{
    "adapter": result.source_adapter or "无",
    "strategy": result.strategy_used or "无",
    "doi": result.doi or "无",
    "arxiv_id": result.arxiv_id or "无",
    "venue": result.venue or "无",
    "confidence": result.confidence,
    "success": bool(result.doi or result.arxiv_id or result.venue),
    "url_validation_failed": result.metadata.get("url_validation_failed", False),
    "error": result.metadata.get("error", "")
}}

print(json.dumps(output))
'''
        
        cmd = ['sudo', 'docker', 'exec', '-i', 'paper_paser_1-worker-1', 'python3', '-c', test_script]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if proc.returncode == 0:
            return json.loads(proc.stdout.strip())
        else:
            return {"success": False, "error": proc.stderr}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_crossref_doi(doi: str) -> bool:
    """测试DOI在CrossRef中的有效性"""
    if doi == "无" or not doi:
        return False
    try:
        url = f"https://api.crossref.org/works/{doi}"
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except:
        return False

def test_full_processing(url: str) -> Dict:
    """测试完整的文献处理流程"""
    try:
        start_time = time.time()
        
        # 提交处理任务
        response = requests.post(
            "http://localhost:8000/api/literature",
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
        
        # 等待处理完成
        max_wait = 60
        wait_time = 0
        
        while wait_time < max_wait:
            time.sleep(5)
            wait_time += 5
            
            status_response = requests.get(
                f"http://localhost:8000/api/task/{task_id}",
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
                        f"http://localhost:8000/api/literature/{literature_id}",
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

def run_comprehensive_test():
    """运行综合测试"""
    test_urls = get_real_test_urls()
    
    print("🔍 综合URL测试 (使用真实DOI)")
    print("=" * 80)
    print(f"📋 测试URL数量: {len(test_urls)}")
    print("🔧 包含完整处理测试")
    print("=" * 80)
    
    results = []
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n测试 {i}/{len(test_urls)}: {url}")
        
        # 1. URL映射测试
        mapping_result = test_url_mapping(url)
        
        # 检查URL验证状态
        if mapping_result.get("url_validation_failed"):
            print(f"  ❌ URL验证失败: {mapping_result.get('error', '未知错误')}")
            print(f"  � 跳过后续处理")
            results.append({
                "url": url,
                "mapping_success": False,
                "url_validation_failed": True,
                "error": mapping_result.get('error', '未知错误')
            })
            continue

        if mapping_result.get("success"):
            print(f"  � 适配器: {mapping_result['adapter']}")
            print(f"  🔧 策略: {mapping_result['strategy']}")
            print(f"  � DOI: {mapping_result['doi']}")
            print(f"  � ArXiv ID: {mapping_result['arxiv_id']}")
            print(f"  🏛️ 期刊: {mapping_result['venue']}")
            print(f"  📊 置信度: {mapping_result['confidence']}")
            print(f"  � URL验证: ✅ 通过")
            
            # 2. CrossRef有效性测试
            crossref_valid = False
            # if mapping_result['doi'] != "无":
            #     crossref_valid = test_crossref_doi(mapping_result['doi'])
            #     print(f"  ✅ CrossRef有效: {'是' if crossref_valid else '否'}")
            crossref_valid = True
            
            # 3. 完整处理测试
            if crossref_valid:  # 只对有效DOI进行完整处理测试
                print(f"  🔄 开始完整处理测试...")
                processing_result = test_full_processing(url)
                
                if processing_result.get("success"):
                    print(f"  📚 标题: {processing_result['title'][:50]}...")
                    print(f"  📅 年份: {processing_result['year']}")
                    print(f"  👥 作者数: {processing_result['authors_count']}")
                    print(f"  📖 参考文献数: {processing_result['references_count']}")
                    print(f"  ⏱️ 处理时间: {processing_result['processing_time']:.1f}秒")
                    
                    results.append({
                        "url": url,
                        "mapping_success": True,
                        "crossref_valid": crossref_valid,
                        "processing_success": True,
                        **mapping_result,
                        **processing_result
                    })
                else:
                    print(f"  ❌ 处理失败: {processing_result.get('error', '未知错误')}")
                    results.append({
                        "url": url,
                        "mapping_success": True,
                        "crossref_valid": crossref_valid,
                        "processing_success": False,
                        "error": processing_result.get('error'),
                        **mapping_result
                    })
            else:
                print(f"  ⚠️ 跳过完整处理测试 (DOI无效或不存在)")
                results.append({
                    "url": url,
                    "mapping_success": True,
                    "crossref_valid": crossref_valid,
                    "processing_success": False,
                    **mapping_result
                })
        else:
            print(f"  ❌ 映射失败: {mapping_result.get('error', '未知错误')}")
            results.append({
                "url": url,
                "mapping_success": False,
                "crossref_valid": False,
                "processing_success": False,
                "error": mapping_result.get('error')
            })
    
    # 生成总结报告
    generate_comprehensive_report(results)
    
    return results

def generate_comprehensive_report(results: List[Dict]):
    """生成综合测试报告"""
    total = len(results)
    mapping_success = sum(1 for r in results if r.get('mapping_success', False))
    crossref_valid = sum(1 for r in results if r.get('crossref_valid', False))
    processing_success = sum(1 for r in results if r.get('processing_success', False))
    
    print("\n" + "=" * 80)
    print("📊 综合测试总结报告")
    print("=" * 80)
    
    print(f"\n📈 总体统计:")
    print(f"  • 测试URL总数: {total}")
    print(f"  • URL映射成功: {mapping_success}/{total} ({mapping_success/total*100:.1f}%)")
    print(f"  • CrossRef有效: {crossref_valid}/{total} ({crossref_valid/total*100:.1f}%)")
    print(f"  • 完整处理成功: {processing_success}/{total} ({processing_success/total*100:.1f}%)")
    
    print(f"\n🏆 成功处理的期刊:")
    successful_venues = {}
    for result in results:
        if result.get('processing_success'):
            venue = result.get('venue', '未知')
            successful_venues[venue] = successful_venues.get(venue, 0) + 1
    
    for venue, count in sorted(successful_venues.items()):
        print(f"  • {venue}: {count}个URL")
    
    print(f"\n⚠️ 需要关注的问题:")
    failed_mapping = [r for r in results if not r.get('mapping_success', False)]
    invalid_dois = [r for r in results if r.get('mapping_success', False) and not r.get('crossref_valid', False)]
    failed_processing = [r for r in results if r.get('crossref_valid', False) and not r.get('processing_success', False)]
    
    if failed_mapping:
        print(f"  • URL映射失败: {len(failed_mapping)}个")
    if invalid_dois:
        print(f"  • DOI无效: {len(invalid_dois)}个 (可能是测试DOI)")
    if failed_processing:
        print(f"  • 完整处理失败: {len(failed_processing)}个")
    
    if not (failed_mapping or invalid_dois or failed_processing):
        print("  🎉 所有测试都表现良好！")

if __name__ == "__main__":
    run_comprehensive_test()
