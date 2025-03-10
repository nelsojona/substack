#!/usr/bin/env python3
"""
Tests for the substack_api_utils module.
"""

import unittest
import json
import datetime
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from substack_api_utils import (
    extract_author_from_url,
    extract_slug_from_url,
    construct_post_url,
    construct_api_url,
    extract_post_id_from_api_response,
    format_post_date,
    extract_images_from_html,
    extract_newsletter_metadata,
    extract_post_metadata,
    extract_comments_from_api_response,
    organize_comments_tree,
    format_comments_markdown,
    generate_frontmatter,
    generate_newsletter_index,
    sanitize_filename,
    generate_filename
)


class TestSubstackApiUtils(unittest.TestCase):
    """Test cases for the substack_api_utils module."""
    
    def test_extract_author_from_url(self):
        """Test extracting author from URL."""
        # Test with valid URLs
        self.assertEqual(extract_author_from_url("https://mattstoller.substack.com/p/how-to-get-rich"), "mattstoller")
        self.assertEqual(extract_author_from_url("https://mattstoller.substack.com/"), "mattstoller")
        self.assertEqual(extract_author_from_url("https://mattstoller.substack.com/archive"), "mattstoller")
        
        # Test with invalid URLs
        self.assertIsNone(extract_author_from_url("https://example.com"))
        self.assertIsNone(extract_author_from_url("not a url"))
    
    def test_extract_slug_from_url(self):
        """Test extracting slug from URL."""
        # Test with valid URLs
        self.assertEqual(extract_slug_from_url("https://mattstoller.substack.com/p/how-to-get-rich"), "how-to-get-rich")
        self.assertEqual(extract_slug_from_url("https://mattstoller.substack.com/p/how-to-get-rich?utm_source=twitter"), "how-to-get-rich")
        
        # Test with invalid URLs
        self.assertIsNone(extract_slug_from_url("https://mattstoller.substack.com/"))
        self.assertIsNone(extract_slug_from_url("https://mattstoller.substack.com/archive"))
        self.assertIsNone(extract_slug_from_url("not a url"))
    
    def test_construct_post_url(self):
        """Test constructing post URL."""
        self.assertEqual(
            construct_post_url("mattstoller", "how-to-get-rich"),
            "https://mattstoller.substack.com/p/how-to-get-rich"
        )
    
    def test_construct_api_url(self):
        """Test constructing API URL."""
        # Test with endpoint
        self.assertEqual(
            construct_api_url("mattstoller", "posts"),
            "https://mattstoller.substack.com/api/v1/posts"
        )
        
        # Test without endpoint
        self.assertEqual(
            construct_api_url("mattstoller"),
            "https://mattstoller.substack.com/api/v1"
        )
    
    def test_extract_post_id_from_api_response(self):
        """Test extracting post ID from API response."""
        # Test with different field names
        self.assertEqual(extract_post_id_from_api_response({"id": 12345}), "12345")
        self.assertEqual(extract_post_id_from_api_response({"post_id": 12345}), "12345")
        self.assertEqual(extract_post_id_from_api_response({"_id": 12345}), "12345")
        self.assertEqual(extract_post_id_from_api_response({"postId": 12345}), "12345")
        
        # Test with missing ID
        self.assertEqual(extract_post_id_from_api_response({"title": "Test"}), "")
    
    def test_format_post_date(self):
        """Test formatting post date."""
        # Test with ISO format
        self.assertEqual(format_post_date("2023-01-01T12:00:00Z"), "2023-01-01")
        
        # Test with custom format
        self.assertEqual(format_post_date("2023-01-01T12:00:00Z", "%Y/%m/%d"), "2023/01/01")
        
        # Test with other formats
        self.assertEqual(format_post_date("2023-01-01"), "2023-01-01")
        self.assertEqual(format_post_date("01/01/2023"), "2023-01-01")
        self.assertEqual(format_post_date("January 01, 2023"), "2023-01-01")
        
        # Test with invalid format
        self.assertEqual(format_post_date("invalid date"), "invalid date")
        
        # Test with None
        self.assertIsNone(format_post_date(None))
    
    def test_extract_images_from_html(self):
        """Test extracting images from HTML."""
        # Test with absolute URLs
        html = '<img src="https://example.com/image1.jpg"><img src="https://example.com/image2.jpg">'
        expected = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
        self.assertEqual(extract_images_from_html(html), expected)
        
        # Test with relative URLs and base URL
        html = '<img src="/image1.jpg"><img src="image2.jpg">'
        expected = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
        self.assertEqual(extract_images_from_html(html, "https://example.com"), expected)
        
        # Test with empty HTML
        self.assertEqual(extract_images_from_html(""), [])
        self.assertEqual(extract_images_from_html(None), [])
    
    def test_extract_newsletter_metadata(self):
        """Test extracting newsletter metadata."""
        # Test with valid data
        api_response = {
            "newsletter": {
                "name": "BIG",
                "description": "A newsletter about monopoly and politics",
                "author": {"name": "Matt Stoller"},
                "logo_url": "https://example.com/logo.jpg",
                "cover_image_url": "https://example.com/cover.jpg",
                "subscribers_count": 10000,
                "post_count": 100
            }
        }
        
        expected = {
            "title": "BIG",
            "description": "A newsletter about monopoly and politics",
            "author": "Matt Stoller",
            "logo_url": "https://example.com/logo.jpg",
            "cover_image_url": "https://example.com/cover.jpg",
            "subscribers_count": 10000,
            "post_count": 100
        }
        
        self.assertEqual(extract_newsletter_metadata(api_response), expected)
        
        # Test with missing data
        api_response = {"newsletter": {}}
        expected = {
            "title": "",
            "description": "",
            "author": "",
            "logo_url": "",
            "cover_image_url": "",
            "subscribers_count": 0,
            "post_count": 0
        }
        self.assertEqual(extract_newsletter_metadata(api_response), expected)
        
        # Test with no newsletter
        api_response = {}
        self.assertEqual(extract_newsletter_metadata(api_response), expected)
    
    def test_extract_post_metadata(self):
        """Test extracting post metadata."""
        # Test with valid data
        post_data = {
            "id": 12345,
            "title": "How to Get Rich",
            "subtitle": "A guide",
            "slug": "how-to-get-rich",
            "post_date": "2023-01-01T12:00:00Z",
            "author": {"name": "Matt Stoller"},
            "canonical_url": "https://mattstoller.substack.com/p/how-to-get-rich",
            "is_paid": True,
            "is_public": False,
            "word_count": 1000,
            "audio_url": "https://example.com/audio.mp3",
            "comments_count": 10,
            "likes_count": 100
        }
        
        metadata = extract_post_metadata(post_data)
        
        self.assertEqual(metadata["id"], "12345")
        self.assertEqual(metadata["title"], "How to Get Rich")
        self.assertEqual(metadata["subtitle"], "A guide")
        self.assertEqual(metadata["slug"], "how-to-get-rich")
        self.assertEqual(metadata["date"], "2023-01-01")
        self.assertEqual(metadata["author"], "Matt Stoller")
        self.assertEqual(metadata["url"], "https://mattstoller.substack.com/p/how-to-get-rich")
        self.assertEqual(metadata["is_paid"], True)
        self.assertEqual(metadata["is_public"], False)
        self.assertEqual(metadata["word_count"], 1000)
        self.assertEqual(metadata["audio_url"], "https://example.com/audio.mp3")
        self.assertEqual(metadata["comments_count"], 10)
        self.assertEqual(metadata["likes_count"], 100)
        
        # Test with published_at instead of post_date
        post_data = {
            "id": 12345,
            "title": "How to Get Rich",
            "published_at": "2023-01-01T12:00:00Z"
        }
        
        metadata = extract_post_metadata(post_data)
        self.assertEqual(metadata["date"], "2023-01-01")
        
        # Test with missing data
        post_data = {}
        metadata = extract_post_metadata(post_data)
        self.assertEqual(metadata["id"], "")
        self.assertEqual(metadata["title"], "")
        self.assertEqual(metadata["date"], "")
    
    def test_extract_comments_from_api_response(self):
        """Test extracting comments from API response."""
        # Test with comments in the response
        api_response = {
            "comments": [
                {
                    "id": "comment1",
                    "body": "Great post!",
                    "created_at": "2023-01-02T12:00:00Z",
                    "commenter": {"name": "User1"},
                    "parent_id": None
                },
                {
                    "id": "comment2",
                    "body": "Thanks!",
                    "created_at": "2023-01-03T12:00:00Z",
                    "commenter": {"name": "User2"},
                    "parent_id": "comment1"
                }
            ]
        }
        
        comments = extract_comments_from_api_response(api_response)
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["id"], "comment1")
        self.assertEqual(comments[0]["body"], "Great post!")
        self.assertEqual(comments[0]["date"], "2023-01-02")
        self.assertEqual(comments[0]["author"], "User1")
        self.assertEqual(len(comments[0]["replies"]), 1)
        self.assertEqual(comments[0]["replies"][0]["id"], "comment2")
        
        # Test with commentsByPostId in the response
        api_response = {
            "post": {"id": "post1"},
            "commentsByPostId": {
                "post1": [
                    {
                        "id": "comment1",
                        "body": "Great post!",
                        "created_at": "2023-01-02T12:00:00Z",
                        "commenter": {"name": "User1"},
                        "parent_id": None
                    }
                ]
            }
        }
        
        comments = extract_comments_from_api_response(api_response)
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["id"], "comment1")
        
        # Test with no comments
        api_response = {}
        self.assertEqual(extract_comments_from_api_response(api_response), [])
    
    def test_organize_comments_tree(self):
        """Test organizing comments into a tree structure."""
        comments = [
            {
                "id": "comment1",
                "body": "Comment 1",
                "author": "User1",
                "parent_id": None
            },
            {
                "id": "comment2",
                "body": "Comment 2",
                "author": "User2",
                "parent_id": "comment1"
            },
            {
                "id": "comment3",
                "body": "Comment 3",
                "author": "User3",
                "parent_id": "comment2"
            },
            {
                "id": "comment4",
                "body": "Comment 4",
                "author": "User4",
                "parent_id": None
            }
        ]
        
        tree = organize_comments_tree(comments)
        
        # Check top-level comments
        self.assertEqual(len(tree), 2)
        self.assertEqual(tree[0]["id"], "comment1")
        self.assertEqual(tree[1]["id"], "comment4")
        
        # Check replies
        self.assertEqual(len(tree[0]["replies"]), 1)
        self.assertEqual(tree[0]["replies"][0]["id"], "comment2")
        
        # Check nested replies
        self.assertEqual(len(tree[0]["replies"][0]["replies"]), 1)
        self.assertEqual(tree[0]["replies"][0]["replies"][0]["id"], "comment3")
    
    def test_format_comments_markdown(self):
        """Test formatting comments as markdown."""
        comments = [
            {
                "id": "comment1",
                "body": "Comment 1",
                "author": "User1",
                "date": "2023-01-01",
                "replies": [
                    {
                        "id": "comment2",
                        "body": "Comment 2",
                        "author": "User2",
                        "date": "2023-01-02",
                        "replies": []
                    }
                ]
            }
        ]
        
        markdown = format_comments_markdown(comments)
        
        # Check that the markdown contains the comment author and body
        self.assertIn("**User1** - 2023-01-01", markdown)
        self.assertIn("Comment 1", markdown)
        
        # Check that the reply is indented
        self.assertIn("  **User2** - 2023-01-02", markdown)
        self.assertIn("  Comment 2", markdown)
    
    def test_generate_frontmatter(self):
        """Test generating frontmatter."""
        metadata = {
            "title": "How to Get Rich",
            "subtitle": "A guide",
            "date": "2023-01-01",
            "author": "Matt Stoller",
            "url": "https://mattstoller.substack.com/p/how-to-get-rich",
            "is_paid": True,
            "word_count": 1000,
            "comments_count": 10,
            "likes_count": 100
        }
        
        frontmatter = generate_frontmatter(metadata)
        
        # Check that the frontmatter contains the metadata
        self.assertIn('title: "How to Get Rich"', frontmatter)
        self.assertIn('subtitle: "A guide"', frontmatter)
        self.assertIn('date: "2023-01-01"', frontmatter)
        self.assertIn('author: "Matt Stoller"', frontmatter)
        self.assertIn('original_url: "https://mattstoller.substack.com/p/how-to-get-rich"', frontmatter)
        self.assertIn('is_paid: true', frontmatter)
        self.assertIn('word_count: 1000', frontmatter)
        self.assertIn('comments_count: 10', frontmatter)
        self.assertIn('likes_count: 100', frontmatter)
    
    def test_generate_newsletter_index(self):
        """Test generating newsletter index."""
        newsletter_metadata = {
            "title": "BIG",
            "description": "A newsletter about monopoly and politics",
            "author": "Matt Stoller",
            "subscribers_count": 10000,
            "post_count": 2
        }
        
        posts_metadata = [
            {
                "title": "Post 1",
                "date": "2023-01-01",
                "url": "https://mattstoller.substack.com/p/post-1"
            },
            {
                "title": "Post 2",
                "date": "2023-01-02",
                "url": "https://mattstoller.substack.com/p/post-2"
            }
        ]
        
        index = generate_newsletter_index(newsletter_metadata, posts_metadata)
        
        # Check that the index contains the newsletter metadata
        self.assertIn('title: "BIG"', index)
        self.assertIn('description: "A newsletter about monopoly and politics"', index)
        self.assertIn('author: "Matt Stoller"', index)
        self.assertIn('post_count: 2', index)
        self.assertIn('subscribers_count: 10000', index)
        
        # Check that the index contains the posts
        self.assertIn('# BIG', index)
        self.assertIn('A newsletter about monopoly and politics', index)
        self.assertIn('## Newsletter Statistics', index)
        self.assertIn('- **Posts**: 2', index)
        self.assertIn('- **Subscribers**: 10000', index)
        self.assertIn('## Posts', index)
        self.assertIn('- [2023-01-02] [Post 2](https://mattstoller.substack.com/p/post-2)', index)
        self.assertIn('- [2023-01-01] [Post 1](https://mattstoller.substack.com/p/post-1)', index)
    
    def test_sanitize_filename(self):
        """Test sanitizing filename."""
        # Test with invalid characters
        self.assertEqual(sanitize_filename('Test: File/Name*With?Invalid"Characters<>|'), 'Test_ File_Name_With_Invalid_Characters___')
        
        # Test with multiple spaces
        self.assertEqual(sanitize_filename('Test   Multiple    Spaces'), 'Test Multiple Spaces')
        
        # Test with long filename
        long_name = 'A' * 120
        sanitized = sanitize_filename(long_name)
        self.assertTrue(len(sanitized) < 120)
        self.assertTrue(sanitized.endswith('...'))
    
    def test_generate_filename(self):
        """Test generating filename."""
        # Test with date and slug
        metadata = {
            "title": "How to Get Rich",
            "date": "2023-01-01",
            "slug": "how-to-get-rich"
        }
        self.assertEqual(generate_filename(metadata), "2023-01-01_how-to-get-rich.md")
        
        # Test with date but no slug
        metadata = {
            "title": "How to Get Rich",
            "date": "2023-01-01"
        }
        self.assertEqual(generate_filename(metadata), "2023-01-01_How to Get Rich.md")
        
        # Test with no date but slug
        metadata = {
            "title": "How to Get Rich",
            "slug": "how-to-get-rich"
        }
        self.assertEqual(generate_filename(metadata), "how-to-get-rich.md")
        
        # Test with no date and no slug
        metadata = {
            "title": "How to Get Rich"
        }
        self.assertEqual(generate_filename(metadata), "How to Get Rich.md")


if __name__ == '__main__':
    unittest.main()
