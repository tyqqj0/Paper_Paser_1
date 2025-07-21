#!/usr/bin/env python3
"""
Simple test to verify the fixes work with proxy disabled
"""
import asyncio
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8000"


async def test_with_proxy_disabled():
    """Test with proxy disabled to see if our fixes work."""
    print("=" * 60)
    print("Testing with proxy disabled")
    print("=" * 60)

    # Test paper with DOI that should extract ArXiv ID
    paper_data = {
        "title": "Attention Is All You Need",
        "doi": "10.48550/arXiv.1706.03762",
        "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit"],
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            # Submit task
            response = await client.post(f"{BASE_URL}/api/literature", json=paper_data)
            print(f"Submit response: {response.status_code}")

            if response.status_code == 202:
                result = response.json()
                task_id = result["task_id"]
                print(f"Task ID: {task_id}")

                # Wait and poll for completion
                print("Waiting for task completion...")
                for i in range(24):  # 2 minutes total
                    await asyncio.sleep(5)

                    # Check current status
                    status_response = await client.get(f"{BASE_URL}/api/task/{task_id}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        current_status = status_data.get("status", "unknown")

                        # Print progress
                        print(f"Check {i+1}: {current_status}")

                        # Show component details
                        if "component_status" in status_data:
                            for comp, comp_info in status_data[
                                "component_status"
                            ].items():
                                if isinstance(comp_info, dict):
                                    comp_status = comp_info.get("status", "unknown")
                                    comp_stage = comp_info.get("stage", "no stage")
                                    print(f"  {comp}: {comp_status} - {comp_stage}")

                        # Break if completed
                        if current_status not in ["progress", "processing", "pending"]:
                            print(f"Task completed with status: {current_status}")
                            break
                    else:
                        print(f"Status check failed: {status_response.status_code}")
                        break

                # Final analysis
                final_response = await client.get(f"{BASE_URL}/api/task/{task_id}")
                if final_response.status_code == 200:
                    final_data = final_response.json()

                    print("\n" + "=" * 60)
                    print("FINAL ANALYSIS")
                    print("=" * 60)

                    metadata_status = (
                        final_data.get("component_status", {})
                        .get("metadata", {})
                        .get("status", "unknown")
                    )
                    content_status = (
                        final_data.get("component_status", {})
                        .get("content", {})
                        .get("status", "unknown")
                    )
                    references_status = (
                        final_data.get("component_status", {})
                        .get("references", {})
                        .get("status", "unknown")
                    )
                    overall_status = final_data.get("status", "unknown")

                    print(f"Overall Status: {overall_status}")
                    print(f"Metadata: {metadata_status}")
                    print(f"Content: {content_status}")
                    print(f"References: {references_status}")

                    # Check if we got metadata
                    if "metadata" in final_data:
                        metadata = final_data["metadata"]
                        print(f"\nMetadata Found:")
                        print(f"  Title: {metadata.get('title', 'N/A')}")
                        print(f"  Authors: {len(metadata.get('authors', []))} authors")
                        print(f"  Year: {metadata.get('year', 'N/A')}")
                        print(
                            f"  Abstract: {'Yes' if metadata.get('abstract') else 'No'}"
                        )

                    # Analysis
                    print(f"\nFix Analysis:")
                    if metadata_status == "success":
                        print("✅ DOI-to-ArXiv extraction working!")
                    else:
                        print("❌ DOI-to-ArXiv extraction failed")

                    if overall_status == "failed" and (
                        metadata_status == "failed" or references_status == "failed"
                    ):
                        print("✅ Status determination logic working!")
                    elif (
                        overall_status == "partial_success"
                        and content_status == "failed"
                    ):
                        print(
                            "✅ Status determination logic working (partial success due to content failure)!"
                        )
                    elif (
                        overall_status == "success"
                        and metadata_status == "success"
                        and references_status == "success"
                    ):
                        print("✅ Paper processed successfully!")
                    else:
                        print("❌ Status determination needs checking")

            else:
                print(f"Failed to submit: {response.status_code}")
                print(response.text)

        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Run the test."""
    print(f"Test started at {datetime.now()}")
    await test_with_proxy_disabled()
    print(f"\nTest completed at {datetime.now()}")


if __name__ == "__main__":
    asyncio.run(main())
