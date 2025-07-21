#!/usr/bin/env python3
"""
Test deduplication logic with different scenarios.
"""

import asyncio
import aiohttp
import json


async def test_deduplication_scenarios():
    """Test different deduplication scenarios."""
    print("🧪 Testing deduplication logic...")

    base_url = "http://localhost:8000/api"

    scenarios = [
        {
            "name": "DOI Deduplication",
            "description": "Submit same DOI twice",
            "data1": {"doi": "10.18653/v1/N19-1423"},
            "data2": {"doi": "10.18653/v1/N19-1423"},
            "expected": "second should be duplicate",
        },
        {
            "name": "ArXiv ID Deduplication",
            "description": "Submit same ArXiv ID twice",
            "data1": {"arxiv_id": "1910.13461"},
            "data2": {"arxiv_id": "1910.13461"},
            "expected": "second should be duplicate",
        },
        {
            "name": "Cross-Identifier Deduplication",
            "description": "Submit DOI first, then ArXiv ID of same paper",
            "data1": {"doi": "10.48550/arXiv.1706.03762"},
            "data2": {"arxiv_id": "1706.03762"},
            "expected": "second should be duplicate (if content fingerprint works)",
        },
        {
            "name": "URL Deduplication",
            "description": "Submit same URL twice",
            "data1": {"url": "https://arxiv.org/abs/1706.03762"},
            "data2": {"url": "https://arxiv.org/abs/1706.03762"},
            "expected": "second should be duplicate",
        },
    ]

    async with aiohttp.ClientSession() as session:

        for i, scenario in enumerate(scenarios, 1):
            print(f"\n{'='*60}")
            print(f"🔍 Scenario {i}: {scenario['name']}")
            print(f"📝 Description: {scenario['description']}")
            print(f"🎯 Expected: {scenario['expected']}")
            print(f"{'='*60}")

            try:
                # Submit first literature
                print(f"\n📤 Submitting first: {scenario['data1']}")
                async with session.post(
                    f"{base_url}/literature", json=scenario["data1"]
                ) as response:
                    if response.status == 202:
                        result1 = await response.json()
                        task_id1 = result1.get("task_id")
                        print(f"✅ First task created: {task_id1}")

                        # Wait for completion
                        final_status1 = await wait_for_completion(
                            session, base_url, task_id1, timeout=45
                        )
                        print(f"📊 First task status: {final_status1}")

                        # Small delay before second submission
                        await asyncio.sleep(2)

                        # Submit second literature
                        print(f"\n📤 Submitting second: {scenario['data2']}")
                        async with session.post(
                            f"{base_url}/literature", json=scenario["data2"]
                        ) as response:
                            if response.status == 202:
                                result2 = await response.json()
                                task_id2 = result2.get("task_id")
                                print(f"✅ Second task created: {task_id2}")

                                # Wait for completion
                                final_status2 = await wait_for_completion(
                                    session, base_url, task_id2, timeout=30
                                )
                                print(f"📊 Second task status: {final_status2}")

                                # Analyze results
                                print(f"\n🎯 Analysis:")
                                if "duplicate" in final_status2.lower():
                                    print(f"✅ PASS: Deduplication worked correctly")
                                elif (
                                    final_status1 == final_status2
                                    and "success" in final_status2.lower()
                                ):
                                    print(
                                        f"⚠️  PARTIAL: Both succeeded but need to check if they're truly different"
                                    )
                                else:
                                    print(
                                        f"❌ FAIL: Expected duplicate detection but got: {final_status2}"
                                    )

                            else:
                                error_text = await response.text()
                                print(
                                    f"❌ Second submission failed: {response.status} - {error_text}"
                                )

                    else:
                        error_text = await response.text()
                        print(
                            f"❌ First submission failed: {response.status} - {error_text}"
                        )

            except Exception as e:
                print(f"❌ Scenario failed: {e}")

            # Delay between scenarios
            await asyncio.sleep(3)

    print(f"\n{'='*60}")
    print("🎉 Deduplication testing completed!")
    print(f"{'='*60}")


async def wait_for_completion(session, base_url, task_id, timeout=30):
    """Wait for task completion and return final status."""
    for i in range(timeout):
        try:
            async with session.get(f"{base_url}/task/{task_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    status = data.get("status", "unknown")

                    if status in [
                        "success",
                        "success_created",
                        "success_duplicate",
                        "failure",
                        "failed",
                    ]:
                        return status

                    if i % 5 == 0:  # Log progress every 5 seconds
                        print(f"  ⏳ Status: {status} ({i}s)")

                    await asyncio.sleep(1)
                else:
                    print(f"  ❌ Status check failed: {response.status}")
                    return "status_check_failed"
        except Exception as e:
            print(f"  ❌ Status check error: {e}")
            return "status_check_error"

    return "timeout"


if __name__ == "__main__":
    asyncio.run(test_deduplication_scenarios())
