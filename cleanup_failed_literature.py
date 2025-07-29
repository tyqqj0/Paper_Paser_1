#!/usr/bin/env python3
"""
清理数据库中状态为错误的文献记录

使用方法:
    python cleanup_failed_literature.py --dry-run    # 只显示要删除的记录，不实际删除
    python cleanup_failed_literature.py --confirm    # 确认删除
    python cleanup_failed_literature.py --help       # 显示帮助信息

功能:
    - 清理任务状态为failed的文献
    - 清理URL验证失败的文献  
    - 清理处理异常的文献
    - 支持干运行模式
    - 详细的删除日志
"""

import argparse
import asyncio
import sys
from datetime import datetime
from typing import List, Dict, Any

# 添加项目路径
sys.path.insert(0, '/app')

from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.db.mongodb import connect_to_mongodb, disconnect_from_mongodb
from literature_parser_backend.models.literature import LiteratureModel
from loguru import logger


class LiteratureCleanup:
    """文献清理工具类"""

    def __init__(self):
        self.dao = None
        self.deleted_count = 0
        self.error_count = 0

    async def _ensure_dao(self):
        """确保DAO已初始化"""
        if self.dao is None:
            self.dao = LiteratureDAO()
    
    async def find_failed_literature(self) -> List[LiteratureModel]:
        """查找所有失败状态的文献"""
        logger.info("🔍 开始查找失败状态的文献...")

        await self._ensure_dao()
        failed_literature = []

        try:
            # 获取所有文献记录 - 使用MongoDB直接查询
            cursor = self.dao.collection.find({})
            all_literature = []
            async for doc in cursor:
                try:
                    literature = LiteratureModel(**doc)
                    all_literature.append(literature)
                except Exception as e:
                    logger.warning(f"跳过无效文献记录 {doc.get('_id', 'unknown')}: {e}")
                    continue
            
            for lit in all_literature:
                is_failed = False
                failure_reason = []
                
                # 检查任务状态
                if lit.task_info:
                    task_status = lit.task_info.status
                    if task_status == "failed":
                        is_failed = True
                        failure_reason.append("任务状态为failed")

                    # 检查组件状态
                    if lit.task_info.component_status:
                        try:
                            # 尝试作为字典处理
                            if hasattr(lit.task_info.component_status, 'items'):
                                for component, status_info in lit.task_info.component_status.items():
                                    if status_info.get("status") == "failed":
                                        is_failed = True
                                        failure_reason.append(f"{component}组件失败")
                            # 尝试作为对象处理
                            elif hasattr(lit.task_info.component_status, '__dict__'):
                                for component, status_info in lit.task_info.component_status.__dict__.items():
                                    if hasattr(status_info, 'status') and status_info.status == "failed":
                                        is_failed = True
                                        failure_reason.append(f"{component}组件失败")
                        except Exception as e:
                            logger.debug(f"检查组件状态时出错: {e}")
                            continue
                
                # 检查是否有错误信息
                if hasattr(lit, 'error_info') and lit.error_info:
                    is_failed = True
                    failure_reason.append("包含错误信息")
                
                # 检查元数据是否为空或异常
                if not lit.metadata or not lit.metadata.title or lit.metadata.title == "Unknown Title":
                    # 进一步检查是否是真正的失败（排除正在处理中的情况）
                    if lit.task_info and lit.task_info.status in ["failed", "completed"]:
                        if lit.metadata and lit.metadata.title == "Unknown Title":
                            is_failed = True
                            failure_reason.append("元数据获取失败")
                
                if is_failed:
                    # 添加失败原因到文献对象（用于显示）
                    lit._failure_reasons = failure_reason
                    failed_literature.append(lit)
            
            logger.info(f"📊 找到 {len(failed_literature)} 个失败状态的文献")
            return failed_literature
            
        except Exception as e:
            logger.error(f"❌ 查找失败文献时出错: {e}")
            return []
    
    def display_failed_literature(self, failed_literature: List[LiteratureModel]):
        """显示失败文献的详细信息"""
        if not failed_literature:
            logger.info("✅ 没有找到失败状态的文献")
            return
        
        logger.info(f"\n📋 失败文献列表 (共 {len(failed_literature)} 个):")
        logger.info("=" * 80)
        
        for i, lit in enumerate(failed_literature, 1):
            logger.info(f"\n{i}. 文献ID: {lit.id}")
            logger.info(f"   标题: {lit.metadata.title if lit.metadata and lit.metadata.title else '无标题'}")
            logger.info(f"   DOI: {lit.identifiers.doi if lit.identifiers and lit.identifiers.doi else '无DOI'}")
            logger.info(f"   创建时间: {lit.created_at}")
            
            # 显示失败原因
            if hasattr(lit, '_failure_reasons'):
                logger.info(f"   失败原因: {', '.join(lit._failure_reasons)}")
            
            # 显示任务状态
            if lit.task_info:
                logger.info(f"   任务状态: {lit.task_info.status}")
                if lit.task_info.component_status:
                    failed_components = []
                    try:
                        # 尝试作为字典处理
                        if hasattr(lit.task_info.component_status, 'items'):
                            failed_components = [
                                comp for comp, status in lit.task_info.component_status.items()
                                if status.get("status") == "failed"
                            ]
                        # 尝试作为对象处理
                        elif hasattr(lit.task_info.component_status, '__dict__'):
                            failed_components = [
                                comp for comp, status in lit.task_info.component_status.__dict__.items()
                                if hasattr(status, 'status') and status.status == "failed"
                            ]
                    except Exception:
                        pass

                    if failed_components:
                        logger.info(f"   失败组件: {', '.join(failed_components)}")
        
        logger.info("=" * 80)
    
    async def delete_failed_literature(self, failed_literature: List[LiteratureModel], dry_run: bool = True):
        """删除失败状态的文献"""
        if not failed_literature:
            logger.info("✅ 没有需要删除的文献")
            return
        
        if dry_run:
            logger.info(f"🔍 [干运行模式] 将要删除 {len(failed_literature)} 个失败文献")
            logger.info("💡 使用 --confirm 参数来实际执行删除操作")
            return
        
        logger.info(f"🗑️  开始删除 {len(failed_literature)} 个失败文献...")
        
        await self._ensure_dao()

        for lit in failed_literature:
            try:
                await self.dao.delete_literature(str(lit.id))
                self.deleted_count += 1
                logger.info(f"✅ 已删除文献: {lit.id} - {lit.metadata.title if lit.metadata and lit.metadata.title else '无标题'}")

            except Exception as e:
                self.error_count += 1
                logger.error(f"❌ 删除文献失败 {lit.id}: {e}")
        
        logger.info(f"\n📊 删除完成统计:")
        logger.info(f"   成功删除: {self.deleted_count} 个")
        logger.info(f"   删除失败: {self.error_count} 个")
        logger.info(f"   总计处理: {len(failed_literature)} 个")
    
    async def cleanup(self, dry_run: bool = True):
        """执行清理操作"""
        logger.info("🚀 开始文献清理操作...")
        logger.info(f"📅 执行时间: {datetime.now()}")
        logger.info(f"🔧 模式: {'干运行' if dry_run else '实际删除'}")

        try:
            # 连接数据库
            logger.info("🔌 连接数据库...")
            await connect_to_mongodb()

            # 查找失败文献
            failed_literature = await self.find_failed_literature()

            # 显示失败文献信息
            self.display_failed_literature(failed_literature)

            # 删除失败文献
            await self.delete_failed_literature(failed_literature, dry_run)

            logger.info("🎉 文献清理操作完成!")

        except Exception as e:
            logger.error(f"❌ 清理操作失败: {e}")
            raise
        finally:
            # 断开数据库连接
            logger.info("🔌 断开数据库连接...")
            await disconnect_from_mongodb()


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="清理数据库中状态为错误的文献记录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    python cleanup_failed_literature.py --dry-run    # 只显示要删除的记录
    python cleanup_failed_literature.py --confirm    # 确认删除
    python cleanup_failed_literature.py --help       # 显示帮助
        """
    )
    
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        default=True,
        help="干运行模式，只显示要删除的记录，不实际删除 (默认)"
    )
    
    parser.add_argument(
        "--confirm", 
        action="store_true", 
        help="确认删除模式，实际执行删除操作"
    )
    
    args = parser.parse_args()
    
    # 确定运行模式
    dry_run = not args.confirm
    
    if not dry_run:
        # 确认删除前的警告
        logger.warning("⚠️  您即将删除数据库中的失败文献记录!")
        logger.warning("⚠️  此操作不可逆，请确认您真的要执行删除操作!")
        
        confirm = input("\n请输入 'YES' 来确认删除操作: ")
        if confirm != "YES":
            logger.info("❌ 操作已取消")
            return
    
    # 执行清理
    cleanup = LiteratureCleanup()
    await cleanup.cleanup(dry_run=dry_run)


if __name__ == "__main__":
    asyncio.run(main())
