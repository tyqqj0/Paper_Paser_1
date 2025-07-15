#!/usr/bin/env python3
"""
Quick test script for the Literature Parser API
"""

import requests
import json
import time


def test_health():
    """Test health endpoint"""
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        print(f"Health check: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False


def test_docs():
    """Test docs endpoint"""
    try:
        response = requests.get("http://localhost:8000/docs", timeout=5)
        print(f"Docs check: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Docs check failed: {e}")
        return False


def test_literature_api():
    """Test literature submission"""
    try:
        data = {
            "source": {
                "type": "arxiv",
                "identifier": "2301.00001",
                "url": "https://arxiv.org/abs/2301.00001",
            },
            "title": "Test Paper",
            "authors": ["Test Author"],
            "abstract": "Test abstract",
        }

        response = requests.post(
            "http://localhost:8000/api/literature", json=data, timeout=10
        )
        print(f"Literature API: {response.status_code}")
        if response.status_code in [200, 202]:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return True, result.get("taskId")
        return False, None
    except Exception as e:
        print(f"Literature API failed: {e}")
        return False, None


def test_task_status(task_id):
    """Test task status endpoint"""
    if not task_id:
        return False

    try:
        response = requests.get(f"http://localhost:8000/api/task/{task_id}", timeout=5)
        print(f"Task status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Task result: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return True
        return False
    except Exception as e:
        print(f"Task status failed: {e}")
        return False


if __name__ == "__main__":
    print("=== Quick API Test ===")

    # Test health
    print("\n1. Testing health endpoint...")
    health_ok = test_health()

    # Test docs
    print("\n2. Testing docs endpoint...")
    docs_ok = test_docs()

    # Test literature API
    print("\n3. Testing literature API...")
    lit_ok, task_id = test_literature_api()

    # Test task status
    if task_id:
        print(f"\n4. Testing task status for {task_id}...")
        time.sleep(2)  # Wait a bit
        task_ok = test_task_status(task_id)
    else:
        task_ok = False

    print("\n=== Summary ===")
    print(f"Health: {'✅' if health_ok else '❌'}")
    print(f"Docs: {'✅' if docs_ok else '❌'}")
    print(f"Literature API: {'✅' if lit_ok else '❌'}")
    print(f"Task Status: {'✅' if task_ok else '❌'}")

    if health_ok and lit_ok:
        print("\n🎉 Core API functionality is working!")
    else:
        print("\n❌ Some issues found")
