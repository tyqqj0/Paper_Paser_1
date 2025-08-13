"""
Author Matching Strategy

Provides matching based on author lists with fuzzy name matching.
"""

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Set

from ..base_matcher import MatchStrategy


class AuthorStrategy(MatchStrategy):
    """Strategy for matching literature based on author similarity."""
    
    @property
    def field_name(self) -> str:
        return "authors"
    
    def _normalize_author_name(self, name: str) -> str:
        """
        Normalize author name for consistent comparison.
        
        Args:
            name: Raw author name
            
        Returns:
            Normalized author name
        """
        if not name:
            return ""
            
        # Convert to lowercase and remove extra whitespace
        name = re.sub(r'\s+', ' ', name.lower().strip())
        
        # Remove common title prefixes and suffixes
        name = re.sub(r'\b(dr|prof|professor|phd|md)\b\.?', '', name)
        
        # Remove punctuation except hyphens in names
        name = re.sub(r'[^\w\s\-]', ' ', name)
        
        # Remove extra spaces
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    def _extract_author_names(self, authors: List[Any]) -> List[str]:
        """
        Extract and normalize author names from various formats.
        
        Args:
            authors: List of author data (strings or dicts)
            
        Returns:
            List of normalized author names
        """
        if not authors:
            return []
            
        names = []
        for author in authors:
            if isinstance(author, str):
                name = self._normalize_author_name(author)
                if name:
                    names.append(name)
            elif isinstance(author, dict):
                # Handle different author dictionary formats
                name = (
                    author.get("name")
                    or author.get("full_name")
                    or f"{author.get('given', '')} {author.get('family', '')}".strip()
                    or author.get("given")
                    or author.get("family")
                    or ""
                )
                name = self._normalize_author_name(str(name))
                if name:
                    names.append(name)
        
        return names
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two author names.
        
        Args:
            name1: First author name
            name2: Second author name
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not name1 or not name2:
            return 0.0
            
        # Direct string match
        if name1 == name2:
            return 1.0
            
        # Check if one is a subset of the other (handles initials)
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        if words1.issubset(words2) or words2.issubset(words1):
            return 0.8
            
        # Sequence-based similarity for partial matches
        sequence_sim = SequenceMatcher(None, name1, name2).ratio()
        
        # Only consider it a match if similarity is reasonably high
        return sequence_sim if sequence_sim >= 0.7 else 0.0
    
    def _find_best_author_matches(
        self, 
        source_authors: List[str], 
        candidate_authors: List[str]
    ) -> float:
        """
        Find best matches between two author lists.
        
        Args:
            source_authors: Source author list
            candidate_authors: Candidate author list
            
        Returns:
            Overall author list similarity score
        """
        if not source_authors and not candidate_authors:
            return 1.0
        if not source_authors or not candidate_authors:
            return 0.0
            
        # Find the best match for each source author
        total_similarity = 0.0
        matched_candidates = set()
        
        for source_author in source_authors:
            best_match_score = 0.0
            best_match_idx = -1
            
            for i, candidate_author in enumerate(candidate_authors):
                if i in matched_candidates:
                    continue
                    
                similarity = self._calculate_name_similarity(source_author, candidate_author)
                if similarity > best_match_score:
                    best_match_score = similarity
                    best_match_idx = i
            
            if best_match_idx >= 0 and best_match_score >= 0.7:
                matched_candidates.add(best_match_idx)
                total_similarity += best_match_score
        
        # Calculate overall similarity based on matched authors
        max_authors = max(len(source_authors), len(candidate_authors))
        return total_similarity / max_authors if max_authors > 0 else 0.0
    
    async def calculate_similarity(
        self, 
        source: Dict[str, Any], 
        candidate: Dict[str, Any]
    ) -> float:
        """
        Calculate author list similarity.
        
        Args:
            source: Source literature data
            candidate: Candidate literature data
            
        Returns:
            Author similarity score between 0.0 and 1.0
        """
        source_authors = self._extract_author_names(source.get("authors", []))
        candidate_authors = self._extract_author_names(candidate.get("authors", []))
        
        return self._find_best_author_matches(source_authors, candidate_authors)

