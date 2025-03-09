#!/usr/bin/env python3
"""
Integration tests for the Substack to Markdown CLI tool.

This module contains tests for the end-to-end workflow of the CLI tool,
testing the integration between the different components.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import tempfile
import shutil
import argparse

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import substack_to_md
from substack_fetcher import SubstackFetcher
from markdown_converter import MarkdownConverter


class TestIntegration(unittest.TestCase):
    """Integration tests for the Substack to Markdown CLI tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for output files
        self.temp_dir = tempfile.mkdtemp()
        
        # Sample post data for testing
        self.sample_posts = [
            {
                'id': 1,
                'title': 'Test Post 1',
                'subtitle': 'A test subtitle',
                'author': {'name': 'Test Author'},
                'post_date': '2023-01-01T12:00:00Z',
                'canonical_url': 'https://example.com/post1',
                'body_html': '<h1>Test Post 1</h1><p>This is test content 1.</p>'
            },
            {
                'id': 2,
                'title': 'Test Post 2',
                'subtitle': 'Another test subtitle',
                'author': {'name': 'Test Author'},
                'post_date': '2023-01-02T12:00:00Z',
                'canonical_url': 'https://example.com/post2',
                'body_html': '<h1>Test Post 2</h1><p>This is test content 2.</p>'
            }
        ]

    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary directory and its contents
        shutil.rmtree(self.temp_dir)

    @patch('substack_to_md.SubstackFetcher')
    @patch('substack_to_md.MarkdownConverter')
    def test_end_to_end_workflow(self, mock_converter_class, mock_fetcher_class):
        """Test the end-to-end workflow of the CLI tool."""
        # Set up mocks
        mock_fetcher = mock_fetcher_class.return_value
        mock_fetcher.fetch_posts.return_value = self.sample_posts
        
        mock_converter = mock_converter_class.return_value
        mock_converter.convert_html_to_markdown.side_effect = [
            "# Test Post 1\n\nThis is test content 1.",
            "# Test Post 2\n\nThis is test content 2."
        ]
        
        # Create a mock for parse_arguments
        with patch('substack_to_md.parse_arguments') as mock_parse_args:
            # Set up the mock to return the desired arguments
            mock_args = argparse.Namespace(
                author='testauthor',
                output=self.temp_dir,
                limit=None,
                verbose=True,
                email=None,
                password=None,
                token=None,
                cookies_file=None,
                save_cookies=None,
                private=False,
                download_images=False,
                image_dir='images',
                image_base_url='',
                max_image_workers=4,
                image_timeout=10,
                use_post_objects=False,
                url=None,
                slug=None
            )
            mock_parse_args.return_value = mock_args
            
            # Call the main function
            result = substack_to_md.main()
            
            # Assert that the main function returned success
            self.assertEqual(result, 0)
            
            # Assert that the fetcher was called correctly
            mock_fetcher.fetch_posts.assert_called_once_with('testauthor', None, True)
            
            # Assert that the converter was called for each post
            self.assertEqual(mock_converter.convert_html_to_markdown.call_count, 2)
            
            # Assert that the output files were created
            expected_files = [
                '2023-01-01_Test Post 1.md',
                '2023-01-02_Test Post 2.md'
            ]
            for filename in expected_files:
                file_path = os.path.join(self.temp_dir, filename)
                self.assertTrue(os.path.exists(file_path), f"File {filename} was not created")
                
                # Check the content of the files
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.assertIn('title: "Test Post', content)
                    self.assertIn('subtitle: "', content)
                    self.assertIn('author: "Test Author"', content)
                    self.assertIn('date: "2023-01-0', content)
                    self.assertIn('original_url: "https://example.com/post', content)
                    self.assertIn('# Test Post', content)
                    self.assertIn('This is test content', content)

    @patch('substack_to_md.SubstackFetcher')
    def test_no_posts_found(self, mock_fetcher_class):
        """Test handling when no posts are found."""
        # Set up mock to return empty list
        mock_fetcher = mock_fetcher_class.return_value
        mock_fetcher.fetch_posts.return_value = []
        
        # Create a mock for parse_arguments
        with patch('substack_to_md.parse_arguments') as mock_parse_args:
            # Set up the mock to return the desired arguments
            mock_args = argparse.Namespace(
                author='testauthor',
                output=self.temp_dir,
                limit=None,
                verbose=True
            )
            mock_parse_args.return_value = mock_args
            
            # Call the main function
            result = substack_to_md.main()
            
            # Assert that the main function returned error
            self.assertEqual(result, 1)

    @patch('substack_to_md.SubstackFetcher')
    def test_invalid_author(self, mock_fetcher_class):
        """Test handling of invalid author."""
        # Set up mock to raise ValueError
        mock_fetcher = mock_fetcher_class.return_value
        mock_fetcher.fetch_posts.side_effect = ValueError("Invalid author identifier")
        
        # Create a mock for parse_arguments
        with patch('substack_to_md.parse_arguments') as mock_parse_args:
            # Set up the mock to return the desired arguments
            mock_args = argparse.Namespace(
                author='invalidauthor',
                output=self.temp_dir,
                limit=None,
                verbose=True
            )
            mock_parse_args.return_value = mock_args
            
            # Call the main function
            result = substack_to_md.main()
            
            # Assert that the main function returned error
            self.assertEqual(result, 1)

    @patch('substack_to_md.SubstackFetcher')
    def test_connection_error(self, mock_fetcher_class):
        """Test handling of connection error."""
        # Set up mock to raise ConnectionError
        mock_fetcher = mock_fetcher_class.return_value
        mock_fetcher.fetch_posts.side_effect = ConnectionError("Failed to connect")
        
        # Create a mock for parse_arguments
        with patch('substack_to_md.parse_arguments') as mock_parse_args:
            # Set up the mock to return the desired arguments
            mock_args = argparse.Namespace(
                author='testauthor',
                output=self.temp_dir,
                limit=None,
                verbose=True
            )
            mock_parse_args.return_value = mock_args
            
            # Call the main function
            result = substack_to_md.main()
            
            # Assert that the main function returned error
            self.assertEqual(result, 1)

    def test_generate_filename(self):
        """Test filename generation for posts."""
        # Test with valid post data
        post = {
            'title': 'Test Post Title',
            'post_date': '2023-01-01T12:00:00Z'
        }
        filename = substack_to_md.generate_filename(post)
        self.assertEqual(filename, '2023-01-01_Test Post Title.md')
        
        # Test with invalid date
        post = {
            'title': 'Test Post Title',
            'post_date': 'invalid-date'
        }
        filename = substack_to_md.generate_filename(post)
        self.assertEqual(filename, 'Test Post Title.md')
        
        # Test with no date
        post = {
            'title': 'Test Post Title'
        }
        filename = substack_to_md.generate_filename(post)
        self.assertEqual(filename, 'Test Post Title.md')
        
        # Test with long title
        long_title = 'A' * 120
        post = {
            'title': long_title,
            'post_date': '2023-01-01T12:00:00Z'
        }
        filename = substack_to_md.generate_filename(post)
        self.assertTrue(len(filename) < 120)
        self.assertTrue(filename.endswith('....md'))

    def test_sanitize_filename(self):
        """Test sanitization of filenames."""
        # Test with invalid characters
        title = 'Test: File/Name*With?Invalid"Characters<>|'
        sanitized = substack_to_md.sanitize_filename(title)
        self.assertEqual(sanitized, 'Test_ File_Name_With_Invalid_Characters___')
        
        # Test with multiple spaces
        title = 'Test   Multiple    Spaces'
        sanitized = substack_to_md.sanitize_filename(title)
        self.assertEqual(sanitized, 'Test Multiple Spaces')


if __name__ == '__main__':
    unittest.main()
