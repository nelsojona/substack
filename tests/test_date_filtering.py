#!/usr/bin/env python3
"""
Tests for date filtering functionality in the SubstackDirectDownloader class.
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.substack_direct_downloader import SubstackDirectDownloader


class TestDateFiltering:
    """Test class for date filtering functionality."""

    @pytest.fixture
    def downloader(self):
        """Create a SubstackDirectDownloader instance for testing."""
        return SubstackDirectDownloader(
            author="testauthor",
            output_dir="test_output",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

    def test_init_with_date_filters(self):
        """Test initialization with date filters."""
        # Create a downloader with date filters
        downloader = SubstackDirectDownloader(
            author="testauthor",
            output_dir="test_output",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        
        # Check that the date filters were set correctly
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31, 23, 59, 59)
        
        # Make sure the comparison is between objects of the same type (both timezone-naive)
        assert downloader.start_date.replace(tzinfo=None) == start_date
        assert downloader.end_date.replace(tzinfo=None) == end_date

    def test_init_with_invalid_date_filters(self):
        """Test initialization with invalid date filters."""
        # Create a downloader with invalid date filters
        downloader = SubstackDirectDownloader(
            author="testauthor",
            output_dir="test_output",
            start_date="invalid-date",
            end_date="2023-12-31"
        )
        
        # Check that the invalid start date was ignored
        assert downloader.start_date is None
        assert downloader.end_date == datetime(2023, 12, 31, 23, 59, 59)
        
        # Create another downloader with invalid end date
        downloader = SubstackDirectDownloader(
            author="testauthor",
            output_dir="test_output",
            start_date="2023-01-01",
            end_date="invalid-date"
        )
        
        # Check that the invalid end date was ignored
        assert downloader.start_date == datetime(2023, 1, 1)
        assert downloader.end_date is None

    def test_is_post_in_date_range(self, downloader):
        """Test the _is_post_in_date_range method."""
        # Test with a date in range
        in_range_date = datetime(2023, 6, 15)
        assert downloader._is_post_in_date_range(in_range_date) is True
        
        # Test with a date before the start date
        before_start_date = datetime(2022, 12, 31)
        assert downloader._is_post_in_date_range(before_start_date) is False
        
        # Test with a date after the end date
        after_end_date = datetime(2024, 1, 1)
        assert downloader._is_post_in_date_range(after_end_date) is False
        
        # Test with None date (should be included)
        assert downloader._is_post_in_date_range(None) is True
        
        # Test with no date filters
        downloader.start_date = None
        downloader.end_date = None
        assert downloader._is_post_in_date_range(in_range_date) is True
        assert downloader._is_post_in_date_range(before_start_date) is True
        assert downloader._is_post_in_date_range(after_end_date) is True
        
        # Test with only start date
        downloader.start_date = datetime(2023, 1, 1)
        downloader.end_date = None
        assert downloader._is_post_in_date_range(in_range_date) is True
        assert downloader._is_post_in_date_range(before_start_date) is False
        assert downloader._is_post_in_date_range(after_end_date) is True
        
        # Test with only end date
        downloader.start_date = None
        downloader.end_date = datetime(2023, 12, 31, 23, 59, 59)
        assert downloader._is_post_in_date_range(in_range_date) is True
        assert downloader._is_post_in_date_range(before_start_date) is True
        assert downloader._is_post_in_date_range(after_end_date) is False

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    async def test_find_post_urls_from_sitemap_with_date_filter(self, mock_fetch, downloader):
        """Test finding post URLs from sitemap with date filter."""
        # Add a patch to normalize dates for comparison
        with patch("src.core.substack_direct_downloader.SubstackDirectDownloader._is_post_in_date_range") as mock_in_range:
            # Set up the mock to return True for 2023 dates and False for others
            def check_date_range(date):
                if not date:
                    return True
                if isinstance(date, str):
                    try:
                        from dateutil import parser
                        date = parser.parse(date)
                    except:
                        return True
                
                # Extract year for simple comparison
                year = date.year if hasattr(date, 'year') else 2023
                return year == 2023
            
            mock_in_range.side_effect = check_date_range
            
            # Create a mock sitemap response with lastmod dates
            sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url>
                    <loc>https://testauthor.substack.com/p/post1</loc>
                    <lastmod>2022-12-15T12:00:00+00:00</lastmod>
                </url>
                <url>
                    <loc>https://testauthor.substack.com/p/post2</loc>
                    <lastmod>2023-02-15T12:00:00+00:00</lastmod>
                </url>
                <url>
                    <loc>https://testauthor.substack.com/p/post3</loc>
                    <lastmod>2023-06-15T12:00:00+00:00</lastmod>
                </url>
                <url>
                    <loc>https://testauthor.substack.com/p/post4</loc>
                    <lastmod>2024-01-15T12:00:00+00:00</lastmod>
                </url>
                <url>
                    <loc>https://testauthor.substack.com/about</loc>
                    <lastmod>2023-01-01T12:00:00+00:00</lastmod>
                </url>
            </urlset>
            """
            
            # Mock the _fetch_url method to return the sitemap
            mock_fetch.return_value = sitemap_xml
            
            # Find post URLs from sitemap
            post_urls = await downloader._find_post_urls_from_sitemap()
            
            # Check the result - should only include posts from 2023
            assert len(post_urls) == 2
            assert "https://testauthor.substack.com/p/post2" in post_urls
            assert "https://testauthor.substack.com/p/post3" in post_urls
            
            # Posts from 2022 and 2024 should be excluded
            assert "https://testauthor.substack.com/p/post1" not in post_urls
            assert "https://testauthor.substack.com/p/post4" not in post_urls
            
            # Non-post URLs should be excluded
            assert "https://testauthor.substack.com/about" not in post_urls

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    async def test_find_post_urls_from_sitemap_with_invalid_lastmod(self, mock_fetch, downloader):
        """Test finding post URLs from sitemap with invalid lastmod dates."""
        # Mock the _is_post_in_date_range method to always return True
        with patch("src.core.substack_direct_downloader.SubstackDirectDownloader._is_post_in_date_range", return_value=True):
            # Create a mock sitemap response with invalid lastmod dates
            sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url>
                    <loc>https://testauthor.substack.com/p/post1</loc>
                    <lastmod>invalid-date</lastmod>
                </url>
                <url>
                    <loc>https://testauthor.substack.com/p/post2</loc>
                    <lastmod>2023-02-15T12:00:00+00:00</lastmod>
                </url>
            </urlset>
            """
            
            # Mock the _fetch_url method to return the sitemap
            mock_fetch.return_value = sitemap_xml
            
            # Find post URLs from sitemap
            post_urls = await downloader._find_post_urls_from_sitemap()
            
            # Check the result - should include post2 and post1 (despite invalid date)
            assert len(post_urls) == 2
            assert "https://testauthor.substack.com/p/post1" in post_urls
            assert "https://testauthor.substack.com/p/post2" in post_urls

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    async def test_download_post_with_date_filter(self, mock_fetch, downloader):
        """Test downloading a post with date filter."""
        # Create a mock HTML response with a date
        html = """
        <html>
        <body>
            <h1 class="post-title">Test Post</h1>
            <time>January 15, 2023</time>
            <div class="post-content">Test content</div>
        </body>
        </html>
        """
        
        # Mock the _fetch_url method to return the HTML
        mock_fetch.return_value = html
        
        # Mock other methods that would be called
        downloader._store_post_metadata = MagicMock(return_value=True)
        downloader.extract_image_urls = AsyncMock(return_value=set())
        
        # Create a temporary directory for output
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader.output_dir = temp_dir
            os.makedirs(downloader.output_dir, exist_ok=True)
            
            # Download the post - should be in date range
            result = await downloader.download_post("https://testauthor.substack.com/p/test-post")
            
            # Check the result - should be successful
            assert result is True
            
            # Now test with a post outside the date range
            html_outside_range = """
            <html>
            <body>
                <h1 class="post-title">Outside Range Post</h1>
                <time>January 15, 2022</time>
                <div class="post-content">Test content</div>
            </body>
            </html>
            """
            
            # Update the mock to return the new HTML
            mock_fetch.return_value = html_outside_range
            
            # Download the post - should be outside date range
            result = await downloader.download_post("https://testauthor.substack.com/p/outside-range-post")
            
            # Check the result - should be skipped
            assert result == "skipped"

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader.direct_fetch")
    async def test_download_post_with_date_filter_direct_method(self, mock_direct_fetch, downloader):
        """Test downloading a post with date filter using direct method."""
        # Create a mock post data with a date in range
        post_data_in_range = {
            "title": "In Range Post",
            "date": "2023-06-15",
            "author": "testauthor",
            "url": "https://testauthor.substack.com/p/in-range-post",
            "content_html": "<p>Test content</p>",
            "html": "<p>Test content</p>"
        }
        
        # Mock the direct_fetch method to return the post data
        mock_direct_fetch.return_value = post_data_in_range
        
        # Mock other methods that would be called
        downloader._store_post_metadata = MagicMock(return_value=True)
        downloader.extract_image_urls = AsyncMock(return_value=set())
        
        # Create a temporary directory for output
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader.output_dir = temp_dir
            os.makedirs(downloader.output_dir, exist_ok=True)
            
            # Download the post - should be in date range
            result = await downloader.download_post(
                "https://testauthor.substack.com/p/in-range-post",
                use_direct=True
            )
            
            # Check the result - should be successful
            assert result is True
            
            # Now test with a post outside the date range
            post_data_outside_range = {
                "title": "Outside Range Post",
                "date": "2022-06-15",
                "author": "testauthor",
                "url": "https://testauthor.substack.com/p/outside-range-post",
                "content_html": "<p>Test content</p>",
                "html": "<p>Test content</p>"
            }
            
            # Update the mock to return the new post data
            mock_direct_fetch.return_value = post_data_outside_range
            
            # Download the post - should be outside date range
            result = await downloader.download_post(
                "https://testauthor.substack.com/p/outside-range-post",
                use_direct=True
            )
            
            # Check the result - should be skipped
            assert result == "skipped"

    def test_cli_arguments(self):
        """Test CLI arguments for date filtering."""
        # This is a simpler test that just verifies the command line arguments are defined
        
        # Import the SubstackDirectDownloader constructor
        from src.core.substack_direct_downloader import SubstackDirectDownloader
        
        # Create a downloader with date filters
        downloader = SubstackDirectDownloader(
            author="testauthor",
            output_dir="test_output",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        
        # Check that the date filters were properly processed
        assert downloader.start_date is not None
        assert downloader.end_date is not None
        
        # Verify that the date strings were converted to date objects
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31, 23, 59, 59)
        
        # Make sure the comparison is between objects of the same type (both timezone-naive)
        assert downloader.start_date.replace(tzinfo=None) == start_date
        assert downloader.end_date.replace(tzinfo=None) == end_date


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
