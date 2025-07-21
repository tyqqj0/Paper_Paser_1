#!/usr/bin/env python3
"""
Enhanced index setup script for the new waterfall deduplication system.

This script creates optimized, non-constraining indexes for fast query performance
without blocking duplicate handling at the database level.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, TEXT
from pymongo.errors import OperationFailure


async def setup_enhanced_indexes():
    """Setup enhanced indexes for the new deduplication system."""
    print("🚀 Setting up enhanced indexes for waterfall deduplication...")

    # Connect to database
    client = AsyncIOMotorClient(
        "mongodb://literature_parser_backend:literature_parser_backend@localhost:27017/admin"
    )
    db = client.literature_parser
    collection = db.literatures

    try:
        # 1. List and analyze existing indexes
        print("\n📋 Analyzing existing indexes...")
        existing_indexes = await collection.list_indexes().to_list(length=None)

        print("Current indexes:")
        for idx in existing_indexes:
            print(f"  - {idx.get('name', 'unnamed')}: {idx.get('key', {})}")
            if idx.get("unique"):
                print(f"    ⚠️  Unique constraint: {idx.get('unique')}")

        # 2. Drop problematic unique indexes
        print("\n🗑️  Removing problematic unique indexes...")
        problematic_indexes = [
            "fingerprint_unique_index",
            "doi_unique_index",
            "arxiv_unique_index",
        ]

        for index_name in problematic_indexes:
            try:
                await collection.drop_index(index_name)
                print(f"  ✅ Dropped problematic index: {index_name}")
            except OperationFailure as e:
                print(f"  ℹ️  Index {index_name} not found or already dropped: {e}")

        # 3. Create new optimized indexes (non-unique, for query performance only)
        print("\n🔨 Creating new optimized indexes...")

        # Core identifier indexes (non-unique, for fast lookups)
        core_indexes = [
            IndexModel([("identifiers.doi", ASCENDING)], name="doi_query_index"),
            IndexModel([("identifiers.arxiv_id", ASCENDING)], name="arxiv_query_index"),
            IndexModel([("identifiers.pmid", ASCENDING)], name="pmid_query_index"),
        ]

        # Content fingerprint index (partial, non-unique)
        content_indexes = [
            IndexModel(
                [("identifiers.fingerprint", ASCENDING)],
                name="fingerprint_query_index",
                partialFilterExpression={"identifiers.fingerprint": {"$exists": True}},
            ),
        ]

        # Source URL indexes for deduplication
        source_indexes = [
            IndexModel(
                [("identifiers.source_urls", ASCENDING)], name="source_urls_index"
            ),
            IndexModel([("content.pdf_url", ASCENDING)], name="pdf_url_index"),
            IndexModel(
                [("content.source_page_url", ASCENDING)], name="source_page_url_index"
            ),
        ]

        # Task and status indexes
        task_indexes = [
            IndexModel([("task_info.task_id", ASCENDING)], name="task_id_index"),
            IndexModel([("task_info.status", ASCENDING)], name="task_status_index"),
            IndexModel(
                [("task_info.status", ASCENDING), ("created_at", ASCENDING)],
                name="status_created_index",
            ),
        ]

        # Processing state indexes
        processing_indexes = [
            IndexModel(
                [("task_info.status", ASCENDING), ("identifiers.doi", ASCENDING)],
                name="processing_doi_index",
                partialFilterExpression={
                    "task_info.status": {
                        "$in": ["pending", "processing", "in_progress"]
                    },
                    "identifiers.doi": {"$exists": True},
                },
            ),
            IndexModel(
                [("task_info.status", ASCENDING), ("identifiers.arxiv_id", ASCENDING)],
                name="processing_arxiv_index",
                partialFilterExpression={
                    "task_info.status": {
                        "$in": ["pending", "processing", "in_progress"]
                    },
                    "identifiers.arxiv_id": {"$exists": True},
                },
            ),
        ]

        # Metadata search indexes
        metadata_indexes = [
            IndexModel([("metadata.title", TEXT)], name="title_text_index"),
            IndexModel([("metadata.title", ASCENDING)], name="title_exact_index"),
            IndexModel(
                [("metadata.authors.name", ASCENDING)], name="author_name_index"
            ),
            IndexModel([("metadata.year", ASCENDING)], name="year_index"),
            IndexModel([("metadata.journal", ASCENDING)], name="journal_index"),
        ]

        # Time-based indexes for cleanup and analytics
        time_indexes = [
            IndexModel([("created_at", ASCENDING)], name="created_at_index"),
            IndexModel([("updated_at", ASCENDING)], name="updated_at_index"),
            IndexModel(
                [("created_at", ASCENDING)],
                name="failed_cleanup_index",
                partialFilterExpression={"task_info.status": "failed"},
            ),
        ]

        # Create all indexes
        all_indexes = (
            core_indexes
            + content_indexes
            + source_indexes
            + task_indexes
            + processing_indexes
            + metadata_indexes
            + time_indexes
        )

        print(f"Creating {len(all_indexes)} optimized indexes...")

        for index in all_indexes:
            try:
                await collection.create_indexes([index])
                print(f"  ✅ Created index: {index.document.get('name', 'unnamed')}")
            except OperationFailure as e:
                if "already exists" in str(e).lower():
                    print(
                        f"  ℹ️  Index {index.document.get('name', 'unnamed')} already exists"
                    )
                else:
                    print(
                        f"  ⚠️  Failed to create index {index.document.get('name', 'unnamed')}: {e}"
                    )

        # 4. Create compound indexes for common query patterns
        print("\n🔗 Creating compound indexes for common query patterns...")

        compound_indexes = [
            IndexModel(
                [("identifiers.doi", ASCENDING), ("task_info.status", ASCENDING)],
                name="doi_status_compound_index",
            ),
            IndexModel(
                [("identifiers.arxiv_id", ASCENDING), ("task_info.status", ASCENDING)],
                name="arxiv_status_compound_index",
            ),
            IndexModel(
                [("metadata.title", ASCENDING), ("metadata.authors.name", ASCENDING)],
                name="title_author_compound_index",
            ),
            IndexModel(
                [("task_info.status", ASCENDING), ("updated_at", ASCENDING)],
                name="status_updated_compound_index",
            ),
        ]

        for index in compound_indexes:
            try:
                await collection.create_indexes([index])
                print(
                    f"  ✅ Created compound index: {index.document.get('name', 'unnamed')}"
                )
            except OperationFailure as e:
                if "already exists" in str(e).lower():
                    print(
                        f"  ℹ️  Compound index {index.document.get('name', 'unnamed')} already exists"
                    )
                else:
                    print(
                        f"  ⚠️  Failed to create compound index {index.document.get('name', 'unnamed')}: {e}"
                    )

        # 5. Setup tasks collection indexes
        print("\n📝 Setting up task collection indexes...")
        tasks_collection = db.tasks

        task_collection_indexes = [
            IndexModel(
                [("task_id", ASCENDING)], name="celery_task_id_index", unique=True
            ),
            IndexModel([("status", ASCENDING)], name="celery_status_index"),
            IndexModel([("literature_id", ASCENDING)], name="literature_ref_index"),
            IndexModel([("created_at", ASCENDING)], name="task_created_index"),
        ]

        for index in task_collection_indexes:
            try:
                await tasks_collection.create_indexes([index])
                print(
                    f"  ✅ Created task index: {index.document.get('name', 'unnamed')}"
                )
            except OperationFailure as e:
                if "already exists" in str(e).lower():
                    print(
                        f"  ℹ️  Task index {index.document.get('name', 'unnamed')} already exists"
                    )
                else:
                    print(
                        f"  ⚠️  Failed to create task index {index.document.get('name', 'unnamed')}: {e}"
                    )

        # 6. Verify final index setup
        print("\n🔍 Verifying final index setup...")
        final_indexes = await collection.list_indexes().to_list(length=None)

        print(f"Total indexes created: {len(final_indexes)}")
        print("\nFinal index summary:")
        for idx in final_indexes:
            name = idx.get("name", "unnamed")
            unique = idx.get("unique", False)
            partial = "partialFilterExpression" in idx

            status = ""
            if unique:
                status += " [UNIQUE]"
            if partial:
                status += " [PARTIAL]"

            print(f"  • {name}{status}")

        print("\n✅ Enhanced index setup completed successfully!")
        print("\n📊 Index Benefits:")
        print("  • Fast identifier lookups (DOI, ArXiv, etc.)")
        print("  • Efficient source URL deduplication")
        print("  • Processing state management")
        print("  • Metadata search capabilities")
        print("  • No blocking unique constraints")
        print("  • Optimized for waterfall deduplication")

    except Exception as e:
        print(f"❌ Error during index setup: {e}")
        import traceback

        traceback.print_exc()

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(setup_enhanced_indexes())
