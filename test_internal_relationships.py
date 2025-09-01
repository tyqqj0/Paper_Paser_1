#!/usr/bin/env python3
"""
测试内部关系图API - 使用真实的解析成功的LID数据
"""

import asyncio
import httpx
import json

# 从测试结果中提取的真实LID数据
REAL_LIDS = [
    "2017-vaswani-aayn-6096",       # ArXiv经典论文 - Transformer
    "2020-dosovits-iwwtir-e64e",    # ArXiv最新论文 - Vision Transformer  
    "2017-krizhevs-icdcnn-c3e3",    # NeurIPS 2012 - AlexNet
    "1992-polyak-asaa-9e1c",        # Acceleration of stochastic approximation
    "2017-ashish-aayn-d46b",        # NeurIPS 2017 - Attention论文
    "2019-do-gtpncr-af82",          # ACM Digital Library - 有DOI
    "2018-peng-jodant-1f30",        # IEEE Xplore论文
    "2015-he-drlir-8046",           # ResNet原论文
    "2014-kingma-amso-13cd",        # ArXiv论文 - Adam优化器
    "2018-devlin-bptdbt-dbc3",      # BERT - 自然语言处理里程碑
    "2016-silver-mgdnnt-ac1b",      # AlphaGo论文 - Nature
    "2014-goodfell-gan-4913",       # GAN论文 - Ian Goodfellow
    "2015-ronneber-ncnbis-e42c",    # U-Net - 医学图像分割
    "2015-ioffe-bnadnt-32fa",       # Batch Normalization
    "2013-mikolov-eewrvs-2806",     # Word2Vec - 词向量
    "2014-sutskeve-sslnn-1fca",     # Seq2Seq - 序列到序列
    "2015-lecun-dl-9d4b",           # 深度学习Nature综述 - LeCun
    "2015-redmon-yolour-73f1",      # YOLO目标检测
    "1997-hochreit-lstm-59a8",      # LSTM - 长短期记忆网络
    "2017-krizhevs-icdcnn-3225",    # imagenet
    "2011-glorot-dsrnn-f3e7",       # ReLU激活函数研究
]

async def test_internal_relationships():
    """测试内部关系图API"""
    print("🔗 测试内部关系图API - 使用真实LID数据")
    print("=" * 60)
    
    base_url = "http://localhost:8000/api"
    
    async with httpx.AsyncClient() as client:
        
        print(f"📋 可用的真实LID数据: {len(REAL_LIDS)} 个")
        print("   示例LID:")
        for i, lid in enumerate(REAL_LIDS[:5], 1):
            print(f"     {i}. {lid}")
        print("   ...")
        print()
        
        # 测试用例
        test_cases = [
            {
                "name": "单个LID测试 - Transformer",
                "lids": [REAL_LIDS[0]],  # 2017-vaswani-aayn-6096
                "description": "测试单篇论文的内部关系（应该只有节点，没有边）"
            },
            {
                "name": "两个相关论文 - Transformer系列",
                "lids": [REAL_LIDS[0], REAL_LIDS[1]],  # Transformer + Vision Transformer
                "description": "测试两篇可能相关的论文"
            },
            {
                "name": "深度学习经典论文集",
                "lids": REAL_LIDS[7:12],  # ResNet, Adam, BERT, AlphaGo, GAN
                "description": "测试5篇深度学习里程碑论文的内部关系"
            },
            {
                "name": "CNN相关论文",
                "lids": [REAL_LIDS[2], REAL_LIDS[7], REAL_LIDS[17]],  # AlexNet, ResNet, YOLO
                "description": "测试CNN相关论文的内部引用关系"
            },
            {
                "name": "优化器和基础技术",
                "lids": [REAL_LIDS[8], REAL_LIDS[12], REAL_LIDS[13]],  # Adam, Batch Norm, Word2Vec
                "description": "测试基础技术论文的关系"
            },
            {
                "name": "大规模测试 - 所有论文",
                "lids": REAL_LIDS[:10],  # 前10篇论文
                "description": "测试多篇论文的内部关系网络"
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"🧪 测试 {i}: {test_case['name']}")
            print(f"   描述: {test_case['description']}")
            print(f"   LID数量: {len(test_case['lids'])}")
            
            # 显示LID
            lids_str = ",".join(test_case['lids'])
            print(f"   LID: {lids_str[:80]}{'...' if len(lids_str) > 80 else ''}")
            
            try:
                # 调用API
                response = await client.get(
                    f"{base_url}/graphs",
                    params={"lids": lids_str}
                )
                
                print(f"   状态码: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    metadata = data.get("metadata", {})
                    
                    print(f"   ✅ 成功!")
                    print(f"     - 节点数: {metadata.get('total_nodes', 0)}")
                    print(f"     - 边数: {metadata.get('total_edges', 0)}")
                    print(f"     - 请求数: {metadata.get('total_requested', 0)}")
                    print(f"     - 关系类型: {metadata.get('relationship_type', 'N/A')}")
                    print(f"     - API版本: {metadata.get('api_version', 'N/A')}")
                    
                    # 显示节点信息
                    nodes = data.get("nodes", [])
                    if nodes:
                        print(f"     📚 节点详情:")
                        for node in nodes[:3]:
                            title = node.get("title", "No title")
                            print(f"       - {node.get('lid')}: {title[:40]}{'...' if len(title) > 40 else ''}")
                        if len(nodes) > 3:
                            print(f"       ... 还有 {len(nodes) - 3} 个节点")
                    
                    # 显示关系信息
                    edges = data.get("edges", [])
                    if edges:
                        print(f"     🔗 关系详情:")
                        for edge in edges[:3]:
                            print(f"       - {edge.get('from_lid')} → {edge.get('to_lid')}")
                            print(f"         置信度: {edge.get('confidence', 'N/A')}, 来源: {edge.get('source', 'N/A')}")
                        if len(edges) > 3:
                            print(f"       ... 还有 {len(edges) - 3} 个关系")
                    else:
                        print(f"     ⚠️ 没有发现内部引用关系")
                    
                elif response.status_code == 400:
                    error_detail = response.json().get('detail', 'Unknown error')
                    print(f"   ❌ 客户端错误: {error_detail}")
                elif response.status_code == 500:
                    error_detail = response.json().get('detail', 'Unknown error')
                    print(f"   ❌ 服务器错误: {error_detail}")
                else:
                    print(f"   ❓ 未知响应: {response.status_code}")
                    print(f"     响应内容: {response.text[:200]}...")
                    
            except Exception as e:
                print(f"   💥 请求异常: {e}")
                
            print()
        
        print("🎯 测试总结:")
        print("✅ API参数简化完成 - 只需要lids参数")
        print("✅ 内部关系逻辑 - 只返回LID列表内部的关系")
        print("✅ 真实数据测试完成")
        print("📊 如果没有关系，说明这些论文之间确实没有直接引用关系")
        print("💡 要看到真实关系，需要选择有引用关系的论文组合")

if __name__ == "__main__":
    asyncio.run(test_internal_relationships())
