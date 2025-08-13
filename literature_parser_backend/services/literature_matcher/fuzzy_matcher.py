"""
Fuzzy Literature Matcher

Implements fuzzy matching using multiple strategies with configurable weights.
"""

import logging
from typing import Any, Dict, List

from .base_matcher import LiteratureMatcher, MatchType, MatchResult
from .strategies import DOIStrategy, TitleStrategy, AuthorStrategy, YearStrategy

logger = logging.getLogger(__name__)


class FuzzyMatcher(LiteratureMatcher):
    """
    Fuzzy matcher that combines multiple matching strategies.
    
    Uses configurable weights and thresholds for different match types.
    """
    
    def __init__(self, dao=None):
        """
        Initialize fuzzy matcher with strategies.
        
        Args:
            dao: Data access object for querying existing literature
        """
        super().__init__(dao)
        
        # Initialize matching strategies
        self.strategies = {
            "doi": DOIStrategy(),
            "title": TitleStrategy(), 
            "authors": AuthorStrategy(),
            "year": YearStrategy(),
        }
        
    async def find_matches(
        self,
        source: Dict[str, Any],
        match_type: MatchType,
        threshold: float = 0.8,
        max_candidates: int = 10
    ) -> List[MatchResult]:
        """
        Find matching literature using fuzzy matching strategies.
        
        Args:
            source: Source literature data to match against
            match_type: Type of matching (dedup, citation, general)
            threshold: Minimum confidence threshold for matches
            max_candidates: Maximum number of matches to return
            
        Returns:
            List of match results sorted by confidence (highest first)
        """
        if not self.dao:
            logger.warning("No DAO provided, cannot perform matching")
            return []
            
        # Normalize source data
        normalized_source = self._normalize_source_data(source)
        
        # Get matching configuration
        config = self._get_match_config(match_type)
        
        # Get all candidate literature from database
        candidates = await self._get_candidates(normalized_source, match_type)
        
        if not candidates:
            logger.debug(f"No candidates found for matching")
            return []
            
        # Calculate matches
        matches = []
        for candidate in candidates:
            match_result = await self._calculate_match(
                normalized_source, 
                candidate, 
                config
            )
            
            if match_result and match_result.confidence >= threshold:
                matches.append(match_result)
        
        # Sort by confidence and limit results
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches[:max_candidates]
    
    async def _get_candidates(
        self, 
        source: Dict[str, Any], 
        match_type: MatchType
    ) -> List[Dict[str, Any]]:
        """
        Get candidate literature for matching.
        
        Args:
            source: Normalized source data
            match_type: Type of matching
            
        Returns:
            List of candidate literature data
        """
        try:
            # For now, get all literature (we can optimize this later with pre-filtering)
            # In a production system, we'd want to pre-filter by DOI, title keywords, etc.
            
            if hasattr(self.dao, 'get_all_literature'):
                candidates = await self.dao.get_all_literature()
                return [self._normalize_candidate_data(lit) for lit in candidates]
            else:
                # Fallback: try to search by available identifiers
                candidates = []
                
                # Try DOI search first
                if source.get("doi"):
                    lit = await self.dao.find_by_doi(source["doi"])
                    if lit:
                        candidates.append(self._normalize_candidate_data(lit))
                
                return candidates
                
        except Exception as e:
            logger.error(f"Error getting candidates: {e}")
            return []
    
    def _normalize_candidate_data(self, literature) -> Dict[str, Any]:
        """
        Normalize candidate literature data for consistent matching.
        
        Args:
            literature: Literature model/object
            
        Returns:
            Normalized candidate data
        """
        try:
            # Handle different literature data formats
            if hasattr(literature, 'model_dump'):
                lit_data = literature.model_dump()
            elif hasattr(literature, '__dict__'):
                lit_data = literature.__dict__
            else:
                lit_data = dict(literature)
            
            # Use the same normalization as source data
            return self._normalize_source_data(lit_data)
            
        except Exception as e:
            logger.warning(f"Error normalizing candidate data: {e}")
            return {}
    
    async def _calculate_match(
        self, 
        source: Dict[str, Any], 
        candidate: Dict[str, Any], 
        config: Dict[str, Any]
    ) -> MatchResult:
        """
        Calculate match score between source and candidate.
        
        Args:
            source: Normalized source data
            candidate: Normalized candidate data  
            config: Matching configuration
            
        Returns:
            Match result with confidence score
        """
        try:
            total_score = 0.0
            max_possible_score = 0.0
            matched_fields = []
            match_details = {}
            
            # Calculate scores for each configured strategy
            for strategy_config in config["strategies"]:
                strategy_type = strategy_config["type"]
                weight = strategy_config["weight"]
                strategy_threshold = strategy_config["threshold"]
                
                if strategy_type not in self.strategies:
                    continue
                    
                strategy = self.strategies[strategy_type]
                similarity = await strategy.calculate_similarity(source, candidate)
                
                match_details[strategy_type] = {
                    "similarity": similarity,
                    "weight": weight,
                    "threshold": strategy_threshold,
                    "passed": similarity >= strategy_threshold
                }
                
                # Add to total if above threshold
                if similarity >= strategy_threshold:
                    weighted_score = similarity * weight
                    total_score += weighted_score
                    matched_fields.append(strategy_type)
                
                max_possible_score += weight
            
            # Calculate final confidence
            confidence = total_score / max_possible_score if max_possible_score > 0 else 0.0
            
            # Check if meets minimum total score requirement
            if confidence < config["min_total_score"]:
                return None
                
            # Special rule: for deduplication, require exact DOI match if both have DOI
            if config.get("require_exact_doi", False):
                if source.get("doi") and candidate.get("doi"):
                    doi_match = match_details.get("doi", {}).get("similarity", 0.0)
                    if doi_match < 1.0:
                        logger.debug("Dedup match rejected: DOI mismatch")
                        return None
            
            return MatchResult(
                lid=candidate.get("lid", "unknown"),
                confidence=confidence,
                matched_fields=matched_fields,
                match_details=match_details,
                source_data=candidate
            )
            
        except Exception as e:
            logger.error(f"Error calculating match: {e}")
            return None

