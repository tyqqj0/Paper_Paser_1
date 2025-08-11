"""
测试Literature ID (LID) 生成和集成功能

This module tests the LID generation service and its integration into the literature creation workflow.
"""

from literature_parser_backend.models.literature import MetadataModel, AuthorModel
from literature_parser_backend.services.lid_generator import LIDGenerator, generate_literature_lid


class TestLIDGenerator:
    """Test suite for LID generation service."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.generator = LIDGenerator()
    
    def test_generate_lid_with_complete_metadata(self):
        """Test LID generation with complete metadata."""
        # Create test metadata
        metadata = MetadataModel(
            title="Attention Is All You Need",
            authors=[
                AuthorModel(name="Ashish Vaswani", s2_id="1738948"),
                AuthorModel(name="Noam Shazeer", s2_id="2104182")
            ],
            year=2017,
            journal="Advances in Neural Information Processing Systems",
            abstract="The dominant sequence transduction models..."
        )
        
        # Generate LID
        lid = self.generator.generate_lid(metadata)
        
        # Validate format
        assert isinstance(lid, str)
        assert self.generator.validate_lid_format(lid)
        
        # Check components
        parts = lid.split('-')
        assert len(parts) == 4
        assert parts[0] == "2017"  # year
        assert parts[1] == "vaswani"  # author surname
        assert len(parts[2]) >= 3 and len(parts[2]) <= 6  # title initials
        assert len(parts[3]) == 4  # hash
        
        print(f"Generated LID: {lid}")
    
    def test_generate_lid_with_missing_year(self):
        """Test LID generation when year is missing."""
        metadata = MetadataModel(
            title="Machine Learning Paper",
            authors=[AuthorModel(name="John Smith")],
            year=None
        )
        
        lid = self.generator.generate_lid(metadata)
        
        # Should use "unkn" for unknown year
        assert lid.startswith("unkn-")
        assert self.generator.validate_lid_format(lid)
    
    def test_generate_lid_with_no_authors(self):
        """Test LID generation when authors are missing."""
        metadata = MetadataModel(
            title="Anonymous Paper",
            authors=[],
            year=2023
        )
        
        lid = self.generator.generate_lid(metadata)
        
        # Should use "noauthor"
        parts = lid.split('-')
        assert parts[1] == "noauthor"
        assert self.generator.validate_lid_format(lid)
    
    def test_generate_lid_with_short_title(self):
        """Test LID generation with a very short title."""
        metadata = MetadataModel(
            title="AI",
            authors=[AuthorModel(name="Bob Wilson")],
            year=2024
        )
        
        lid = self.generator.generate_lid(metadata)
        
        # Should handle short titles gracefully
        assert self.generator.validate_lid_format(lid)
        
        parts = lid.split('-')
        assert len(parts[2]) >= 3  # Should pad or use fallback
    
    def test_generate_lid_with_special_characters(self):
        """Test LID generation with special characters in names/titles."""
        metadata = MetadataModel(
            title="The AI Revolution: How Machine Learning is Changing Everything!",
            authors=[AuthorModel(name="María García-López")],
            year=2023
        )
        
        lid = self.generator.generate_lid(metadata)
        
        # Special characters should be handled
        assert self.generator.validate_lid_format(lid)
        
        parts = lid.split('-')
        # Should extract surname and clean special characters
        assert "garcia" in parts[1] or "lopez" in parts[1]
    
    def test_generate_lid_fallback_mode(self):
        """Test LID generation fallback when structured generation fails."""
        # Create metadata that might cause issues
        metadata = MetadataModel(
            title="",  # Empty title
            authors=[],  # No authors
            year=None
        )
        
        lid = self.generator.generate_lid(metadata)
        
        # Should produce fallback LID
        assert lid.startswith("lit-") or self.generator.validate_lid_format(lid)
    
    def test_validate_lid_format(self):
        """Test LID format validation."""
        generator = LIDGenerator()
        
        # Valid primary format
        assert generator.validate_lid_format("2017-vaswani-aiaynu-a8c4")
        assert generator.validate_lid_format("unkn-noauthor-title-ff00")
        
        # Valid fallback format
        assert generator.validate_lid_format("lit-abcdef123456")
        
        # Invalid formats
        assert not generator.validate_lid_format("invalid-lid")
        assert not generator.validate_lid_format("2017-vaswani")  # Too short
        assert not generator.validate_lid_format("2017_vaswani_title_hash")  # Wrong separator
    
    def test_convenience_function(self):
        """Test the convenience function for LID generation."""
        metadata = MetadataModel(
            title="Test Paper",
            authors=[AuthorModel(name="Test Author")],
            year=2024
        )
        
        lid = generate_literature_lid(metadata)
        
        assert isinstance(lid, str)
        generator = LIDGenerator()
        assert generator.validate_lid_format(lid)
    
    def test_lid_uniqueness(self):
        """Test that generated LIDs are unique (due to hash component)."""
        metadata = MetadataModel(
            title="Same Title",
            authors=[AuthorModel(name="Same Author")],
            year=2024
        )
        
        # Generate multiple LIDs with same metadata
        lids = [self.generator.generate_lid(metadata) for _ in range(5)]
        
        # All should be different due to random hash
        assert len(set(lids)) == 5
        
        # But all should have same prefix (year-author-title)
        prefixes = ['-'.join(lid.split('-')[:3]) for lid in lids]
        assert len(set(prefixes)) == 1


if __name__ == "__main__":
    # Run basic tests
    test_suite = TestLIDGenerator()
    test_suite.setup_method()
    
    print("=== Testing LID Generation ===")
    
    # Test 1: Complete metadata
    print("\n1. Testing with complete metadata:")
    test_suite.test_generate_lid_with_complete_metadata()
    
    # Test 2: Missing data
    print("\n2. Testing with missing year:")
    test_suite.test_generate_lid_with_missing_year()
    
    # Test 3: Special characters
    print("\n3. Testing with special characters:")
    test_suite.test_generate_lid_with_special_characters()
    
    # Test 4: Format validation
    print("\n4. Testing format validation:")
    test_suite.test_validate_lid_format()
    print("Format validation tests passed!")
    
    print("\n=== All LID Generation Tests Passed! ===")
