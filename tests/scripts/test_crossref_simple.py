#!/usr/bin/env python3

from literature_parser_backend.services.crossref import CrossRefClient


def test():
    client = CrossRefClient()
    print("Testing CrossRef API client...")

    try:
        metadata = client.get_metadata_by_doi("10.1038/nature12373")
        if metadata:
            print("SUCCESS: Got metadata")
            print(f"Title: {metadata.get('title', 'N/A')}")
            print(f"Journal: {metadata.get('journal', 'N/A')}")
            print(f"Year: {metadata.get('year', 'N/A')}")
            print(f"Authors: {len(metadata.get('authors', []))}")
            return True
        else:
            print("ERROR: No metadata found")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


if __name__ == "__main__":
    result = test()
    print(f"Test result: {'PASS' if result else 'FAIL'}")
