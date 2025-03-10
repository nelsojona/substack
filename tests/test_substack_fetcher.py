#!/usr/bin/env python3
"""
Unit tests for the SubstackFetcher class.

This module contains tests for the SubstackFetcher class, which is responsible
for fetching posts from the Substack API.
"""

import unittest
from unittest.mock import patch, MagicMock
import requests

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.substack_fetcher import SubstackFetcher


class TestSubstackFetcher(unittest.TestCase):
    """Test cases for the SubstackFetcher class."""

    def setUp(self):
        """Set up test fixtures."""
        self.fetcher = SubstackFetcher(max_retries=2, retry_delay=0.01)
        
        # Sample post data for testing
        self.sample_posts = [
            {
                'id': 1,
                'title': 'Test Post 1',
                'body_html': '<p>Test content 1</p>',
                'post_date': '2023-01-01T12:00:00Z'
            },
            {
                'id': 2,
                'title': 'Test Post 2',
                'body_html': '<p>Test content 2</p>',
                'post_date': '2023-01-02T12:00:00Z'
            }
        ]

    @patch('src.core.substack_fetcher.Substack')
    def test_init(self, mock_substack):
        """Test initialization of SubstackFetcher."""
        fetcher = SubstackFetcher(max_retries=5, retry_delay=3)
        
        # Assert that Substack client was initialized
        mock_substack.assert_called_once()
        
        # Assert that attributes were set correctly
        self.assertEqual(fetcher.max_retries, 5)
        self.assertEqual(fetcher.retry_delay, 3)

    @patch('src.core.substack_fetcher.SubstackFetcher._fetch_with_retry')
    def test_fetch_posts_success(self, mock_fetch_with_retry):
        """Test successful fetching of posts."""
        # Set up mock to return all posts at once
        mock_fetch_with_retry.side_effect = [
            self.sample_posts,  # All posts in one response
            []  # Empty page to indicate end of posts
        ]
        
        # Call the method
        posts = self.fetcher.fetch_posts('testauthor', verbose=True)
        
        # Assert results
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0]['id'], 1)
        self.assertEqual(posts[1]['id'], 2)
        
        # Assert that _fetch_with_retry was called correctly
        self.assertEqual(mock_fetch_with_retry.call_count, 1)
        mock_fetch_with_retry.assert_called_once_with('testauthor', 0, True)

    @patch('src.core.substack_fetcher.SubstackFetcher._fetch_with_retry')
    def test_fetch_posts_with_limit(self, mock_fetch_with_retry):
        """Test fetching posts with a limit."""
        # Set up mock
        mock_fetch_with_retry.return_value = self.sample_posts
        
        # Call the method with limit=1
        posts = self.fetcher.fetch_posts('testauthor', limit=1, verbose=True)
        
        # Assert results
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]['id'], 1)
        
        # Assert that _fetch_with_retry was called correctly
        mock_fetch_with_retry.assert_called_once_with('testauthor', 0, True)

    @patch('src.core.substack_fetcher.SubstackFetcher._fetch_with_retry')
    def test_fetch_posts_empty(self, mock_fetch_with_retry):
        """Test fetching posts when no posts are available."""
        # Set up mock
        mock_fetch_with_retry.return_value = []
        
        # Call the method
        posts = self.fetcher.fetch_posts('testauthor')
        
        # Assert results
        self.assertEqual(len(posts), 0)
        
        # Assert that _fetch_with_retry was called correctly
        mock_fetch_with_retry.assert_called_once_with('testauthor', 0, False)

    @patch('src.core.substack_fetcher.SubstackFetcher._fetch_with_retry')
    def test_fetch_posts_invalid_author(self, mock_fetch_with_retry):
        """Test fetching posts with an invalid author."""
        # Set up mock to raise ValueError
        mock_fetch_with_retry.side_effect = ValueError("Invalid author identifier")
        
        # Call the method and assert it raises ValueError
        with self.assertRaises(ValueError):
            self.fetcher.fetch_posts('invalidauthor')
        
        # Assert that _fetch_with_retry was called correctly
        mock_fetch_with_retry.assert_called_once_with('invalidauthor', 0, False)

    @patch('src.core.substack_fetcher.SubstackFetcher._fetch_with_retry')
    def test_fetch_posts_rate_limit(self, mock_fetch_with_retry):
        """Test handling of rate limiting."""
        # Set up mock to simulate rate limiting then success
        mock_fetch_with_retry.side_effect = [
            self.sample_posts  # Successful response after handling rate limit internally
        ]
        
        # Call the method
        posts = self.fetcher.fetch_posts('testauthor', verbose=True)
        
        # Assert results
        self.assertEqual(len(posts), 2)
        
        # Assert that _fetch_with_retry was called correctly
        mock_fetch_with_retry.assert_called_once_with('testauthor', 0, True)

    @patch('src.core.substack_fetcher.SubstackFetcher._fetch_with_retry')
    def test_fetch_posts_connection_error(self, mock_fetch_with_retry):
        """Test handling of connection errors."""
        # Set up mock to simulate connection error handling
        mock_fetch_with_retry.side_effect = [
            self.sample_posts  # Successful response after handling connection error internally
        ]
        
        # Call the method
        posts = self.fetcher.fetch_posts('testauthor', verbose=True)
        
        # Assert results
        self.assertEqual(len(posts), 2)
        
        # Assert that _fetch_with_retry was called correctly
        mock_fetch_with_retry.assert_called_once_with('testauthor', 0, True)

    @patch('src.core.substack_fetcher.SubstackFetcher._fetch_with_retry')
    def test_fetch_posts_max_retries_exceeded(self, mock_fetch_with_retry):
        """Test handling when max retries are exceeded."""
        # Set up mock to raise ConnectionError after max retries
        mock_fetch_with_retry.side_effect = ConnectionError("Failed after max retries")
        
        # Call the method and assert it raises ConnectionError
        with self.assertRaises(ConnectionError):
            self.fetcher.fetch_posts('testauthor', verbose=True)
        
        # Assert that _fetch_with_retry was called correctly
        mock_fetch_with_retry.assert_called_once_with('testauthor', 0, True)


if __name__ == '__main__':
    unittest.main()
