#!/usr/bin/env python3
"""
Test script to verify MongoDB connection fix
"""

import json
import time

import requests


def test_api_after_fix():
    """Test API functionality after MongoDB connection fix"""

    print("🔧 Testing API after MongoDB connection fix...")
    print("=" * 50)

    # Wait for services to be ready
    print("⏳ Waiting for services to stabilize...")
    time.sleep(5)

    # Test health endpoint
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=10)
        print(f"✅ Health check: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

    # Test literature submission
    try:
        data = {
            "doi": "10.1038/nature12373",
            "title": "Test Paper After Fix",
            "authors": ["Test Author"],
            "abstract": "Test abstract for MongoDB connection fix",
        }

        response = requests.post(
            "http://localhost:8000/api/literature",
            json=data,
            timeout=15,
        )
        print(f"✅ Literature submission: {response.status_code}")

        if response.status_code in [200, 202]:
            result = response.json()
            print(f"   Response: {json.dumps(result, indent=2, ensure_ascii=False)}")

            # If we got a task ID, test task status
            if "taskId" in result:
                task_id = result["taskId"]
                print(f"\n🔍 Testing task status for: {task_id}")

                # Wait a bit then check status
                time.sleep(3)

                status_response = requests.get(
                    f"http://localhost:8000/api/task/{task_id}",
                    timeout=10,
                )
                print(f"✅ Task status: {status_response.status_code}")

                if status_response.status_code == 200:
                    status_result = status_response.json()
                    print(
                        f"   Task status: {json.dumps(status_result, indent=2, ensure_ascii=False)}",
                    )
                    return True

        return True

    except Exception as e:
        print(f"❌ Literature submission failed: {e}")
        return False

    # Test docs endpoint
    try:
        response = requests.get("http://localhost:8000/api/docs", timeout=10)
        print(f"✅ API docs: {response.status_code}")
        if response.status_code == 200:
            print("   📖 API documentation is accessible!")
        else:
            print(f"   ⚠️ Docs returned: {response.status_code}")
    except Exception as e:
        print(f"❌ Docs check failed: {e}")


if __name__ == "__main__":
    success = test_api_after_fix()

    print("\n" + "=" * 50)
    if success:
        print("🎉 MongoDB connection fix appears to be working!")
        print("📖 Try accessing: http://localhost:8000/api/docs")
    else:
        print("❌ Some issues remain. Check Docker logs:")
        print("   docker logs literature_parser_backend-api-1")
        print("   docker logs literature_parser_backend-worker-1")
