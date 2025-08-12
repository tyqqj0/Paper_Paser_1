"""
New API endpoints for literature data retrieval (0.2 version).

This module implements literature query endpoints as specified in the 0.2 API design.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from literature_parser_backend.models.literature import LiteratureSummaryDTO
from literature_parser_backend.db.dao import LiteratureDAO

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/literatures", tags=["文献查询"])


@router.get("/{lid}", summary="Get literature by LID")
async def get_literature_by_lid(lid: str) -> LiteratureSummaryDTO:
    """
    Get detailed information for a literature by its LID.
    
    This endpoint supports both the new LID format and legacy MongoDB ObjectId
    for backward compatibility.
    
    Args:
        lid: Literature ID (LID) or legacy MongoDB ObjectId
        
    Returns:
        Detailed literature information including metadata, content summary, and references
        
    Raises:
        404: Literature not found
        500: Internal server error
    """
    try:
        dao = LiteratureDAO()
        
        # Find by LID using Neo4j DAO
        literature = await dao.find_by_lid(lid)
        if not literature:
            # For legacy ObjectId support, we may need to implement this method
            # For now, try to find by LID only in Neo4j-only mode
            pass

        if not literature:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Literature not found: {lid}",
            )

        # Extract convenience fields (simplified for Neo4j-only mode)
        convenience_data = {
            'title': literature.metadata.title if literature.metadata else None,
            'authors': [author.name for author in literature.metadata.authors] if literature.metadata and literature.metadata.authors else [],
            'year': literature.metadata.year if literature.metadata else None,
            'journal': literature.metadata.journal if literature.metadata else None,
            'doi': literature.identifiers.doi if literature.identifiers else None,
            'abstract': literature.metadata.abstract if literature.metadata else None,
        }

        # Create content summary (exclude large parsed_fulltext)
        content_summary = {}
        if literature.content:
            content_dict = literature.content.model_dump()
            content_summary = {
                "pdf_url": content_dict.get("pdf_url"),
                "source_page_url": content_dict.get("source_page_url"),
                "sources_tried": content_dict.get("sources_tried", []),
                "has_parsed_fulltext": content_dict.get("parsed_fulltext") is not None,
                "grobid_processing_summary": _create_processing_summary(
                    content_dict.get("grobid_processing_info") or {},
                ),
            }

        # Build response DTO
        summary = LiteratureSummaryDTO(
            id=literature.lid or str(literature.id),  # Use LID if available, fallback to ObjectId
            identifiers=literature.identifiers,
            metadata=literature.metadata,
            content=content_summary,
            references=literature.references,
            task_info=literature.task_info,
            created_at=literature.created_at,
            updated_at=literature.updated_at,
            # Convenience fields
            title=convenience_data["title"],
            authors=convenience_data["authors"],
            year=convenience_data["year"],
            journal=convenience_data["journal"],
            doi=convenience_data["doi"],
            abstract=convenience_data["abstract"],
        )

        logger.info(f"Literature retrieved successfully: {lid}")
        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving literature {lid}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e!s}",
        ) from e


@router.get("", summary="Get multiple literatures by LIDs")  
async def get_literatures_batch(
    lids: str = Query(
        ..., 
        description="Comma-separated list of LIDs (e.g., 'lid1,lid2,lid3')",
        example="2017-vaswani-aayn-6a05,2019-do-gtpncr-72ef"
    )
) -> List[LiteratureSummaryDTO]:
    """
    Get detailed information for multiple literatures by their LIDs.
    
    This endpoint supports batch querying of literatures using a comma-separated
    list of LIDs in the query parameter.
    
    Args:
        lids: Comma-separated string of Literature IDs
        
    Returns:
        List of literature summaries. Missing literatures are omitted from results.
        
    Raises:
        400: Invalid LIDs parameter format
        500: Internal server error
    """
    try:
        # Parse comma-separated LIDs
        lid_list = [lid.strip() for lid in lids.split(",") if lid.strip()]
        
        if not lid_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one LID must be provided.",
            )

        if len(lid_list) > 50:  # Reasonable batch size limit
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many LIDs requested. Maximum 50 LIDs per request.",
            )

        logger.info(f"Batch literature request for {len(lid_list)} LIDs")

        dao = LiteratureDAO()
        results = []
        
        for lid in lid_list:
            try:
                # Try LID first, then fall back to MongoDB ObjectId
                literature = await dao.find_by_lid(lid)
                if not literature:
                    literature = await dao.get_literature_by_id(lid)

                if literature:
                    # Extract convenience fields  
                    convenience_data = {
                        'title': literature.metadata.title if literature.metadata else None,
                        'authors': [author.name for author in literature.metadata.authors] if literature.metadata and literature.metadata.authors else [],
                        'year': literature.metadata.year if literature.metadata else None,
                        'journal': literature.metadata.journal if literature.metadata else None,
                        'doi': literature.identifiers.doi if literature.identifiers else None,
                        'abstract': literature.metadata.abstract if literature.metadata else None,
                    }

                    # Create content summary
                    content_summary = {}
                    if literature.content:
                        content_dict = literature.content.model_dump()
                        content_summary = {
                            "pdf_url": content_dict.get("pdf_url"),
                            "source_page_url": content_dict.get("source_page_url"),
                            "sources_tried": content_dict.get("sources_tried", []),
                            "has_parsed_fulltext": content_dict.get("parsed_fulltext") is not None,
                            "grobid_processing_summary": _create_processing_summary(
                                content_dict.get("grobid_processing_info") or {},
                            ),
                        }

                    summary = LiteratureSummaryDTO(
                        id=literature.lid or str(literature.id),
                        identifiers=literature.identifiers,
                        metadata=literature.metadata,
                        content=content_summary,
                        references=literature.references,
                        task_info=literature.task_info,
                        created_at=literature.created_at,
                        updated_at=literature.updated_at,
                        # Convenience fields
                        title=convenience_data["title"],
                        authors=convenience_data["authors"],
                        year=convenience_data["year"],
                        journal=convenience_data["journal"],
                        doi=convenience_data["doi"],
                        abstract=convenience_data["abstract"],
                    )
                    results.append(summary)
                else:
                    logger.warning(f"Literature not found: {lid}")
            except Exception as e:
                logger.error(f"Error processing LID {lid}: {e}")
                # Continue processing other LIDs, don't fail entire batch

        logger.info(f"Batch request completed: {len(results)}/{len(lid_list)} found")
        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch literature request: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e!s}",
        ) from e


def _create_processing_summary(grobid_info: dict) -> dict:
    """Create a processing summary from GROBID processing info."""
    return {
        "processed_at": grobid_info.get("processed_at"),
        "processing_time_ms": grobid_info.get("processing_time_ms"),
        "success": grobid_info.get("success"),
        "pages_processed": grobid_info.get("pages_processed"),
        "text_length_chars": grobid_info.get("text_length_chars"),
        "grobid_version": grobid_info.get("grobid_version"),
    }
