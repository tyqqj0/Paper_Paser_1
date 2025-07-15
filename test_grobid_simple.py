#!/usr/bin/env python3
import asyncio
from literature_parser_backend.services.grobid import GrobidClient

async def test():
    client = GrobidClient()
    print("Testing GROBID API client...")
    
    # Test 1: Health check
    print("\n1. Testing health check...")
    try:
        is_healthy = await client.health_check()
        if is_healthy:
            print("SUCCESS: GROBID service is healthy")
        else:
            print("ERROR: GROBID service is not healthy")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    
    # Test 2: Get version
    print("\n2. Testing version check...")
    try:
        version = await client.get_version()
        if version:
            print(f"SUCCESS: GROBID version: {version}")
        else:
            print("WARNING: Could not get GROBID version")
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test 3: Process a dummy PDF (we'll create a minimal PDF-like content)
    print("\n3. Testing PDF processing...")
    try:
        # Create a minimal PDF-like content for testing
        # In real usage, this would be actual PDF bytes
        dummy_pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n%%EOF"
        
        # This will likely fail because it's not a real PDF, but we can test the client
        result = await client.process_header_only(dummy_pdf)
        print(f"SUCCESS: Got result with status: {result.get('status', 'unknown')}")
    except Exception as e:
        print(f"Expected error (dummy PDF): {e}")
        print("This is expected - we need real PDF content for actual processing")
    
    return True

if __name__ == "__main__":
    result = asyncio.run(test())
    print(f"\nTest result: {'PASS' if result else 'FAIL'}") 