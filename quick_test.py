#!/usr/bin/env python3
"""
Quick test script for basic system functionality.
"""

import asyncio
import aiohttp
import json
from loguru import logger


async def test_basic_functionality():
    """Test basic API functionality after index fixes."""
    print("🧪 Testing basic system functionality...")

    base_url = "http://localhost:8000/api"

    async with aiohttp.ClientSession() as session:
        try:
            # Test 1: Submit a simple DOI
            print("\n📝 Test 1: Submit literature with DOI...")
            test_data = {"doi": "10.1234/test.doi.example"}

            async with session.post(
                f"{base_url}/literature", json=test_data
            ) as response:
                if response.status == 202:
                    result = await response.json()
                    task_id = result.get("task_id")
                    print(f"✅ Task created: {task_id}")

                    # Test 2: Check task status
                    print("\n📊 Test 2: Check task status...")
                    for i in range(30):  # Wait up to 30 seconds
                        async with session.get(
                            f"{base_url}/task/{task_id}"
                        ) as status_response:
                            if status_response.status == 200:
                                status_data = await status_response.json()
                                status = status_data.get("status")
                                stage = status_data.get("stage", "Processing")

                                print(f"Status: {status}, Stage: {stage}")

                                if status in ["SUCCESS", "FAILED", "SUCCESS_DUPLICATE"]:
                                    print(f"✅ Task completed with status: {status}")
                                    break

                                await asyncio.sleep(1)
                            else:
                                print(
                                    f"❌ Status check failed: {status_response.status}"
                                )
                                break

                    # Test 3: Submit same DOI again (should detect duplicate)
                    print("\n🔄 Test 3: Submit same DOI again...")
                    async with session.post(
                        f"{base_url}/literature", json=test_data
                    ) as response:
                        if response.status == 202:
                            result = await response.json()
                            task_id2 = result.get("task_id")
                            print(f"✅ Second task created: {task_id2}")

                            # Check if it detects duplicate
                            for i in range(10):
                                async with session.get(
                                    f"{base_url}/task/{task_id2}"
                                ) as status_response:
                                    if status_response.status == 200:
                                        status_data = await status_response.json()
                                        status = status_data.get("status")

                                        if status == "SUCCESS_DUPLICATE":
                                            print("✅ Duplicate detection working!")
                                            break
                                        elif status in ["SUCCESS", "FAILED"]:
                                            print(
                                                f"⚠️ Expected duplicate but got: {status}"
                                            )
                                            break

                                        await asyncio.sleep(1)
                                    else:
                                        break
                        else:
                            print(f"❌ Second submission failed: {response.status}")

                else:
                    print(f"❌ Literature submission failed: {response.status}")
                    text = await response.text()
                    print(f"Error: {text}")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    print("\n🎉 Basic functionality test completed!")


if __name__ == "__main__":
    asyncio.run(test_basic_functionality())
