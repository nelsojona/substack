#!/usr/bin/env python3
"""
Tests for newsletter metadata extraction functionality.

This module tests the newsletter metadata extraction features of the Substack to Markdown CLI.
"""

import os
import sys
import pytest
import json
from unittest.mock import patch, MagicMock

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.substack_api_utils import (
    extract_newsletter_metadata,
    generate_newsletter_index,
    generate_frontmatter
)


class TestNewsletterMetadata:
    """Test class for newsletter metadata extraction functionality."""

    def test_extract_newsletter_metadata(self):
        """Test extracting newsletter metadata from API response."""
        # Arrange
        api_response = {
            "newsletter": {
                "name": "Test Newsletter",
                "description": "A test newsletter for unit testing",
                "author": {
                    "name": "Test Author"
                },
                "logo_url": "https://example.com/logo.png",
                "cover_image_url": "https://example.com/cover.png",
                "subscribers_count": 1000,
                "post_count": 50
            }
        }
        
        # Act
        metadata = extract_newsletter_metadata(api_response)
        
        # Assert
        assert metadata["title"] == "Test Newsletter"
        assert metadata["description"] == "A test newsletter for unit testing"
        assert metadata["author"] == "Test Author"
        assert metadata["logo_url"] == "https://example.com/logo.png"
        assert metadata["cover_image_url"] == "https://example.com/cover.png"
        assert metadata["subscribers_count"] == 1000
        assert metadata["post_count"] == 50

    def test_extract_newsletter_metadata_missing_fields(self):
        """Test extracting newsletter metadata with missing fields."""
        # Arrange
        api_response = {
            "newsletter": {
                "name": "Test Newsletter"
                # Missing other fields
            }
        }
        
        # Act
        metadata = extract_newsletter_metadata(api_response)
        
        # Assert
        assert metadata["title"] == "Test Newsletter"
        assert metadata["description"] == ""
        assert metadata["author"] == ""
        assert metadata["logo_url"] == ""
        assert metadata["cover_image_url"] == ""
        assert metadata["subscribers_count"] == 0
        assert metadata["post_count"] == 0

    def test_extract_newsletter_metadata_no_newsletter(self):
        """Test extracting newsletter metadata when newsletter field is missing."""
        # Arrange
        api_response = {
            # No newsletter field
        }
        
        # Act
        metadata = extract_newsletter_metadata(api_response)
        
        # Assert
        assert metadata["title"] == ""
        assert metadata["description"] == ""
        assert metadata["author"] == ""
        assert metadata["logo_url"] == ""
        assert metadata["cover_image_url"] == ""
        assert metadata["subscribers_count"] == 0
        assert metadata["post_count"] == 0

    def test_generate_newsletter_index(self):
        """Test generating a newsletter index markdown file."""
        # Arrange
        newsletter_metadata = {
            "title": "Test Newsletter",
            "description": "A test newsletter for unit testing",
            "author": "Test Author",
            "subscribers_count": 1000,
            "post_count": 3
        }
        
        posts_metadata = [
            {
                "title": "Test Post 1",
                "date": "2023-01-01",
                "url": "https://example.com/p/test-post-1"
            },
            {
                "title": "Test Post 2",
                "date": "2023-01-02",
                "url": "https://example.com/p/test-post-2"
            },
            {
                "title": "Test Post 3",
                "date": "2023-01-03",
                "url": "https://example.com/p/test-post-3"
            }
        ]
        
        # Act
        markdown = generate_newsletter_index(newsletter_metadata, posts_metadata)
        
        # Assert
        assert "# Test Newsletter" in markdown
        assert "A test newsletter for unit testing" in markdown
        assert "## Newsletter Statistics" in markdown
        assert "**Posts**: 3" in markdown
        assert "**Subscribers**: 1000" in markdown
        assert "## Posts" in markdown
        assert "[2023-01-03] [Test Post 3](https://example.com/p/test-post-3)" in markdown
        assert "[2023-01-02] [Test Post 2](https://example.com/p/test-post-2)" in markdown
        assert "[2023-01-01] [Test Post 1](https://example.com/p/test-post-1)" in markdown

    def test_generate_frontmatter(self):
        """Test generating frontmatter for a markdown file."""
        # Arrange
        metadata = {
            "title": "Test Post",
            "subtitle": "A test post",
            "date": "2023-01-01",
            "author": "Test Author",
            "url": "https://example.com/p/test-post",
            "is_paid": True,
            "word_count": 1000,
            "comments_count": 10,
            "likes_count": 50
        }
        
        # Act
        frontmatter = generate_frontmatter(metadata)
        
        # Assert
        assert 'title: "Test Post"' in frontmatter
        assert 'subtitle: "A test post"' in frontmatter
        assert 'date: "2023-01-01"' in frontmatter
        assert 'author: "Test Author"' in frontmatter
        assert 'original_url: "https://example.com/p/test-post"' in frontmatter
        assert 'is_paid: true' in frontmatter
        assert 'word_count: 1000' in frontmatter
        assert 'comments_count: 10' in frontmatter
        assert 'likes_count: 50' in frontmatter


class TestNewsletterMetadataIntegration:
    """Integration tests for newsletter metadata functionality."""

    @pytest.fixture
    def mock_api_response(self):
        """Create a mock API response for testing."""
        return {
            "newsletter": {
                "name": "Test Newsletter",
                "description": "A test newsletter for integration testing",
                "author": {
                    "name": "Test Author"
                },
                "subscribers_count": 1000,
                "post_count": 50
            },
            "posts": [
                {
                    "id": "post1",
                    "title": "Test Post 1",
                    "published_at": "2023-01-01T12:00:00Z",
                    "canonical_url": "https://example.com/p/test-post-1"
                },
                {
                    "id": "post2",
                    "title": "Test Post 2",
                    "published_at": "2023-01-02T12:00:00Z",
                    "canonical_url": "https://example.com/p/test-post-2"
                }
            ]
        }

    def test_end_to_end_newsletter_processing(self, mock_api_response, tmp_path):
        """Test end-to-end newsletter metadata processing."""
        # Arrange
        from src.utils.substack_api_utils import extract_post_metadata
        
        # Extract newsletter metadata
        newsletter_metadata = extract_newsletter_metadata(mock_api_response)
        
        # Extract post metadata
        posts_metadata = [extract_post_metadata(post) for post in mock_api_response.get("posts", [])]
        
        # Generate newsletter index
        index_markdown = generate_newsletter_index(newsletter_metadata, posts_metadata)
        
        # Write to file
        index_path = os.path.join(tmp_path, "index.md")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_markdown)
        
        # Act & Assert
        assert os.path.exists(index_path)
        
        # Read the file and check its content
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "# Test Newsletter" in content
            assert "A test newsletter for integration testing" in content
            assert "**Posts**: 50" in content
            assert "**Subscribers**: 1000" in content
            assert "[Test Post 2]" in content
            assert "[Test Post 1]" in content


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
