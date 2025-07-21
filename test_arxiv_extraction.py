#!/usr/bin/env python3
"""Test ArXiv ID extraction from DOI."""

import re


def test_arxiv_extraction():
    """Test the ArXiv ID extraction logic."""

    def _extract_arxiv_id_from_doi(doi: str):
        """Extract ArXiv ID from DOI patterns like 10.48550/arXiv.1706.03762."""

        # Pattern 1: 10.48550/arXiv.XXXX.XXXXX
        pattern1 = r"10\.48550/arXiv\.(\d{4}\.\d{4,5})"
        match1 = re.search(pattern1, doi)
        if match1:
            return match1.group(1)

        # Pattern 2: 10.48550/arXiv.XXXX.XXXXX vN (with version)
        pattern2 = r"10\.48550/arXiv\.(\d{4}\.\d{4,5})v\d+"
        match2 = re.search(pattern2, doi)
        if match2:
            return match2.group(1)

        # Pattern 3: Direct arXiv in DOI like arxiv.org/abs/XXXX.XXXXX
        pattern3 = r"arxiv\.org/abs/(\d{4}\.\d{4,5})"
        match3 = re.search(pattern3, doi)
        if match3:
            return match3.group(1)

        return None

    # Test the problematic DOI
    test_doi = "10.48550/arXiv.1706.03762"
    result = _extract_arxiv_id_from_doi(test_doi)

    print(f"DOI: {test_doi}")
    print(f"Extracted ArXiv ID: {result}")

    # Test each pattern individually
    pattern1 = r"10\.48550/arXiv\.(\d{4}\.\d{4,5})"
    match1 = re.search(pattern1, test_doi)
    print(f"Pattern 1 match: {match1.group(1) if match1 else None}")


if __name__ == "__main__":
    test_arxiv_extraction()
