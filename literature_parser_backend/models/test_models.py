"""
Simple test script for validating Pydantic models.

This can be run directly to ensure all models are properly defined
and can be instantiated without errors.
"""

from datetime import datetime

from .common import PyObjectId
from .literature import (
    AuthorModel,
    IdentifiersModel,
    LiteratureCreateDTO,
    LiteratureModel,
    MetadataModel,
)
from .task import TaskStage, TaskStatus, TaskStatusDTO


def test_basic_models():
    """Test basic model instantiation and validation."""

    # Test AuthorModel
    author = AuthorModel(full_name="Ashish Vaswani", sequence="first")
    print(f"✓ AuthorModel: {author.full_name}")

    # Test IdentifiersModel
    identifiers = IdentifiersModel(
        doi="10.48550/arXiv.1706.03762", arxiv_id="1706.03762",
    )
    print(f"✓ IdentifiersModel: DOI={identifiers.doi}")

    # Test MetadataModel
    metadata = MetadataModel(
        title="Attention Is All You Need",
        authors=[author],
        year=2017,
        journal="NeurIPS",
    )
    print(f"✓ MetadataModel: {metadata.title}")

    # Test LiteratureCreateDTO
    create_dto = LiteratureCreateDTO(
        source={
            "doi": "10.48550/arXiv.1706.03762",
            "url": "https://arxiv.org/abs/1706.03762",
        },
    )
    print(f"✓ LiteratureCreateDTO: {create_dto.source.doi}")

    # Test TaskStatusDTO
    task_status = TaskStatusDTO(
        task_id="test-123",
        status=TaskStatus.PROCESSING,
        stage=TaskStage.FETCHING_METADATA_CROSSREF,
        progress_percentage=50,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    print(f"✓ TaskStatusDTO: {task_status.status} - {task_status.stage}")

    # Test PyObjectId
    obj_id = PyObjectId()
    print(f"✓ PyObjectId: {obj_id}")

    # Test LiteratureModel
    literature = LiteratureModel(identifiers=identifiers, metadata=metadata)
    print(f"✓ LiteratureModel: {literature.metadata.title}")

    print("\n🎉 All basic model tests passed!")


if __name__ == "__main__":
    test_basic_models()
