#!/usr/bin/env python3
"""
Tests for the cache_manager module.
"""

import os
import time
import unittest
import tempfile
import hashlib
from unittest.mock import patch, MagicMock

from src.utils.cache_manager import CacheManager


class TestCacheManager(unittest.TestCase):
    """Test cases for the CacheManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_cache.db")
        
        # Create the cache manager
        self.cache_manager = CacheManager(
            db_path=self.db_path,
            default_ttl=3600  # 1 hour
        )
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Close the database connection
        self.cache_manager.close()
        
        # Remove the temporary database file
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        # Remove the temporary directory
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.cache_manager.db_path, self.db_path)
        self.assertEqual(self.cache_manager.default_ttl, 3600)
        self.assertIsNotNone(self.cache_manager.conn)
    
    def test_generate_key(self):
        """Test generating cache keys."""
        # Test with a simple URL
        url = "https://example.com"
        key = self.cache_manager._generate_key(url)
        expected_key = hashlib.sha256(url.encode()).hexdigest()
        self.assertEqual(key, expected_key)
        
        # Test with a URL with query parameters
        url = "https://example.com?param1=value1&param2=value2"
        key = self.cache_manager._generate_key(url)
        expected_key = hashlib.sha256(url.encode()).hexdigest()
        self.assertEqual(key, expected_key)
    
    def test_set_get_api_cache(self):
        """Test setting and getting API cache entries."""
        # Set a cache entry
        url = "https://example.com/api"
        data = {"key": "value"}
        self.cache_manager.set_api_cache(url, data)
        
        # Get the cache entry
        cached_data = self.cache_manager.get_api_cache(url)
        self.assertEqual(cached_data, data)
        
        # Get a non-existent cache entry
        cached_data = self.cache_manager.get_api_cache("https://example.com/nonexistent")
        self.assertIsNone(cached_data)
    
    def test_set_get_page_cache(self):
        """Test setting and getting page cache entries."""
        # Set a cache entry
        url = "https://example.com/page"
        html = "<html><body>Test page</body></html>"
        self.cache_manager.set_page_cache(url, html)
        
        # Get the cache entry
        cached_html = self.cache_manager.get_page_cache(url)
        self.assertEqual(cached_html, html)
        
        # Get a non-existent cache entry
        cached_html = self.cache_manager.get_page_cache("https://example.com/nonexistent")
        self.assertIsNone(cached_html)
    
    def test_cache_expiration(self):
        """Test cache entry expiration."""
        # Create a cache manager with a short TTL
        cache_manager = CacheManager(
            db_path=self.db_path,
            default_ttl=1  # 1 second
        )
        
        # Set a cache entry
        url = "https://example.com/api"
        data = {"key": "value"}
        cache_manager.set_api_cache(url, data)
        
        # Get the cache entry immediately
        cached_data = cache_manager.get_api_cache(url)
        self.assertEqual(cached_data, data)
        
        # Wait for the cache entry to expire
        time.sleep(2)
        
        # Get the cache entry after expiration
        cached_data = cache_manager.get_api_cache(url)
        self.assertIsNone(cached_data)
        
        # Close the cache manager
        cache_manager.close()
    
    def test_clear_api_cache(self):
        """Test clearing API cache entries."""
        # Set some cache entries
        self.cache_manager.set_api_cache("https://example.com/api1", {"key1": "value1"})
        self.cache_manager.set_api_cache("https://example.com/api2", {"key2": "value2"})
        
        # Clear the API cache
        cleared = self.cache_manager.clear_api_cache()
        self.assertEqual(cleared, 2)
        
        # Check that the cache entries are gone
        self.assertIsNone(self.cache_manager.get_api_cache("https://example.com/api1"))
        self.assertIsNone(self.cache_manager.get_api_cache("https://example.com/api2"))
    
    def test_clear_page_cache(self):
        """Test clearing page cache entries."""
        # Set some cache entries
        self.cache_manager.set_page_cache("https://example.com/page1", "<html>Page 1</html>")
        self.cache_manager.set_page_cache("https://example.com/page2", "<html>Page 2</html>")
        
        # Clear the page cache
        cleared = self.cache_manager.clear_page_cache()
        self.assertEqual(cleared, 2)
        
        # Check that the cache entries are gone
        self.assertIsNone(self.cache_manager.get_page_cache("https://example.com/page1"))
        self.assertIsNone(self.cache_manager.get_page_cache("https://example.com/page2"))
    
    def test_clear_all_cache(self):
        """Test clearing all cache entries."""
        # Set some cache entries
        self.cache_manager.set_api_cache("https://example.com/api", {"key": "value"})
        self.cache_manager.set_page_cache("https://example.com/page", "<html>Page</html>")
        
        # Clear all cache
        api_cleared, page_cleared = self.cache_manager.clear_all_cache()
        self.assertEqual(api_cleared, 1)
        self.assertEqual(page_cleared, 1)
        
        # Check that the cache entries are gone
        self.assertIsNone(self.cache_manager.get_api_cache("https://example.com/api"))
        self.assertIsNone(self.cache_manager.get_page_cache("https://example.com/page"))
    
    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        # Set some cache entries
        self.cache_manager.set_api_cache("https://example.com/api1", {"key1": "value1"})
        self.cache_manager.set_api_cache("https://example.com/api2", {"key2": "value2"})
        self.cache_manager.set_page_cache("https://example.com/page1", "<html>Page 1</html>")
        
        # Get cache stats
        stats = self.cache_manager.get_cache_stats()
        self.assertEqual(stats["api_count"], 2)
        self.assertEqual(stats["page_count"], 1)
        self.assertEqual(stats["total_count"], 3)
        self.assertEqual(stats["total_expired"], 0)
    
    def test_context_manager(self):
        """Test using the cache manager as a context manager."""
        # Create a cache manager using a context manager
        with CacheManager(db_path=self.db_path) as cache_manager:
            # Set a cache entry
            cache_manager.set_api_cache("https://example.com/api", {"key": "value"})
            
            # Get the cache entry
            cached_data = cache_manager.get_api_cache("https://example.com/api")
            self.assertEqual(cached_data, {"key": "value"})
        
        # The connection should be closed after the context manager exits
        self.assertIsNone(cache_manager.conn)


if __name__ == '__main__':
    unittest.main()
