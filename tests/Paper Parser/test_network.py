#!/usr/bin/env python3
"""
Test script to check proxy configuration and network connectivity
"""
import os
import requests
import time
from typing import Dict, Optional


def test_proxy_connectivity():
    """Test if proxy is working."""
    print("=" * 60)
    print("Testing proxy connectivity")
    print("=" * 60)

    # Check environment variables
    env_vars = {
        "LITERATURE_PARSER_BACKEND_HTTP_PROXY": os.getenv(
            "LITERATURE_PARSER_BACKEND_HTTP_PROXY"
        ),
        "LITERATURE_PARSER_BACKEND_HTTPS_PROXY": os.getenv(
            "LITERATURE_PARSER_BACKEND_HTTPS_PROXY"
        ),
    }

    print("Environment variables:")
    for key, value in env_vars.items():
        print(f"  {key}: {value}")

    # Test proxy addresses
    proxy_addresses = [
        "http://10.16.57.138:7890",
        "http://host.docker.internal:7890",
        "http://127.0.0.1:7890",
        "http://localhost:7890",
    ]

    print("\nTesting proxy addresses:")
    for proxy in proxy_addresses:
        print(f"\nTesting {proxy}...")
        try:
            proxies = {"http": proxy, "https": proxy}
            response = requests.get(
                "https://httpbin.org/ip", proxies=proxies, timeout=10
            )
            if response.status_code == 200:
                print(f"  ✅ {proxy} works! IP: {response.json()}")
            else:
                print(f"  ❌ {proxy} returned {response.status_code}")
        except Exception as e:
            print(f"  ❌ {proxy} failed: {e}")

    # Test direct connection (no proxy)
    print(f"\nTesting direct connection (no proxy)...")
    try:
        response = requests.get("https://httpbin.org/ip", timeout=10)
        if response.status_code == 200:
            print(f"  ✅ Direct connection works! IP: {response.json()}")
        else:
            print(f"  ❌ Direct connection returned {response.status_code}")
    except Exception as e:
        print(f"  ❌ Direct connection failed: {e}")


def test_api_endpoints():
    """Test access to external APIs."""
    print("\n" + "=" * 60)
    print("Testing external API endpoints")
    print("=" * 60)

    # Test endpoints
    endpoints = [
        ("CrossRef", "https://api.crossref.org/works/10.1037/0003-066X.59.1.29"),
        (
            "Semantic Scholar",
            "https://api.semanticscholar.org/graph/v1/paper/ARXIV:1706.03762",
        ),
        ("ArXiv", "https://arxiv.org/abs/1706.03762"),
    ]

    # Try with and without proxy
    proxy_configs = [
        ("No proxy", {}),
        (
            "With proxy",
            {"http": "http://10.16.57.138:7890", "https": "http://10.16.57.138:7890"},
        ),
    ]

    for proxy_name, proxies in proxy_configs:
        print(f"\n{proxy_name}:")
        for service, url in endpoints:
            try:
                response = requests.get(url, proxies=proxies, timeout=15)
                if response.status_code == 200:
                    print(f"  ✅ {service}: {response.status_code}")
                else:
                    print(f"  ⚠️  {service}: {response.status_code}")
            except Exception as e:
                print(f"  ❌ {service}: {e}")


def test_docker_internal_connectivity():
    """Test Docker internal connectivity."""
    print("\n" + "=" * 60)
    print("Testing Docker internal connectivity")
    print("=" * 60)

    # Test internal services
    internal_services = [
        ("MongoDB", "mongodb://db:27017"),
        ("Redis", "redis://redis:6379"),
        ("GROBID", "http://grobid:8070/api/isalive"),
    ]

    for service, url in internal_services:
        try:
            if service == "GROBID":
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print(f"  ✅ {service}: Available")
                else:
                    print(f"  ⚠️  {service}: {response.status_code}")
            else:
                print(f"  ⚠️  {service}: Cannot test from here (need proper client)")
        except Exception as e:
            print(f"  ❌ {service}: {e}")


if __name__ == "__main__":
    print(f"Network connectivity test started at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    test_proxy_connectivity()
    test_api_endpoints()
    test_docker_internal_connectivity()

    print(f"\nTest completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
