#!/usr/bin/env python3
"""
Tests for authentication functionality in the Substack to Markdown CLI tool.

This module contains tests for authenticating with Substack and accessing private content.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import tempfile
import http.cookiejar
import json

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from substack_fetcher import SubstackFetcher


class TestAuthentication(unittest.TestCase):
    """Tests for authentication functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.fetcher = SubstackFetcher(max_retries=1, retry_delay=0.01)
        
        # Sample authentication data
        self.email = "test@example.com"
        self.password = "password123"
        self.token = "test_token_12345"
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.cookies_file = os.path.join(self.temp_dir, "cookies.txt")
        
        # Sample cookies
        self.cookies = {
            "session": "test_session_cookie",
            "token": "test_token_cookie"
        }
        
        # Sample private post data
        self.private_post_data = {
            "id": 123,
            "title": "Private Test Post",
            "subtitle": "A private test post",
            "author": {"name": "Test Author"},
            "post_date": "2023-01-01T12:00:00Z",
            "canonical_url": "https://example.substack.com/p/private-test-post"
        }
        
        self.private_post_content = "<h1>Private Test Post</h1><p>This is private content.</p>"

    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary directory and its contents
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch('requests.Session.post')
    @patch('substack_fetcher.SubstackFetcher._verify_authentication')
    def test_authenticate_with_email_password(self, mock_verify, mock_post):
        """Test authentication with email and password."""
        # Set up mocks
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": self.token}
        mock_response.cookies = {"session": "test_session_cookie"}
        mock_post.return_value = mock_response
        mock_verify.return_value = True
        
        # Call the method
        result = self.fetcher.authenticate(email=self.email, password=self.password)
        
        # Assert that the method returned True
        self.assertTrue(result)
        
        # Assert that the session was updated
        self.assertEqual(self.fetcher.auth_token, self.token)
        self.assertTrue(self.fetcher.is_authenticated)
        
        # Assert that the post method was called with the correct arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["email"], self.email)
        self.assertEqual(kwargs["json"]["password"], self.password)

    @patch('requests.Session.post')
    @patch('substack_fetcher.SubstackFetcher._verify_authentication')
    def test_authenticate_with_email_password_failure(self, mock_verify, mock_post):
        """Test authentication failure with email and password."""
        # Set up mocks
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        mock_verify.return_value = False
        
        # Call the method
        result = self.fetcher.authenticate(email=self.email, password=self.password)
        
        # Assert that the method returned False
        self.assertFalse(result)
        
        # Assert that the session was not updated
        self.assertEqual(self.fetcher.auth_token, "")
        self.assertFalse(self.fetcher.is_authenticated)

    @patch('substack_fetcher.SubstackFetcher._verify_authentication')
    def test_authenticate_with_token(self, mock_verify):
        """Test authentication with token."""
        # Set up mock
        mock_verify.return_value = True
        
        # Call the method
        result = self.fetcher.authenticate(token=self.token)
        
        # Assert that the method returned True
        self.assertTrue(result)
        
        # Assert that the session was updated
        self.assertEqual(self.fetcher.auth_token, self.token)
        self.assertTrue(self.fetcher.is_authenticated)
        
        # Assert that the headers were updated
        self.assertEqual(self.fetcher.session.headers["Authorization"], f"Bearer {self.token}")

    @patch('substack_fetcher.SubstackFetcher._verify_authentication')
    def test_authenticate_with_cookies(self, mock_verify):
        """Test authentication with cookies dictionary."""
        # Set up mock
        mock_verify.return_value = True
        
        # Call the method
        result = self.fetcher.authenticate(cookies=self.cookies)
        
        # Assert that the method returned True
        self.assertTrue(result)
        
        # Assert that the session was updated
        self.assertEqual(self.fetcher.auth_cookies, self.cookies)
        self.assertTrue(self.fetcher.is_authenticated)
        
        # Assert that the cookies were set
        for name, value in self.cookies.items():
            self.assertEqual(self.fetcher.session.cookies.get(name), value)

    @patch('os.path.exists')
    @patch('http.cookiejar.MozillaCookieJar')
    @patch('substack_fetcher.SubstackFetcher._verify_authentication')
    def test_authenticate_with_cookies_file(self, mock_verify, mock_cookie_jar, mock_exists):
        """Test authentication with cookies file."""
        # Set up mocks
        mock_exists.return_value = True
        mock_verify.return_value = True
        
        # Call the method
        result = self.fetcher.authenticate(cookies_file=self.cookies_file)
        
        # Assert that the method returned True
        self.assertTrue(result)
        
        # Assert that the session was updated
        self.assertEqual(self.fetcher.cookies_file, self.cookies_file)
        self.assertTrue(self.fetcher.is_authenticated)
        
        # Assert that the cookie jar was loaded
        mock_cookie_jar.assert_called_once_with(self.cookies_file)
        mock_cookie_jar.return_value.load.assert_called_once()

    @patch('os.path.exists')
    def test_authenticate_with_nonexistent_cookies_file(self, mock_exists):
        """Test authentication with nonexistent cookies file."""
        # Set up mock
        mock_exists.return_value = False
        
        # Call the method
        result = self.fetcher.authenticate(cookies_file=self.cookies_file)
        
        # Assert that the method returned False
        self.assertFalse(result)
        
        # Assert that the session was not updated
        self.assertEqual(self.fetcher.cookies_file, "")
        self.assertFalse(self.fetcher.is_authenticated)

    @patch('requests.Session.get')
    def test_verify_authentication_success(self, mock_get):
        """Test verification of authentication success."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Call the method
        result = self.fetcher._verify_authentication()
        
        # Assert that the method returned True
        self.assertTrue(result)
        
        # Assert that the get method was called with the correct URL
        mock_get.assert_called_once_with("https://substack.com/api/v1/me")

    @patch('requests.Session.get')
    def test_verify_authentication_failure(self, mock_get):
        """Test verification of authentication failure."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        # Call the method
        result = self.fetcher._verify_authentication()
        
        # Assert that the method returned False
        self.assertFalse(result)

    @patch('os.makedirs')
    @patch('http.cookiejar.MozillaCookieJar')
    def test_save_cookies(self, mock_cookie_jar, mock_makedirs):
        """Test saving cookies to a file."""
        # Set up the fetcher
        self.fetcher.is_authenticated = True
        
        # Call the method
        result = self.fetcher.save_cookies(self.cookies_file)
        
        # Assert that the method returned True
        self.assertTrue(result)
        
        # Assert that the directory was created
        mock_makedirs.assert_called_once()
        
        # Assert that the cookie jar was saved
        mock_cookie_jar.assert_called_once_with(self.cookies_file)
        mock_cookie_jar.return_value.save.assert_called_once()

    def test_save_cookies_not_authenticated(self):
        """Test saving cookies when not authenticated."""
        # Set up the fetcher
        self.fetcher.is_authenticated = False
        
        # Call the method
        result = self.fetcher.save_cookies(self.cookies_file)
        
        # Assert that the method returned False
        self.assertFalse(result)

    @patch('requests.Session.get')
    def test_fetch_private_post_success(self, mock_get):
        """Test fetching a private post successfully."""
        # Set up the fetcher
        self.fetcher.is_authenticated = True
        
        # Set up mocks
        mock_response1 = MagicMock()
        mock_response1.status_code = 200
        mock_response1.json.return_value = self.private_post_data
        
        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.json.return_value = {"body_html": self.private_post_content}
        
        mock_get.side_effect = [mock_response1, mock_response2]
        
        # Call the method
        post_data, post_content = self.fetcher.fetch_private_post(
            "https://example.substack.com/p/private-test-post",
            verbose=True
        )
        
        # Assert that the method returned the expected data
        self.assertEqual(post_data, self.private_post_data)
        self.assertEqual(post_content, self.private_post_content)
        
        # Assert that the get method was called twice
        self.assertEqual(mock_get.call_count, 2)

    def test_fetch_private_post_not_authenticated(self):
        """Test fetching a private post when not authenticated."""
        # Set up the fetcher
        self.fetcher.is_authenticated = False
        
        # Call the method
        post_data, post_content = self.fetcher.fetch_private_post(
            "https://example.substack.com/p/private-test-post",
            verbose=True
        )
        
        # Assert that the method returned None, None
        self.assertIsNone(post_data)
        self.assertIsNone(post_content)

    @patch('requests.Session.get')
    def test_fetch_private_post_invalid_url(self, mock_get):
        """Test fetching a private post with an invalid URL."""
        # Set up the fetcher
        self.fetcher.is_authenticated = True
        
        # Call the method
        post_data, post_content = self.fetcher.fetch_private_post(
            "https://example.substack.com/invalid-url",
            verbose=True
        )
        
        # Assert that the method returned None, None
        self.assertIsNone(post_data)
        self.assertIsNone(post_content)
        
        # Assert that the get method was not called
        mock_get.assert_not_called()

    @patch('requests.Session.get')
    def test_fetch_private_post_api_error(self, mock_get):
        """Test fetching a private post with an API error."""
        # Set up the fetcher
        self.fetcher.is_authenticated = True
        
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        # Call the method
        post_data, post_content = self.fetcher.fetch_private_post(
            "https://example.substack.com/p/private-test-post",
            verbose=True
        )
        
        # Assert that the method returned None, None
        self.assertIsNone(post_data)
        self.assertIsNone(post_content)


if __name__ == '__main__':
    unittest.main()
