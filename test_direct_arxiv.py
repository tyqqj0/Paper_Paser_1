#!/usr/bin/env python3
"""
Simple test to verify ArXiv ID extraction works correctly
"""
import asyncio
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8000"


async def test_direct_arxiv():
    """Test with direct ArXiv ID to bypass network issues."""
    print("=" * 60)
    print("Testing direct ArXiv ID (bypass network issues)")
    print("=" * 60)

    # Test paper with direct ArXiv ID
    paper_data = {
        "title": "Attention Is All You Need",
        "arxiv_id": "1706.03762",
        "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit"],
    }

    async with httpx.AsyncClient() as client:
        try:
            # Submit task
            response = await client.post(f"{BASE_URL}/api/literature", json=paper_data)
            print(f"Submit response: {response.status_code}")

            if response.status_code == 202:
                result = response.json()
                task_id = result["task_id"]
                print(f"Task ID: {task_id}")

                # Wait for completion with polling
                print("Waiting for task completion...")
                max_wait = 120
                poll_interval = 10

                for i in range(max_wait // poll_interval):
                    await asyncio.sleep(poll_interval)

                    # Check current status
                    status_response = await client.get(f"{BASE_URL}/api/task/{task_id}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        current_status = status_data.get("status", "unknown")

                        print(f"Status check {i+1}: {current_status}")

                        # Check if task is complete
                        if current_status not in ["progress", "processing", "pending"]:
                            print("Task completed!")
                            break

                        # Print component statuses for debugging
                        if "component_status" in status_data:
                            for comp, comp_info in status_data[
                                "component_status"
                            ].items():
                                if isinstance(comp_info, dict):
                                    comp_status = comp_info.get("status", "unknown")
                                    comp_stage = comp_info.get("stage", "no stage")
                                    print(f"  {comp}: {comp_status} - {comp_stage}")
                    else:
                        print("Task status endpoint failed")
                        break

                # Check final status
                status_response = await client.get(f"{BASE_URL}/api/task/{task_id}")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"\nFinal Status: {status_data['status']}")

                    # Print component statuses
                    if "component_status" in status_data:
                        print("\nComponent Status:")
                        for comp, status in status_data["component_status"].items():
                            if isinstance(status, dict):
                                print(
                                    f"  {comp}: {status.get('status', 'unknown')} - {status.get('stage', 'no stage')}"
                                )
                            else:
                                print(f"  {comp}: {status}")

                    # Print metadata to verify ArXiv worked
                    if "metadata" in status_data:
                        metadata = status_data["metadata"]
                        print(f"\nMetadata Retrieved:")
                        print(f"  Title: {metadata.get('title', 'N/A')}")
                        print(f"  Authors: {len(metadata.get('authors', []))} authors")
                        print(f"  Year: {metadata.get('year', 'N/A')}")
                        print(
                            f"  Abstract: {'Available' if metadata.get('abstract') else 'Not available'}"
                        )

                    # Status analysis
                    metadata_status = (
                        status_data.get("component_status", {})
                        .get("metadata", {})
                        .get("status", "unknown")
                    )
                    content_status = (
                        status_data.get("component_status", {})
                        .get("content", {})
                        .get("status", "unknown")
                    )
                    references_status = (
                        status_data.get("component_status", {})
                        .get("references", {})
                        .get("status", "unknown")
                    )

                    print(f"\nDirect ArXiv Test Results:")
                    print(f"  Metadata: {metadata_status}")
                    print(f"  Content: {content_status}")
                    print(f"  References: {references_status}")
                    print(f"  Overall: {status_data['status']}")

                    if metadata_status == "success":
                        print("✅ Direct ArXiv ID works!")
                    else:
                        print("❌ Direct ArXiv ID failed")

                else:
                    print(f"Failed to get final status: {status_response.status_code}")
            else:
                print(f"Failed to submit task: {response.status_code}")
                print(response.text)

        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Run the test."""
    print(f"Starting direct ArXiv test at {datetime.now()}")
    await test_direct_arxiv()
    print(f"\nTest completed at {datetime.now()}")


if __name__ == "__main__":
    asyncio.run(main())
