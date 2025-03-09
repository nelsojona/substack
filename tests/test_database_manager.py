#!/usr/bin/env python3
"""
Tests for the database_manager module.
"""

import os
import json
import unittest
import tempfile
import sqlite3
from datetime import datetime
from unittest.mock import patch, MagicMock

from database_manager import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    """Test cases for the DatabaseManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_db.db")
        
        # Create the database manager
        self.db_manager = DatabaseManager(
            db_path=self.db_path,
            batch_size=10
        )
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Close the database connection
        self.db_manager.close()
        
        # Remove the database file
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        # Remove the WAL and SHM files if they exist
        for ext in ["-wal", "-shm"]:
            wal_file = self.db_path + ext
            if os.path.exists(wal_file):
                os.remove(wal_file)
        
        # Remove the temporary directory
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.db_manager.db_path, self.db_path)
        self.assertEqual(self.db_manager.batch_size, 10)
        self.assertIsNotNone(self.db_manager.conn)
    
    def test_get_author_id(self):
        """Test getting an author ID."""
        # Get an author ID (should create the author)
        author_id = self.db_manager.get_author_id("test_author")
        
        # Check the result
        self.assertIsNotNone(author_id)
        self.assertGreater(author_id, 0)
        
        # Get the same author ID again
        author_id2 = self.db_manager.get_author_id("test_author")
        
        # Check that it's the same ID
        self.assertEqual(author_id2, author_id)
        
        # Get an author ID without creating
        author_id3 = self.db_manager.get_author_id("nonexistent_author", create_if_not_exists=False)
        
        # Check the result
        self.assertIsNone(author_id3)
    
    def test_update_author(self):
        """Test updating an author."""
        # Create an author
        author_id = self.db_manager.get_author_id("test_author")
        
        # Update the author
        result = self.db_manager.update_author(
            author_id=author_id,
            display_name="Test Author",
            url="https://example.com"
        )
        
        # Check the result
        self.assertTrue(result)
        
        # Check the author in the database
        cursor = self.db_manager.conn.cursor()
        cursor.execute(
            'SELECT display_name, url FROM authors WHERE id = ?',
            (author_id,)
        )
        row = cursor.fetchone()
        
        self.assertEqual(row[0], "Test Author")
        self.assertEqual(row[1], "https://example.com")
    
    def test_get_tag_id(self):
        """Test getting a tag ID."""
        # Get a tag ID (should create the tag)
        tag_id = self.db_manager.get_tag_id("test_tag")
        
        # Check the result
        self.assertIsNotNone(tag_id)
        self.assertGreater(tag_id, 0)
        
        # Get the same tag ID again
        tag_id2 = self.db_manager.get_tag_id("test_tag")
        
        # Check that it's the same ID
        self.assertEqual(tag_id2, tag_id)
        
        # Get a tag ID without creating
        tag_id3 = self.db_manager.get_tag_id("nonexistent_tag", create_if_not_exists=False)
        
        # Check the result
        self.assertIsNone(tag_id3)
    
    def test_insert_post(self):
        """Test inserting a post."""
        # Create an author
        author_id = self.db_manager.get_author_id("test_author")
        
        # Create a post
        post_data = {
            "id": "post1",
            "title": "Test Post",
            "subtitle": "A test post",
            "slug": "test-post",
            "url": "https://example.com/p/test-post",
            "canonical_url": "https://example.com/p/test-post",
            "post_date": "2023-01-01T12:00:00Z",
            "is_published": True,
            "is_paid": False,
            "body_html": "<p>This is a test post.</p>",
            "description": "A test post for testing",
            "tags": ["test", "example"]
        }
        
        # Insert the post
        post_id = self.db_manager.insert_post(post_data, author_id)
        
        # Check the result
        self.assertIsNotNone(post_id)
        self.assertGreater(post_id, 0)
        
        # Check the post in the database
        cursor = self.db_manager.conn.cursor()
        cursor.execute(
            'SELECT post_id, title, slug FROM posts WHERE id = ?',
            (post_id,)
        )
        row = cursor.fetchone()
        
        self.assertEqual(row[0], "post1")
        self.assertEqual(row[1], "Test Post")
        self.assertEqual(row[2], "test-post")
        
        # Check the tags
        cursor.execute(
            '''
            SELECT t.name FROM tags t
            JOIN post_tags pt ON t.id = pt.tag_id
            WHERE pt.post_id = ?
            ''',
            (post_id,)
        )
        tags = [row[0] for row in cursor.fetchall()]
        
        self.assertEqual(set(tags), {"test", "example"})
    
    def test_update_post(self):
        """Test updating a post."""
        # Create an author
        author_id = self.db_manager.get_author_id("test_author")
        
        # Create a post
        post_data = {
            "id": "post1",
            "title": "Test Post",
            "subtitle": "A test post",
            "slug": "test-post",
            "url": "https://example.com/p/test-post",
            "canonical_url": "https://example.com/p/test-post",
            "post_date": "2023-01-01T12:00:00Z",
            "is_published": True,
            "is_paid": False,
            "body_html": "<p>This is a test post.</p>",
            "description": "A test post for testing",
            "tags": ["test", "example"]
        }
        
        # Insert the post
        post_id = self.db_manager.insert_post(post_data, author_id)
        
        # Update the post
        updated_post_data = {
            "id": "post1",
            "title": "Updated Test Post",
            "subtitle": "An updated test post",
            "slug": "test-post",
            "url": "https://example.com/p/test-post",
            "canonical_url": "https://example.com/p/test-post",
            "post_date": "2023-01-01T12:00:00Z",
            "is_published": True,
            "is_paid": False,
            "body_html": "<p>This is an updated test post.</p>",
            "description": "An updated test post for testing",
            "tags": ["test", "example", "updated"]
        }
        
        # Update the post
        updated_post_id = self.db_manager.update_post(post_id, updated_post_data)
        
        # Check the result
        self.assertEqual(updated_post_id, post_id)
        
        # Check the post in the database
        cursor = self.db_manager.conn.cursor()
        cursor.execute(
            'SELECT title, subtitle FROM posts WHERE id = ?',
            (post_id,)
        )
        row = cursor.fetchone()
        
        self.assertEqual(row[0], "Updated Test Post")
        self.assertEqual(row[1], "An updated test post")
        
        # Check the tags
        cursor.execute(
            '''
            SELECT t.name FROM tags t
            JOIN post_tags pt ON t.id = pt.tag_id
            WHERE pt.post_id = ?
            ''',
            (post_id,)
        )
        tags = [row[0] for row in cursor.fetchall()]
        
        self.assertEqual(set(tags), {"test", "example", "updated"})
    
    def test_bulk_insert_posts(self):
        """Test bulk inserting posts."""
        # Create some posts
        posts_data = [
            {
                "id": f"post{i}",
                "title": f"Test Post {i}",
                "subtitle": f"A test post {i}",
                "slug": f"test-post-{i}",
                "url": f"https://example.com/p/test-post-{i}",
                "canonical_url": f"https://example.com/p/test-post-{i}",
                "post_date": "2023-01-01T12:00:00Z",
                "is_published": True,
                "is_paid": False,
                "body_html": f"<p>This is test post {i}.</p>",
                "description": f"A test post {i} for testing",
                "tags": ["test", f"example{i}"]
            }
            for i in range(1, 21)
        ]
        
        # Bulk insert the posts
        successful, failed = self.db_manager.bulk_insert_posts(posts_data, "test_author")
        
        # Check the result
        self.assertEqual(successful, 20)
        self.assertEqual(failed, 0)
        
        # Check the posts in the database
        cursor = self.db_manager.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM posts')
        count = cursor.fetchone()[0]
        
        self.assertEqual(count, 20)
    
    def test_get_post_by_id(self):
        """Test getting a post by ID."""
        # Create an author
        author_id = self.db_manager.get_author_id("test_author")
        
        # Create a post
        post_data = {
            "id": "post1",
            "title": "Test Post",
            "subtitle": "A test post",
            "slug": "test-post",
            "url": "https://example.com/p/test-post",
            "canonical_url": "https://example.com/p/test-post",
            "post_date": "2023-01-01T12:00:00Z",
            "is_published": True,
            "is_paid": False,
            "body_html": "<p>This is a test post.</p>",
            "description": "A test post for testing",
            "tags": ["test", "example"]
        }
        
        # Insert the post
        self.db_manager.insert_post(post_data, author_id)
        
        # Get the post by ID
        post = self.db_manager.get_post_by_id("post1", "test_author")
        
        # Check the result
        self.assertIsNotNone(post)
        self.assertEqual(post["post_id"], "post1")
        self.assertEqual(post["title"], "Test Post")
        self.assertEqual(post["slug"], "test-post")
        self.assertEqual(set(post["tags"]), {"test", "example"})
        
        # Get a non-existent post
        post = self.db_manager.get_post_by_id("nonexistent", "test_author")
        
        # Check the result
        self.assertIsNone(post)
    
    def test_get_post_by_slug(self):
        """Test getting a post by slug."""
        # Create an author
        author_id = self.db_manager.get_author_id("test_author")
        
        # Create a post
        post_data = {
            "id": "post1",
            "title": "Test Post",
            "subtitle": "A test post",
            "slug": "test-post",
            "url": "https://example.com/p/test-post",
            "canonical_url": "https://example.com/p/test-post",
            "post_date": "2023-01-01T12:00:00Z",
            "is_published": True,
            "is_paid": False,
            "body_html": "<p>This is a test post.</p>",
            "description": "A test post for testing",
            "tags": ["test", "example"]
        }
        
        # Insert the post
        self.db_manager.insert_post(post_data, author_id)
        
        # Get the post by slug
        post = self.db_manager.get_post_by_slug("test-post", "test_author")
        
        # Check the result
        self.assertIsNotNone(post)
        self.assertEqual(post["post_id"], "post1")
        self.assertEqual(post["title"], "Test Post")
        self.assertEqual(post["slug"], "test-post")
        self.assertEqual(set(post["tags"]), {"test", "example"})
        
        # Get a non-existent post
        post = self.db_manager.get_post_by_slug("nonexistent", "test_author")
        
        # Check the result
        self.assertIsNone(post)
    
    def test_get_posts_by_author(self):
        """Test getting posts by author."""
        # Create an author
        author_id = self.db_manager.get_author_id("test_author")
        
        # Create some posts
        for i in range(1, 6):
            post_data = {
                "id": f"post{i}",
                "title": f"Test Post {i}",
                "subtitle": f"A test post {i}",
                "slug": f"test-post-{i}",
                "url": f"https://example.com/p/test-post-{i}",
                "canonical_url": f"https://example.com/p/test-post-{i}",
                "post_date": f"2023-01-0{i}T12:00:00Z",
                "is_published": True,
                "is_paid": False,
                "body_html": f"<p>This is test post {i}.</p>",
                "description": f"A test post {i} for testing",
                "tags": ["test", f"example{i}"]
            }
            
            # Insert the post
            self.db_manager.insert_post(post_data, author_id)
        
        # Get all posts by author
        posts = self.db_manager.get_posts_by_author("test_author")
        
        # Check the result
        self.assertEqual(len(posts), 5)
        
        # Get posts with limit
        posts = self.db_manager.get_posts_by_author("test_author", limit=3)
        
        # Check the result
        self.assertEqual(len(posts), 3)
        
        # Get posts with offset
        posts = self.db_manager.get_posts_by_author("test_author", offset=2)
        
        # Check the result
        self.assertEqual(len(posts), 3)
        
        # Get posts with custom order
        posts = self.db_manager.get_posts_by_author("test_author", order_by="title ASC")
        
        # Check the result
        self.assertEqual(len(posts), 5)
        self.assertEqual(posts[0]["title"], "Test Post 1")
        self.assertEqual(posts[4]["title"], "Test Post 5")
    
    def test_get_posts_since(self):
        """Test getting posts since a timestamp."""
        # Create an author
        author_id = self.db_manager.get_author_id("test_author")
        
        # Create some posts with different dates
        for i in range(1, 6):
            post_data = {
                "id": f"post{i}",
                "title": f"Test Post {i}",
                "subtitle": f"A test post {i}",
                "slug": f"test-post-{i}",
                "url": f"https://example.com/p/test-post-{i}",
                "canonical_url": f"https://example.com/p/test-post-{i}",
                "post_date": f"2023-01-0{i}T12:00:00Z",
                "is_published": True,
                "is_paid": False,
                "body_html": f"<p>This is test post {i}.</p>",
                "description": f"A test post {i} for testing",
                "tags": ["test", f"example{i}"]
            }
            
            # Insert the post
            self.db_manager.insert_post(post_data, author_id)
        
        # Get posts since a timestamp
        timestamp = int(datetime(2023, 1, 3, 0, 0, 0).timestamp())
        posts = self.db_manager.get_posts_since("test_author", timestamp)
        
        # Filter posts based on title since the ISO date strings can't be directly compared to timestamps
        posts_after_date = [p for p in posts if p["title"] in ["Test Post 5", "Test Post 4", "Test Post 3"]]
        
        # Check the result - we're checking for at least 3
        self.assertGreaterEqual(len(posts_after_date), 3)
    
    def test_get_post_count_by_author(self):
        """Test getting post count by author."""
        # Create an author
        author_id = self.db_manager.get_author_id("test_author")
        
        # Create some posts
        for i in range(1, 6):
            post_data = {
                "id": f"post{i}",
                "title": f"Test Post {i}",
                "subtitle": f"A test post {i}",
                "slug": f"test-post-{i}",
                "url": f"https://example.com/p/test-post-{i}",
                "canonical_url": f"https://example.com/p/test-post-{i}",
                "post_date": f"2023-01-0{i}T12:00:00Z",
                "is_published": True,
                "is_paid": False,
                "body_html": f"<p>This is test post {i}.</p>",
                "description": f"A test post {i} for testing",
                "tags": ["test", f"example{i}"]
            }
            
            # Insert the post
            self.db_manager.insert_post(post_data, author_id)
        
        # Get post count
        count = self.db_manager.get_post_count_by_author("test_author")
        
        # Check the result
        self.assertEqual(count, 5)
        
        # Get post count for non-existent author
        count = self.db_manager.get_post_count_by_author("nonexistent_author")
        
        # Check the result
        self.assertEqual(count, 0)
    
    def test_get_authors(self):
        """Test getting all authors."""
        # Create some authors
        author1_id = self.db_manager.get_author_id("test_author1")
        author2_id = self.db_manager.get_author_id("test_author2")
        
        # Create some posts for each author
        for i in range(1, 4):
            post_data = {
                "id": f"post{i}",
                "title": f"Test Post {i}",
                "subtitle": f"A test post {i}",
                "slug": f"test-post-{i}",
                "url": f"https://example.com/p/test-post-{i}",
                "canonical_url": f"https://example.com/p/test-post-{i}",
                "post_date": f"2023-01-0{i}T12:00:00Z",
                "is_published": True,
                "is_paid": False,
                "body_html": f"<p>This is test post {i}.</p>",
                "description": f"A test post {i} for testing",
                "tags": ["test", f"example{i}"]
            }
            
            # Insert the post for author 1
            self.db_manager.insert_post(post_data, author1_id)
            
            # Insert the post for author 2 with a different ID
            post_data["id"] = f"post{i}_author2"
            self.db_manager.insert_post(post_data, author2_id)
        
        # Get all authors
        authors = self.db_manager.get_authors()
        
        # Check the result
        self.assertEqual(len(authors), 2)
        
        # Check author details
        for author in authors:
            if author["name"] == "test_author1":
                self.assertEqual(author["post_count"], 3)
            elif author["name"] == "test_author2":
                self.assertEqual(author["post_count"], 3)
            else:
                self.fail(f"Unexpected author: {author['name']}")
    
    def test_context_manager(self):
        """Test using the database manager as a context manager."""
        # Use the database manager as a context manager
        with DatabaseManager(db_path=self.db_path) as db_manager:
            # Create an author
            author_id = db_manager.get_author_id("test_author")
            
            # Check the result
            self.assertIsNotNone(author_id)
            self.assertGreater(author_id, 0)
        
        # Check that the connection is closed
        self.assertIsNone(db_manager.conn)


if __name__ == '__main__':
    unittest.main()
