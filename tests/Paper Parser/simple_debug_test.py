#!/usr/bin/env python3
"""
Simple debug test to check API endpoints.
"""

import asyncio
import aiohttp
import json


async def debug_api_endpoints():
    """Debug API endpoint availability."""
    print("🔍 Debugging API endpoint availability...")

    base_url = "http://localhost:8000"

    async with aiohttp.ClientSession() as session:
        try:
            # Test 1: Check API root
            print("\n📡 Test 1: Check API root...")
            async with session.get(f"{base_url}/") as response:
                print(f"Root endpoint: {response.status}")
                if response.status == 200:
                    text = await response.text()
                    print(f"Response: {text[:200]}...")

            # Test 2: Check API docs
            print("\n📚 Test 2: Check API docs...")
            async with session.get(f"{base_url}/docs") as response:
                print(f"Docs endpoint: {response.status}")

            # Test 3: Create a task
            print("\n📝 Test 3: Create a literature task...")
            test_data = {"doi": "10.1234/debug.test"}

            async with session.post(
                f"{base_url}/api/literature", json=test_data
            ) as response:
                print(f"Literature submission: {response.status}")

                if response.status == 202:
                    result = await response.json()
                    task_id = result.get("task_id")
                    status_url = result.get("status_url")

                    print(f"Task ID: {task_id}")
                    print(f"Status URL: {status_url}")

                    # Test 4: Check task status with different paths
                    print("\n🔍 Test 4: Check task status with different paths...")

                    # Try the official path from status_url
                    print(f"Trying official path: {status_url}")
                    async with session.get(
                        f"{base_url}{status_url}"
                    ) as status_response:
                        print(f"Official path status: {status_response.status}")
                        if status_response.status == 200:
                            data = await status_response.json()
                            print(f"Status data: {data}")

                    # Try direct task endpoint
                    print(f"Trying direct task endpoint: /api/task/{task_id}")
                    async with session.get(
                        f"{base_url}/api/task/{task_id}"
                    ) as status_response:
                        print(f"Direct task endpoint: {status_response.status}")
                        if status_response.status == 200:
                            data = await status_response.json()
                            print(f"Status data: {data}")
                        else:
                            error_text = await status_response.text()
                            print(f"Error response: {error_text}")

                else:
                    error_text = await response.text()
                    print(f"Error creating task: {error_text}")

        except Exception as e:
            print(f"❌ Debug test failed: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_api_endpoints())
