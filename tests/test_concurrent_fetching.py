#!/usr/bin/env python3
"""
Tests for concurrent fetching functionality.

This module tests the concurrent fetching features of the Substack to Markdown CLI,
including connection pooling, semaphore control, and dynamic concurrency limits.
"""

import os
import sys
import pytest
import asyncio
import aiohttp
from unittest.mock import patch, MagicMock, AsyncMock
from aiohttp import ClientSession, TCPConnector

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.connection_pool import ConnectionPool, OptimizedHttpClient
from src.utils.adaptive_throttler import AsyncAdaptiveThrottler
from src.core.substack_direct_downloader import SubstackDirectDownloader


class TestConnectionPool:
    """Test class for connection pool functionality."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating a session with the connection pool."""
        # Arrange
        pool = ConnectionPool(
            max_connections=10,
            max_connections_per_host=5,
            timeout=30,
            keep_alive=120
        )
        
        # Act
        session = await pool.create_session("test_session")
        
        # Assert
        assert session is not None
        assert isinstance(session, ClientSession)
        assert "test_session" in pool.sessions
        assert pool.sessions["test_session"] == session
        
        # Clean up
        await pool.close_all_sessions()

    @pytest.mark.asyncio
    async def test_get_or_create_session(self):
        """Test getting or creating a session with the connection pool."""
        # Arrange
        pool = ConnectionPool(
            max_connections=10,
            max_connections_per_host=5,
            timeout=30,
            keep_alive=120
        )
        
        # Act - First call should create a new session
        session1 = await pool.get_or_create_session("test_session")
        
        # Second call should return the existing session
        session2 = await pool.get_or_create_session("test_session")
        
        # Assert
        assert session1 is not None
        assert session2 is not None
        assert session1 == session2  # Should be the same session object
        
        # Clean up
        await pool.close_all_sessions()

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test closing a session in the connection pool."""
        # Arrange
        pool = ConnectionPool(
            max_connections=10,
            max_connections_per_host=5,
            timeout=30,
            keep_alive=120
        )
        
        # Create a session
        await pool.create_session("test_session")
        
        # Act
        result = await pool.close_session("test_session")
        
        # Assert
        assert result is True
        assert "test_session" not in pool.sessions

    @pytest.mark.asyncio
    async def test_close_all_sessions(self):
        """Test closing all sessions in the connection pool."""
        # Arrange
        pool = ConnectionPool(
            max_connections=10,
            max_connections_per_host=5,
            timeout=30,
            keep_alive=120
        )
        
        # Create multiple sessions
        await pool.create_session("session1")
        await pool.create_session("session2")
        await pool.create_session("session3")
        
        # Act
        count = await pool.close_all_sessions()
        
        # Assert
        assert count == 3
        assert len(pool.sessions) == 0

    @pytest.mark.asyncio
    async def test_session_context_manager(self):
        """Test using the session context manager."""
        # Arrange
        pool = ConnectionPool(
            max_connections=10,
            max_connections_per_host=5,
            timeout=30,
            keep_alive=120
        )
        
        # Act & Assert
        async with pool.session("test_session") as session:
            assert session is not None
            assert isinstance(session, ClientSession)
            assert "test_session" in pool.sessions
        
        # Session should still exist after context exit (managed by the pool)
        assert "test_session" in pool.sessions
        
        # Clean up
        await pool.close_all_sessions()


class TestOptimizedHttpClient:
    """Test class for optimized HTTP client functionality."""

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_request(self, mock_get):
        """Test making a GET request with the optimized HTTP client."""
        # Arrange
        mock_response = MagicMock()
        mock_get.return_value.__aenter__.return_value = mock_response
        
        pool = ConnectionPool(
            max_connections=10,
            max_connections_per_host=5,
            timeout=30,
            keep_alive=120
        )
        
        # Act
        async with OptimizedHttpClient(pool, "test_client") as client:
            response = await client.get("https://example.com")
        
        # Assert
        assert response == mock_response
        mock_get.assert_called_once()
        
        # Clean up
        await pool.close_all_sessions()

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_post_request(self, mock_post):
        """Test making a POST request with the optimized HTTP client."""
        # Arrange
        mock_response = MagicMock()
        mock_post.return_value.__aenter__.return_value = mock_response
        
        pool = ConnectionPool(
            max_connections=10,
            max_connections_per_host=5,
            timeout=30,
            keep_alive=120
        )
        
        # Act
        async with OptimizedHttpClient(pool, "test_client") as client:
            response = await client.post(
                "https://example.com",
                data={"key": "value"},
                json={"json_key": "json_value"}
            )
        
        # Assert
        assert response == mock_response
        mock_post.assert_called_once()
        
        # Clean up
        await pool.close_all_sessions()

    @pytest.mark.asyncio
    async def test_client_headers_merging(self):
        """Test that headers are properly merged in the HTTP client."""
        # Arrange
        pool = ConnectionPool()
        default_headers = {"User-Agent": "Test Agent", "Accept": "application/json"}
        request_headers = {"Authorization": "Bearer token", "Accept": "text/html"}
        
        # Mock the session's get method
        mock_session = MagicMock()
        mock_session.get = AsyncMock()
        
        # Create a client with the mocked session
        client = OptimizedHttpClient(pool, "test_client", headers=default_headers)
        client.session = mock_session
        
        # Act
        await client.get("https://example.com", headers=request_headers)
        
        # Assert
        # The Accept header in request_headers should override the one in default_headers
        expected_headers = {
            "User-Agent": "Test Agent",
            "Accept": "text/html",
            "Authorization": "Bearer token"
        }
        
        # Check that the merged headers were passed to the get method
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args[1]
        assert "headers" in call_args
        assert call_args["headers"] == expected_headers


class TestConcurrentFetching:
    """Test class for concurrent fetching functionality."""

    @pytest.fixture
    def downloader(self):
        """Create a SubstackDirectDownloader instance for testing."""
        return SubstackDirectDownloader(
            author="testauthor",
            output_dir="test_output",
            max_concurrency=5
        )

    @pytest.mark.asyncio
    async def test_semaphore_limiting(self, downloader):
        """Test that the semaphore properly limits concurrent requests."""
        # Arrange
        # Create a mock for _fetch_url that sleeps to simulate network delay
        original_fetch_url = downloader._fetch_url
        
        fetch_count = 0
        fetch_concurrent = 0
        max_concurrent = 0
        
        async def mock_fetch_url(url, retries=3):
            nonlocal fetch_count, fetch_concurrent, max_concurrent
            fetch_count += 1
            fetch_concurrent += 1
            max_concurrent = max(max_concurrent, fetch_concurrent)
            
            # Simulate network delay
            await asyncio.sleep(0.1)
            
            fetch_concurrent -= 1
            return f"Content for {url}"
        
        downloader._fetch_url = mock_fetch_url
        
        # Initialize the semaphore
        downloader.semaphore = asyncio.Semaphore(downloader.connection_pool.max_connections)
        
        # Act
        # Create 10 tasks to fetch URLs concurrently
        urls = [f"https://example.com/page{i}" for i in range(10)]
        tasks = [downloader._fetch_url(url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        # Assert
        assert len(results) == 10
        assert fetch_count == 10
        # The max concurrent fetches should be limited by the semaphore
        assert max_concurrent <= downloader.connection_pool.max_connections
        
        # Restore the original method
        downloader._fetch_url = original_fetch_url

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_concurrent_post_downloads(self, mock_get, downloader):
        """Test concurrent downloading of multiple posts."""
        # Arrange
        # Mock the response for each URL
        mock_responses = {}
        
        for i in range(5):
            url = f"https://testauthor.substack.com/p/post{i}"
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=f"<html><body><h1 class='post-title'>Post {i}</h1><time>January {i+1}, 2023</time><div class='post-content'>Content {i}</div></body></html>")
            mock_responses[url] = mock_response
        
        # Set up the mock to return the appropriate response for each URL
        async def side_effect(url, **kwargs):
            mock_resp = mock_responses.get(url, MagicMock())
            mock_resp.__aenter__.return_value = mock_resp
            return mock_resp
        
        mock_get.side_effect = side_effect
        
        # Mock methods that would be called during download
        downloader._store_post_metadata = MagicMock(return_value=True)
        downloader.extract_image_urls = AsyncMock(return_value=set())
        
        # Create a temporary directory for output
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader.output_dir = temp_dir
            
            # Initialize the session and semaphore
            connector = aiohttp.TCPConnector(
                limit=downloader.connection_pool.max_connections,
                limit_per_host=downloader.connection_pool.max_connections_per_host,
                keepalive_timeout=downloader.connection_pool.keep_alive
            )
            
            downloader.session = aiohttp.ClientSession(connector=connector)
            downloader.semaphore = asyncio.Semaphore(downloader.connection_pool.max_connections)
            
            # Act
            # Download multiple posts concurrently
            urls = [f"https://testauthor.substack.com/p/post{i}" for i in range(5)]
            tasks = [downloader.download_post(url, force=True) for url in urls]
            results = await asyncio.gather(*tasks)
            
            # Assert
            assert all(results)  # All downloads should succeed
            
            # Check that files were created
            files = os.listdir(temp_dir)
            assert len(files) == 5
            
            # Close the session
            await downloader.session.close()

    @pytest.mark.asyncio
    async def test_adaptive_throttling_integration(self):
        """Test integration with adaptive throttling."""
        # Arrange
        throttler = AsyncAdaptiveThrottler(min_delay=0.1, max_delay=1.0)
        
        # Mock the current time to control the timing
        original_time = time.time
        time_values = [100.0, 100.5]  # 0.5 seconds response time
        time_index = 0
        
        def mock_time():
            nonlocal time_index
            result = time_values[time_index]
            if time_index < len(time_values) - 1:
                time_index += 1
            return result
        
        import time
        time.time = mock_time
        
        # Act
        # First request - should use min_delay
        await throttler.async_throttle("example.com")
        
        # Update with a good response
        await throttler.update_from_response(
            status_code=200,
            response_time=0.5,
            rate_limit_headers={},
            domain="example.com"
        )
        
        # Get the delay for the next request
        delay = throttler.get_delay("example.com")
        
        # Reset the mock
        time.time = original_time
        
        # Assert
        # The delay should be adjusted based on the response time
        assert delay >= throttler.min_delay
        assert delay <= throttler.max_delay
        
        # The delay should be related to the response time
        assert abs(delay - 0.5) < 0.5  # Should be close to the response time


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
