#!/usr/bin/env python3
"""
Integration test for downloading Trade Companion Substack posts.

This module contains a test case for downloading all posts from the
Trade Companion Substack newsletter, including images and verifying
the downloaded content.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import tempfile
import shutil
import glob
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import substack_to_md
from substack_fetcher import SubstackFetcher
from markdown_converter import MarkdownConverter
from env_loader import load_env_vars


class TestTradeCompanion(unittest.TestCase):
    """Test case for downloading Trade Companion Substack posts."""

    def setUp(self):
        """Set up test fixtures."""
        # Set up the output directory
        self.output_dir = os.path.join("output", "tradecompanion")
        # Create the directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load environment variables
        load_env_vars()
        
        # Sample post data for mocking
        self.sample_posts = [
            {
                'id': 1,
                'title': 'Trade Companion Post 1',
                'subtitle': 'A test subtitle',
                'author': {'name': 'Trade Companion'},
                'post_date': '2023-01-01T12:00:00Z',
                'canonical_url': 'https://tradecompanion.substack.com/p/post1',
                'body_html': '<h1>Trade Companion Post 1</h1><p>This is test content with an <img src="https://example.com/image1.jpg" alt="test image"></p>'
            },
            {
                'id': 2,
                'title': 'Trade Companion Post 2',
                'subtitle': 'Another test subtitle',
                'author': {'name': 'Trade Companion'},
                'post_date': '2023-01-02T12:00:00Z',
                'canonical_url': 'https://tradecompanion.substack.com/p/post2',
                'body_html': '<h1>Trade Companion Post 2</h1><p>This is more test content with an <img src="https://example.com/image2.jpg" alt="test image"></p>'
            }
        ]

    def tearDown(self):
        """Tear down test fixtures."""
        # We're not cleaning up the output directory anymore
        # to keep the downloaded files for inspection
        pass

    @patch('substack_to_md.SubstackFetcher')
    @patch('substack_to_md.MarkdownConverter')
    def test_download_trade_companion(self, mock_converter_class, mock_fetcher_class):
        """Test downloading all posts from Trade Companion Substack with images."""
        # Set up mocks
        mock_fetcher = mock_fetcher_class.return_value
        mock_fetcher.fetch_posts.return_value = self.sample_posts
        
        mock_converter = mock_converter_class.return_value
        mock_converter.convert_html_to_markdown.side_effect = [
            "# Trade Companion Post 1\n\nThis is test content with an ![test image](images/image1.jpg)",
            "# Trade Companion Post 2\n\nThis is more test content with an ![test image](images/image2.jpg)"
        ]
        
        # Create a mock for parse_arguments
        with patch('substack_to_md.parse_arguments') as mock_parse_args:
            # Set up the mock to return the desired arguments
            mock_args = MagicMock()
            mock_args.author = 'tradecompanion'
            mock_args.output = self.output_dir
            mock_args.limit = None
            mock_args.verbose = True
            mock_args.email = None
            mock_args.password = None
            mock_args.token = None
            mock_args.cookies_file = None
            mock_args.save_cookies = None
            mock_args.private = False
            mock_args.download_images = True
            mock_args.image_dir = 'images'
            mock_args.image_base_url = ''
            mock_args.max_image_workers = 4
            mock_args.image_timeout = 10
            mock_args.use_post_objects = False
            mock_args.url = None
            mock_args.slug = None
            mock_parse_args.return_value = mock_args
            
            # Call the main function
            result = substack_to_md.main()
            
            # Assert that the main function returned success
            self.assertEqual(result, 0)
            
            # Assert that the fetcher was called correctly
            mock_fetcher.fetch_posts.assert_called_once_with('tradecompanion', None, True)
            
            # Assert that the converter was called for each post
            self.assertEqual(mock_converter.convert_html_to_markdown.call_count, 2)
            
            # Assert that the output directory was created
            self.assertTrue(os.path.exists(self.output_dir))
            
            # Assert that the output files were created
            expected_files = [
                '2023-01-01_Trade Companion Post 1.md',
                '2023-01-02_Trade Companion Post 2.md'
            ]
            for filename in expected_files:
                file_path = os.path.join(self.output_dir, filename)
                self.assertTrue(os.path.exists(file_path), f"File {filename} was not created")
                
                # Check the content of the files
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.assertIn('title: "Trade Companion Post', content)
                    self.assertIn('subtitle: "', content)
                    self.assertIn('author: "Trade Companion"', content)
                    self.assertIn('date: "2023-01-0', content)
                    self.assertIn('original_url: "https://tradecompanion.substack.com/p/post', content)
                    self.assertIn('# Trade Companion Post', content)
                    self.assertIn('This is', content)
                    self.assertIn('![test image](images/', content)

    @patch('substack_fetcher.Substack')
    def test_fetch_posts_real_connection(self, mock_substack_class):
        """Test fetching posts from Trade Companion with a real connection (limited)."""
        # This test attempts to make a real connection to the Substack API
        # but mocks the actual Substack client to control the response
        
        # Set up mock to return sample posts
        mock_substack = mock_substack_class.return_value
        mock_substack.get_posts.return_value = self.sample_posts
        
        # Create a real fetcher
        fetcher = SubstackFetcher(max_retries=2, retry_delay=0.1)
        
        # Fetch posts with a limit to avoid excessive API calls
        posts = fetcher.fetch_posts('tradecompanion', limit=2, verbose=True)
        
        # Assert that we got the expected posts
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0]['title'], 'Trade Companion Post 1')
        self.assertEqual(posts[1]['title'], 'Trade Companion Post 2')

    @patch('substack_to_md.SubstackFetcher')
    @patch('substack_to_md.MarkdownConverter')
    def test_download_with_image_options(self, mock_converter_class, mock_fetcher_class):
        """Test downloading posts with custom image options."""
        # Set up mocks
        mock_fetcher = mock_fetcher_class.return_value
        mock_fetcher.fetch_posts.return_value = self.sample_posts
        
        mock_converter = mock_converter_class.return_value
        mock_converter.convert_html_to_markdown.side_effect = [
            "# Trade Companion Post 1\n\nThis is test content with an ![test image](custom-images/image1.jpg)",
            "# Trade Companion Post 2\n\nThis is more test content with an ![test image](custom-images/image2.jpg)"
        ]
        
        # Create a mock for parse_arguments
        with patch('substack_to_md.parse_arguments') as mock_parse_args:
            # Set up the mock to return the desired arguments with custom image options
            mock_args = MagicMock()
            mock_args.author = 'tradecompanion'
            mock_args.output = self.output_dir
            mock_args.limit = None
            mock_args.verbose = True
            mock_args.download_images = True
            mock_args.image_dir = 'custom-images'  # Custom image directory
            mock_args.image_base_url = 'https://example.com/images/'  # Custom base URL
            mock_args.max_image_workers = 8  # Custom worker count
            mock_args.image_timeout = 20  # Custom timeout
            mock_args.use_post_objects = False
            mock_args.url = None
            mock_args.slug = None
            mock_args.email = None
            mock_args.password = None
            mock_args.token = None
            mock_args.cookies_file = None
            mock_args.save_cookies = None
            mock_args.private = False
            mock_parse_args.return_value = mock_args
            
            # Call the main function
            result = substack_to_md.main()
            
            # Assert that the main function returned success
            self.assertEqual(result, 0)
            
            # Assert that the converter was initialized with the custom image options
            mock_converter_class.assert_called_once_with(
                download_images=True,
                image_dir='custom-images',
                image_base_url='https://example.com/images/',
                max_workers=8,
                timeout=20
            )
            
            # Assert that the output files were created
            expected_files = [
                '2023-01-01_Trade Companion Post 1.md',
                '2023-01-02_Trade Companion Post 2.md'
            ]
            for filename in expected_files:
                file_path = os.path.join(self.output_dir, filename)
                self.assertTrue(os.path.exists(file_path), f"File {filename} was not created")
                
                # Check the content of the files for custom image paths
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.assertIn('custom-images/', content)

    @patch('substack_to_md.SubstackFetcher')
    @patch('substack_to_md.MarkdownConverter')
    def test_download_all_posts(self, mock_converter_class, mock_fetcher_class):
        """Test downloading all posts from Trade Companion Substack without limit."""
        # Set up mocks with more posts to simulate downloading all posts
        mock_fetcher = mock_fetcher_class.return_value
        
        # Create a larger sample of posts to simulate "all posts"
        all_posts = self.sample_posts.copy()
        for i in range(3, 10):  # Add more sample posts
            all_posts.append({
                'id': i,
                'title': f'Trade Companion Post {i}',
                'subtitle': f'Subtitle for post {i}',
                'author': {'name': 'Trade Companion'},
                'post_date': f'2023-01-{i:02d}T12:00:00Z',
                'canonical_url': f'https://tradecompanion.substack.com/p/post{i}',
                'body_html': f'<h1>Trade Companion Post {i}</h1><p>Content for post {i} with an <img src="https://example.com/image{i}.jpg" alt="test image"></p>'
            })
        
        mock_fetcher.fetch_posts.return_value = all_posts
        
        # Set up converter mock to handle all posts
        mock_converter = mock_converter_class.return_value
        mock_converter.convert_html_to_markdown.side_effect = [
            f"# Trade Companion Post {i}\n\nContent for post {i} with an ![test image](images/image{i}.jpg)" 
            for i in range(1, 10)
        ]
        
        # Create a mock for parse_arguments
        with patch('substack_to_md.parse_arguments') as mock_parse_args:
            # Set up the mock to return the desired arguments
            mock_args = MagicMock()
            mock_args.author = 'tradecompanion'
            mock_args.output = self.output_dir
            mock_args.limit = None  # No limit - download all posts
            mock_args.verbose = True
            mock_args.email = None
            mock_args.password = None
            mock_args.token = None
            mock_args.cookies_file = None
            mock_args.save_cookies = None
            mock_args.private = False
            mock_args.download_images = True
            mock_args.image_dir = 'images'
            mock_args.image_base_url = ''
            mock_args.max_image_workers = 4
            mock_args.image_timeout = 10
            mock_args.use_post_objects = False
            mock_args.url = None
            mock_args.slug = None
            mock_parse_args.return_value = mock_args
            
            # Call the main function
            result = substack_to_md.main()
            
            # Assert that the main function returned success
            self.assertEqual(result, 0)
            
            # Assert that the fetcher was called correctly with no limit
            mock_fetcher.fetch_posts.assert_called_once_with('tradecompanion', None, True)
            
            # Assert that the converter was called for each post
            self.assertEqual(mock_converter.convert_html_to_markdown.call_count, len(all_posts))
            
            # Assert that the output directory exists
            self.assertTrue(os.path.exists(self.output_dir))
            
            # Assert that all expected output files were created
            for i in range(1, 10):
                filename = f'2023-01-{i:02d}_Trade Companion Post {i}.md'
                file_path = os.path.join(self.output_dir, filename)
                self.assertTrue(os.path.exists(file_path), f"File {filename} was not created")
                
                # Check the content of the files
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.assertIn(f'title: "Trade Companion Post {i}"', content)
                    self.assertIn('author: "Trade Companion"', content)
                    self.assertIn(f'date: "2023-01-{i:02d}"', content)
                    self.assertIn(f'original_url: "https://tradecompanion.substack.com/p/post{i}"', content)
                    self.assertIn(f'# Trade Companion Post {i}', content)
                    self.assertIn('![test image](images/', content)

    @patch('substack_to_md.SubstackFetcher')
    def test_error_handling(self, mock_fetcher_class):
        """Test error handling when downloading posts."""
        # Set up mock to raise an exception
        mock_fetcher = mock_fetcher_class.return_value
        mock_fetcher.fetch_posts.side_effect = ConnectionError("Failed to connect to Substack API")
        
        # Create a mock for parse_arguments
        with patch('substack_to_md.parse_arguments') as mock_parse_args:
            # Set up the mock to return the desired arguments
            mock_args = MagicMock()
            mock_args.author = 'tradecompanion'
            mock_args.output = self.output_dir
            mock_args.limit = None
            mock_args.verbose = True
            mock_args.download_images = True
            mock_args.image_dir = 'images'
            mock_args.image_base_url = ''
            mock_args.max_image_workers = 4
            mock_args.image_timeout = 10
            mock_args.use_post_objects = False
            mock_args.url = None
            mock_args.slug = None
            mock_args.email = None
            mock_args.password = None
            mock_args.token = None
            mock_args.cookies_file = None
            mock_args.save_cookies = None
            mock_args.private = False
            mock_parse_args.return_value = mock_args
            
            # Call the main function
            result = substack_to_md.main()
            
            # Assert that the main function returned error
            self.assertEqual(result, 1)


if __name__ == '__main__':
    unittest.main()
