#!/usr/bin/env python3
"""
Tests for the substack_api_cache module.
"""

import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.substack_api_cache import SubstackApiCache


class TestSubstackApiCache(unittest.TestCase):
    """Test cases for the SubstackApiCache class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for cache files
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a cache instance
        self.cache = SubstackApiCache(cache_dir=self.temp_dir)
        
        # Sample post data for testing
        self.post_data = {
            "id": "12345",
            "title": "Test Post",
            "slug": "test-post",
            "post_date": "2023-01-01T12:00:00Z",
            "author": {"name": "Test Author"}
        }
        
        # Sample comments for testing
        self.comments = [
            {
                "id": "comment1",
                "body": "Test comment",
                "author": "Test User",
                "date": "2023-01-02"
            }
        ]
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Close the cache
        self.cache.close()
        
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_init(self):
        """Test initialization."""
        # Check that the cache directory was created
        self.assertTrue(os.path.exists(self.temp_dir))
        
        # Check that the cache instance was created
        self.assertIsNotNone(self.cache.cache)
        
        # Check that the default TTL values were set
        self.assertEqual(self.cache.default_ttl["post"], 86400 * 7)  # 7 days
        self.assertEqual(self.cache.default_ttl["posts_list"], 3600)  # 1 hour
        self.assertEqual(self.cache.default_ttl["comments"], 3600 * 6)  # 6 hours
        self.assertEqual(self.cache.default_ttl["newsletter"], 86400)  # 1 day
        self.assertEqual(self.cache.default_ttl["author"], 86400 * 3)  # 3 days
        self.assertEqual(self.cache.default_ttl["default"], 3600)  # 1 hour
    
    def test_get_ttl(self):
        """Test getting TTL for different content types."""
        # Test with known content types
        self.assertEqual(self.cache._get_ttl("post"), 86400 * 7)
        self.assertEqual(self.cache._get_ttl("posts_list"), 3600)
        self.assertEqual(self.cache._get_ttl("comments"), 3600 * 6)
        self.assertEqual(self.cache._get_ttl("newsletter"), 86400)
        self.assertEqual(self.cache._get_ttl("author"), 86400 * 3)
        
        # Test with unknown content type
        self.assertEqual(self.cache._get_ttl("unknown"), 3600)
    
    def test_generate_keys(self):
        """Test generating cache keys."""
        # Test generating post key
        self.assertEqual(self.cache._generate_post_key("author", "slug"), "post:author:slug")
        
        # Test generating posts list key
        self.assertEqual(self.cache._generate_posts_list_key("author"), "posts_list:author:0")
        self.assertEqual(self.cache._generate_posts_list_key("author", 1), "posts_list:author:1")
        
        # Test generating comments key
        self.assertEqual(self.cache._generate_comments_key("post_id"), "comments:post_id")
        
        # Test generating newsletter key
        self.assertEqual(self.cache._generate_newsletter_key("author"), "newsletter:author")
        
        # Test generating author key
        self.assertEqual(self.cache._generate_author_key("author"), "author:author")
    
    def test_cache_post(self):
        """Test caching a post."""
        # Cache a post
        result = self.cache.cache_post("author", "slug", self.post_data)
        
        # Check the result
        self.assertTrue(result)
        
        # Get the cached post
        cached_post = self.cache.get_cached_post("author", "slug")
        
        # Check the cached post
        self.assertEqual(cached_post, self.post_data)
    
    def test_cache_post_by_url(self):
        """Test caching a post by URL."""
        # Cache a post by URL
        url = "https://author.substack.com/p/slug"
        result = self.cache.cache_post_by_url(url, self.post_data)
        
        # Check the result
        self.assertTrue(result)
        
        # Get the cached post by URL
        cached_post = self.cache.get_cached_post_by_url(url)
        
        # Check the cached post
        self.assertEqual(cached_post, self.post_data)
        
        # Also check that we can get it by author and slug
        cached_post = self.cache.get_cached_post("author", "slug")
        self.assertEqual(cached_post, self.post_data)
    
    def test_cache_posts_list(self):
        """Test caching a list of posts."""
        # Cache a posts list
        posts_list = [self.post_data]
        result = self.cache.cache_posts_list("author", posts_list)
        
        # Check the result
        self.assertTrue(result)
        
        # Get the cached posts list
        cached_posts = self.cache.get_cached_posts_list("author")
        
        # Check the cached posts list
        self.assertEqual(cached_posts, posts_list)
        
        # Also check that individual posts were cached
        cached_post = self.cache.get_cached_post("author", "test-post")
        self.assertEqual(cached_post, self.post_data)
    
    def test_cache_comments(self):
        """Test caching comments."""
        # Cache comments
        result = self.cache.cache_comments("post_id", self.comments)
        
        # Check the result
        self.assertTrue(result)
        
        # Get the cached comments
        cached_comments = self.cache.get_cached_comments("post_id")
        
        # Check the cached comments
        self.assertEqual(cached_comments, self.comments)
    
    def test_cache_comments_by_post_data(self):
        """Test caching comments using post data."""
        # Cache comments using post data
        result = self.cache.cache_comments_by_post_data(self.post_data, self.comments)
        
        # Check the result
        self.assertTrue(result)
        
        # Get the cached comments using post data
        cached_comments = self.cache.get_cached_comments_by_post_data(self.post_data)
        
        # Check the cached comments
        self.assertEqual(cached_comments, self.comments)
    
    def test_cache_newsletter(self):
        """Test caching newsletter metadata."""
        # Cache newsletter metadata
        newsletter_data = {
            "title": "Test Newsletter",
            "description": "A test newsletter",
            "author": "Test Author"
        }
        result = self.cache.cache_newsletter("author", newsletter_data)
        
        # Check the result
        self.assertTrue(result)
        
        # Get the cached newsletter metadata
        cached_newsletter = self.cache.get_cached_newsletter("author")
        
        # Check the cached newsletter metadata
        self.assertEqual(cached_newsletter, newsletter_data)
    
    def test_cache_author(self):
        """Test caching author information."""
        # Cache author information
        author_data = {
            "name": "Test Author",
            "bio": "A test author"
        }
        result = self.cache.cache_author("author", author_data)
        
        # Check the result
        self.assertTrue(result)
        
        # Get the cached author information
        cached_author = self.cache.get_cached_author("author")
        
        # Check the cached author information
        self.assertEqual(cached_author, author_data)
    
    def test_cache_api_response(self):
        """Test caching a generic API response."""
        # Cache an API response
        url = "https://api.example.com/endpoint"
        response_data = {"key": "value"}
        result = self.cache.cache_api_response(url, response_data)
        
        # Check the result
        self.assertTrue(result)
        
        # Get the cached API response
        cached_response = self.cache.get_cached_api_response(url)
        
        # Check the cached API response
        self.assertEqual(cached_response, response_data)
    
    def test_clear_post_cache(self):
        """Test clearing the cache for a specific post."""
        # Cache a post
        self.cache.cache_post("author", "slug", self.post_data)
        
        # Clear the cache for the post
        result = self.cache.clear_post_cache("author", "slug")
        
        # Check the result
        self.assertTrue(result)
        
        # Get the cached post
        cached_post = self.cache.get_cached_post("author", "slug")
        
        # Check that the post is either None or an empty dictionary (depending on cache implementation)
        self.assertTrue(cached_post is None or cached_post == {})
    
    def test_clear_all_cache(self):
        """Test clearing all cache entries."""
        # Cache a post
        self.cache.cache_post("author", "slug", self.post_data)
        
        # Cache comments
        self.cache.cache_comments("post_id", self.comments)
        
        # Clear all cache entries
        api_count, page_count = self.cache.clear_all_cache()
        
        # Check the result
        self.assertGreaterEqual(api_count, 1)
        
        # Get the cached post
        cached_post = self.cache.get_cached_post("author", "slug")
        
        # Check that the post is no longer in the cache
        self.assertIsNone(cached_post)
        
        # Get the cached comments
        cached_comments = self.cache.get_cached_comments("post_id")
        
        # Check that the comments are no longer in the cache
        self.assertIsNone(cached_comments)
    
    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        # Cache a post
        self.cache.cache_post("author", "slug", self.post_data)
        
        # Get cache statistics
        stats = self.cache.get_cache_stats()
        
        # Check the statistics
        self.assertIn("api_count", stats)
        self.assertIn("page_count", stats)
        self.assertIn("total_count", stats)
        self.assertIn("total_expired", stats)
        self.assertGreaterEqual(stats["api_count"], 1)
    
    def test_context_manager(self):
        """Test using the cache as a context manager."""
        # Create a cache using a context manager
        with SubstackApiCache(cache_dir=self.temp_dir) as cache:
            # Cache a post
            cache.cache_post("author", "slug", self.post_data)
            
            # Get the cached post
            cached_post = cache.get_cached_post("author", "slug")
            
            # Check the cached post
            self.assertEqual(cached_post, self.post_data)
        
        # Create a new cache to check if the previous one was closed properly
        cache = SubstackApiCache(cache_dir=self.temp_dir)
        
        # Get the cached post
        cached_post = cache.get_cached_post("author", "slug")
        
        # Check the cached post
        self.assertEqual(cached_post, self.post_data)
        
        # Close the cache
        cache.close()


if __name__ == '__main__':
    unittest.main()
