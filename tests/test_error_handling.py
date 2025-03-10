#!/usr/bin/env python3
"""
Tests for error handling in the Substack to Markdown CLI tool.

This module contains tests for how the CLI tool handles various error conditions,
such as API errors, file system errors, and conversion errors.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import tempfile
import shutil
import argparse
import requests

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core import substack_to_md
from src.core.substack_fetcher import SubstackFetcher
from src.utils.markdown_converter import MarkdownConverter


class TestErrorHandling(unittest.TestCase):
    """Tests for error handling in the Substack to Markdown CLI tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for output files
        self.temp_dir = tempfile.mkdtemp()
        
        # Sample post data for testing
        self.sample_post = {
            'id': 1,
            'title': 'Test Post',
            'body_html': '<p>Test content</p>'
        }

    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary directory and its contents
        shutil.rmtree(self.temp_dir)

    @patch('src.core.substack_fetcher.Substack')
    def test_api_404_error(self, mock_substack):
        """Test handling of 404 API errors."""
        # Set up mock to raise 404 error
        mock_client = mock_substack.return_value
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_error = requests.exceptions.HTTPError(response=mock_response)
        mock_client.get_posts.side_effect = mock_error
        
        # Create a fetcher and call the method
        fetcher = SubstackFetcher(max_retries=1, retry_delay=0.01)
        
        # Assert that it raises ValueError
        with self.assertRaises(ValueError):
            fetcher.fetch_posts('invalidauthor')

    @patch('src.core.substack_fetcher.Substack')
    @patch('src.core.substack_fetcher.time.sleep')
    def test_api_rate_limit(self, mock_sleep, mock_substack):
        """Test handling of rate limiting."""
        # Set up mock to raise 429 error then succeed
        mock_client = mock_substack.return_value
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_error = requests.exceptions.HTTPError(response=mock_response)
        mock_client.get_posts.side_effect = [mock_error, [self.sample_post]]
        
        # Create a fetcher and call the method
        fetcher = SubstackFetcher(max_retries=2, retry_delay=0.01)
        posts = fetcher.fetch_posts('testauthor', verbose=True)
        
        # Assert that it retried and succeeded
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]['id'], 1)
        
        # Assert that sleep was called for rate limiting
        mock_sleep.assert_called_once()

    @patch('src.core.substack_fetcher.Substack')
    @patch('src.core.substack_fetcher.time.sleep')
    def test_api_connection_error(self, mock_sleep, mock_substack):
        """Test handling of connection errors."""
        # Set up mock to raise connection error then succeed
        mock_client = mock_substack.return_value
        mock_client.get_posts.side_effect = [
            requests.exceptions.ConnectionError("Connection error"),
            [self.sample_post]
        ]
        
        # Create a fetcher and call the method
        fetcher = SubstackFetcher(max_retries=2, retry_delay=0.01)
        posts = fetcher.fetch_posts('testauthor', verbose=True)
        
        # Assert that it retried and succeeded
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]['id'], 1)
        
        # Assert that sleep was called for retry
        mock_sleep.assert_called_once()

    @patch('src.core.substack_fetcher.Substack')
    @patch('src.core.substack_fetcher.time.sleep')
    def test_api_max_retries_exceeded(self, mock_sleep, mock_substack):
        """Test handling when max retries are exceeded."""
        # Set up mock to always raise connection error
        mock_client = mock_substack.return_value
        mock_client.get_posts.side_effect = requests.exceptions.ConnectionError("Connection error")
        
        # Create a fetcher and call the method
        fetcher = SubstackFetcher(max_retries=2, retry_delay=0.01)
        
        # Assert that it raises ConnectionError
        with self.assertRaises(ConnectionError):
            fetcher.fetch_posts('testauthor', verbose=True)
        
        # Assert that sleep was called for each retry
        self.assertEqual(mock_sleep.call_count, 2)

    def test_markdown_conversion_empty_html(self):
        """Test handling of empty HTML during conversion."""
        # Create a converter and call the method with empty HTML
        converter = MarkdownConverter()
        result = converter.convert_html_to_markdown("", verbose=True)
        
        # Assert that it returns None
        self.assertIsNone(result)

    @patch('src.utils.markdown_converter.md')
    def test_markdown_conversion_exception(self, mock_md):
        """Test handling of exceptions during conversion."""
        # Set up mock to raise an exception
        mock_md.side_effect = Exception("Conversion error")
        
        # Create a converter and call the method
        converter = MarkdownConverter()
        result = converter.convert_html_to_markdown("<p>Test</p>", verbose=True)
        
        # Assert that it returns None
        self.assertIsNone(result)

    @patch('src.core.substack_to_md.open', new_callable=mock_open)
    def test_file_system_error(self, mock_file):
        """Test handling of file system errors."""
        # Set up mock to raise an OSError
        mock_file.side_effect = OSError("File system error")
        
        # Call the method
        result = substack_to_md.save_markdown_to_file(
            "Test content",
            "test.md",
            self.temp_dir,
            verbose=True
        )
        
        # Assert that it returns False
        self.assertFalse(result)

    @patch('os.makedirs')
    def test_directory_creation_error(self, mock_makedirs):
        """Test handling of directory creation errors."""
        # Set up mock to raise an OSError
        mock_makedirs.side_effect = OSError("Directory creation error")
        
        # Call the method
        result = substack_to_md.save_markdown_to_file(
            "Test content",
            "test.md",
            "/nonexistent/directory",
            verbose=True
        )
        
        # Assert that it returns False
        self.assertFalse(result)

    @patch('src.core.substack_to_md.SubstackFetcher')
    @patch('src.core.substack_to_md.MarkdownConverter')
    def test_process_posts_empty(self, mock_converter_class, mock_fetcher_class):
        """Test processing of empty post list."""
        # Call the method with empty list
        result = substack_to_md.process_posts([], self.temp_dir, verbose=True)
        
        # Assert that it returns 0
        self.assertEqual(result, 0)

    @patch('src.core.substack_to_md.SubstackFetcher')
    @patch('src.core.substack_to_md.MarkdownConverter')
    def test_process_posts_no_html(self, mock_converter_class, mock_fetcher_class):
        """Test processing of posts with no HTML content."""
        # Create a post with no HTML content
        post = {
            'title': 'Test Post',
            'body_html': None
        }
        
        # Call the method
        result = substack_to_md.process_posts([post], self.temp_dir, verbose=True)
        
        # Assert that it returns 0
        self.assertEqual(result, 0)

    @patch('src.core.substack_to_md.MarkdownConverter')
    def test_process_posts_conversion_failure(self, mock_converter_class):
        """Test processing of posts when conversion fails."""
        # Set up mock to return None for conversion
        mock_converter = mock_converter_class.return_value
        mock_converter.convert_html_to_markdown.return_value = None
        
        # Create a post with HTML content
        post = {
            'title': 'Test Post',
            'body_html': '<p>Test content</p>'
        }
        
        # Call the method
        result = substack_to_md.process_posts([post], self.temp_dir, verbose=True)
        
        # Assert that it returns 0
        self.assertEqual(result, 0)

    @patch('src.core.substack_to_md.save_markdown_to_file')
    @patch('src.core.substack_to_md.MarkdownConverter')
    def test_process_posts_save_failure(self, mock_converter_class, mock_save):
        """Test processing of posts when saving fails."""
        # Set up mocks
        mock_converter = mock_converter_class.return_value
        mock_converter.convert_html_to_markdown.return_value = "Test markdown"
        mock_save.return_value = False
        
        # Create a post with HTML content
        post = {
            'title': 'Test Post',
            'body_html': '<p>Test content</p>'
        }
        
        # Call the method
        result = substack_to_md.process_posts([post], self.temp_dir, verbose=True)
        
        # Assert that it returns 0
        self.assertEqual(result, 0)

    @patch('src.core.substack_to_md.parse_arguments')
    def test_keyboard_interrupt(self, mock_parse_args):
        """Test handling of keyboard interrupt."""
        # Set up mock to raise KeyboardInterrupt
        mock_parse_args.side_effect = KeyboardInterrupt()
        
        # Call the main function
        result = substack_to_md.main()
        
        # Assert that it returns 130 (standard exit code for SIGINT)
        self.assertEqual(result, 130)

    @patch('src.core.substack_to_md.parse_arguments')
    def test_unexpected_exception(self, mock_parse_args):
        """Test handling of unexpected exceptions."""
        # Set up mock to raise an unexpected exception
        mock_parse_args.side_effect = Exception("Unexpected error")
        
        # Call the main function
        result = substack_to_md.main()
        
        # Assert that it returns 1 (error)
        self.assertEqual(result, 1)


if __name__ == '__main__':
    unittest.main()
