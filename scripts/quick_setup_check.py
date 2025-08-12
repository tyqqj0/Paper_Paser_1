#!/usr/bin/env python3
"""
快速安装和配置检查脚本
检查迁移前的环境是否准备就绪
"""

import sys
import importlib
import subprocess
import os
from typing import List, Tuple


def check_python_version() -> Tuple[bool, str]:
    """检查Python版本"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        return True, f"✅ Python {version.major}.{version.minor}.{version.micro}"
    else:
        return False, f"❌ Python {version.major}.{version.minor}.{version.micro} (需要 3.9+)"


def check_required_modules() -> List[Tuple[bool, str]]:
    """检查必需的Python模块"""
    required_modules = [
        ("pydantic", "Pydantic数据验证"),
        ("pydantic_settings", "Pydantic设置管理"),
        ("fastapi", "FastAPI框架"),
        ("motor", "MongoDB异步驱动"),
        ("redis", "Redis客户端"),
        ("neo4j", "Neo4j图数据库驱动"),
        ("elasticsearch", "Elasticsearch客户端"),
        ("celery", "Celery任务队列"),
        ("loguru", "Loguru日志库"),
    ]
    
    results = []
    for module_name, description in required_modules:
        try:
            importlib.import_module(module_name)
            results.append((True, f"✅ {description} ({module_name})"))
        except ImportError:
            results.append((False, f"❌ {description} ({module_name}) - 未安装"))
    
    return results


def check_docker() -> Tuple[bool, str]:
    """检查Docker是否可用"""
    try:
        result = subprocess.run(
            ["sudo", "docker", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return True, f"✅ {version}"
        else:
            return False, "❌ Docker不可用"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, "❌ Docker命令不存在或无权限"


def check_docker_compose() -> Tuple[bool, str]:
    """检查Docker Compose是否可用"""
    try:
        result = subprocess.run(
            ["sudo", "docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return True, f"✅ {version}"
        else:
            return False, "❌ Docker Compose不可用"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, "❌ Docker Compose命令不存在或无权限"


def check_config_files() -> List[Tuple[bool, str]]:
    """检查配置文件"""
    required_files = [
        ("docker-compose.neo4j.yml", "Neo4j Docker Compose配置"),
        ("pyproject.toml", "Python项目配置"),
        ("scripts/mongodb_to_neo4j_migration.py", "迁移脚本"),
        ("scripts/start_migration.sh", "启动脚本"),
    ]
    
    results = []
    for file_path, description in required_files:
        if os.path.exists(file_path):
            results.append((True, f"✅ {description} ({file_path})"))
        else:
            results.append((False, f"❌ {description} ({file_path}) - 文件不存在"))
    
    return results


def check_directory_structure() -> List[Tuple[bool, str]]:
    """检查目录结构"""
    required_dirs = [
        ("literature_parser_backend", "主要代码目录"),
        ("literature_parser_backend/db", "数据库层"),
        ("literature_parser_backend/models", "数据模型"),
        ("scripts", "脚本目录"),
    ]
    
    results = []
    for dir_path, description in required_dirs:
        if os.path.isdir(dir_path):
            results.append((True, f"✅ {description} ({dir_path})"))
        else:
            results.append((False, f"❌ {description} ({dir_path}) - 目录不存在"))
    
    return results


def print_section(title: str, results: List[Tuple[bool, str]]):
    """打印检查结果部分"""
    print(f"\n📋 {title}")
    print("=" * 50)
    
    for success, message in results:
        print(f"  {message}")
    
    failed_count = sum(1 for success, _ in results if not success)
    if failed_count == 0:
        print(f"  ✅ 所有检查通过 ({len(results)}/{len(results)})")
    else:
        print(f"  ⚠️  {failed_count}/{len(results)} 项检查失败")


def main():
    """主检查函数"""
    print("🔍 Neo4j迁移环境检查")
    print("=" * 50)
    
    # Python版本检查
    python_ok, python_msg = check_python_version()
    print(f"\n🐍 Python环境")
    print("=" * 50)
    print(f"  {python_msg}")
    
    # Python模块检查
    module_results = check_required_modules()
    print_section("Python依赖模块", module_results)
    
    # Docker检查
    docker_ok, docker_msg = check_docker()
    compose_ok, compose_msg = check_docker_compose()
    docker_results = [(docker_ok, docker_msg), (compose_ok, compose_msg)]
    print_section("Docker环境", docker_results)
    
    # 配置文件检查
    config_results = check_config_files()
    print_section("配置文件", config_results)
    
    # 目录结构检查
    dir_results = check_directory_structure()
    print_section("目录结构", dir_results)
    
    # 总体评估
    all_results = (
        [python_ok] + 
        [success for success, _ in module_results] +
        [success for success, _ in docker_results] +
        [success for success, _ in config_results] +
        [success for success, _ in dir_results]
    )
    
    total_checks = len(all_results)
    passed_checks = sum(all_results)
    
    print(f"\n🎯 总体评估")
    print("=" * 50)
    print(f"  通过检查: {passed_checks}/{total_checks}")
    
    if passed_checks == total_checks:
        print("  🎉 环境完全就绪，可以开始迁移！")
        print("\n▶️  下一步:")
        print("     ./scripts/start_migration.sh")
        return True
    elif passed_checks >= total_checks * 0.8:
        print("  ⚠️  环境基本就绪，有少量问题需要解决")
        print("\n🔧 建议修复:")
        
        # 模块缺失建议
        missing_modules = [name for success, msg in module_results if not success for name in [msg.split('(')[1].split(')')[0]] if '(' in msg]
        if missing_modules:
            print(f"     poetry install  # 安装缺失模块")
        
        return False
    else:
        print("  ❌ 环境存在较多问题，需要先修复")
        print("\n🔧 修复建议:")
        
        if not python_ok:
            print("     • 升级Python到3.9+版本")
        
        if not any(success for success, _ in docker_results):
            print("     • 安装Docker和Docker Compose")
            print("     • 确保有sudo权限运行Docker命令")
        
        missing_modules = [name for success, msg in module_results if not success for name in [msg.split('(')[1].split(')')[0]] if '(' in msg]
        if missing_modules:
            print("     • 运行: poetry install")
        
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n中断检查")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 检查过程中出现错误: {e}")
        sys.exit(1)
