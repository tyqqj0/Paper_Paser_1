"""
Year Matching Strategy

Provides matching based on publication year with tolerance for close years.
"""

from typing import Any, Dict

from ..base_matcher import MatchStrategy


class YearStrategy(MatchStrategy):
    """Strategy for matching literature based on publication year."""
    
    @property
    def field_name(self) -> str:
        return "year"
    
    def _extract_year(self, data: Dict[str, Any]) -> int:
        """
        Extract publication year from various formats.
        
        Args:
            data: Literature data
            
        Returns:
            Publication year as integer, or 0 if not found
        """
        year = data.get("year")
        
        if year is None:
            return 0
            
        # Handle different year formats
        if isinstance(year, int):
            return year if 1900 <= year <= 2030 else 0
        elif isinstance(year, str):
            try:
                year_int = int(year)
                return year_int if 1900 <= year_int <= 2030 else 0
            except ValueError:
                return 0
        else:
            return 0
    
    async def calculate_similarity(
        self, 
        source: Dict[str, Any], 
        candidate: Dict[str, Any]
    ) -> float:
        """
        Calculate year similarity with tolerance.
        
        Args:
            source: Source literature data
            candidate: Candidate literature data
            
        Returns:
            Year similarity score between 0.0 and 1.0
        """
        source_year = self._extract_year(source)
        candidate_year = self._extract_year(candidate)
        
        # Both must have valid years for comparison
        if source_year == 0 or candidate_year == 0:
            return 0.0
            
        # Exact match
        if source_year == candidate_year:
            return 1.0
            
        # Calculate similarity with tolerance
        year_diff = abs(source_year - candidate_year)
        
        if year_diff == 1:
            # One year difference (common in publication delays)
            return 0.9
        elif year_diff == 2:
            # Two year difference (still possible)
            return 0.7
        elif year_diff <= 5:
            # Up to 5 years difference (preprint to publication gap)
            return 0.5
        else:
            # Too far apart
            return 0.0

