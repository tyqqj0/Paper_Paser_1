#!/usr/bin/env python3
"""
Quick test to verify status logic fix
"""
import asyncio
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8000"


async def test_status_fix():
    """Test the fixed status determination logic."""
    print("=" * 60)
    print("Testing fixed status determination logic")
    print("=" * 60)

    # Same test paper
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

                # Wait for completion
                print("Waiting for task completion...")
                for i in range(20):
                    await asyncio.sleep(6)

                    status_response = await client.get(f"{BASE_URL}/api/task/{task_id}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        current_status = status_data.get("status", "unknown")

                        print(f"Check {i+1}: {current_status}")

                        if current_status not in ["progress", "processing", "pending"]:
                            print(f"Task completed!")
                            break
                    else:
                        print(f"Status check failed: {status_response.status_code}")
                        break

                # Final check
                final_response = await client.get(f"{BASE_URL}/api/task/{task_id}")
                if final_response.status_code == 200:
                    final_data = final_response.json()

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

                    print(f"\nFINAL RESULT:")
                    print(f"Overall: {overall_status}")
                    print(f"Metadata: {metadata_status}")
                    print(f"Content: {content_status}")
                    print(f"References: {references_status}")

                    # Status logic verification
                    print(f"\nSTATUS LOGIC VERIFICATION:")
                    if (
                        overall_status == "partial_success"
                        and content_status == "failed"
                    ):
                        print(
                            "✅ FIXED! Status shows partial_success due to content failure"
                        )
                    elif overall_status == "success" and content_status == "success":
                        print("✅ WORKING! Full success with all components")
                    elif overall_status == "failed":
                        print(
                            "✅ WORKING! Failed status due to critical component failure"
                        )
                    else:
                        print("❌ Status logic still needs work")
                        print(f"   Expected: partial_success (if content failed)")
                        print(f"   Got: {overall_status}")
                else:
                    print("Failed to get final status")
            else:
                print(f"Failed to submit: {response.status_code}")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_status_fix())
