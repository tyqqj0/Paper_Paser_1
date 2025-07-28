"""
URL映射适配器模块

包含各种期刊和平台的URL适配器实现。
"""

from .arxiv import ArXivAdapter
from .cvf import CVFAdapter
from .nature import NatureAdapter
from .ieee import IEEEAdapter
from .neurips import NeurIPSAdapter
from .plos import PLOSAdapter
from .acm import ACMAdapter
from .science import ScienceAdapter
from .springer import SpringerAdapter
from .cell import CellAdapter
from .generic import GenericAdapter

__all__ = [
    "ArXivAdapter",
    "CVFAdapter",
    "NatureAdapter",
    "IEEEAdapter",
    "NeurIPSAdapter",
    "PLOSAdapter",
    "ACMAdapter",
    "ScienceAdapter",
    "SpringerAdapter",
    "CellAdapter",
    "GenericAdapter",
]

# 适配器注册表
ADAPTER_REGISTRY = {
    "arxiv": ArXivAdapter,
    "cvf": CVFAdapter,
    "nature": NatureAdapter,
    "ieee": IEEEAdapter,
    "neurips": NeurIPSAdapter,
    "plos": PLOSAdapter,
    "acm": ACMAdapter,
    "science": ScienceAdapter,
    "springer": SpringerAdapter,
    "cell": CellAdapter,
    "generic": GenericAdapter,
}

def get_all_adapters():
    """获取所有可用的适配器类"""
    return list(ADAPTER_REGISTRY.values())

def get_adapter_by_name(name: str):
    """根据名称获取适配器类"""
    return ADAPTER_REGISTRY.get(name.lower())

def create_all_adapters():
    """创建所有适配器的实例"""
    return [adapter_class() for adapter_class in ADAPTER_REGISTRY.values()]
