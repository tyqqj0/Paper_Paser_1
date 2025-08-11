"""
Literature ID (LID) Generator Service.

This service generates unique and readable identifiers for literature based on metadata.
Format: {year}-{author_surname}-{title_initials}-{hash}

Example: 2017-vaswani-aiaynu-a8c4
- 2017: Publication year
- vaswani: First author's surname (lowercase, max 8 chars)
- aiaynu: Title initials (Attention Is All You Need Universe)
- a8c4: Random 4-digit hex hash for uniqueness
"""

import hashlib
import re
import secrets
from typing import Optional

from loguru import logger

from ..models.literature import MetadataModel


class LIDGenerator:
    """Service for generating Literature IDs (LIDs)."""
    
    # Common English stop words to filter out from titles
    STOP_WORDS = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", 
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "can", "shall"
    }
    
    def __init__(self):
        """Initialize the LID generator."""
        self.logger = logger.bind(service="lid_generator")
    
    def generate_lid(self, metadata: MetadataModel) -> str:
        """
        Generate a Literature ID from metadata.
        
        Args:
            metadata: Literature metadata containing title, authors, year
            
        Returns:
            str: Generated LID in format: {year}-{author}-{title}-{hash}
            
        Example:
            >>> generator = LIDGenerator()
            >>> metadata = MetadataModel(
            ...     title="Attention Is All You Need",
            ...     authors=[AuthorModel(name="Ashish Vaswani")],
            ...     year=2017
            ... )
            >>> lid = generator.generate_lid(metadata)
            >>> print(lid)  # 2017-vaswani-aiaynu-a8c4
        """
        try:
            # Extract components
            year_part = self._extract_year(metadata)
            author_part = self._extract_author_surname(metadata)
            title_part = self._extract_title_initials(metadata)
            hash_part = self._generate_hash_suffix()
            
            # Combine parts
            lid = f"{year_part}-{author_part}-{title_part}-{hash_part}"
            
            self.logger.info(f"Generated LID: {lid} for title: {metadata.title[:50]}...")
            return lid
            
        except Exception as e:
            # Fallback to a simple hash-based LID if generation fails
            self.logger.warning(f"Failed to generate structured LID: {e}, using fallback")
            return self._generate_fallback_lid(metadata)
    
    def _extract_year(self, metadata: MetadataModel) -> str:
        """Extract year component (4 digits)."""
        if metadata.year and isinstance(metadata.year, int):
            return str(metadata.year)
        
        # Try to extract year from title or journal if available
        if metadata.title:
            year_match = re.search(r'\b(19|20)\d{2}\b', metadata.title)
            if year_match:
                return year_match.group()
        
        # Default to current year placeholder
        return "unkn"
    
    def _extract_author_surname(self, metadata: MetadataModel) -> str:
        """Extract primary author surname (max 8 chars, lowercase)."""
        if not metadata.authors or len(metadata.authors) == 0:
            return "noauthor"
        
        # Get first author's name
        first_author = metadata.authors[0].name
        
        # Handle various name formats
        name_parts = first_author.strip().split()
        
        if len(name_parts) == 0:
            return "noauthor"
        
        # Assume last part is surname for Western names
        # For names like "Ashish Vaswani", take "Vaswani"
        # For single names, use the whole name
        surname = name_parts[-1] if len(name_parts) > 1 else name_parts[0]
        
        # Clean and format surname
        surname = re.sub(r'[^a-zA-Z]', '', surname)  # Remove non-letters
        surname = surname.lower()
        
        # Truncate to 8 characters
        return surname[:8] if len(surname) > 8 else surname
    
    def _extract_title_initials(self, metadata: MetadataModel) -> str:
        """Extract title initials from meaningful words (max 6 chars)."""
        if not metadata.title:
            return "notitle"
        
        title = metadata.title.lower()
        
        # Remove punctuation and split into words
        words = re.findall(r'\b[a-zA-Z]+\b', title)
        
        # Filter out stop words and short words
        meaningful_words = [
            word for word in words 
            if word not in self.STOP_WORDS and len(word) >= 3
        ]
        
        # Take first letter of first 6 meaningful words
        initials = ''.join(word[0] for word in meaningful_words[:6])
        
        # If we don't have enough meaningful words, use original words
        if len(initials) < 3:
            all_words = [word for word in words if len(word) >= 2]
            initials = ''.join(word[0] for word in all_words[:6])
        
        # Ensure minimum length
        if len(initials) < 3:
            initials = "title"
        
        return initials[:6].lower()  # Max 6 characters, lowercase
    
    def _generate_hash_suffix(self) -> str:
        """Generate a 4-character hex hash for uniqueness."""
        return secrets.token_hex(2)  # 2 bytes = 4 hex characters
    
    def _generate_fallback_lid(self, metadata: MetadataModel) -> str:
        """Generate a fallback LID when structured generation fails."""
        # Create a simple hash from available data
        content = f"{metadata.title or 'unknown'}{metadata.year or 'unknown'}"
        for author in metadata.authors[:3]:  # First 3 authors
            content += author.name
        
        # Generate 12-character hash
        hash_value = hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
        return f"lit-{hash_value}"
    
    def validate_lid_format(self, lid: str) -> bool:
        """
        Validate if a string matches the expected LID format.
        
        Args:
            lid: String to validate
            
        Returns:
            bool: True if valid LID format, False otherwise
        """
        # Primary format: year-author-title-hash (e.g., 2017-vaswani-aiaynu-a8c4)
        primary_pattern = r'^(\d{4}|unkn)-[a-z]{1,8}-[a-z]{3,6}-[a-f0-9]{4}$'
        
        # Fallback format: lit-{12-char-hash}
        fallback_pattern = r'^lit-[a-f0-9]{12}$'
        
        return (re.match(primary_pattern, lid) is not None or 
                re.match(fallback_pattern, lid) is not None)


# Convenience function for direct usage
def generate_literature_lid(metadata: MetadataModel) -> str:
    """
    Convenience function to generate a LID from metadata.
    
    Args:
        metadata: Literature metadata
        
    Returns:
        str: Generated Literature ID
    """
    generator = LIDGenerator()
    return generator.generate_lid(metadata)
