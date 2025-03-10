#!/usr/bin/env python3
"""
Tests for the multiprocessing_downloader module.
"""

import os
import unittest
import tempfile
from unittest.mock import patch, MagicMock, Mock

from src.core.multiprocessing_downloader import MultiprocessingDownloader


class TestMultiprocessingDownloader(unittest.TestCase):
    """Test cases for the MultiprocessingDownloader class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create the downloader
        self.downloader = MultiprocessingDownloader(
            author="test_author",
            output_dir=self.temp_dir,
            min_delay=0.1,
            max_delay=0.5,
            process_count=2
        )
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary directory
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for file in files:
                os.remove(os.path.join(root, file))
            for dir in dirs:
                os.rmdir(os.path.join(root, dir))
        
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.downloader.author, "test_author")
        self.assertEqual(self.downloader.output_dir, self.temp_dir)
        self.assertEqual(self.downloader.min_delay, 0.1)
        self.assertEqual(self.downloader.max_delay, 0.5)
        self.assertEqual(self.downloader.process_count, 2)
        self.assertIsNone(self.downloader.auth_token)
    
    def test_set_auth_token(self):
        """Test setting the authentication token."""
        self.downloader.set_auth_token("test_token")
        self.assertEqual(self.downloader.auth_token, "test_token")
    
    @patch('requests.Session.get')
    def test_fetch_url(self, mock_get):
        """Test fetching a URL."""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "test response"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_get.return_value = mock_response
        
        # Fetch a URL
        response = self.downloader._fetch_url("https://example.com")
        
        # Check the result
        self.assertEqual(response, "test response")
        
        # Check that requests.get was called with the correct URL
        mock_get.assert_called_once_with("https://example.com", cookies=None)
    
    @patch('requests.Session.get')
    def test_fetch_url_with_auth(self, mock_get):
        """Test fetching a URL with authentication."""
        # Set the authentication token
        self.downloader.set_auth_token("test_token")
        
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "test response"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_get.return_value = mock_response
        
        # Fetch a URL
        response = self.downloader._fetch_url("https://example.com")
        
        # Check the result
        self.assertEqual(response, "test response")
        
        # Check that requests.get was called with the correct URL and cookies
        mock_get.assert_called_once_with(
            "https://example.com",
            cookies={"substack.sid": "test_token"}
        )
    
    @patch('requests.Session.get')
    def test_fetch_url_error(self, mock_get):
        """Test fetching a URL with an error."""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.headers = {"Content-Type": "text/html"}
        mock_get.return_value = mock_response
        
        # Fetch a URL
        response = self.downloader._fetch_url("https://example.com")
        
        # Check the result
        self.assertIsNone(response)
    
    @patch('src.core.multiprocessing_downloader.MultiprocessingDownloader._fetch_url')
    def test_find_post_urls(self, mock_fetch_url):
        """Test finding post URLs."""
        # Mock the fetch_url method
        mock_fetch_url.return_value = """
        <html>
        <body>
            <a class="post-preview-title" href="https://test_author.substack.com/p/post1">Post 1</a>
            <a class="post-preview-title" href="https://test_author.substack.com/p/post2">Post 2</a>
            <a class="post-preview-title" href="https://test_author.substack.com/p/post3">Post 3</a>
        </body>
        </html>
        """
        
        # Find post URLs
        urls = self.downloader.find_post_urls(max_pages=1)
        
        # Check the result
        self.assertEqual(len(urls), 3)
        self.assertIn("https://test_author.substack.com/p/post1", urls)
        self.assertIn("https://test_author.substack.com/p/post2", urls)
        self.assertIn("https://test_author.substack.com/p/post3", urls)
        
        # Check that fetch_url was called with the correct URL
        mock_fetch_url.assert_called_once_with("https://test_author.substack.com/archive")
    
    @patch('src.core.multiprocessing_downloader.MultiprocessingDownloader._fetch_url')
    def test_find_post_urls_multiple_pages(self, mock_fetch_url):
        """Test finding post URLs from multiple pages."""
        # Mock the fetch_url method
        mock_fetch_url.side_effect = [
            # First page
            """
            <html>
            <body>
                <a class="post-preview-title" href="https://test_author.substack.com/p/post1">Post 1</a>
                <a class="post-preview-title" href="https://test_author.substack.com/p/post2">Post 2</a>
                <a class="next-page" href="https://test_author.substack.com/archive?page=2">Next page</a>
            </body>
            </html>
            """,
            # Second page
            """
            <html>
            <body>
                <a class="post-preview-title" href="https://test_author.substack.com/p/post3">Post 3</a>
                <a class="post-preview-title" href="https://test_author.substack.com/p/post4">Post 4</a>
            </body>
            </html>
            """
        ]
        
        # Find post URLs
        urls = self.downloader.find_post_urls(max_pages=2)
        
        # Check the result
        self.assertEqual(len(urls), 4)
        self.assertIn("https://test_author.substack.com/p/post1", urls)
        self.assertIn("https://test_author.substack.com/p/post2", urls)
        self.assertIn("https://test_author.substack.com/p/post3", urls)
        self.assertIn("https://test_author.substack.com/p/post4", urls)
        
        # Check that fetch_url was called with the correct URLs
        mock_fetch_url.assert_any_call("https://test_author.substack.com/archive")
        mock_fetch_url.assert_any_call("https://test_author.substack.com/archive?page=2")
    
    @patch('src.core.multiprocessing_downloader.MultiprocessingDownloader._fetch_url')
    @patch('src.core.multiprocessing_downloader.MarkdownConverter.convert_html_to_markdown')
    def test_download_post(self, mock_convert, mock_fetch_url):
        """Test downloading a post."""
        # Mock the fetch_url method
        mock_fetch_url.return_value = """
        <html>
        <head>
            <title>Test Post</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <article>
                <h1>Test Post</h1>
                <div class="body">
                    <p>This is a test post.</p>
                </div>
            </article>
        </body>
        </html>
        """
        
        # Mock the convert_html_to_markdown method
        mock_convert.return_value = "# Test Post\n\nThis is a test post."
        
        # Download the post
        result = self.downloader.download_post(
            url="https://test_author.substack.com/p/test-post",
            force_refresh=False
        )
        
        # Check the result
        self.assertTrue(result)
        
        # Check that fetch_url was called with the correct URL
        mock_fetch_url.assert_called_once_with("https://test_author.substack.com/p/test-post")
        
        # Check that convert_html_to_markdown was called
        mock_convert.assert_called_once()
        
        # Check that the markdown file was created
        markdown_file = os.path.join(self.temp_dir, "test-post.md")
        self.assertTrue(os.path.exists(markdown_file))
        
        # Check the content of the markdown file
        with open(markdown_file, "r") as f:
            content = f.read()
        
        self.assertEqual(content, "# Test Post\n\nThis is a test post.")
    
    @patch('src.core.multiprocessing_downloader.Pool')
    @patch('src.core.multiprocessing_downloader.MultiprocessingDownloader.find_post_urls')
    def test_download_all_posts(self, mock_find_post_urls, mock_pool):
        """Test downloading all posts."""
        # Mock the find_post_urls method
        mock_find_post_urls.return_value = [
            "https://test_author.substack.com/p/post1",
            "https://test_author.substack.com/p/post2",
            "https://test_author.substack.com/p/post3"
        ]
        
        # Mock the Pool
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        mock_pool_instance.__enter__ = Mock(return_value=mock_pool_instance)
        mock_pool_instance.__exit__ = Mock(return_value=None)
        mock_pool_instance.map = Mock(return_value=[True, True, False])
        
        # Download all posts
        successful, failed, skipped = self.downloader.download_all_posts(
            max_pages=1,
            force_refresh=False,
            max_posts=None,
            download_images=False
        )
        
        # Check the result
        self.assertEqual(successful, 2)
        self.assertEqual(failed, 1)
        self.assertEqual(skipped, 0)
        
        # Check that find_post_urls was called with the correct arguments
        mock_find_post_urls.assert_called_once_with(max_pages=1)
        
        # Check that Pool was created with the correct number of processes
        mock_pool.assert_called_once_with(processes=2)
        
        # Check that map was called with the correct arguments
        mock_pool_instance.map.assert_called_once()
        args, kwargs = mock_pool_instance.map.call_args
        self.assertEqual(args[0].__name__, "_download_post_wrapper")
        self.assertEqual(len(args[1]), 3)
    
    @patch('src.core.multiprocessing_downloader.Pool')
    @patch('src.core.multiprocessing_downloader.MultiprocessingDownloader.find_post_urls')
    def test_download_all_posts_with_limit(self, mock_find_post_urls, mock_pool):
        """Test downloading all posts with a limit."""
        # Mock the find_post_urls method
        mock_find_post_urls.return_value = [
            "https://test_author.substack.com/p/post1",
            "https://test_author.substack.com/p/post2",
            "https://test_author.substack.com/p/post3"
        ]
        
        # Mock the Pool
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        mock_pool_instance.__enter__ = Mock(return_value=mock_pool_instance)
        mock_pool_instance.__exit__ = Mock(return_value=None)
        mock_pool_instance.map = Mock(return_value=[True, True])
        
        # Download all posts with a limit
        successful, failed, skipped = self.downloader.download_all_posts(
            max_pages=1,
            force_refresh=False,
            max_posts=2,
            download_images=False
        )
        
        # Check the result
        self.assertEqual(successful, 2)
        self.assertEqual(failed, 0)
        self.assertEqual(skipped, 1)
        
        # Check that find_post_urls was called with the correct arguments
        mock_find_post_urls.assert_called_once_with(max_pages=1)
        
        # Check that Pool was created with the correct number of processes
        mock_pool.assert_called_once_with(processes=2)
        
        # Check that map was called with the correct arguments
        mock_pool_instance.map.assert_called_once()
        args, kwargs = mock_pool_instance.map.call_args
        self.assertEqual(args[0].__name__, "_download_post_wrapper")
        self.assertEqual(len(args[1]), 2)
        
        # Check skipped count
        self.assertEqual(skipped, 1)
    
    def test_download_post_wrapper(self):
        """Test the download post wrapper function."""
        # Mock the download_post method
        self.downloader.download_post = Mock(return_value=True)
        
        # Call the wrapper function
        result = self.downloader._download_post_wrapper(
            ("https://test_author.substack.com/p/test-post", False, False)
        )
        
        # Check the result
        self.assertTrue(result)
        
        # Check that download_post was called with the correct arguments
        self.downloader.download_post.assert_called_once_with(
            url="https://test_author.substack.com/p/test-post",
            force_refresh=False,
            download_images=False
        )


if __name__ == '__main__':
    unittest.main()
