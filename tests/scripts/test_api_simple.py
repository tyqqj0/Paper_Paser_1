#!/usr/bin/env python3
"""
Simple script to test if the Literature Parser API is working.
"""

import requests
import json
import time


def test_api_health():
    """Test API health endpoint."""
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=10)
        print(f"✅ Health Check Status: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ Response: {response.json()}")
            return True
        else:
            print(f"❌ Health check failed: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API - service may not be running")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_api_docs():
    """Test if API documentation is accessible."""
    try:
        response = requests.get("http://localhost:8000/docs", timeout=10)
        if response.status_code == 200:
            print("✅ API Documentation is accessible at http://localhost:8000/docs")
            return True
        else:
            print(f"❌ API docs not accessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot access API docs: {e}")
        return False


def test_literature_submission():
    """Test literature submission endpoint."""
    try:
        # Test data
        test_literature = {
            "source": {
                "type": "arxiv",
                "identifier": "2301.00001",
                "url": "https://arxiv.org/abs/2301.00001",
            },
            "title": "Test Paper for API Validation",
            "authors": ["Test Author"],
            "abstract": "This is a test paper for validating the literature parser API.",
        }

        response = requests.post(
            "http://localhost:8000/api/literature", json=test_literature, timeout=10
        )

        print(f"✅ Literature Submission Status: {response.status_code}")
        if response.status_code in [200, 202]:
            result = response.json()
            print(f"✅ Response: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"❌ Literature submission failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error testing literature submission: {e}")
        return False


def main():
    """Run all API tests."""
    print("🚀 Testing Literature Parser API...")
    print("=" * 50)

    # Wait a moment for services to be ready
    print("⏳ Waiting 5 seconds for services to stabilize...")
    time.sleep(5)

    # Test health
    health_ok = test_api_health()
    print()

    # Test docs
    docs_ok = test_api_docs()
    print()

    # Test literature submission if health is OK
    if health_ok:
        literature_ok = test_literature_submission()
        print()
    else:
        literature_ok = False
        print("⚠️  Skipping literature test due to health check failure")

    # Summary
    print("=" * 50)
    print("📊 Test Summary:")
    print(f"   Health Check: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"   Documentation: {'✅ PASS' if docs_ok else '❌ FAIL'}")
    print(f"   Literature API: {'✅ PASS' if literature_ok else '❌ FAIL'}")

    if health_ok and docs_ok:
        print()
        print("🎉 API is working! You can now:")
        print("   📖 View documentation: http://localhost:8000/docs")
        print("   🔍 Check health: http://localhost:8000/api/health")
        print("   📚 Submit literature for processing")
    else:
        print()
        print("❌ Some tests failed. Check Docker logs:")
        print("   docker logs literature_parser_backend-api-1")
        print("   docker logs literature_parser_backend-worker-1")


if __name__ == "__main__":
    main()
