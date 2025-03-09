#!/usr/bin/env python3
"""
CLI tests for the Substack to Markdown CLI tool.

This module contains tests for the command-line interface functionality,
testing argument parsing, options, flags, and error handling.
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


class TestCLI(unittest.TestCase):
    """Test cases for the command-line interface."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for output files
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary directory and its contents
        shutil.rmtree(self.temp_dir)

    def test_parse_arguments_required(self):
        """Test parsing of required arguments."""
        # Test with required arguments
        with patch('sys.argv', ['substack_to_md.py', '--author', 'testauthor', '--output', self.temp_dir]):
            args = substack_to_md.parse_arguments(use_env_defaults=False)
            self.assertEqual(args.author, 'testauthor')
            self.assertEqual(args.output, self.temp_dir)
            self.assertIsNone(args.limit)
            self.assertFalse(args.verbose)

    def test_parse_arguments_optional(self):
        """Test parsing of optional arguments."""
        # Test with optional arguments
        with patch('sys.argv', [
            'substack_to_md.py', '--author', 'testauthor',
            '--output', self.temp_dir,
            '--limit', '5',
            '--verbose'
        ]):
            args = substack_to_md.parse_arguments(use_env_defaults=False)
            self.assertEqual(args.author, 'testauthor')
            self.assertEqual(args.output, self.temp_dir)
            self.assertEqual(args.limit, 5)
            self.assertTrue(args.verbose)

    def test_parse_arguments_authentication(self):
        """Test parsing of authentication arguments."""
        # Test with email/password authentication
        with patch('sys.argv', [
            'substack_to_md.py', '--author', 'testauthor',
            '--output', self.temp_dir,
            '--email', 'test@example.com',
            '--password', 'password123',
            '--private'
        ]):
            args = substack_to_md.parse_arguments(use_env_defaults=False)
            self.assertEqual(args.email, 'test@example.com')
            self.assertEqual(args.password, 'password123')
            self.assertTrue(args.private)
            self.assertIsNone(args.token)
            self.assertIsNone(args.cookies_file)

        # Test with token authentication
        with patch('sys.argv', [
            'substack_to_md.py', '--author', 'testauthor',
            '--output', self.temp_dir,
            '--token', 'abc123',
            '--private'
        ]):
            args = substack_to_md.parse_arguments(use_env_defaults=False)
            self.assertEqual(args.token, 'abc123')
            self.assertTrue(args.private)
            self.assertIsNone(args.email)
            self.assertIsNone(args.password)
            self.assertIsNone(args.cookies_file)

        # Test with cookies file authentication
        with patch('sys.argv', [
            'substack_to_md.py', '--author', 'testauthor',
            '--output', self.temp_dir,
            '--cookies-file', 'cookies.json',
            '--private'
        ]):
            args = substack_to_md.parse_arguments(use_env_defaults=False)
            self.assertEqual(args.cookies_file, 'cookies.json')
            self.assertTrue(args.private)
            self.assertIsNone(args.email)
            self.assertIsNone(args.password)
            self.assertIsNone(args.token)

    def test_parse_arguments_image_options(self):
        """Test parsing of image-related arguments."""
        # Test with image download options
        with patch('sys.argv', [
            'substack_to_md.py', '--author', 'testauthor',
            '--output', self.temp_dir,
            '--download-images',
            '--image-dir', 'custom-images',
            '--image-base-url', 'https://example.com/images/',
            '--max-image-workers', '8',
            '--image-timeout', '20'
        ]):
            args = substack_to_md.parse_arguments(use_env_defaults=False)
            self.assertTrue(args.download_images)
            self.assertEqual(args.image_dir, 'custom-images')
            self.assertEqual(args.image_base_url, 'https://example.com/images/')
            self.assertEqual(args.max_image_workers, 8)
            self.assertEqual(args.image_timeout, 20)

    def test_parse_arguments_url_slug(self):
        """Test parsing of URL and slug arguments."""
        # Test with URL
        with patch('sys.argv', [
            'substack_to_md.py', '--author', 'testauthor',
            '--output', self.temp_dir,
            '--url', 'https://example.substack.com/p/test-post'
        ]):
            args = substack_to_md.parse_arguments(use_env_defaults=False)
            self.assertEqual(args.url, 'https://example.substack.com/p/test-post')
            self.assertIsNone(args.slug)

        # Test with slug
        with patch('sys.argv', [
            'substack_to_md.py', '--author', 'testauthor',
            '--output', self.temp_dir,
            '--slug', 'test-post'
        ]):
            args = substack_to_md.parse_arguments(use_env_defaults=False)
            self.assertEqual(args.slug, 'test-post')
            self.assertIsNone(args.url)

    @patch('substack_to_md.SubstackFetcher')
    @patch('substack_to_md.MarkdownConverter')
    def test_main_exit_codes(self, mock_converter_class, mock_fetcher_class):
        """Test exit codes for different scenarios."""
        # Set up mocks
        mock_fetcher = mock_fetcher_class.return_value
        mock_converter = mock_converter_class.return_value

        # Test successful execution
        mock_fetcher.fetch_posts.return_value = [
            {
                'id': 1,
                'title': 'Test Post',
                'post_date': '2023-01-01T12:00:00Z',
                'body_html': '<p>Test content</p>'
            }
        ]
        mock_converter.convert_html_to_markdown.return_value = "# Test Post\n\nTest content"

        with patch('sys.argv', ['substack_to_md.py', '--author', 'testauthor', '--output', self.temp_dir]):
            exit_code = substack_to_md.main()
            self.assertEqual(exit_code, 0)

        # Test no posts found
        mock_fetcher.fetch_posts.return_value = []

        with patch('sys.argv', ['substack_to_md.py', '--author', 'testauthor', '--output', self.temp_dir]):
            exit_code = substack_to_md.main()
            self.assertEqual(exit_code, 1)

        # Test error during fetching
        mock_fetcher.fetch_posts.side_effect = ValueError("Invalid author")

        with patch('sys.argv', ['substack_to_md.py', '--author', 'testauthor', '--output', self.temp_dir]):
            exit_code = substack_to_md.main()
            self.assertEqual(exit_code, 1)

        # Test connection error
        mock_fetcher.fetch_posts.side_effect = ConnectionError("Network error")

        with patch('sys.argv', ['substack_to_md.py', '--author', 'testauthor', '--output', self.temp_dir]):
            exit_code = substack_to_md.main()
            self.assertEqual(exit_code, 1)

    @patch('substack_to_md.SubstackFetcher')
    @patch('substack_to_md.MarkdownConverter')
    def test_output_directory_creation(self, mock_converter_class, mock_fetcher_class):
        """Test creation of output directory if it doesn't exist."""
        # Set up mocks
        mock_fetcher = mock_fetcher_class.return_value
        mock_converter = mock_converter_class.return_value

        # Set up test data
        mock_fetcher.fetch_posts.return_value = [
            {
                'id': 1,
                'title': 'Test Post',
                'post_date': '2023-01-01T12:00:00Z',
                'body_html': '<p>Test content</p>'
            }
        ]
        mock_converter.convert_html_to_markdown.return_value = "# Test Post\n\nTest content"

        # Create a nested output directory path that doesn't exist
        nested_dir = os.path.join(self.temp_dir, 'nested', 'output', 'dir')

        # Test with non-existent output directory
        with patch('sys.argv', ['substack_to_md.py', '--author', 'testauthor', '--output', nested_dir]):
            exit_code = substack_to_md.main()
            self.assertEqual(exit_code, 0)
            self.assertTrue(os.path.exists(nested_dir))

    @patch('substack_to_md.SubstackFetcher')
    @patch('substack_to_md.MarkdownConverter')
    def test_limit_parameter(self, mock_converter_class, mock_fetcher_class):
        """Test the limit parameter for fetching posts."""
        # Set up mocks
        mock_fetcher = mock_fetcher_class.return_value
        mock_converter = mock_converter_class.return_value

        # Set up test data - Return only one post when limit is applied
        mock_fetcher.fetch_posts.return_value = [
            {
                'id': 1,
                'title': 'Test Post 1',
                'post_date': '2023-01-01T12:00:00Z',
                'body_html': '<p>Test content 1</p>'
            }
        ]
        mock_converter.convert_html_to_markdown.return_value = "# Test Post\n\nTest content"

        # Test with limit parameter
        with patch('sys.argv', [
            'substack_to_md.py', '--author', 'testauthor',
            '--output', self.temp_dir,
            '--limit', '1'
        ]):
            exit_code = substack_to_md.main()
            self.assertEqual(exit_code, 0)
            
            # Verify that fetch_posts was called with the limit parameter
            mock_fetcher.fetch_posts.assert_called_once_with('testauthor', 1, False)
            
            # Check that only one file was created
            files = os.listdir(self.temp_dir)
            self.assertEqual(len(files), 1)

    @patch('substack_to_md.SubstackFetcher')
    @patch('substack_to_md.MarkdownConverter')
    def test_verbose_output(self, mock_converter_class, mock_fetcher_class):
        """Test verbose output mode."""
        # Set up mocks
        mock_fetcher = mock_fetcher_class.return_value
        mock_converter = mock_converter_class.return_value

        # Set up test data
        mock_fetcher.fetch_posts.return_value = [
            {
                'id': 1,
                'title': 'Test Post',
                'post_date': '2023-01-01T12:00:00Z',
                'body_html': '<p>Test content</p>'
            }
        ]
        mock_converter.convert_html_to_markdown.return_value = "# Test Post\n\nTest content"

        # Test with verbose flag
        with patch('sys.argv', [
            'substack_to_md.py', '--author', 'testauthor',
            '--output', self.temp_dir,
            '--verbose'
        ]):
            with patch('builtins.print') as mock_print:
                exit_code = substack_to_md.main()
                self.assertEqual(exit_code, 0)
                
                # Check that verbose output was printed
                mock_print.assert_called()


if __name__ == '__main__':
    unittest.main()
