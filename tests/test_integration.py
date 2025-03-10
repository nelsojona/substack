#!/usr/bin/env python3
"""
Integration tests for Substack to Markdown CLI.

This module provides end-to-end integration tests that verify the combined functionality
of multiple features working together, including comment extraction, newsletter metadata,
concurrent fetching, and subscriber-only content.
"""

import os
import sys
import pytest
import asyncio
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.substack_direct_downloader import SubstackDirectDownloader
from src.utils.substack_api_utils import (
    extract_newsletter_metadata,
    extract_post_metadata,
    generate_newsletter_index
)


class TestIntegration:
    """Integration tests for Substack to Markdown CLI."""

    @pytest.fixture
    def mock_html_with_comments(self):
        """Create mock HTML with comments for testing."""
        return """
        <html>
        <body>
            <h1 class="post-title">Test Post</h1>
            <time>January 1, 2023</time>
            <div class="post-content">
                <p>This is test content.</p>
                <img src="https://example.com/image1.jpg" />
                <img src="https://example.com/image2.jpg" />
            </div>
            <div id="comments">
                <div class="comment-thread">
                    <div class="comment" id="comment-1">
                        <div class="comment-body">Test comment 1</div>
                        <div class="comment-author">Author 1</div>
                        <div class="comment-date">2023-01-02</div>
                        <div class="comment-replies">
                            <div class="comment" id="comment-2">
                                <div class="comment-body">Reply to comment 1</div>
                                <div class="comment-author">Author 2</div>
                                <div class="comment-date">2023-01-03</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <script>
                window.__PRELOADED_STATE__ = JSON.parse("{\\\"postBySlug\\\":{\\\"id\\\":\\\"post123\\\"},\\\"commentsByPostId\\\":{\\\"post123\\\":[{\\\"id\\\":\\\"comment1\\\",\\\"body\\\":\\\"JavaScript comment 1\\\",\\\"commenter\\\":{\\\"name\\\":\\\"JS Author 1\\\"},\\\"createdAt\\\":\\\"2023-01-02\\\",\\\"parentCommentId\\\":null},{\\\"id\\\":\\\"comment2\\\",\\\"body\\\":\\\"JavaScript reply 1\\\",\\\"commenter\\\":{\\\"name\\\":\\\"JS Author 2\\\"},\\\"createdAt\\\":\\\"2023-01-03\\\",\\\"parentCommentId\\\":\\\"comment1\\\"}]}}");
            </script>
        </body>
        </html>
        """

    @pytest.fixture
    def mock_api_response(self):
        """Create mock API response for testing."""
        return {
            "id": "post123",
            "title": "Test Post",
            "body_html": "<p>This is test content.</p>",
            "published_at": "2023-01-01T12:00:00Z",
            "audience": "everyone"
        }

    @pytest.fixture
    def mock_newsletter_response(self):
        """Create mock newsletter API response for testing."""
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
                    "canonical_url": "https://testauthor.substack.com/p/test-post-1"
                },
                {
                    "id": "post2",
                    "title": "Test Post 2",
                    "published_at": "2023-01-02T12:00:00Z",
                    "canonical_url": "https://testauthor.substack.com/p/test-post-2"
                }
            ]
        }

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    @patch("src.core.substack_direct_downloader.BatchImageDownloader.download_images_batch")
    async def test_download_post_with_comments_and_images(self, mock_download_images, mock_fetch, mock_html_with_comments, tmp_path):
        """Test downloading a post with comments and images."""
        # Arrange
        # Create a downloader with comments enabled
        downloader = SubstackDirectDownloader(
            author="testauthor",
            output_dir=str(tmp_path),
            include_comments=True
        )
        
        # Mock the fetch_url method to return HTML with comments
        mock_fetch.return_value = mock_html_with_comments
        
        # Mock the image downloader
        mock_download_images.return_value = {
            "https://example.com/image1.jpg": "images/test-post_image1.jpg",
            "https://example.com/image2.jpg": "images/test-post_image2.jpg"
        }
        
        # Mock other methods that would be called
        downloader._store_post_metadata = MagicMock(return_value=True)
        
        # Initialize the session and semaphore for testing
        await downloader.__aenter__()
        
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
            
            # Check post content
            assert "Test Post" in content
            assert "This is test content" in content
            
            # Check image paths were updated
            assert "images/test-post_image1.jpg" in content
            assert "images/test-post_image2.jpg" in content
            
            # Check comments were included
            assert "## Comments" in content
            assert "**JS Author 1** - 2023-01-02" in content
            assert "JavaScript comment 1" in content
            assert "**JS Author 2** - 2023-01-03" in content
            assert "JavaScript reply 1" in content
        
        # Clean up
        await downloader.__aexit__(None, None, None)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_concurrent_downloads_with_semaphore(self, mock_get, tmp_path):
        """Test concurrent downloading of multiple posts with semaphore control."""
        # Arrange
        # Create a downloader with concurrency settings
        downloader = SubstackDirectDownloader(
            author="testauthor",
            output_dir=str(tmp_path),
            max_concurrency=3
        )
        
        # Mock responses for multiple URLs
        mock_responses = {}
        
        for i in range(5):
            url = f"https://testauthor.substack.com/p/post{i}"
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=f"""
            <html>
            <body>
                <h1 class="post-title">Post {i}</h1>
                <time>January {i+1}, 2023</time>
                <div class="post-content">Content {i}</div>
            </body>
            </html>
            """)
            mock_responses[url] = mock_response
        
        # Set up the mock to return the appropriate response for each URL
        async def side_effect(url, **kwargs):
            mock_resp = mock_responses.get(url, MagicMock())
            mock_resp.__aenter__.return_value = mock_resp
            return mock_resp
        
        mock_get.side_effect = side_effect
        
        # Mock methods that would be called during download
        downloader._store_post_metadata = MagicMock(return_value=True)
        downloader.extract_image_urls = AsyncMock(return_value=set())
        
        # Initialize the session and semaphore for testing
        await downloader.__aenter__()
        
        # Track concurrent executions
        execution_tracker = {
            'current': 0,
            'max': 0
        }
        
        # Override _fetch_url to track concurrency
        original_fetch_url = downloader._fetch_url
        
        async def tracking_fetch_url(url, retries=3):
            execution_tracker['current'] += 1
            execution_tracker['max'] = max(execution_tracker['max'], execution_tracker['current'])
            
            try:
                return await original_fetch_url(url, retries)
            finally:
                execution_tracker['current'] -= 1
        
        downloader._fetch_url = tracking_fetch_url
        
        # Act
        # Download multiple posts concurrently
        urls = [f"https://testauthor.substack.com/p/post{i}" for i in range(5)]
        tasks = [downloader.download_post(url, force=True) for url in urls]
        results = await asyncio.gather(*tasks)
        
        # Assert
        assert all(results)  # All downloads should succeed
        
        # Check that files were created
        files = os.listdir(str(tmp_path))
        assert len(files) == 5
        
        # Check that concurrency was limited by the semaphore
        assert execution_tracker['max'] <= downloader.connection_pool.max_connections
        
        # Clean up
        await downloader.__aexit__(None, None, None)

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader.direct_fetch")
    async def test_subscriber_only_content_with_newsletter_metadata(self, mock_direct_fetch, mock_fetch, mock_newsletter_response, tmp_path):
        """Test downloading subscriber-only content with newsletter metadata."""
        # Arrange
        # Create a downloader with auth token
        downloader = SubstackDirectDownloader(
            author="testauthor",
            output_dir=str(tmp_path)
        )
        downloader.set_auth_token("test_auth_token_123")
        
        # Mock direct_fetch to return subscriber-only content
        mock_direct_fetch.return_value = {
            "title": "Subscriber Only Post",
            "date": "2023-01-01",
            "author": "testauthor",
            "url": "https://testauthor.substack.com/p/subscriber-only-post",
            "content_html": "<p>This is premium content</p>",
            "html": "<p>This is premium content</p>"
        }
        
        # Mock _fetch_url to return newsletter data
        mock_fetch.side_effect = lambda url, retries=3: (
            json.dumps(mock_newsletter_response) if "api/v1" in url else None
        )
        
        # Mock other methods that would be called
        downloader._store_post_metadata = MagicMock(return_value=True)
        downloader.extract_image_urls = AsyncMock(return_value=set())
        
        # Initialize the session and semaphore for testing
        await downloader.__aenter__()
        
        # Act
        # 1. Download subscriber-only post
        post_result = await downloader.download_post(
            url="https://testauthor.substack.com/p/subscriber-only-post",
            force=True,
            use_direct=True
        )
        
        # 2. Extract newsletter metadata
        newsletter_metadata = extract_newsletter_metadata(mock_newsletter_response)
        
        # 3. Extract post metadata
        posts_metadata = [extract_post_metadata(post) for post in mock_newsletter_response.get("posts", [])]
        
        # 4. Generate newsletter index
        index_markdown = generate_newsletter_index(newsletter_metadata, posts_metadata)
        
        # 5. Write index file
        index_path = os.path.join(str(tmp_path), "index.md")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_markdown)
        
        # Assert
        # Check post download result
        assert post_result is True
        
        # Check that the post file was created
        post_files = [f for f in os.listdir(str(tmp_path)) if f != "index.md"]
        assert len(post_files) == 1
        
        # Read the post file and check its content
        with open(os.path.join(str(tmp_path), post_files[0]), 'r', encoding='utf-8') as f:
            content = f.read()
            assert "Subscriber Only Post" in content
            assert "This is premium content" in content
        
        # Check that the index file was created
        assert os.path.exists(index_path)
        
        # Read the index file and check its content
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "# Test Newsletter" in content
            assert "A test newsletter for integration testing" in content
            assert "**Posts**: 50" in content
            assert "**Subscribers**: 1000" in content
        
        # Clean up
        await downloader.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, tmp_path):
        """Test the complete end-to-end workflow with real network requests (mocked)."""
        # This test simulates the complete workflow:
        # 1. Initialize downloader with all features enabled
        # 2. Find post URLs from sitemap
        # 3. Download posts with comments and images
        # 4. Generate newsletter index
        
        # Arrange
        # Create a downloader with all features enabled
        downloader = SubstackDirectDownloader(
            author="testauthor",
            output_dir=str(tmp_path),
            include_comments=True,
            max_concurrency=3,
            max_image_concurrency=5
        )
        
        # Set auth token for subscriber-only content
        downloader.set_auth_token("test_auth_token_123")
        
        # Mock the find_post_urls method
        downloader.find_post_urls = AsyncMock(return_value=[
            "https://testauthor.substack.com/p/post1",
            "https://testauthor.substack.com/p/post2",
            "https://testauthor.substack.com/p/post3"
        ])
        
        # Mock the download_post method
        downloader.download_post = AsyncMock(return_value=True)
        
        # Initialize the session and semaphore for testing
        await downloader.__aenter__()
        
        # Act
        # 1. Find post URLs
        post_urls = await downloader.find_post_urls()
        
        # 2. Download posts
        results = []
        for url in post_urls:
            result = await downloader.download_post(url, force=True)
            results.append(result)
        
        # 3. Create mock newsletter metadata
        newsletter_metadata = {
            "title": "Test Newsletter",
            "description": "A test newsletter for end-to-end testing",
            "author": "Test Author",
            "subscribers_count": 1000,
            "post_count": len(post_urls)
        }
        
        # 4. Create mock post metadata
        posts_metadata = [
            {
                "title": f"Test Post {i+1}",
                "date": f"2023-01-{i+1:02d}",
                "url": url
            }
            for i, url in enumerate(post_urls)
        ]
        
        # 5. Generate newsletter index
        index_markdown = generate_newsletter_index(newsletter_metadata, posts_metadata)
        
        # 6. Write index file
        index_path = os.path.join(str(tmp_path), "index.md")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_markdown)
        
        # Assert
        # Check that all downloads were successful
        assert all(results)
        
        # Check that download_post was called for each URL
        assert downloader.download_post.call_count == len(post_urls)
        
        # Check that the index file was created
        assert os.path.exists(index_path)
        
        # Read the index file and check its content
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "# Test Newsletter" in content
            assert "A test newsletter for end-to-end testing" in content
            assert f"**Posts**: {len(post_urls)}" in content
            assert "**Subscribers**: 1000" in content
            for i, url in enumerate(post_urls):
                assert f"Test Post {i+1}" in content
                assert url in content
        
        # Clean up
        await downloader.__aexit__(None, None, None)


