#!/usr/bin/env python3
import asyncio

from literature_parser_backend.services.semantic_scholar import SemanticScholarClient


async def test():
    client = SemanticScholarClient()
    print("Testing Semantic Scholar API client...")

    # Test 1: Get metadata by DOI
    print("\n1. Testing DOI lookup...")
    try:
        metadata = await client.get_metadata("10.1038/nature12373", "doi")
        if metadata:
            print("SUCCESS: Got metadata")
            print(f"Title: {metadata.get('title', 'N/A')}")
            print(f"Venue: {metadata.get('venue', 'N/A')}")
            print(f"Year: {metadata.get('year', 'N/A')}")
            print(f"Authors: {len(metadata.get('authors', []))}")
            print(f"Citation count: {metadata.get('citation_count', 'N/A')}")
            print(f"Reference count: {metadata.get('reference_count', 'N/A')}")
        else:
            print("ERROR: No metadata found")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

    # Test 2: Get metadata by ArXiv ID
    print("\n2. Testing ArXiv ID lookup...")
    try:
        metadata = await client.get_metadata("1706.03762", "arxiv")
        if metadata:
            print("SUCCESS: Got ArXiv metadata")
            print(f"Title: {metadata.get('title', 'N/A')}")
            print(f"Year: {metadata.get('year', 'N/A')}")
            print(f"Authors: {len(metadata.get('authors', []))}")
        else:
            print("WARNING: No ArXiv metadata found")
    except Exception as e:
        print(f"ERROR: {e}")

    # Test 3: Get references
    print("\n3. Testing references lookup...")
    try:
        references = await client.get_references("10.1038/nature12373", limit=5)
        print(f"SUCCESS: Got {len(references)} references")
        for i, ref in enumerate(references[:3], 1):
            print(f"  {i}. {ref.get('title', 'N/A')} ({ref.get('year', 'N/A')})")
    except Exception as e:
        print(f"ERROR: {e}")

    return True


if __name__ == "__main__":
    result = asyncio.run(test())
    print(f"\nTest result: {'PASS' if result else 'FAIL'}")
