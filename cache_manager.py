#!/usr/bin/env python3
"""
Cache Manager Module

This module provides caching functionality for API responses and downloaded pages.
It implements a cache layer using SQLite with TTL settings for cache entries.
"""

import os
import json
import time
import sqlite3
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CacheManager:
    """
    A class for managing cache of API responses and downloaded pages.
    
    Attributes:
        db_path (str): Path to the SQLite database file.
        default_ttl (int): Default time-to-live for cache entries in seconds.
        conn (sqlite3.Connection): Connection to the SQLite database.
    """
    
    def __init__(self, db_path: str = "cache.db", default_ttl: int = 86400):
        """
        Initialize the CacheManager.
        
        Args:
            db_path (str, optional): Path to the SQLite database file. 
                                    Defaults to "cache.db".
            default_ttl (int, optional): Default time-to-live for cache entries in seconds. 
                                        Defaults to 86400 (1 day).
        """
        self.db_path = db_path
        self.default_ttl = default_ttl
        self.conn = None
        
        # Initialize the database
        self._init_db()
    
    def _init_db(self):
        """Initialize the SQLite database and create tables if they don't exist."""
        try:
            # Create directory for the database if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            
            # Connect to the database
            self.conn = sqlite3.connect(self.db_path)
            
            # Create tables if they don't exist
            cursor = self.conn.cursor()
            
            # Create API cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    created_at INTEGER,
                    expires_at INTEGER
                )
            ''')
            
            # Create page cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS page_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    created_at INTEGER,
                    expires_at INTEGER
                )
            ''')
            
            # Create indexes for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_cache_expires_at ON api_cache(expires_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_page_cache_expires_at ON page_cache(expires_at)')
            
            self.conn.commit()
            logger.debug(f"Initialized cache database at {self.db_path}")
        
        except sqlite3.Error as e:
            logger.error(f"Error initializing cache database: {e}")
            if self.conn:
                self.conn.close()
                self.conn = None
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def _generate_key(self, url: str) -> str:
        """
        Generate a cache key from a URL.
        
        Args:
            url (str): The URL to generate a key for.
        
        Returns:
            str: The generated cache key.
        """
        return hashlib.sha256(url.encode()).hexdigest()
    
    def _clean_expired_entries(self, table: str) -> int:
        """
        Clean expired entries from a cache table.
        
        Args:
            table (str): The name of the cache table.
        
        Returns:
            int: The number of entries removed.
        """
        if not self.conn:
            return 0
        
        try:
            cursor = self.conn.cursor()
            
            # Get the current time
            now = int(time.time())
            
            # Delete expired entries
            cursor.execute(
                f'DELETE FROM {table} WHERE expires_at < ?',
                (now,)
            )
            
            # Get the number of rows affected
            count = cursor.rowcount
            
            # Commit the changes
            self.conn.commit()
            
            return count
        
        except sqlite3.Error as e:
            logger.error(f"Error cleaning expired entries from {table}: {e}")
            return 0
    
    def set_api_cache(self, url: str, data: Any, ttl: Optional[int] = None) -> bool:
        """
        Set an API cache entry.
        
        Args:
            url (str): The URL to cache.
            data (Any): The data to cache.
            ttl (Optional[int], optional): Time-to-live in seconds. 
                                         Defaults to None (use default_ttl).
        
        Returns:
            bool: True if the cache entry was set successfully, False otherwise.
        """
        if not self.conn:
            return False
        
        try:
            cursor = self.conn.cursor()
            
            # Generate a key from the URL
            key = self._generate_key(url)
            
            # Serialize the data
            value = json.dumps(data)
            
            # Get the current time
            now = int(time.time())
            
            # Calculate the expiration time
            expires_at = now + (ttl if ttl is not None else self.default_ttl)
            
            # Insert or replace the cache entry
            cursor.execute(
                '''
                INSERT OR REPLACE INTO api_cache (key, value, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                ''',
                (key, value, now, expires_at)
            )
            
            # Commit the changes
            self.conn.commit()
            
            return True
        
        except sqlite3.Error as e:
            logger.error(f"Error setting API cache for {url}: {e}")
            return False
    
    def get_api_cache(self, url: str) -> Optional[Any]:
        """
        Get an API cache entry.
        
        Args:
            url (str): The URL to get the cache entry for.
        
        Returns:
            Optional[Any]: The cached data, or None if not found or expired.
        """
        if not self.conn:
            return None
        
        try:
            cursor = self.conn.cursor()
            
            # Generate a key from the URL
            key = self._generate_key(url)
            
            # Get the current time
            now = int(time.time())
            
            # Get the cache entry
            cursor.execute(
                '''
                SELECT value FROM api_cache
                WHERE key = ? AND expires_at >= ?
                ''',
                (key, now)
            )
            
            row = cursor.fetchone()
            
            if row:
                # Deserialize the data
                return json.loads(row[0])
            
            return None
        
        except sqlite3.Error as e:
            logger.error(f"Error getting API cache for {url}: {e}")
            return None
    
    def set_page_cache(self, url: str, html: str, ttl: Optional[int] = None) -> bool:
        """
        Set a page cache entry.
        
        Args:
            url (str): The URL to cache.
            html (str): The HTML content to cache.
            ttl (Optional[int], optional): Time-to-live in seconds. 
                                         Defaults to None (use default_ttl).
        
        Returns:
            bool: True if the cache entry was set successfully, False otherwise.
        """
        if not self.conn:
            return False
        
        try:
            cursor = self.conn.cursor()
            
            # Generate a key from the URL
            key = self._generate_key(url)
            
            # Get the current time
            now = int(time.time())
            
            # Calculate the expiration time
            expires_at = now + (ttl if ttl is not None else self.default_ttl)
            
            # Insert or replace the cache entry
            cursor.execute(
                '''
                INSERT OR REPLACE INTO page_cache (key, value, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                ''',
                (key, html, now, expires_at)
            )
            
            # Commit the changes
            self.conn.commit()
            
            return True
        
        except sqlite3.Error as e:
            logger.error(f"Error setting page cache for {url}: {e}")
            return False
    
    def get_page_cache(self, url: str) -> Optional[str]:
        """
        Get a page cache entry.
        
        Args:
            url (str): The URL to get the cache entry for.
        
        Returns:
            Optional[str]: The cached HTML content, or None if not found or expired.
        """
        if not self.conn:
            return None
        
        try:
            cursor = self.conn.cursor()
            
            # Generate a key from the URL
            key = self._generate_key(url)
            
            # Get the current time
            now = int(time.time())
            
            # Get the cache entry
            cursor.execute(
                '''
                SELECT value FROM page_cache
                WHERE key = ? AND expires_at >= ?
                ''',
                (key, now)
            )
            
            row = cursor.fetchone()
            
            if row:
                return row[0]
            
            return None
        
        except sqlite3.Error as e:
            logger.error(f"Error getting page cache for {url}: {e}")
            return None
    
    def clear_api_cache(self) -> int:
        """
        Clear all API cache entries.
        
        Returns:
            int: The number of entries removed.
        """
        if not self.conn:
            return 0
        
        try:
            cursor = self.conn.cursor()
            
            # Delete all entries
            cursor.execute('DELETE FROM api_cache')
            
            # Get the number of rows affected
            count = cursor.rowcount
            
            # Commit the changes
            self.conn.commit()
            
            return count
        
        except sqlite3.Error as e:
            logger.error(f"Error clearing API cache: {e}")
            return 0
    
    def clear_page_cache(self) -> int:
        """
        Clear all page cache entries.
        
        Returns:
            int: The number of entries removed.
        """
        if not self.conn:
            return 0
        
        try:
            cursor = self.conn.cursor()
            
            # Delete all entries
            cursor.execute('DELETE FROM page_cache')
            
            # Get the number of rows affected
            count = cursor.rowcount
            
            # Commit the changes
            self.conn.commit()
            
            return count
        
        except sqlite3.Error as e:
            logger.error(f"Error clearing page cache: {e}")
            return 0
    
    def clear_all_cache(self) -> Tuple[int, int]:
        """
        Clear all cache entries.
        
        Returns:
            Tuple[int, int]: Tuple of (api_count, page_count) entries removed.
        """
        api_count = self.clear_api_cache()
        page_count = self.clear_page_cache()
        
        return api_count, page_count
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dict[str, int]: Dictionary with cache statistics.
        """
        if not self.conn:
            return {
                "api_count": 0,
                "page_count": 0,
                "total_count": 0,
                "total_expired": 0
            }
        
        try:
            cursor = self.conn.cursor()
            
            # Get the current time
            now = int(time.time())
            
            # Get API cache count
            cursor.execute('SELECT COUNT(*) FROM api_cache')
            api_count = cursor.fetchone()[0]
            
            # Get page cache count
            cursor.execute('SELECT COUNT(*) FROM page_cache')
            page_count = cursor.fetchone()[0]
            
            # Get expired API cache count
            cursor.execute('SELECT COUNT(*) FROM api_cache WHERE expires_at < ?', (now,))
            api_expired = cursor.fetchone()[0]
            
            # Get expired page cache count
            cursor.execute('SELECT COUNT(*) FROM page_cache WHERE expires_at < ?', (now,))
            page_expired = cursor.fetchone()[0]
            
            return {
                "api_count": api_count,
                "page_count": page_count,
                "total_count": api_count + page_count,
                "total_expired": api_expired + page_expired
            }
        
        except sqlite3.Error as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "api_count": 0,
                "page_count": 0,
                "total_count": 0,
                "total_expired": 0
            }


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Create a cache manager
    with CacheManager(db_path="example_cache.db") as cache:
        # Set some cache entries
        cache.set_api_cache("https://example.com/api", {"key": "value"})
        cache.set_page_cache("https://example.com", "<html><body>Example</body></html>")
        
        # Get the cache entries
        api_data = cache.get_api_cache("https://example.com/api")
        page_html = cache.get_page_cache("https://example.com")
        
        print(f"API data: {api_data}")
        print(f"Page HTML: {page_html}")
        
        # Get cache stats
        stats = cache.get_cache_stats()
        print(f"Cache stats: {stats}")
        
        # Clear the cache
        api_count, page_count = cache.clear_all_cache()
        print(f"Cleared {api_count} API cache entries and {page_count} page cache entries")
