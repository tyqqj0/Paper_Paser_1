"""
New API endpoints for literature relationship graphs (0.2 version).

This module implements graph query endpoints as specified in the 0.2 API design.
Provides citation graph functionality powered by Neo4j relationship traversal.
"""

import logging
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException, Query, status

from literature_parser_backend.db.relationship_dao import RelationshipDAO

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/graphs", tags=["关系图"])


@router.get("", summary="Get internal literature relationship graph")
async def get_literature_graph(
    lids: str = Query(
        ...,
        description="Comma-separated list of LIDs to analyze internal relationships for",
        example="2017-vaswani-aayn-6a05,2019-do-gtpncr-72ef"
    )
) -> Dict[str, Any]:
    """
    Get internal relationship graph for specified literatures.
    
    This endpoint analyzes citation relationships ONLY between the specified literatures
    (internal relationships only, no external connections).
    
    Args:
        lids: Comma-separated string of Literature IDs to analyze
        
    Returns:
        Graph data structure with nodes (literatures) and edges (internal relationships)
        
    Raises:
        400: Invalid parameters
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

        if len(lid_list) > 20:  # Reasonable limit for graph analysis
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many LIDs requested. Maximum 20 LIDs per graph request.",
            )

        logger.info(f"🕸️ Internal graph request for {len(lid_list)} LIDs")

        # Get internal citation graph using RelationshipDAO
        relationship_dao = RelationshipDAO.create_from_global_connection()
        graph_data = await relationship_dao.get_internal_citation_graph(
            target_lids=lid_list
        )
        
        # Enhance response with metadata
        response = {
            **graph_data,
            "metadata": {
                "total_nodes": len(graph_data.get("nodes", [])),
                "total_edges": len(graph_data.get("edges", [])),
                "requested_lids": lid_list,
                "total_requested": len(lid_list),
                "relationship_type": "internal_only",
                "api_version": "0.2",
                "status": "success"
            }
        }
        
        logger.info(f"✅ Graph query successful: {response['metadata']['total_nodes']} nodes, {response['metadata']['total_edges']} edges")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in graph request: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate literature graph: {e!s}",
        ) from e
