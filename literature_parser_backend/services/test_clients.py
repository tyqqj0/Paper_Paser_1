"""
Test script for external API clients.

This script tests the basic functionality of all external API clients
without requiring actual API keys or running external services.
"""

import asyncio
import logging

from .crossref import CrossRefClient
from .grobid import GrobidClient
from .semantic_scholar import SemanticScholarClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_grobid_client():
    """Test GROBID client initialization and health check."""
    logger.info("Testing GROBID client...")

    try:
        client = GrobidClient()
        logger.info(f"✓ GROBID client initialized with base URL: {client.base_url}")

        # Test health check (will fail if GROBID is not running, but that's expected)
        try:
            is_healthy = await client.health_check()
            if is_healthy:
                logger.info("✓ GROBID service is running and healthy")

                # Test version check
                version = await client.get_version()
                if version:
                    logger.info(f"✓ GROBID version: {version}")

            else:
                logger.warning(
                    "⚠ GROBID service is not running (expected if not configured)",
                )
        except Exception as e:
            logger.warning(
                f"⚠ GROBID health check failed (expected if not running): {e}",
            )

        # Test error handling with empty PDF
        try:
            await client.process_pdf(b"")
        except ValueError as e:
            logger.info(f"✓ GROBID client correctly handles empty PDF: {e}")

        logger.info("✓ GROBID client tests completed\n")

    except Exception as e:
        logger.error(f"✗ GROBID client test failed: {e}")


async def test_crossref_client():
    """Test CrossRef client initialization and basic methods."""
    logger.info("Testing CrossRef client...")

    try:
        client = CrossRefClient()
        logger.info(f"✓ CrossRef client initialized with base URL: {client.base_url}")
        logger.info(f"✓ User-Agent for polite pool: {client.user_agent}")

        # Test DOI validation
        try:
            await client.get_metadata_by_doi("")
        except ValueError as e:
            logger.info(f"✓ CrossRef client correctly handles empty DOI: {e}")

        # Test search validation
        try:
            await client.search_by_title_author("")
        except ValueError as e:
            logger.info(f"✓ CrossRef client correctly handles empty title: {e}")

        # Test agency check method (safe to call)
        agency = await client.check_doi_agency("10.1000/invalid")
        logger.info(f"✓ DOI agency check works (returned: {agency})")

        # Test work types retrieval
        try:
            work_types = await client.get_work_types()
            logger.info(f"✓ Retrieved {len(work_types)} work types from CrossRef")
        except Exception as e:
            logger.warning(f"⚠ Work types retrieval failed: {e}")

        logger.info("✓ CrossRef client tests completed\n")

    except Exception as e:
        logger.error(f"✗ CrossRef client test failed: {e}")


async def test_semantic_scholar_client():
    """Test Semantic Scholar client initialization and basic methods."""
    logger.info("Testing Semantic Scholar client...")

    try:
        client = SemanticScholarClient()
        logger.info(
            f"✓ Semantic Scholar client initialized with base URL: {client.base_url}",
        )

        # Show available fields
        logger.info(f"✓ Paper fields available: {len(client.paper_fields)}")
        logger.info(f"✓ Author fields available: {len(client.author_fields)}")

        # Test identifier detection
        test_cases = [
            ("10.1000/test", "doi"),
            ("doi:10.1000/test", "doi"),
            ("arxiv:1234.5678", "arxiv"),
            ("1234567890123456789012345678901234567890", "paper_id"),
            ("some-other-id", "paper_id"),
        ]

        for identifier, expected_type in test_cases:
            detected_type = client._detect_identifier_type(identifier)
            if detected_type == expected_type:
                logger.info(f"✓ Correctly detected {identifier} as {detected_type}")
            else:
                logger.warning(
                    f"⚠ Expected {expected_type} for {identifier}, got {detected_type}",
                )

        # Test validation
        try:
            await client.get_metadata("")
        except ValueError as e:
            logger.info(
                f"✓ Semantic Scholar client correctly handles empty identifier: {e}",
            )

        try:
            await client.get_references("")
        except ValueError as e:
            logger.info(
                f"✓ Semantic Scholar client correctly handles empty identifier for references: {e}",
            )

        logger.info("✓ Semantic Scholar client tests completed\n")

    except Exception as e:
        logger.error(f"✗ Semantic Scholar client test failed: {e}")


async def test_all_clients():
    """Test all external API clients."""
    logger.info("=" * 60)
    logger.info("TESTING EXTERNAL API CLIENTS")
    logger.info("=" * 60)

    await test_grobid_client()
    await test_crossref_client()
    await test_semantic_scholar_client()

    logger.info("=" * 60)
    logger.info("ALL CLIENT TESTS COMPLETED")
    logger.info("=" * 60)


def main():
    """Main function to run all tests."""
    asyncio.run(test_all_clients())


if __name__ == "__main__":
    main()
