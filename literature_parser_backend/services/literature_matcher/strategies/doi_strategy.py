"""
DOI Matching Strategy

Provides exact matching based on DOI (Digital Object Identifier).
"""

import re
from typing import Any, Dict

from ..base_matcher import MatchStrategy


class DOIStrategy(MatchStrategy):
    """Strategy for matching literature based on DOI."""
    
    @property
    def field_name(self) -> str:
        return "doi"
    
    def _normalize_doi(self, doi: str) -> str:
        """
        Normalize DOI format for consistent comparison.
        
        Args:
            doi: Raw DOI string
            
        Returns:
            Normalized DOI string
        """
        if not doi:
            return ""
            
        # Remove common prefixes and whitespace
        doi = doi.strip()
        doi = re.sub(r'^(https?://)?(dx\.)?doi\.org/', '', doi, flags=re.IGNORECASE)
        doi = re.sub(r'^doi:', '', doi, flags=re.IGNORECASE)
        
        # Convert to lowercase for comparison
        return doi.lower()
    
    async def calculate_similarity(
        self, 
        source: Dict[str, Any], 
        candidate: Dict[str, Any]
    ) -> float:
        """
        Calculate DOI similarity (exact match only).
        
        Args:
            source: Source literature data
            candidate: Candidate literature data
            
        Returns:
            1.0 if DOIs match exactly, 0.0 otherwise
        """
        source_doi = self._normalize_doi(source.get("doi", ""))
        candidate_doi = self._normalize_doi(candidate.get("doi", ""))
        
        # Both must have DOI for comparison
        if not source_doi or not candidate_doi:
            return 0.0
            
        # Exact match required for DOI
        return 1.0 if source_doi == candidate_doi else 0.0

