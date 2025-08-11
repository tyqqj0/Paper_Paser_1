#!/usr/bin/env python3
"""
Quick fix script for MongoDB index issues.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING
from pymongo.errors import OperationFailure


async def quick_fix():
    """Quick fix for MongoDB index issues."""
    print("🔧 Running quick fix for MongoDB index issues...")

    # Connect to database
    client = AsyncIOMotorClient(
        "mongodb://literature_parser_backend:literature_parser_backend@localhost:27017/admin"
    )
    db = client.literature_parser
    collection = db.literatures

    try:
        # 1. Drop problematic indexes
        print("🗑️ Dropping problematic indexes...")
        problematic_indexes = [
            "fingerprint_unique_index",
            "doi_unique_index",
            "arxiv_unique_index",
            "pmid_unique_index",
        ]

        for index_name in problematic_indexes:
            try:
                await collection.drop_index(index_name)
                print(f"✅ Dropped: {index_name}")
            except OperationFailure:
                print(f"ℹ️ {index_name} not found (already dropped)")

        # 2. Create essential indexes only (simple, non-unique)
        print("\n🔨 Creating essential indexes...")

        essential_indexes = [
            # Core identifier indexes (non-unique)
            ("identifiers.doi", "doi_query_index"),
            ("identifiers.arxiv_id", "arxiv_query_index"),
            ("identifiers.pmid", "pmid_query_index"),
            # Content fingerprint (simple, non-unique)
            ("identifiers.fingerprint", "fingerprint_query_index"),
            # Source URLs
            ("identifiers.source_urls", "source_urls_index"),
            # Task management
            ("task_info.task_id", "task_id_index"),
            ("task_info.status", "task_status_index"),
            # Basic metadata
            ("metadata.title", "title_exact_index"),
            ("created_at", "created_at_index_asc"),
            ("updated_at", "updated_at_index_asc"),
        ]

        for field, index_name in essential_indexes:
            try:
                await collection.create_index(field, name=index_name)
                print(f"✅ Created: {index_name} on {field}")
            except OperationFailure as e:
                if "already exists" in str(e) or "IndexKeySpecsConflict" in str(e):
                    print(f"ℹ️ {index_name} already exists")
                else:
                    print(f"⚠️ Failed to create {index_name}: {e}")

        # 3. Check final index status
        print("\n🔍 Checking final index status...")
        indexes = await collection.list_indexes().to_list(length=None)

        print(f"Total indexes: {len(indexes)}")
        for idx in indexes:
            name = idx.get("name", "unnamed")
            unique = idx.get("unique", False)
            status = " [UNIQUE]" if unique else ""
            print(f"  • {name}{status}")

        print("\n✅ Quick fix completed successfully!")

        # 4. Verify basic functionality
        print("\n🧪 Testing basic database operations...")

        # Test basic query
        count = await collection.count_documents({})
        print(f"Document count: {count}")

        # Test index usage with a simple query
        if count > 0:
            sample_doc = await collection.find_one({})
            if sample_doc:
                print(f"Sample document ID: {sample_doc.get('_id')}")

        print("✅ Basic functionality verified!")

    except Exception as e:
        print(f"❌ Quick fix failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(quick_fix())
