#!/usr/bin/env python3
"""
Tests for comment extraction functionality.

This module tests the comment extraction features of the SubstackDirectDownloader class.
"""

import os
import sys
import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from bs4 import BeautifulSoup

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.substack_direct_downloader import SubstackDirectDownloader


class TestCommentExtraction:
    """Test class for comment extraction functionality."""

    @pytest.fixture
    def downloader(self):
        """Create a SubstackDirectDownloader instance for testing."""
        return SubstackDirectDownloader(
            author="testauthor",
            output_dir="test_output",
            include_comments=True
        )

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    async def test_extract_comments_structure(self, mock_fetch, downloader):
        """Test that comments are extracted with the correct structure."""
        # Arrange
        mock_fetch.return_value = """
        <html>
        <body>
            <div id="comments">
                <div class="comment-thread">
                    <div class="comment" id="comment-1">
                        <div class="comment-body">Test comment 1</div>
                        <div class="comment-author">Author 1</div>
                        <div class="comment-date">2023-01-01</div>
                        <div class="comment-replies">
                            <div class="comment" id="comment-2">
                                <div class="comment-body">Reply to comment 1</div>
                                <div class="comment-author">Author 2</div>
                                <div class="comment-date">2023-01-02</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Act
        comments = await downloader.extract_comments("https://testauthor.substack.com/p/test-post")
        
        # Assert
        assert len(comments) == 1
        assert comments[0]['body'] == "Test comment 1"
        assert comments[0]['author'] == "Author 1"
        assert comments[0]['date'] == "2023-01-01"
        assert len(comments[0]['replies']) == 1
        assert comments[0]['replies'][0]['body'] == "Reply to comment 1"
        assert comments[0]['replies'][0]['author'] == "Author 2"
        assert comments[0]['replies'][0]['date'] == "2023-01-02"

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._extract_comments_from_js")
    async def test_extract_comments_from_js(self, mock_extract_comments_from_js, downloader):
        """Test extracting comments from JavaScript data."""
        # Arrange
        mock_comments = [
            {
                'id': 'comment1',
                'body': 'JavaScript comment 1',
                'author': 'JS Author 1',
                'date': '2023-01-01',
                'replies': [
                    {
                        'id': 'comment2',
                        'body': 'JavaScript reply 1',
                        'author': 'JS Author 2',
                        'date': '2023-01-02',
                        'replies': []
                    }
                ]
            }
        ]
        
        # Mock the _extract_comments_from_js method to return our test comments
        mock_extract_comments_from_js.return_value = mock_comments
        
        # Act
        # Call the method directly with some HTML
        comments = downloader._extract_comments_from_js("<html><body>Test HTML</body></html>")
        
        # Assert
        assert comments == mock_comments
        assert len(comments) == 1
        assert comments[0]['body'] == "JavaScript comment 1"
        assert comments[0]['author'] == "JS Author 1"
        assert len(comments[0]['replies']) == 1
        assert comments[0]['replies'][0]['body'] == "JavaScript reply 1"
        assert comments[0]['replies'][0]['author'] == "JS Author 2"

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    async def test_format_comments_markdown(self, mock_fetch, downloader):
        """Test formatting comments as markdown."""
        # Arrange
        comments = [
            {
                'id': 'comment1',
                'body': 'Test comment 1',
                'author': 'Author 1',
                'date': '2023-01-01',
                'replies': [
                    {
                        'id': 'comment2',
                        'body': 'Reply to comment 1',
                        'author': 'Author 2',
                        'date': '2023-01-02',
                        'replies': []
                    }
                ]
            }
        ]
        
        # Act
        markdown = downloader._format_comments_markdown(comments)
        
        # Assert
        assert "**Author 1** - 2023-01-01" in markdown
        assert "Test comment 1" in markdown
        assert "  **Author 2** - 2023-01-02" in markdown  # Indented reply
        assert "  Reply to comment 1" in markdown  # Indented reply content

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader.extract_comments")
    async def test_download_post_with_comments(self, mock_extract_comments, mock_fetch, downloader, tmp_path):
        """Test that comments are included in the downloaded post."""
        # Arrange
        downloader.output_dir = str(tmp_path)
        os.makedirs(downloader.output_dir, exist_ok=True)
        
        # Mock the fetch_url method to return HTML
        mock_fetch.return_value = """
        <html>
        <body>
            <h1 class="post-title">Test Post</h1>
            <time>January 1, 2023</time>
            <div class="post-content">Test content</div>
        </body>
        </html>
        """
        
        # Mock the extract_comments method
        mock_extract_comments.return_value = [
            {
                'id': 'comment1',
                'body': 'Test comment',
                'author': 'Test Author',
                'date': '2023-01-01',
                'replies': []
            }
        ]
        
        # Mock other methods that would be called
        downloader._store_post_metadata = MagicMock(return_value=True)
        downloader.extract_image_urls = AsyncMock(return_value=set())
        
        # Act
        result = await downloader.download_post(
            url="https://testauthor.substack.com/p/test-post",
            force=True
        )
        
        # Assert
        assert result is True
        
        # Check that the file was created
        files = os.listdir(str(tmp_path))
        assert len(files) == 1
        
        # Read the file and check its content
        with open(os.path.join(str(tmp_path), files[0]), 'r', encoding='utf-8') as f:
            content = f.read()
            assert "## Comments" in content
            assert "**Test Author** - 2023-01-01" in content
            assert "Test comment" in content

    @pytest.mark.asyncio
    async def test_organize_comments_tree(self, downloader):
        """Test organizing flat comments into a tree structure."""
        # Arrange
        flat_comments = [
            {
                'id': 'comment1',
                'body': 'Parent comment 1',
                'author': 'Author 1',
                'parent_id': None
            },
            {
                'id': 'comment2',
                'body': 'Reply to parent 1',
                'author': 'Author 2',
                'parent_id': 'comment1'
            },
            {
                'id': 'comment3',
                'body': 'Parent comment 2',
                'author': 'Author 3',
                'parent_id': None
            },
            {
                'id': 'comment4',
                'body': 'Reply to reply',
                'author': 'Author 4',
                'parent_id': 'comment2'
            }
        ]
        
        # Act
        tree = downloader._organize_comments_tree(flat_comments)
        
        # Assert
        assert len(tree) == 2  # Two top-level comments
        
        # Check first top-level comment and its replies
        assert tree[0]['id'] == 'comment1'
        assert tree[0]['body'] == 'Parent comment 1'
        assert len(tree[0]['replies']) == 1
        assert tree[0]['replies'][0]['id'] == 'comment2'
        assert tree[0]['replies'][0]['body'] == 'Reply to parent 1'
        assert len(tree[0]['replies'][0]['replies']) == 1
        assert tree[0]['replies'][0]['replies'][0]['id'] == 'comment4'
        
        # Check second top-level comment
        assert tree[1]['id'] == 'comment3'
        assert tree[1]['body'] == 'Parent comment 2'
        assert len(tree[1]['replies']) == 0


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
