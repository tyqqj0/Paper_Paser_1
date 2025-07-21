#!/usr/bin/env python3
"""
Debug script for Attention paper metadata fetching.
"""

import asyncio
import aiohttp


async def debug_attention_paper():
    """Debug why Attention paper metadata is not being fetched."""
    print("🔍 Debugging Attention paper metadata fetching...")

    # Test DOI: 10.48550/arXiv.1706.03762
    doi = "10.48550/arXiv.1706.03762"
    arxiv_id = "1706.03762"

    async with aiohttp.ClientSession() as session:

        # Test 1: CrossRef API
        print(f"\n📚 Test 1: CrossRef API for DOI {doi}")
        crossref_url = f"https://api.crossref.org/works/{doi}"

        try:
            async with session.get(
                crossref_url,
                headers={
                    "User-Agent": "literature-parser/1.0 (mailto:literature-parser@example.com)"
                },
            ) as response:
                print(f"CrossRef Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    work = data.get("message", {})
                    print(
                        f"✅ Title: {work.get('title', ['N/A'])[0] if work.get('title') else 'N/A'}"
                    )
                    print(f"✅ Authors: {len(work.get('author', []))} authors")
                    print(
                        f"✅ Year: {work.get('published-print', {}).get('date-parts', [[None]])[0][0]}"
                    )
                else:
                    error_text = await response.text()
                    print(f"❌ CrossRef Error: {error_text[:200]}...")
        except Exception as e:
            print(f"❌ CrossRef Exception: {e}")

        # Test 2: Semantic Scholar API
        print(f"\n🧠 Test 2: Semantic Scholar API for DOI {doi}")
        ss_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"

        try:
            async with session.get(
                ss_url,
                params={
                    "fields": "paperId,title,abstract,venue,year,referenceCount,citationCount,authors,externalIds,url"
                },
            ) as response:
                print(f"Semantic Scholar Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Title: {data.get('title', 'N/A')}")
                    print(f"✅ Authors: {len(data.get('authors', []))} authors")
                    print(f"✅ Year: {data.get('year', 'N/A')}")
                    print(f"✅ Venue: {data.get('venue', 'N/A')}")
                else:
                    error_text = await response.text()
                    print(f"❌ Semantic Scholar Error: {error_text[:200]}...")
        except Exception as e:
            print(f"❌ Semantic Scholar Exception: {e}")

        # Test 3: Try with ArXiv ID
        print(f"\n📄 Test 3: Semantic Scholar API for ArXiv ID {arxiv_id}")
        ss_arxiv_url = (
            f"https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}"
        )

        try:
            async with session.get(
                ss_arxiv_url,
                params={
                    "fields": "paperId,title,abstract,venue,year,referenceCount,citationCount,authors,externalIds,url"
                },
            ) as response:
                print(f"Semantic Scholar ArXiv Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Title: {data.get('title', 'N/A')}")
                    print(f"✅ Authors: {len(data.get('authors', []))} authors")
                    print(f"✅ Year: {data.get('year', 'N/A')}")
                    print(f"✅ Venue: {data.get('venue', 'N/A')}")
                else:
                    error_text = await response.text()
                    print(f"❌ Semantic Scholar ArXiv Error: {error_text[:200]}...")
        except Exception as e:
            print(f"❌ Semantic Scholar ArXiv Exception: {e}")

        # Test 4: Test direct ArXiv access
        print(f"\n📰 Test 4: Direct ArXiv access")
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"

        try:
            async with session.get(arxiv_url) as response:
                print(f"ArXiv Status: {response.status}")
                if response.status == 200:
                    print("✅ ArXiv paper exists and is accessible")
                else:
                    print(f"❌ ArXiv access failed: {response.status}")
        except Exception as e:
            print(f"❌ ArXiv Exception: {e}")

    print("\n🎯 Diagnosis Summary:")
    print(
        "The Attention paper should be available through Semantic Scholar with ArXiv ID."
    )
    print("If the APIs are working, the issue might be in our metadata fetching logic.")


async def test_working_papers():
    """Test papers that we know work."""
    print("\n\n🧪 Testing papers that work vs don't work...")

    test_cases = [
        {
            "name": "BERT (works)",
            "doi": "10.18653/v1/N19-1423",
            "expected": "should work",
        },
        {
            "name": "Attention (doesn't work)",
            "doi": "10.48550/arXiv.1706.03762",
            "expected": "has issues",
        },
    ]

    async with aiohttp.ClientSession() as session:
        for case in test_cases:
            print(f"\n📋 Testing {case['name']}: {case['doi']}")

            # Test CrossRef
            crossref_url = f"https://api.crossref.org/works/{case['doi']}"
            try:
                async with session.get(
                    crossref_url,
                    headers={
                        "User-Agent": "literature-parser/1.0 (mailto:literature-parser@example.com)"
                    },
                ) as response:
                    print(f"  CrossRef: {response.status}")
            except Exception as e:
                print(f"  CrossRef: ERROR - {e}")

            # Test Semantic Scholar
            ss_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{case['doi']}"
            try:
                async with session.get(
                    ss_url, params={"fields": "title,year"}
                ) as response:
                    print(f"  Semantic Scholar: {response.status}")
            except Exception as e:
                print(f"  Semantic Scholar: ERROR - {e}")


if __name__ == "__main__":
    asyncio.run(debug_attention_paper())
    asyncio.run(test_working_papers())
