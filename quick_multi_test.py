#!/usr/bin/env python3
"""
快速多链接测试 - 基于成功的test_various_links.py
"""

# 直接添加到现有的TEST_CASES列表中
QUICK_MULTI_TESTS = [
    {
        "name": "Dropout - 正则化技术",
        "url": "https://arxiv.org/abs/1207.0580",
        "expected_processor": "ArXiv Official API",
        "expected_features": ['arxiv_id', 'high_quality'],
        "description": "Dropout正则化技术的原始论文"
    },
    {
        "name": "VGG - 深度卷积网络",
        "url": "https://arxiv.org/abs/1409.1556",
        "expected_processor": "ArXiv Official API",
        "expected_features": ['arxiv_id', 'high_quality'],
        "description": "VGG网络架构"
    },
    {
        "name": "DQN - 深度Q网络",
        "url": "https://arxiv.org/abs/1312.5602",
        "expected_processor": "ArXiv Official API",
        "expected_features": ['arxiv_id', 'high_quality'],
        "description": "深度强化学习的突破"
    },
    {
        "name": "VAE - 变分自编码器",
        "url": "https://arxiv.org/abs/1312.6114",
        "expected_processor": "ArXiv Official API",
        "expected_features": ['arxiv_id', 'high_quality'],
        "description": "变分自编码器"
    },
]

print("🎯 快速多链接测试用例准备完成!")
print(f"📊 包含 {len(quick_tests)} 个测试用例")
print("💡 将这些用例添加到 test_various_links.py 的 TEST_CASES 中即可运行")
