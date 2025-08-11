#!/usr/bin/env python3
"""
快速URL映射测试脚本
仅测试URL识别和DOI提取，不进行完整处理
"""

import subprocess
import json
import requests
from typing import List, Dict

def test_url_mapping():
    """测试URL映射功能"""
    
    test_urls = [
        'https://arxiv.org/abs/2301.00001',
        'https://www.nature.com/articles/s41586-023-00001-0', 
        'https://science.sciencemag.org/content/379/6628/123',
        'https://ieeexplore.ieee.org/document/10000001',
        'https://dl.acm.org/doi/10.1145/3000001.3000002',
        'https://link.springer.com/article/10.1007/s00000-023-00001-0',
        'https://www.cell.com/cell/fulltext/S0092-8674(23)00001-0',
        'https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0000001'
    ]
    
    print("🔍 快速URL映射测试")
    print("=" * 80)
    
    results = []
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n测试 {i}/{len(test_urls)}: {url}")
        
        try:
            # 创建测试脚本
            test_script = f'''
import sys
sys.path.insert(0, '/app')
from literature_parser_backend.services.url_mapper import get_url_mapping_service
import json

service = get_url_mapping_service()
result = service.map_url_sync("{url}")

output = {{
    "adapter": result.source_adapter or "无",
    "strategy": result.strategy_used or "无",
    "doi": result.doi or "无",
    "arxiv_id": result.arxiv_id or "无",
    "venue": result.venue or "无",
    "confidence": result.confidence,
    "success": bool(result.doi or result.arxiv_id or result.venue)
}}

print(json.dumps(output))
'''
            
            # 执行测试
            cmd = ['sudo', 'docker', 'exec', '-i', 'paper_paser_1-worker-1', 'python3', '-c', test_script]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if proc.returncode == 0:
                data = json.loads(proc.stdout.strip())
                
                print(f"  📍 适配器: {data['adapter']}")
                print(f"  🔧 策略: {data['strategy']}")
                print(f"  📄 DOI: {data['doi']}")
                print(f"  📚 ArXiv ID: {data['arxiv_id']}")
                print(f"  🏛️ 期刊: {data['venue']}")
                print(f"  📊 置信度: {data['confidence']}")

                # 测试DOI有效性
                if data['doi'] != "无":
                    crossref_valid = test_crossref_doi(data['doi'])
                    print(f"  ✅ CrossRef有效: {'是' if crossref_valid else '否'}")
                    data['crossref_valid'] = crossref_valid
                else:
                    data['crossref_valid'] = False
                
                results.append({
                    'url': url,
                    'success': data['success'],
                    **data
                })
                
            else:
                print(f"  ❌ 测试失败: {proc.stderr}")
                results.append({
                    'url': url,
                    'success': False,
                    'error': proc.stderr
                })
                
        except Exception as e:
            print(f"  ❌ 异常: {str(e)}")
            results.append({
                'url': url,
                'success': False,
                'error': str(e)
            })
    
    # 生成总结报告
    generate_summary_report(results)
    
    return results

def test_crossref_doi(doi: str) -> bool:
    """测试DOI在CrossRef中的有效性"""
    try:
        url = f"https://api.crossref.org/works/{doi}"
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except:
        return False

def generate_summary_report(results: List[Dict]):
    """生成总结报告"""
    total = len(results)
    mapping_success = sum(1 for r in results if r.get('success', False))
    crossref_valid = sum(1 for r in results if r.get('crossref_valid', False))
    
    print("\n" + "=" * 80)
    print("📊 测试总结报告")
    print("=" * 80)
    
    print(f"\n📈 总体统计:")
    print(f"  • 测试URL总数: {total}")
    print(f"  • URL映射成功: {mapping_success}/{total} ({mapping_success/total*100:.1f}%)")
    print(f"  • CrossRef有效: {crossref_valid}/{total} ({crossref_valid/total*100:.1f}%)")
    
    print(f"\n📋 适配器统计:")
    adapters = {}
    for result in results:
        if result.get('success'):
            adapter = result.get('adapter', '无')
            adapters[adapter] = adapters.get(adapter, 0) + 1
    
    for adapter, count in sorted(adapters.items()):
        print(f"  • {adapter}: {count}个URL")
    
    print(f"\n📄 DOI提取统计:")
    doi_results = [r for r in results if r.get('doi', '无') != '无']
    print(f"  • 成功提取DOI: {len(doi_results)}/{total} ({len(doi_results)/total*100:.1f}%)")
    print(f"  • DOI有效性: {crossref_valid}/{len(doi_results) if doi_results else 1} ({crossref_valid/len(doi_results)*100 if doi_results else 0:.1f}%)")
    
    print(f"\n❌ 失败URL:")
    failed_results = [r for r in results if not r.get('success', False)]
    if failed_results:
        for result in failed_results:
            print(f"  • {result['url']}")
            if 'error' in result:
                print(f"    错误: {result['error']}")
    else:
        print("  🎉 所有URL都成功处理！")

if __name__ == "__main__":
    test_url_mapping()
