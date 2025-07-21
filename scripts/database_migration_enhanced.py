#!/usr/bin/env python3
"""
Enhanced database migration script for waterfall deduplication system.

This script performs a comprehensive database migration including:
1. Cleanup of problematic data and indexes
2. Migration of existing data to new schema
3. Setup of enhanced indexes
4. Data validation and consistency checks
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, TEXT
from pymongo.errors import OperationFailure

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseMigrationEnhanced:
    """Enhanced database migration for waterfall deduplication."""

    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        self.tasks_collection = None
        self.migration_stats = {
            "documents_processed": 0,
            "documents_updated": 0,
            "duplicates_cleaned": 0,
            "failed_documents_removed": 0,
            "indexes_created": 0,
            "indexes_dropped": 0,
        }

    async def connect(self):
        """Connect to MongoDB."""
        self.client = AsyncIOMotorClient(
            "mongodb://literature_parser_backend:literature_parser_backend@localhost:27017/admin"
        )
        self.db = self.client.literature_parser
        self.collection = self.db.literatures
        self.tasks_collection = self.db.tasks

        # Test connection
        await self.client.admin.command("ping")
        logger.info("✅ Connected to MongoDB successfully")

    async def run_migration(self):
        """Run the complete migration process."""
        logger.info("🚀 Starting enhanced database migration...")

        try:
            await self.connect()

            # Phase 1: Cleanup and validation
            await self.cleanup_problematic_data()

            # Phase 2: Schema migration
            await self.migrate_document_schema()

            # Phase 3: Index management
            await self.manage_indexes()

            # Phase 4: Data validation
            await self.validate_data_consistency()

            # Phase 5: Performance optimization
            await self.optimize_database()

            logger.info("✅ Database migration completed successfully!")
            self.print_migration_summary()

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise
        finally:
            if self.client:
                self.client.close()

    async def cleanup_problematic_data(self):
        """Cleanup problematic data that could cause issues."""
        logger.info("🧹 Phase 1: Cleaning up problematic data...")

        # 1. Remove documents with failed status
        failed_query = {"task_info.status": "failed"}
        failed_count = await self.collection.count_documents(failed_query)

        if failed_count > 0:
            logger.info(f"Found {failed_count} failed documents to remove")
            result = await self.collection.delete_many(failed_query)
            self.migration_stats["failed_documents_removed"] = result.deleted_count
            logger.info(f"✅ Removed {result.deleted_count} failed documents")

        # 2. Handle duplicate fingerprints
        await self.cleanup_duplicate_fingerprints()

        # 3. Remove orphaned task records
        await self.cleanup_orphaned_tasks()

        # 4. Fix malformed identifiers
        await self.fix_malformed_identifiers()

    async def cleanup_duplicate_fingerprints(self):
        """Clean up duplicate fingerprints."""
        logger.info("🔍 Cleaning up duplicate fingerprints...")

        # Find all null fingerprints
        null_fingerprints = await self.collection.find(
            {"identifiers.fingerprint": None}
        ).to_list(length=None)

        if len(null_fingerprints) > 1:
            # Keep the most recent one, remove others
            sorted_docs = sorted(
                null_fingerprints, key=lambda x: x.get("created_at", datetime.min)
            )
            docs_to_remove = sorted_docs[:-1]

            if docs_to_remove:
                ids_to_remove = [doc["_id"] for doc in docs_to_remove]
                result = await self.collection.delete_many(
                    {"_id": {"$in": ids_to_remove}}
                )
                self.migration_stats["duplicates_cleaned"] += result.deleted_count
                logger.info(
                    f"✅ Removed {result.deleted_count} duplicate null fingerprint documents"
                )

        # Find and resolve actual duplicate fingerprints
        pipeline = [
            {"$match": {"identifiers.fingerprint": {"$ne": None}}},
            {
                "$group": {
                    "_id": "$identifiers.fingerprint",
                    "docs": {"$push": "$$ROOT"},
                    "count": {"$sum": 1},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
        ]

        duplicates = await self.collection.aggregate(pipeline).to_list(length=None)

        for duplicate_group in duplicates:
            docs = duplicate_group["docs"]
            fingerprint = duplicate_group["_id"]

            # Keep the most recent document
            sorted_docs = sorted(docs, key=lambda x: x.get("updated_at", datetime.min))
            docs_to_remove = sorted_docs[:-1]

            if docs_to_remove:
                ids_to_remove = [doc["_id"] for doc in docs_to_remove]
                result = await self.collection.delete_many(
                    {"_id": {"$in": ids_to_remove}}
                )
                self.migration_stats["duplicates_cleaned"] += result.deleted_count
                logger.info(
                    f"✅ Resolved {result.deleted_count} duplicate documents for fingerprint {fingerprint}"
                )

    async def cleanup_orphaned_tasks(self):
        """Clean up orphaned task records."""
        logger.info("🗑️ Cleaning up orphaned task records...")

        # Find task records without corresponding literature
        pipeline = [
            {
                "$lookup": {
                    "from": "literatures",
                    "localField": "literature_id",
                    "foreignField": "_id",
                    "as": "literature",
                }
            },
            {"$match": {"literature": {"$size": 0}}},
            {"$project": {"_id": 1}},
        ]

        orphaned_tasks = await self.tasks_collection.aggregate(pipeline).to_list(
            length=None
        )

        if orphaned_tasks:
            orphaned_ids = [task["_id"] for task in orphaned_tasks]
            result = await self.tasks_collection.delete_many(
                {"_id": {"$in": orphaned_ids}}
            )
            logger.info(f"✅ Removed {result.deleted_count} orphaned task records")

    async def fix_malformed_identifiers(self):
        """Fix malformed identifier fields."""
        logger.info("🔧 Fixing malformed identifiers...")

        # Fix missing identifiers object
        missing_identifiers = await self.collection.find(
            {"identifiers": {"$exists": False}}
        ).to_list(length=None)

        if missing_identifiers:
            for doc in missing_identifiers:
                await self.collection.update_one(
                    {"_id": doc["_id"]}, {"$set": {"identifiers": {"source_urls": []}}}
                )
            logger.info(
                f"✅ Fixed {len(missing_identifiers)} documents with missing identifiers"
            )

        # Ensure source_urls field exists
        await self.collection.update_many(
            {"identifiers.source_urls": {"$exists": False}},
            {"$set": {"identifiers.source_urls": []}},
        )

    async def migrate_document_schema(self):
        """Migrate documents to new schema format."""
        logger.info("📋 Phase 2: Migrating document schema...")

        # Get all documents
        cursor = self.collection.find({})

        async for doc in cursor:
            self.migration_stats["documents_processed"] += 1

            # Check if document needs migration
            needs_update = False
            update_ops = {}

            # 1. Ensure identifiers.source_urls exists
            if "identifiers" not in doc:
                update_ops["identifiers"] = {"source_urls": []}
                needs_update = True
            elif "source_urls" not in doc["identifiers"]:
                update_ops["identifiers.source_urls"] = []
                needs_update = True

            # 2. Migrate URL information to source_urls
            if needs_update or self._should_migrate_urls(doc):
                source_urls = self._extract_source_urls(doc)
                if source_urls:
                    update_ops["identifiers.source_urls"] = source_urls
                    needs_update = True

            # 3. Ensure proper task_info structure
            if "task_info" in doc and self._should_migrate_task_info(doc["task_info"]):
                migrated_task_info = self._migrate_task_info(doc["task_info"])
                update_ops["task_info"] = migrated_task_info
                needs_update = True

            # Apply updates
            if needs_update:
                await self.collection.update_one(
                    {"_id": doc["_id"]}, {"$set": update_ops}
                )
                self.migration_stats["documents_updated"] += 1

                if self.migration_stats["documents_processed"] % 100 == 0:
                    logger.info(
                        f"Processed {self.migration_stats['documents_processed']} documents..."
                    )

        logger.info(
            f"✅ Schema migration completed. Updated {self.migration_stats['documents_updated']} documents"
        )

    def _should_migrate_urls(self, doc: Dict[str, Any]) -> bool:
        """Check if document URLs should be migrated."""
        if "identifiers" not in doc or "source_urls" not in doc["identifiers"]:
            return True

        # Check if source_urls is empty but we have URL data
        if not doc["identifiers"]["source_urls"]:
            return (
                doc.get("content", {}).get("pdf_url")
                or doc.get("content", {}).get("source_page_url")
                or doc.get("identifiers", {}).get("doi")
                or doc.get("identifiers", {}).get("arxiv_id")
            )

        return False

    def _extract_source_urls(self, doc: Dict[str, Any]) -> List[str]:
        """Extract source URLs from document."""
        urls = []

        # From content
        if content := doc.get("content"):
            if pdf_url := content.get("pdf_url"):
                urls.append(pdf_url)
            if source_page_url := content.get("source_page_url"):
                urls.append(source_page_url)

        # From identifiers (construct URLs)
        if identifiers := doc.get("identifiers"):
            if doi := identifiers.get("doi"):
                urls.append(f"https://doi.org/{doi}")
            if arxiv_id := identifiers.get("arxiv_id"):
                urls.append(f"https://arxiv.org/abs/{arxiv_id}")

        return list(set(urls))  # Remove duplicates

    def _should_migrate_task_info(self, task_info: Dict[str, Any]) -> bool:
        """Check if task_info needs migration."""
        return "enhanced_component_status" not in task_info

    def _migrate_task_info(self, task_info: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate task_info to new format."""
        # Keep existing fields and add enhanced structure
        migrated = task_info.copy()

        # Add enhanced_component_status if missing
        if "enhanced_component_status" not in migrated:
            migrated["enhanced_component_status"] = {
                "metadata": {"status": "pending", "stage": "等待开始"},
                "content": {"status": "pending", "stage": "等待开始"},
                "references": {"status": "pending", "stage": "等待开始"},
            }

        return migrated

    async def manage_indexes(self):
        """Manage database indexes."""
        logger.info("🔨 Phase 3: Managing database indexes...")

        # Drop problematic indexes
        await self.drop_problematic_indexes()

        # Create new indexes
        await self.create_enhanced_indexes()

    async def drop_problematic_indexes(self):
        """Drop problematic unique indexes."""
        problematic_indexes = [
            "fingerprint_unique_index",
            "doi_unique_index",
            "arxiv_unique_index",
            "pmid_unique_index",
        ]

        for index_name in problematic_indexes:
            try:
                await self.collection.drop_index(index_name)
                self.migration_stats["indexes_dropped"] += 1
                logger.info(f"✅ Dropped problematic index: {index_name}")
            except OperationFailure:
                logger.info(f"ℹ️ Index {index_name} not found (already dropped)")

    async def create_enhanced_indexes(self):
        """Create enhanced indexes for waterfall deduplication."""
        indexes = [
            # Core identifier indexes
            IndexModel([("identifiers.doi", ASCENDING)], name="doi_query_index"),
            IndexModel([("identifiers.arxiv_id", ASCENDING)], name="arxiv_query_index"),
            IndexModel([("identifiers.pmid", ASCENDING)], name="pmid_query_index"),
            # Content fingerprint (partial)
            IndexModel(
                [("identifiers.fingerprint", ASCENDING)],
                name="fingerprint_partial_index",
                partialFilterExpression={"identifiers.fingerprint": {"$exists": True}},
            ),
            # Source URLs
            IndexModel(
                [("identifiers.source_urls", ASCENDING)], name="source_urls_index"
            ),
            # Task management
            IndexModel([("task_info.task_id", ASCENDING)], name="task_id_index"),
            IndexModel([("task_info.status", ASCENDING)], name="task_status_index"),
            # Processing state
            IndexModel(
                [("task_info.status", ASCENDING), ("identifiers.doi", ASCENDING)],
                name="processing_doi_index",
                partialFilterExpression={
                    "task_info.status": {"$in": ["pending", "processing"]},
                    "identifiers.doi": {"$exists": True},
                },
            ),
            # Metadata search
            IndexModel([("metadata.title", TEXT)], name="title_search_index"),
            IndexModel([("metadata.title", ASCENDING)], name="title_exact_index"),
            # Time-based
            IndexModel([("created_at", ASCENDING)], name="created_at_index"),
            IndexModel([("updated_at", ASCENDING)], name="updated_at_index"),
        ]

        for index in indexes:
            try:
                await self.collection.create_indexes([index])
                self.migration_stats["indexes_created"] += 1
                logger.info(f"✅ Created index: {index.document['name']}")
            except OperationFailure as e:
                if "already exists" in str(e):
                    logger.info(f"ℹ️ Index {index.document['name']} already exists")
                else:
                    logger.warning(
                        f"⚠️ Failed to create index {index.document['name']}: {e}"
                    )

    async def validate_data_consistency(self):
        """Validate data consistency after migration."""
        logger.info("🔍 Phase 4: Validating data consistency...")

        # Check for documents without required fields
        missing_identifiers = await self.collection.count_documents(
            {"identifiers": {"$exists": False}}
        )

        if missing_identifiers > 0:
            logger.warning(
                f"⚠️ Found {missing_identifiers} documents without identifiers"
            )

        # Check for duplicate fingerprints
        pipeline = [
            {"$match": {"identifiers.fingerprint": {"$ne": None}}},
            {"$group": {"_id": "$identifiers.fingerprint", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
        ]

        duplicates = await self.collection.aggregate(pipeline).to_list(length=None)

        if duplicates:
            logger.warning(f"⚠️ Found {len(duplicates)} duplicate fingerprints")
        else:
            logger.info("✅ No duplicate fingerprints found")

        # Validate task_info structure
        invalid_task_info = await self.collection.count_documents(
            {"task_info": {"$exists": True}, "task_info.task_id": {"$exists": False}}
        )

        if invalid_task_info > 0:
            logger.warning(
                f"⚠️ Found {invalid_task_info} documents with invalid task_info"
            )

        logger.info("✅ Data consistency validation completed")

    async def optimize_database(self):
        """Optimize database performance."""
        logger.info("⚡ Phase 5: Optimizing database performance...")

        # Analyze collection stats
        stats = await self.db.command("collStats", "literatures")
        logger.info(
            f"Collection stats: {stats['count']} documents, {stats['size']} bytes"
        )

        # Run database command for reindexing
        try:
            await self.db.command("reIndex", "literatures")
            logger.info("✅ Collection reindexed")
        except Exception as e:
            logger.warning(f"⚠️ Reindex failed (not critical): {e}")

        # Compact database (if needed)
        logger.info("✅ Database optimization completed")

    def print_migration_summary(self):
        """Print migration summary."""
        logger.info("\n" + "=" * 50)
        logger.info("📊 MIGRATION SUMMARY")
        logger.info("=" * 50)

        for key, value in self.migration_stats.items():
            logger.info(f"{key.replace('_', ' ').title()}: {value}")

        logger.info("=" * 50)
        logger.info("🎉 Migration completed successfully!")


async def main():
    """Main migration function."""
    migration = DatabaseMigrationEnhanced()
    await migration.run_migration()


if __name__ == "__main__":
    asyncio.run(main())
