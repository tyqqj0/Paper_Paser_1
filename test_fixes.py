#!/usr/bin/env python3
"""
Test script to verify the fixes for DOI-to-ArXiv extraction and status determination.
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"


async def test_attention_paper_fix():
    """Test the Attention paper with the DOI-to-ArXiv fix."""
    print("=" * 60)
    print("Testing Attention paper with DOI-to-ArXiv fix")
    print("=" * 60)

    # Test paper with DOI that should extract ArXiv ID
    paper_data = {
        "title": "Attention Is All You Need",
        "doi": "10.48550/arXiv.1706.03762",
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
                max_wait = 120  # 2 minutes
                poll_interval = 10  # 10 seconds

                for i in range(max_wait // poll_interval):
                    await asyncio.sleep(poll_interval)

                    # Check current status
                    status_response = await client.get(f"{BASE_URL}/api/task/{task_id}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        current_status = status_data.get("status", "unknown")

                        # Print progress update
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

                    # Print metadata to verify ArXiv extraction worked
                    if "metadata" in status_data:
                        metadata = status_data["metadata"]
                        print(f"\nMetadata Retrieved:")
                        print(f"  Title: {metadata.get('title', 'N/A')}")
                        print(f"  Authors: {len(metadata.get('authors', []))} authors")
                        print(f"  Year: {metadata.get('year', 'N/A')}")
                        print(
                            f"  Abstract: {'Available' if metadata.get('abstract') else 'Not available'}"
                        )

                    # Check if status is correctly "failed" for metadata+references failure
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

                    print(f"\nStatus Analysis:")
                    print(f"  Metadata status: {metadata_status}")
                    print(f"  Content status: {content_status}")
                    print(f"  References status: {references_status}")
                    print(f"  Overall status: {status_data['status']}")

                    # Verify fixes worked
                    print(f"\nFix Analysis:")
                    if metadata_status == "success":
                        print("✅ DOI-to-ArXiv extraction FIX WORKED!")
                    else:
                        print("❌ DOI-to-ArXiv extraction might still have issues")

                    if content_status == "failed":
                        print("✅ Content parsing failure detection FIX WORKED!")
                    elif content_status == "success":
                        print(
                            "⚠️  Content shows success (check if GROBID actually worked)"
                        )
                    else:
                        print("❌ Content status unclear")

                    if status_data["status"] == "failed":
                        print("✅ Status determination FIX WORKED!")
                    elif (
                        status_data["status"] == "success"
                        and metadata_status == "success"
                    ):
                        print(
                            "✅ Overall success - both metadata and content fixes worked!"
                        )
                    else:
                        print("❌ Status determination might still have issues")

                    # Print any error info
                    if "component_status" in status_data:
                        for comp, comp_info in status_data["component_status"].items():
                            if (
                                isinstance(comp_info, dict)
                                and "error_info" in comp_info
                            ):
                                print(f"  {comp} error: {comp_info['error_info']}")

                else:
                    print(f"Failed to get status: {status_response.status_code}")
            else:
                print(f"Failed to submit task: {response.status_code}")
                print(response.text)

        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Run all tests."""
    print(f"Starting tests at {datetime.now()}")
    await test_attention_paper_fix()
    print(f"\nTests completed at {datetime.now()}")


if __name__ == "__main__":
    asyncio.run(main())
