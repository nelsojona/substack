#!/usr/bin/env python3
"""
Tests for subscriber-only content functionality.

This module tests the features related to accessing and exporting subscriber-only content
from Substack, including authentication, token handling, and private content extraction.
"""

import os
import sys
import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.substack_direct_downloader import SubstackDirectDownloader


class TestSubscriberOnlyContent:
    """Test class for subscriber-only content functionality."""

    @pytest.fixture
    def downloader(self):
        """Create a SubstackDirectDownloader instance for testing."""
        return SubstackDirectDownloader(
            author="testauthor",
            output_dir="test_output"
        )

    def test_set_auth_token(self, downloader):
        """Test setting the authentication token."""
        # Arrange
        test_token = "test_auth_token_123"
        
        # Act
        downloader.set_auth_token(test_token)
        
        # Assert
        assert downloader.auth_token == test_token

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_update_session_cookies(self, mock_session_class, downloader):
        """Test that session cookies are updated when auth token is set."""
        # Arrange
        mock_session = MagicMock()
        mock_cookie_jar = MagicMock()
        mock_session.cookie_jar = mock_cookie_jar
        downloader.session = mock_session
        
        test_token = "test_auth_token_123"
        
        # Act
        downloader.set_auth_token(test_token)
        
        # Assert
        mock_cookie_jar.update_cookies.assert_called_once()
        # Check that the correct cookies were set
        cookies_dict = mock_cookie_jar.update_cookies.call_args[0][0]
        assert cookies_dict["substack.sid"] == test_token
        assert cookies_dict["substack-sid"] == test_token
        assert cookies_dict["substack.authpub"] == downloader.author
        assert cookies_dict["substack-auth"] == "1"

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    async def test_direct_fetch_with_auth(self, mock_fetch, downloader):
        """Test direct fetch method with authentication."""
        # Arrange
        # Set auth token
        downloader.set_auth_token("test_auth_token_123")
        
        # Mock the session's get method
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "post123",
            "title": "Subscriber Only Post",
            "body_html": "<p>This is premium content</p>",
            "published_at": "2023-01-01T12:00:00Z",
            "audience": "paid"
        })
        
        # Create a mock session
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        downloader.session = mock_session
        
        # Act
        result = await downloader.direct_fetch("https://testauthor.substack.com/p/subscriber-only-post")
        
        # Assert
        assert result is not None
        assert result["title"] == "Subscriber Only Post"
        assert result["content_html"] == "<p>This is premium content</p>"
        assert result["date"] == "2023-01-01"
        assert "html" in result
        
        # Check that the session's get method was called with the correct URL
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args[0]
        assert "https://testauthor.substack.com/api/v1/posts/subscriber-only-post" in call_args

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    async def test_download_subscriber_only_post(self, mock_fetch, downloader, tmp_path):
        """Test downloading a subscriber-only post."""
        # Arrange
        # Set auth token
        downloader.set_auth_token("test_auth_token_123")
        downloader.output_dir = str(tmp_path)
        os.makedirs(downloader.output_dir, exist_ok=True)
        
        # Mock direct_fetch to return subscriber-only content
        mock_post_data = {
            "title": "Subscriber Only Post",
            "date": "2023-01-01",
            "author": "testauthor",
            "url": "https://testauthor.substack.com/p/subscriber-only-post",
            "content_html": "<p>This is premium content</p>",
            "html": "<p>This is premium content</p>"
        }
        downloader.direct_fetch = AsyncMock(return_value=mock_post_data)
        
        # Mock other methods that would be called
        downloader._store_post_metadata = MagicMock(return_value=True)
        downloader.extract_image_urls = AsyncMock(return_value=set())
        
        # Act
        result = await downloader.download_post(
            url="https://testauthor.substack.com/p/subscriber-only-post",
            force=True,
            use_direct=True
        )
        
        # Assert
        assert result is True
        
        # Check that the file was created
        files = os.listdir(str(tmp_path))
        assert len(files) == 1
        
        # Read the file and check its content
        with open(os.path.join(str(tmp_path), files[0]), 'r', encoding='utf-8') as f:
            content = f.read()
            assert "Subscriber Only Post" in content
            assert "This is premium content" in content

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    async def test_tradecompanion_direct_fetch(self, mock_fetch, downloader):
        """Test the special Trade Companion fetch method."""
        # Arrange
        # Set auth token
        downloader.set_auth_token("test_auth_token_123")
        downloader.author = "tradecompanion"
        
        # Mock the session's get method
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "post123",
            "title": "Trade Analysis",
            "body_html": "<p>This is trade analysis content</p>",
            "published_at": "2023-01-01T12:00:00Z"
        })
        
        # Create a mock session
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        downloader.session = mock_session
        
        # Act
        result = await downloader.tradecompanion_direct_fetch("https://tradecompanion.substack.com/p/trade-analysis")
        
        # Assert
        assert result is not None
        assert "<!DOCTYPE html>" in result
        assert "<title>Trade Analysis</title>" in result
        assert "<h1 class=\"post-title\">Trade Analysis</h1>" in result
        assert "<p>This is trade analysis content</p>" in result
        
        # Check that the session's get method was called with the correct URL and headers
        mock_session.get.assert_called_once()
        call_args, call_kwargs = mock_session.get.call_args
        assert "https://tradecompanion.substack.com/api/v1/posts/trade-analysis" in call_args
        assert "headers" in call_kwargs
        assert "cookies" in call_kwargs
        assert call_kwargs["headers"]["Accept"] == "application/json"
        assert call_kwargs["cookies"]["substack.sid"] == "test_auth_token_123"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_session_initialization_with_auth(self, mock_session_class, downloader):
        """Test that the session is initialized with auth cookies when token is set."""
        # Arrange
        # Set auth token before session initialization
        test_token = "test_auth_token_123"
        downloader.set_auth_token(test_token)
        
        # Mock ClientSession constructor
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Act
        # Initialize session via __aenter__
        await downloader.__aenter__()
        
        # Assert
        # Check that ClientSession was called with cookies
        mock_session_class.assert_called_once()
        call_kwargs = mock_session_class.call_args[1]
        assert "cookies" in call_kwargs
        cookies = call_kwargs["cookies"]
        assert cookies["substack.sid"] == test_token
        assert cookies["substack-sid"] == test_token
        assert cookies["substack.authpub"] == downloader.author
        assert cookies["substack-auth"] == "1"
        
        # Clean up
        await downloader.__aexit__(None, None, None)

    @pytest.mark.asyncio
    @patch("src.core.substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    async def test_fallback_to_normal_fetch_when_direct_fails(self, mock_fetch, downloader):
        """Test fallback to normal fetch when direct fetch fails."""
        # Arrange
        # Set auth token
        downloader.set_auth_token("test_auth_token_123")
        
        # Mock direct_fetch to return None (failure)
        downloader.direct_fetch = AsyncMock(return_value=None)
        
        # Mock tradecompanion_direct_fetch to return None (not applicable)
        downloader.tradecompanion_direct_fetch = AsyncMock(return_value=None)
        
        # Mock _fetch_url to return HTML
        mock_fetch.return_value = """
        <html>
        <body>
            <h1 class="post-title">Fallback Post</h1>
            <time>January 1, 2023</time>
            <div class="post-content">Fallback content</div>
        </body>
        </html>
        """
        
        # Mock other methods that would be called
        downloader._store_post_metadata = MagicMock(return_value=True)
        downloader.extract_image_urls = AsyncMock(return_value=set())
        
        # Create a temporary directory for output
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader.output_dir = temp_dir
            
            # Act
            result = await downloader.download_post(
                url="https://testauthor.substack.com/p/fallback-post",
                force=True,
                use_direct=True  # Try direct first, but it will fail
            )
            
            # Assert
            assert result is True
            
            # Check that direct_fetch was called
            downloader.direct_fetch.assert_called_once()
            
            # Check that _fetch_url was called as fallback
            mock_fetch.assert_called_once()
            
            # Check that the file was created with fallback content
            files = os.listdir(temp_dir)
            assert len(files) == 1
            
            with open(os.path.join(temp_dir, files[0]), 'r', encoding='utf-8') as f:
                content = f.read()
                assert "Fallback Post" in content
                assert "Fallback content" in content


class TestTokenExtraction:
    """Test class for token extraction functionality."""

    @pytest.mark.parametrize("cookie_string,expected", [
        ("substack.sid=test_token; Path=/; Domain=.substack.com", "test_token"),
        ("other=value; substack.sid=test_token; more=stuff", "test_token"),
        ("substack.sid=complex%3Dtoken%26with%3Dencoding; Path=/", "complex=token&with=encoding"),
        ("no_token_here=value", None)
    ])
    def test_extract_token_from_cookie_string(self, cookie_string, expected):
        """Test extracting token from cookie string."""
        # Import the function directly from the script
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))
        from get_substack_token import extract_token_from_cookie_string
        
        # Act
        result = extract_token_from_cookie_string(cookie_string)
        
        # Assert
        assert result == expected

    @pytest.mark.parametrize("headers_string,expected", [
        ("Set-Cookie: substack.sid=test_token; Path=/; Domain=.substack.com", "test_token"),
        ("Header: value\nSet-Cookie: substack.sid=test_token; Path=/\nMore: headers", "test_token"),
        ("Set-Cookie: substack.sid=complex%3Dtoken%26with%3Dencoding; Path=/", "complex=token&with=encoding"),
        ("No-Token: here", None)
    ])
    def test_extract_token_from_headers_string(self, headers_string, expected):
        """Test extracting token from headers string."""
        # Import the function directly from the script
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))
        from get_substack_token import extract_token_from_headers_string
        
        # Act
        result = extract_token_from_headers_string(headers_string)
        
        # Assert
        assert result == expected

    @patch("requests.Session")
    def test_extract_token_with_http(self, mock_session_class):
        """Test extracting token using HTTP method."""
        # Import the function directly from the script
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))
        from get_substack_token import extract_token_with_http
        
        # Arrange
        # Mock the session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock responses
        mock_signin_response = MagicMock()
        mock_email_response = MagicMock()
        mock_login_response = MagicMock()
        
        # Set up response sequence
        mock_session.get.return_value = mock_signin_response
        mock_session.post.side_effect = [mock_email_response, mock_login_response]
        
        # Set up login response with cookies
        mock_login_response.status_code = 302
        mock_login_response.headers = {
            'Set-Cookie': 'substack.sid=http_test_token; Path=/; Domain=.substack.com'
        }
        
        # Act
        result = extract_token_with_http("test@example.com", "password123")
        
        # Assert
        assert result == "http_test_token"
        assert mock_session.get.call_count == 1
        assert mock_session.post.call_count == 2


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
