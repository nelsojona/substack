#!/usr/bin/env python3
"""
Substack API Cache Module

This module extends the CacheManager to provide specialized caching functionality
for Substack API responses. It implements efficient caching for different types
of API responses with appropriate TTL settings and indexing.
"""

import os
import json
import time
import logging
import hashlib
from typing import Dict, List, Any, Optional, Union, Tuple

# Import the base CacheManager
from src.utils.cache_manager import CacheManager

# Import utility functions
from src.utils.substack_api_utils import (
    extract_author_from_url,
    extract_slug_from_url,
    extract_post_id_from_api_response
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default TTL values for different types of content (in seconds)
DEFAULT_TTL = {
    "post": 86400 * 7,  # 7 days for posts (rarely change)
    "posts_list": 3600,  # 1 hour for post lists (may update frequently)
    "comments": 3600 * 6,  # 6 hours for comments (moderate update frequency)
    "newsletter": 86400,  # 1 day for newsletter metadata
    "author": 86400 * 3,  # 3 days for author information
    "default": 3600  # 1 hour default
}


class SubstackApiCache:
    """
    A specialized cache for Substack API responses.
    
    This class extends the functionality of CacheManager to provide
    Substack-specific caching with appropriate TTL values and indexing.
    
    Attributes:
        cache (CacheManager): The underlying cache manager.
        cache_dir (str): Directory for cache files.
        default_ttl (Dict[str, int]): Default TTL values for different content types.
    """
    
    def __init__(
        self,
        cache_dir: str = "cache",
        db_path: Optional[str] = None,
        default_ttl: Optional[Dict[str, int]] = None
    ):
        """
        Initialize the SubstackApiCache.
        
        Args:
            cache_dir (str, optional): Directory for cache files. Defaults to "cache".
            db_path (Optional[str], optional): Path to the SQLite database file.
                                             Defaults to None (uses cache_dir/api_cache.db).
            default_ttl (Optional[Dict[str, int]], optional): Default TTL values.
                                                           Defaults to None (uses DEFAULT_TTL).
        """
        # Create cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
        
        # Set up the database path
        if db_path is None:
            db_path = os.path.join(cache_dir, "api_cache.db")
        
        # Initialize the cache manager
        self.cache = CacheManager(db_path=db_path)
        
        # Set default TTL values
        self.default_ttl = default_ttl or DEFAULT_TTL
        self.cache_dir = cache_dir
    
    def close(self):
        """Close the cache."""
        self.cache.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def _get_ttl(self, content_type: str) -> int:
        """
        Get the TTL for a specific content type.
        
        Args:
            content_type (str): The content type.
        
        Returns:
            int: The TTL in seconds.
        """
        return self.default_ttl.get(content_type, self.default_ttl["default"])
    
    def _generate_post_key(self, author: str, slug: str) -> str:
        """
        Generate a cache key for a post.
        
        Args:
            author (str): The author identifier.
            slug (str): The post slug.
        
        Returns:
            str: The cache key.
        """
        return f"post:{author}:{slug}"
    
    def _generate_posts_list_key(self, author: str, page: int = 0) -> str:
        """
        Generate a cache key for a posts list.
        
        Args:
            author (str): The author identifier.
            page (int, optional): The page number. Defaults to 0.
        
        Returns:
            str: The cache key.
        """
        return f"posts_list:{author}:{page}"
    
    def _generate_comments_key(self, post_id: str) -> str:
        """
        Generate a cache key for comments.
        
        Args:
            post_id (str): The post ID.
        
        Returns:
            str: The cache key.
        """
        return f"comments:{post_id}"
    
    def _generate_newsletter_key(self, author: str) -> str:
        """
        Generate a cache key for newsletter metadata.
        
        Args:
            author (str): The author identifier.
        
        Returns:
            str: The cache key.
        """
        return f"newsletter:{author}"
    
    def _generate_author_key(self, author: str) -> str:
        """
        Generate a cache key for author information.
        
        Args:
            author (str): The author identifier.
        
        Returns:
            str: The cache key.
        """
        return f"author:{author}"
    
    def cache_post(self, author: str, slug: str, post_data: Dict[str, Any]) -> bool:
        """
        Cache a post.
        
        Args:
            author (str): The author identifier.
            slug (str): The post slug.
            post_data (Dict[str, Any]): The post data.
        
        Returns:
            bool: True if the post was cached successfully, False otherwise.
        """
        key = self._generate_post_key(author, slug)
        ttl = self._get_ttl("post")
        return self.cache.set_api_cache(key, post_data, ttl)
    
    def get_cached_post(self, author: str, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get a cached post.
        
        Args:
            author (str): The author identifier.
            slug (str): The post slug.
        
        Returns:
            Optional[Dict[str, Any]]: The cached post data, or None if not found.
        """
        key = self._generate_post_key(author, slug)
        return self.cache.get_api_cache(key)
    
    def cache_post_by_url(self, url: str, post_data: Dict[str, Any]) -> bool:
        """
        Cache a post by URL.
        
        Args:
            url (str): The post URL.
            post_data (Dict[str, Any]): The post data.
        
        Returns:
            bool: True if the post was cached successfully, False otherwise.
        """
        author = extract_author_from_url(url)
        slug = extract_slug_from_url(url)
        
        if author and slug:
            return self.cache_post(author, slug, post_data)
        
        # If we couldn't extract author and slug, use the URL as the key
        ttl = self._get_ttl("post")
        return self.cache.set_api_cache(url, post_data, ttl)
    
    def get_cached_post_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get a cached post by URL.
        
        Args:
            url (str): The post URL.
        
        Returns:
            Optional[Dict[str, Any]]: The cached post data, or None if not found.
        """
        author = extract_author_from_url(url)
        slug = extract_slug_from_url(url)
        
        if author and slug:
            return self.get_cached_post(author, slug)
        
        # If we couldn't extract author and slug, use the URL as the key
        return self.cache.get_api_cache(url)
    
    def cache_posts_list(self, author: str, posts_list: List[Dict[str, Any]], page: int = 0) -> bool:
        """
        Cache a list of posts.
        
        Args:
            author (str): The author identifier.
            posts_list (List[Dict[str, Any]]): The list of posts.
            page (int, optional): The page number. Defaults to 0.
        
        Returns:
            bool: True if the posts list was cached successfully, False otherwise.
        """
        key = self._generate_posts_list_key(author, page)
        ttl = self._get_ttl("posts_list")
        
        # Also cache individual posts with longer TTL
        for post in posts_list:
            if "slug" in post:
                self.cache_post(author, post["slug"], post)
        
        return self.cache.set_api_cache(key, posts_list, ttl)
    
    def get_cached_posts_list(self, author: str, page: int = 0) -> Optional[List[Dict[str, Any]]]:
        """
        Get a cached list of posts.
        
        Args:
            author (str): The author identifier.
            page (int, optional): The page number. Defaults to 0.
        
        Returns:
            Optional[List[Dict[str, Any]]]: The cached posts list, or None if not found.
        """
        key = self._generate_posts_list_key(author, page)
        return self.cache.get_api_cache(key)
    
    def cache_comments(self, post_id: str, comments: List[Dict[str, Any]]) -> bool:
        """
        Cache comments for a post.
        
        Args:
            post_id (str): The post ID.
            comments (List[Dict[str, Any]]): The comments.
        
        Returns:
            bool: True if the comments were cached successfully, False otherwise.
        """
        key = self._generate_comments_key(post_id)
        ttl = self._get_ttl("comments")
        return self.cache.set_api_cache(key, comments, ttl)
    
    def cache_comments_by_post_data(self, post_data: Dict[str, Any], comments: List[Dict[str, Any]]) -> bool:
        """
        Cache comments using post data to extract the post ID.
        
        Args:
            post_data (Dict[str, Any]): The post data.
            comments (List[Dict[str, Any]]): The comments.
        
        Returns:
            bool: True if the comments were cached successfully, False otherwise.
        """
        post_id = extract_post_id_from_api_response(post_data)
        if post_id:
            return self.cache_comments(post_id, comments)
        return False
    
    def get_cached_comments(self, post_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached comments for a post.
        
        Args:
            post_id (str): The post ID.
        
        Returns:
            Optional[List[Dict[str, Any]]]: The cached comments, or None if not found.
        """
        key = self._generate_comments_key(post_id)
        return self.cache.get_api_cache(key)
    
    def get_cached_comments_by_post_data(self, post_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached comments using post data to extract the post ID.
        
        Args:
            post_data (Dict[str, Any]): The post data.
        
        Returns:
            Optional[List[Dict[str, Any]]]: The cached comments, or None if not found.
        """
        post_id = extract_post_id_from_api_response(post_data)
        if post_id:
            return self.get_cached_comments(post_id)
        return None
    
    def cache_newsletter(self, author: str, newsletter_data: Dict[str, Any]) -> bool:
        """
        Cache newsletter metadata.
        
        Args:
            author (str): The author identifier.
            newsletter_data (Dict[str, Any]): The newsletter metadata.
        
        Returns:
            bool: True if the newsletter metadata was cached successfully, False otherwise.
        """
        key = self._generate_newsletter_key(author)
        ttl = self._get_ttl("newsletter")
        return self.cache.set_api_cache(key, newsletter_data, ttl)
    
    def get_cached_newsletter(self, author: str) -> Optional[Dict[str, Any]]:
        """
        Get cached newsletter metadata.
        
        Args:
            author (str): The author identifier.
        
        Returns:
            Optional[Dict[str, Any]]: The cached newsletter metadata, or None if not found.
        """
        key = self._generate_newsletter_key(author)
        return self.cache.get_api_cache(key)
    
    def cache_author(self, author: str, author_data: Dict[str, Any]) -> bool:
        """
        Cache author information.
        
        Args:
            author (str): The author identifier.
            author_data (Dict[str, Any]): The author information.
        
        Returns:
            bool: True if the author information was cached successfully, False otherwise.
        """
        key = self._generate_author_key(author)
        ttl = self._get_ttl("author")
        return self.cache.set_api_cache(key, author_data, ttl)
    
    def get_cached_author(self, author: str) -> Optional[Dict[str, Any]]:
        """
        Get cached author information.
        
        Args:
            author (str): The author identifier.
        
        Returns:
            Optional[Dict[str, Any]]: The cached author information, or None if not found.
        """
        key = self._generate_author_key(author)
        return self.cache.get_api_cache(key)
    
    def cache_api_response(self, url: str, response_data: Any, content_type: str = "default") -> bool:
        """
        Cache a generic API response.
        
        Args:
            url (str): The API URL.
            response_data (Any): The response data.
            content_type (str, optional): The content type. Defaults to "default".
        
        Returns:
            bool: True if the response was cached successfully, False otherwise.
        """
        ttl = self._get_ttl(content_type)
        return self.cache.set_api_cache(url, response_data, ttl)
    
    def get_cached_api_response(self, url: str) -> Optional[Any]:
        """
        Get a cached API response.
        
        Args:
            url (str): The API URL.
        
        Returns:
            Optional[Any]: The cached response data, or None if not found.
        """
        return self.cache.get_api_cache(url)
    
    def clear_author_cache(self, author: str) -> int:
        """
        Clear all cache entries for a specific author.
        
        Args:
            author (str): The author identifier.
        
        Returns:
            int: The number of entries removed.
        """
        # This is a simplified implementation that clears the entire cache
        # A more sophisticated implementation would only clear entries for the specified author
        return self.cache.clear_api_cache()
    
    def clear_post_cache(self, author: str, slug: str) -> bool:
        """
        Clear the cache for a specific post.
        
        Args:
            author (str): The author identifier.
            slug (str): The post slug.
        
        Returns:
            bool: True if the cache was cleared successfully, False otherwise.
        """
        # The CacheManager doesn't support deleting individual entries,
        # so we set an expired entry instead
        key = self._generate_post_key(author, slug)
        return self.cache.set_api_cache(key, {}, 0)
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dict[str, int]: Dictionary with cache statistics.
        """
        return self.cache.get_cache_stats()
    
    def clear_all_cache(self) -> Tuple[int, int]:
        """
        Clear all cache entries.
        
        Returns:
            Tuple[int, int]: Tuple of (api_count, page_count) entries removed.
        """
        return self.cache.clear_all_cache()


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Create a cache
    with SubstackApiCache(cache_dir="example_cache") as cache:
        # Cache a post
        post_data = {
            "id": "12345",
            "title": "How to Get Rich Sabotaging Nuclear Power Plants",
            "slug": "how-to-get-rich-sabotaging-nuclear",
            "post_date": "2023-01-01T12:00:00Z",
            "author": {"name": "Matt Stoller"}
        }
        cache.cache_post("mattstoller", "how-to-get-rich-sabotaging-nuclear", post_data)
        
        # Get the cached post
        cached_post = cache.get_cached_post("mattstoller", "how-to-get-rich-sabotaging-nuclear")
        print(f"Cached post: {json.dumps(cached_post, indent=2)}")
        
        # Cache a posts list
        posts_list = [post_data]
        cache.cache_posts_list("mattstoller", posts_list)
        
        # Get the cached posts list
        cached_posts = cache.get_cached_posts_list("mattstoller")
        print(f"Cached posts list: {json.dumps(cached_posts, indent=2)}")
        
        # Cache comments
        comments = [
            {
                "id": "comment1",
                "body": "Great post!",
                "author": "User1",
                "date": "2023-01-02"
            }
        ]
        cache.cache_comments("12345", comments)
        
        # Get the cached comments
        cached_comments = cache.get_cached_comments("12345")
        print(f"Cached comments: {json.dumps(cached_comments, indent=2)}")
        
        # Get cache stats
        stats = cache.get_cache_stats()
        print(f"Cache stats: {stats}")
        
        # Clear the cache
        api_count, page_count = cache.clear_all_cache()
        print(f"Cleared {api_count} API cache entries and {page_count} page cache entries")