class TestPerformance:
    """Performance tests for Substack to Markdown CLI."""

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    async def test_concurrent_download_performance(self, mock_fetch, tmp_path):
        """Test performance of concurrent downloads."""
        # Arrange
        # Create a downloader with high concurrency
        downloader = SubstackDirectDownloader(
            author="testauthor",
            output_dir=str(tmp_path),
            max_concurrency=10
        )
        
        # Mock _fetch_url to return HTML with minimal delay
        async def mock_fetch_url(url, retries=3):
            # Simulate minimal network delay
            await asyncio.sleep(0.01)
            return f"""
            <html>
            <body>
                <h1 class="post-title">Post {url.split('/')[-1]}</h1>
                <time>January 1, 2023</time>
                <div class="post-content">Content for {url}</div>
            </body>
            </html>
            """
        
        mock_fetch.side_effect = mock_fetch_url
        
        # Mock other methods that would be called
        downloader._store_post_metadata = MagicMock(return_value=True)
        downloader.extract_image_urls = AsyncMock(return_value=set())
        
        # Initialize the session and semaphore for testing
        await downloader.__aenter__()
        
        # Generate a large number of test URLs
        test_urls = [f"https://testauthor.substack.com/p/post{i}" for i in range(20)]
        
        # Act
        # Measure the time to download all posts
        import time
        start_time = time.time()
        
        tasks = [downloader.download_post(url, force=True) for url in test_urls]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Assert
        assert all(results)  # All downloads should succeed
        
        # Check that files were created
        files = os.listdir(str(tmp_path))
        assert len(files) == len(test_urls)
        
        # Performance assertion - should be much faster than sequential
        # With 20 posts and 10 concurrency, should be roughly 2x faster than sequential
        # Sequential would take ~20 * 0.01 = 0.2 seconds
        # Concurrent should take ~2 * 0.01 = 0.02 seconds plus overhead
        # Allow for some overhead, but should still be significantly faster
        assert duration < 0.1  # Should complete in under 0.1 seconds with concurrency
        
        # Clean up
        await downloader.__aexit__(None, None, None)


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
