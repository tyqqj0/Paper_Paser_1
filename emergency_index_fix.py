#!/usr/bin/env python3
"""
Emergency fix for fingerprint_unique_index issue.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure


async def emergency_fix():
    """Emergency fix for fingerprint index issue."""
    print("🚨 Emergency fix for fingerprint_unique_index...")

    # Connect to database
    client = AsyncIOMotorClient(
        "mongodb://literature_parser_backend:literature_parser_backend@localhost:27017/admin"
    )
    db = client.literature_parser
    collection = db.literatures

    try:
        # 1. List all indexes first
        print("📋 Current indexes:")
        indexes = await collection.list_indexes().to_list(length=None)
        for idx in indexes:
            name = idx.get("name", "unnamed")
            unique = idx.get("unique", False)
            key = idx.get("key", {})
            print(f"  • {name}: {key} {'[UNIQUE]' if unique else ''}")

        # 2. Drop the problematic unique index
        print("\n🗑️ Dropping fingerprint_unique_index...")
        try:
            await collection.drop_index("fingerprint_unique_index")
            print("✅ fingerprint_unique_index dropped successfully")
        except OperationFailure as e:
            print(f"⚠️ Failed to drop fingerprint_unique_index: {e}")

        # 3. Drop any other problematic indexes
        problematic_indexes = [
            "doi_unique_index",
            "arxiv_unique_index",
            "pmid_unique_index",
            "title_unique_index",
        ]

        for index_name in problematic_indexes:
            try:
                await collection.drop_index(index_name)
                print(f"✅ Dropped: {index_name}")
            except OperationFailure:
                print(f"ℹ️ {index_name} not found")

        # 4. Clean up any documents with null fingerprints that might be causing issues
        print("\n🧹 Cleaning up problematic documents...")

        # Count documents with null fingerprints
        null_count = await collection.count_documents({"identifiers.fingerprint": None})
        print(f"Documents with null fingerprint: {null_count}")

        if null_count > 1:
            # Keep only the most recent one
            docs = (
                await collection.find({"identifiers.fingerprint": None})
                .sort("created_at", -1)
                .to_list(length=None)
            )
            if len(docs) > 1:
                docs_to_delete = docs[
                    1:
                ]  # Keep the first (most recent), delete the rest
                ids_to_delete = [doc["_id"] for doc in docs_to_delete]
                result = await collection.delete_many({"_id": {"$in": ids_to_delete}})
                print(
                    f"✅ Deleted {result.deleted_count} duplicate null fingerprint documents"
                )

        # 5. Create new non-unique indexes
        print("\n🔨 Creating new non-unique indexes...")

        essential_indexes = [
            ("identifiers.doi", "doi_query_index"),
            ("identifiers.arxiv_id", "arxiv_query_index"),
            ("identifiers.pmid", "pmid_query_index"),
            ("identifiers.fingerprint", "fingerprint_query_index"),
            ("identifiers.source_urls", "source_urls_index"),
            ("task_info.task_id", "task_id_index"),
            ("task_info.status", "task_status_index"),
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

        # 6. Final verification
        print("\n🔍 Final verification...")
        final_indexes = await collection.list_indexes().to_list(length=None)

        unique_indexes = [idx for idx in final_indexes if idx.get("unique", False)]
        if unique_indexes:
            print(f"⚠️ Still have {len(unique_indexes)} unique indexes:")
            for idx in unique_indexes:
                print(f"  • {idx.get('name', 'unnamed')}: {idx.get('key', {})}")
        else:
            print("✅ No unique indexes found - all good!")

        print(f"\nTotal indexes: {len(final_indexes)}")

        # 7. Test insertion
        print("\n🧪 Testing document insertion...")
        test_doc = {
            "identifiers": {
                "doi": "test.emergency.fix",
                "arxiv_id": None,
                "pmid": None,
                "fingerprint": None,
                "source_urls": [],
            },
            "metadata": {"title": "Test Document"},
            "task_info": {"task_id": "test-123", "status": "testing"},
            "created_at": "2025-07-17T00:00:00Z",
            "updated_at": "2025-07-17T00:00:00Z",
        }

        try:
            result = await collection.insert_one(test_doc)
            print(f"✅ Test insertion successful: {result.inserted_id}")

            # Clean up test document
            await collection.delete_one({"_id": result.inserted_id})
            print("✅ Test document cleaned up")

        except Exception as e:
            print(f"❌ Test insertion failed: {e}")

        print("\n🎉 Emergency fix completed!")

    except Exception as e:
        print(f"❌ Emergency fix failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(emergency_fix())
