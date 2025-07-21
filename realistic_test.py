#!/usr/bin/env python3
"""
Realistic test with real DOI/ArXiv papers.
"""

import asyncio
import aiohttp
import json


async def test_with_real_papers():
    """Test with real papers that should return actual data."""
    print("🧪 Testing with real papers...")

    base_url = "http://localhost:8000/api"

    # Test papers that should work
    test_papers = [
        {
            "name": "Attention Is All You Need",
            "doi": "10.48550/arXiv.1706.03762",
            "description": "Famous transformer paper",
        },
        {
            "name": "BERT Paper",
            "doi": "10.18653/v1/N19-1423",
            "description": "BERT language model",
        },
        {
            "name": "GPT-2 Paper",
            "arxiv_id": "1910.13461",
            "description": "GPT-2 language model",
        },
    ]

    async with aiohttp.ClientSession() as session:

        for i, paper in enumerate(test_papers, 1):
            print(f"\n📝 Test {i}: {paper['name']} - {paper['description']}")

            # Prepare test data
            test_data = {}
            if "doi" in paper:
                test_data["doi"] = paper["doi"]
            if "arxiv_id" in paper:
                test_data["arxiv_id"] = paper["arxiv_id"]

            try:
                # Submit literature
                async with session.post(
                    f"{base_url}/literature", json=test_data
                ) as response:
                    if response.status == 202:
                        result = await response.json()
                        task_id = result.get("task_id")
                        print(f"✅ Task created: {task_id}")

                        # Monitor progress
                        print("📊 Monitoring progress...")
                        for j in range(60):  # Wait up to 60 seconds
                            async with session.get(
                                f"{base_url}/task/{task_id}"
                            ) as status_response:
                                if status_response.status == 200:
                                    status_data = await status_response.json()
                                    status = status_data.get("status")
                                    stage = status_data.get("stage", "Processing")

                                    print(f"  Status: {status}, Stage: {stage}")

                                    if status in ["success", "success_created"]:
                                        literature_id = status_data.get("literature_id")
                                        print(
                                            f"✅ Success! Literature ID: {literature_id}"
                                        )

                                        # Get literature details
                                        if literature_id:
                                            async with session.get(
                                                f"{base_url}/literature/{literature_id}"
                                            ) as lit_response:
                                                if lit_response.status == 200:
                                                    lit_data = await lit_response.json()
                                                    print(
                                                        f"📚 Title: {lit_data.get('title', 'N/A')}"
                                                    )
                                                    print(
                                                        f"👥 Authors: {len(lit_data.get('authors', []))} authors"
                                                    )
                                                    print(
                                                        f"📅 Year: {lit_data.get('year', 'N/A')}"
                                                    )
                                                    print(
                                                        f"📖 Journal: {lit_data.get('journal', 'N/A')}"
                                                    )
                                        break

                                    elif status in ["failed", "failure"]:
                                        print(f"❌ Task failed: {status}")
                                        break

                                    await asyncio.sleep(2)
                                else:
                                    print(
                                        f"❌ Status check failed: {status_response.status}"
                                    )
                                    break

                        print("-" * 50)

                    else:
                        error_text = await response.text()
                        print(f"❌ Submission failed: {response.status} - {error_text}")

            except Exception as e:
                print(f"❌ Test failed for {paper['name']}: {e}")

            # Small delay between tests
            await asyncio.sleep(3)

    print("\n🎉 Real paper testing completed!")


if __name__ == "__main__":
    asyncio.run(test_with_real_papers())
