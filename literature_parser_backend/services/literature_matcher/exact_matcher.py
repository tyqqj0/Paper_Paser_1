"""
Exact Literature Matcher

Implements exact matching primarily for deduplication with high precision.
"""

import logging
from typing import Any, Dict, List

from .base_matcher import LiteratureMatcher, MatchType, MatchResult
from .fuzzy_matcher import FuzzyMatcher

logger = logging.getLogger(__name__)


class ExactMatcher(LiteratureMatcher):
    """
    Exact matcher for high-precision deduplication.
    
    Uses strict matching criteria to avoid false positives.
    """
    
    def __init__(self, dao=None):
        """
        Initialize exact matcher.
        
        Args:
            dao: Data access object for querying existing literature
        """
        super().__init__(dao)
        
        # Use fuzzy matcher as backend but with strict thresholds
        self.fuzzy_matcher = FuzzyMatcher(dao)
        
    async def find_matches(
        self,
        source: Dict[str, Any],
        match_type: MatchType,
        threshold: float = 0.95,  # High threshold for exact matching
        max_candidates: int = 5   # Fewer candidates for exact matching
    ) -> List[MatchResult]:
        """
        Find exact matches using strict criteria.
        
        Args:
            source: Source literature data to match against
            match_type: Type of matching (forced to DEDUPLICATION for exact matching)
            threshold: Minimum confidence threshold (defaults to 0.95 for exact matching)
            max_candidates: Maximum number of matches to return
            
        Returns:
            List of match results sorted by confidence (highest first)
        """
        # Force deduplication mode for exact matching
        exact_match_type = MatchType.DEDUPLICATION
        
        # Use high threshold for exact matching
        exact_threshold = max(threshold, 0.95)
        
        # Delegate to fuzzy matcher with strict parameters
        matches = await self.fuzzy_matcher.find_matches(
            source=source,
            match_type=exact_match_type,
            threshold=exact_threshold,
            max_candidates=max_candidates
        )
        
        # Additional filtering for extra precision
        exact_matches = []
        for match in matches:
            if self._is_exact_match(match):
                exact_matches.append(match)
        
        return exact_matches
    
    def _is_exact_match(self, match: MatchResult) -> bool:
        """
        Apply additional exact matching criteria.
        
        Args:
            match: Match result to validate
            
        Returns:
            True if match meets exact matching criteria
        """
        match_details = match.match_details
        
        # Require DOI match if available
        if "doi" in match_details:
            doi_similarity = match_details["doi"]["similarity"]
            if doi_similarity < 1.0:  # DOI must be perfect match
                return False
        
        # Require very high title similarity
        if "title" in match_details:
            title_similarity = match_details["title"]["similarity"]
            if title_similarity < 0.9:  # Title must be very similar
                return False
        
        # Require reasonable author overlap
        if "authors" in match_details:
            author_similarity = match_details["authors"]["similarity"]
            if author_similarity < 0.8:  # Authors must have good overlap
                return False
        
        # Overall confidence must be very high
        if match.confidence < 0.95:
            return False
        
        return True

