#!/usr/bin/env python3
"""
Test script for Celery tasks.

This script tests the literature processing task without requiring
Redis or MongoDB to be running (uses mock data).
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, patch

from ..models import LiteratureCreateDTO, LiteratureSourceDTO
from .tasks import _process_literature_async, extract_authoritative_identifiers

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_identifier_extraction():
    """Test authoritative identifier extraction."""
    logger.info("Testing identifier extraction...")

    test_cases = [
        # DOI URL
        {
            "url": "https://doi.org/10.1038/nature12373",
            "expected_doi": "10.1038/nature12373",
            "expected_type": "doi",
        },
        # ArXiv URL
        {
            "url": "https://arxiv.org/abs/1706.03762",
            "expected_arxiv": "1706.03762",
            "expected_type": "arxiv",
        },
        # Direct DOI
        {
            "doi": "10.1145/3025453.3025898",
            "expected_doi": "10.1145/3025453.3025898",
            "expected_type": "doi",
        },
        # Fingerprint generation
        {
            "title": "Attention Is All You Need",
            "authors": "Vaswani et al.",
            "year": "2017",
            "expected_type": "fingerprint",
        },
    ]

    for i, case in enumerate(test_cases):
        logger.info(f"Test case {i+1}: {case}")
        identifiers, primary_type = extract_authoritative_identifiers(case)

        # Verify primary type
        if primary_type != case["expected_type"]:
            logger.error(f"Expected type {case['expected_type']}, got {primary_type}")
        else:
            logger.info(f"✓ Correct primary type: {primary_type}")

        # Verify specific identifiers
        if "expected_doi" in case:
            if identifiers.doi != case["expected_doi"]:
                logger.error(
                    f"Expected DOI {case['expected_doi']}, got {identifiers.doi}",
                )
            else:
                logger.info(f"✓ Correct DOI: {identifiers.doi}")

        if "expected_arxiv" in case:
            if identifiers.arxiv_id != case["expected_arxiv"]:
                logger.error(
                    f"Expected ArXiv {case['expected_arxiv']}, got {identifiers.arxiv_id}",
                )
            else:
                logger.info(f"✓ Correct ArXiv ID: {identifiers.arxiv_id}")

        if case["expected_type"] == "fingerprint":
            if not identifiers.fingerprint:
                logger.error("Expected fingerprint to be generated")
            else:
                logger.info(f"✓ Generated fingerprint: {identifiers.fingerprint}")

        logger.info("-" * 50)


async def test_literature_processing():
    """Test the full literature processing pipeline."""
    logger.info("Testing literature processing pipeline...")

    # Mock external service calls
    with patch(
        "literature_parser_backend.worker.tasks.connect_to_mongodb",
    ) as mock_db, patch(
        "literature_parser_backend.worker.tasks.LiteratureDAO",
    ) as mock_dao:

        # Mock database operations
        mock_dao_instance = AsyncMock()
        mock_dao.return_value = mock_dao_instance
        mock_dao_instance.create_literature.return_value = "test_literature_id_123"

        # Test data
        test_source = {
            "url": "https://doi.org/10.1038/nature12373",
            "title": "Test Literature Title",
            "abstract": "This is a test abstract for literature processing.",
            "authors": "Test Author 1, Test Author 2",
            "year": 2024,
            "journal": "Test Journal",
            "publisher": "Test Publisher",
        }

        # Process the literature
        try:
            result_id = await _process_literature_async("test_task_123", test_source)
            logger.info("✓ Literature processing completed successfully")
            logger.info(f"✓ Generated literature ID: {result_id}")

            # Verify database save was called
            mock_dao_instance.create_literature.assert_called_once()
            logger.info("✓ Database save operation was called")

        except Exception as e:
            logger.error(f"✗ Literature processing failed: {e}")
            raise


def test_task_validation():
    """Test task input validation."""
    logger.info("Testing task input validation...")

    # Test valid source
    try:
        valid_source_data = {
            "url": "https://example.com/paper.pdf",
        }
        valid_source = {"source": LiteratureSourceDTO(**valid_source_data)}
        source_dto = LiteratureCreateDTO(**valid_source)
        logger.info("✓ Valid source passed validation")

    except Exception as e:
        logger.error(f"✗ Valid source failed validation: {e}")

    # Test invalid source (missing required fields)
    try:
        invalid_source = {"invalid_field": "test"}
        source_dto = LiteratureCreateDTO(**invalid_source)
        logger.error("✗ Invalid source should have failed validation")

    except Exception as e:
        logger.info(f"✓ Invalid source correctly failed validation: {e}")


def test_celery_task_simulation():
    """Simulate a Celery task call."""
    logger.info("Testing Celery task simulation...")

    from .celery_app import celery_app

    # Test task registration
    if "process_literature_task" in celery_app.tasks:
        logger.info("✓ Task is properly registered with Celery")
    else:
        logger.error("✗ Task is not registered with Celery")

    # Get task function
    task_func = celery_app.tasks.get("process_literature_task")
    if task_func:
        logger.info(f"✓ Task function retrieved: {task_func}")

        # Simulate task call (without actually running it)
        test_source = {
            "url": "https://example.com/test.pdf",
            "title": "Test Literature",
        }

        logger.info(
            f"Task would be called with source: {json.dumps(test_source, indent=2)}",
        )
        logger.info("✓ Task simulation completed")
    else:
        logger.error("✗ Could not retrieve task function")


async def run_all_tests():
    """Run all test functions."""
    logger.info("=" * 60)
    logger.info("RUNNING CELERY TASK TESTS")
    logger.info("=" * 60)

    # Run synchronous tests
    test_identifier_extraction()
    test_task_validation()
    test_celery_task_simulation()

    # Run async tests
    await test_literature_processing()

    logger.info("=" * 60)
    logger.info("ALL TESTS COMPLETED")
    logger.info("=" * 60)


def main():
    """Main function to run all tests."""
    asyncio.run(run_all_tests())


if __name__ == "__main__":
    main()
