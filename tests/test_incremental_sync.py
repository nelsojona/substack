#!/usr/bin/env python3
"""
Tests for the incremental_sync module.
"""

import os
import json
import time
import unittest
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.utils.incremental_sync import IncrementalSync, IncrementalSyncManager


class TestIncrementalSync(unittest.TestCase):
    """Test cases for the IncrementalSync class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create the incremental sync
        self.sync = IncrementalSync(
            author="test_author",
            cache_dir=self.temp_dir
        )
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the state file
        state_file = os.path.join(self.temp_dir, "test_author_sync_state.json")
        if os.path.exists(state_file):
            os.remove(state_file)
        
        # Remove the cache database
        cache_db = os.path.join(self.temp_dir, "test_author_cache.db")
        if os.path.exists(cache_db):
            os.remove(cache_db)
        
        # Remove the temporary directory
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.sync.author, "test_author")
        self.assertEqual(self.sync.cache_dir, self.temp_dir)
        self.assertEqual(self.sync.state_file, os.path.join(self.temp_dir, "test_author_sync_state.json"))
        self.assertEqual(self.sync.last_sync, 0)
        self.assertEqual(len(self.sync.synced_posts), 0)
    
    def test_load_save_state(self):
        """Test loading and saving state."""
        # Set some state
        self.sync.last_sync = 1234567890
        self.sync.synced_posts = {"post1", "post2", "post3"}
        
        # Save the state
        self.sync._save_state()
        
        # Create a new sync object to load the state
        sync2 = IncrementalSync(
            author="test_author",
            cache_dir=self.temp_dir
        )
        
        # Check the loaded state
        self.assertEqual(sync2.last_sync, 1234567890)
        self.assertEqual(sync2.synced_posts, {"post1", "post2", "post3"})
    
    def test_get_last_sync_time(self):
        """Test getting the last sync time."""
        # Test with no sync
        last_sync_time = self.sync.get_last_sync_time()
        self.assertEqual(last_sync_time, datetime.min)
        
        # Test with a sync time
        self.sync.last_sync = 1234567890
        last_sync_time = self.sync.get_last_sync_time()
        self.assertEqual(last_sync_time, datetime.fromtimestamp(1234567890))
    
    def test_is_post_synced(self):
        """Test checking if a post is synced."""
        # Test with no synced posts
        self.assertFalse(self.sync.is_post_synced("post1"))
        
        # Test with synced posts
        self.sync.synced_posts = {"post1", "post2"}
        self.assertTrue(self.sync.is_post_synced("post1"))
        self.assertTrue(self.sync.is_post_synced("post2"))
        self.assertFalse(self.sync.is_post_synced("post3"))
    
    def test_mark_post_synced(self):
        """Test marking a post as synced."""
        # Mark some posts as synced
        self.sync.mark_post_synced("post1")
        self.sync.mark_post_synced("post2")
        
        # Check the synced posts
        self.assertEqual(self.sync.synced_posts, {"post1", "post2"})
    
    def test_filter_new_posts(self):
        """Test filtering new posts."""
        # Create some test posts
        posts = [
            {
                "id": "post1",
                "title": "Post 1",
                "post_date": "2023-01-01T12:00:00Z"
            },
            {
                "id": "post2",
                "title": "Post 2",
                "post_date": "2023-01-02T12:00:00Z"
            },
            {
                "id": "post3",
                "title": "Post 3",
                "post_date": "2023-01-03T12:00:00Z"
            }
        ]
        
        # Test with no sync (should include all posts)
        new_posts = self.sync.filter_new_posts(posts)
        self.assertEqual(len(new_posts), 3)
        
        # Test with a sync time and some synced posts
        self.sync.last_sync = datetime(2023, 1, 2, 0, 0, 0).timestamp()
        self.sync.synced_posts = {"post1"}
        new_posts = self.sync.filter_new_posts(posts)
        self.assertEqual(len(new_posts), 2)
        self.assertEqual(new_posts[0]["id"], "post2")
        self.assertEqual(new_posts[1]["id"], "post3")
    
    def test_update_sync_time(self):
        """Test updating the sync time."""
        # Update the sync time
        self.sync.update_sync_time()
        
        # Check the sync time
        self.assertGreater(self.sync.last_sync, 0)
        self.assertLessEqual(self.sync.last_sync, time.time())
    
    def test_reset_sync_state(self):
        """Test resetting the sync state."""
        # Set some state
        self.sync.last_sync = 1234567890
        self.sync.synced_posts = {"post1", "post2", "post3"}
        
        # Reset the state
        self.sync.reset_sync_state()
        
        # Check the state
        self.assertEqual(self.sync.last_sync, 0)
        self.assertEqual(len(self.sync.synced_posts), 0)
    
    def test_get_sync_stats(self):
        """Test getting sync statistics."""
        # Set some state
        self.sync.last_sync = 1234567890
        self.sync.synced_posts = {"post1", "post2", "post3"}
        
        # Get the stats
        stats = self.sync.get_sync_stats()
        
        # Check the stats
        self.assertEqual(stats["author"], "test_author")
        self.assertEqual(stats["last_sync"], 1234567890)
        self.assertEqual(stats["last_sync_time"], datetime.fromtimestamp(1234567890).isoformat())
        self.assertEqual(stats["synced_posts_count"], 3)
        self.assertEqual(set(stats["synced_posts"]), {"post1", "post2", "post3"})


class TestIncrementalSyncManager(unittest.TestCase):
    """Test cases for the IncrementalSyncManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create the incremental sync manager
        self.manager = IncrementalSyncManager(
            cache_dir=self.temp_dir
        )
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the state files
        for author in ["test_author1", "test_author2"]:
            state_file = os.path.join(self.temp_dir, f"{author}_sync_state.json")
            if os.path.exists(state_file):
                os.remove(state_file)
            
            cache_db = os.path.join(self.temp_dir, f"{author}_cache.db")
            if os.path.exists(cache_db):
                os.remove(cache_db)
        
        # Remove the temporary directory
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.manager.cache_dir, self.temp_dir)
        self.assertEqual(len(self.manager.syncs), 0)
    
    def test_get_sync(self):
        """Test getting a sync."""
        # Get a sync
        sync = self.manager.get_sync("test_author1")
        
        # Check the sync
        self.assertEqual(sync.author, "test_author1")
        self.assertEqual(sync.cache_dir, self.temp_dir)
        
        # Check that the sync is cached
        self.assertEqual(len(self.manager.syncs), 1)
        self.assertEqual(self.manager.syncs["test_author1"], sync)
        
        # Get the same sync again
        sync2 = self.manager.get_sync("test_author1")
        
        # Check that it's the same object
        self.assertIs(sync2, sync)
    
    def test_reset_all_syncs(self):
        """Test resetting all syncs."""
        # Get some syncs
        sync1 = self.manager.get_sync("test_author1")
        sync2 = self.manager.get_sync("test_author2")
        
        # Set some state
        sync1.last_sync = 1234567890
        sync1.synced_posts = {"post1", "post2"}
        sync2.last_sync = 1234567890
        sync2.synced_posts = {"post3", "post4"}
        
        # Reset all syncs
        self.manager.reset_all_syncs()
        
        # Check the state
        self.assertEqual(sync1.last_sync, 0)
        self.assertEqual(len(sync1.synced_posts), 0)
        self.assertEqual(sync2.last_sync, 0)
        self.assertEqual(len(sync2.synced_posts), 0)
    
    def test_get_all_sync_stats(self):
        """Test getting all sync statistics."""
        # Get some syncs
        sync1 = self.manager.get_sync("test_author1")
        sync2 = self.manager.get_sync("test_author2")
        
        # Set some state
        sync1.last_sync = 1234567890
        sync1.synced_posts = {"post1", "post2"}
        sync2.last_sync = 1234567890
        sync2.synced_posts = {"post3", "post4"}
        
        # Get all stats
        stats = self.manager.get_all_sync_stats()
        
        # Check the stats
        self.assertEqual(len(stats), 2)
        self.assertEqual(stats["test_author1"]["author"], "test_author1")
        self.assertEqual(stats["test_author1"]["synced_posts_count"], 2)
        self.assertEqual(stats["test_author2"]["author"], "test_author2")
        self.assertEqual(stats["test_author2"]["synced_posts_count"], 2)


if __name__ == '__main__':
    unittest.main()
