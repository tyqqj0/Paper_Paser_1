#!/usr/bin/env python3
"""
Quick test for the PDF download fix
"""
import asyncio
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8000"


async def test_pdf_fix():
    """Test the PDF download fix."""
    print("=" * 60)
    print("Testing PDF download fix")
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

                # Wait longer and check more frequently
                print("Monitoring task progress...")
                for i in range(30):  # 2.5 minutes total
                    await asyncio.sleep(5)

                    # Check current status
                    status_response = await client.get(f"{BASE_URL}/api/task/{task_id}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        current_status = status_data.get("status", "unknown")

                        # Show progress
                        print(f"Check {i+1}: Overall={current_status}")

                        # Show detailed component status
                        if "component_status" in status_data:
                            for comp, comp_info in status_data[
                                "component_status"
                            ].items():
                                if isinstance(comp_info, dict):
                                    comp_status = comp_info.get("status", "unknown")
                                    comp_stage = comp_info.get("stage", "no stage")
                                    print(f"  {comp}: {comp_status} - {comp_stage}")

                        # Break if completed (not just created)
                        if current_status not in [
                            "progress",
                            "processing",
                            "pending",
                            "success_created",
                        ]:
                            print(f"Task completed with final status: {current_status}")
                            break
                    else:
                        print(f"Status check failed: {status_response.status_code}")
                        break

                # Final detailed analysis
                final_response = await client.get(f"{BASE_URL}/api/task/{task_id}")
                if final_response.status_code == 200:
                    final_data = final_response.json()

                    print("\n" + "=" * 60)
                    print("FINAL DETAILED ANALYSIS")
                    print("=" * 60)

                    # Task info
                    task_info = final_data.get("task_info", {})
                    print(f"Task Status: {task_info.get('status', 'unknown')}")

                    # Component details
                    comp_status = final_data.get("component_status", {})
                    for comp in ["metadata", "content", "references"]:
                        if comp in comp_status:
                            comp_info = comp_status[comp]
                            if isinstance(comp_info, dict):
                                status = comp_info.get("status", "unknown")
                                stage = comp_info.get("stage", "no stage")
                                progress = comp_info.get("progress", 0)
                                error = comp_info.get("error_info", None)
                                print(f"\n{comp.upper()}:")
                                print(f"  Status: {status}")
                                print(f"  Stage: {stage}")
                                print(f"  Progress: {progress}%")
                                if error:
                                    print(f"  Error: {error}")

                    # Content specific analysis
                    content_info = final_data.get("content", {})
                    if content_info:
                        grobid_info = content_info.get("grobid_processing_info", {})
                        print(f"\nCONTENT ANALYSIS:")
                        print(f"  PDF URL: {content_info.get('pdf_url', 'N/A')}")
                        print(
                            f"  GROBID Status: {grobid_info.get('status', 'unknown')}"
                        )
                        print(
                            f"  GROBID Error: {grobid_info.get('error_message', 'N/A')}"
                        )

                    # Fix verification
                    print(f"\nFIX VERIFICATION:")
                    metadata_status = comp_status.get("metadata", {}).get(
                        "status", "unknown"
                    )
                    content_status = comp_status.get("content", {}).get(
                        "status", "unknown"
                    )
                    references_status = comp_status.get("references", {}).get(
                        "status", "unknown"
                    )
                    overall_status = task_info.get("status", "unknown")

                    if metadata_status == "success":
                        print("✅ DOI-to-ArXiv extraction working!")
                    else:
                        print("❌ DOI-to-ArXiv extraction failed")

                    if content_status == "success":
                        print("✅ PDF download and parsing working!")
                    elif content_status == "failed":
                        print("⚠️  PDF download/parsing still failing")

                    if (
                        overall_status == "partial_success"
                        and content_status == "failed"
                    ):
                        print("✅ Status logic working correctly!")
                    elif overall_status == "success":
                        print("✅ Full success achieved!")
                    else:
                        print(f"⚠️  Status logic needs review: {overall_status}")

            else:
                print(f"Failed to submit: {response.status_code}")
                print(response.text)

        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Run the test."""
    print(f"PDF fix test started at {datetime.now()}")
    await test_pdf_fix()
    print(f"\nTest completed at {datetime.now()}")


if __name__ == "__main__":
    asyncio.run(main())
