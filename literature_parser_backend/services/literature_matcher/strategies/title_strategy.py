"""
Title Matching Strategy

Provides fuzzy matching based on paper titles using various similarity metrics.
"""

import re
from difflib import SequenceMatcher
from typing import Any, Dict, Set

from ..base_matcher import MatchStrategy


class TitleStrategy(MatchStrategy):
    """Strategy for matching literature based on title similarity."""
    
    @property
    def field_name(self) -> str:
        return "title"
    
    def _normalize_title(self, title: str) -> str:
        """
        Normalize title for consistent comparison.
        
        Args:
            title: Raw title string
            
        Returns:
            Normalized title string
        """
        if not title:
            return ""
            
        # Convert to lowercase and remove extra whitespace
        title = re.sub(r'\s+', ' ', title.lower().strip())
        
        # Remove common punctuation and special characters
        title = re.sub(r'[^\w\s]', ' ', title)
        
        # Remove extra spaces again
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title
    
    def _get_title_words(self, title: str) -> Set[str]:
        """
        Extract meaningful words from title.
        
        Args:
            title: Normalized title string
            
        Returns:
            Set of meaningful words
        """
        if not title:
            return set()
            
        # Split into words and filter out stopwords and short words
        stopwords = {
            'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'between', 'among', 'under', 'over'
        }
        
        words = [
            word for word in title.split()
            if len(word) >= 2 and word not in stopwords
        ]
        
        return set(words)
    
    def _calculate_sequence_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate sequence-based similarity using difflib.
        
        Args:
            title1: First title
            title2: Second title
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        return SequenceMatcher(None, title1, title2).ratio()
    
    def _calculate_jaccard_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate Jaccard similarity based on word sets.
        
        Args:
            title1: First title
            title2: Second title
            
        Returns:
            Jaccard similarity between 0.0 and 1.0
        """
        words1 = self._get_title_words(title1)
        words2 = self._get_title_words(title2)
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
            
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    async def calculate_similarity(
        self, 
        source: Dict[str, Any], 
        candidate: Dict[str, Any]
    ) -> float:
        """
        Calculate title similarity using multiple metrics.
        
        Args:
            source: Source literature data
            candidate: Candidate literature data
            
        Returns:
            Combined similarity score between 0.0 and 1.0
        """
        source_title = self._normalize_title(source.get("title", ""))
        candidate_title = self._normalize_title(candidate.get("title", ""))
        
        # Both must have title for comparison
        if not source_title or not candidate_title:
            return 0.0
            
        # Calculate multiple similarity metrics
        sequence_sim = self._calculate_sequence_similarity(source_title, candidate_title)
        jaccard_sim = self._calculate_jaccard_similarity(source_title, candidate_title)
        
        # Weighted combination of metrics
        # Sequence similarity catches character-level similarities
        # Jaccard similarity catches semantic word-level similarities
        combined_similarity = (0.6 * sequence_sim) + (0.4 * jaccard_sim)
        
        return min(combined_similarity, 1.0)

