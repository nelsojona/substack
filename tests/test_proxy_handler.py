#!/usr/bin/env python3
"""
Tests for proxy handler functionality.

This module tests the proxy handler features of the Substack to Markdown CLI,
specifically for integrating with Oxylabs proxy service.
"""

import os
import sys
import pytest
import urllib.request
from unittest.mock import patch, MagicMock

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.proxy_handler import OxylabsProxyHandler
from src.utils.env_loader import get_oxylabs_config
from src.utils.connection_pool import ConnectionPool
from src.core.substack_direct_downloader import SubstackDirectDownloader


class TestProxyHandler:
    """Test class for proxy handler functionality."""

    def test_build_proxy_url_basic(self):
        """Test building a basic proxy URL with just username and password."""
        # Arrange
        handler = OxylabsProxyHandler(
            username="testuser",
            password="testpass"
        )
        
        # Act
        url = handler.proxy_url
        
        # Assert
        assert url == "http://customer-testuser:testpass@pr.oxylabs.io:7777"
    
    def test_build_proxy_url_with_country(self):
        """Test building a proxy URL with country code."""
        # Arrange
        handler = OxylabsProxyHandler(
            username="testuser",
            password="testpass",
            country_code="US"
        )
        
        # Act
        url = handler.proxy_url
        
        # Assert
        assert url == "http://customer-testuser-cc-US:testpass@pr.oxylabs.io:7777"
    
    def test_build_proxy_url_with_city(self):
        """Test building a proxy URL with country and city."""
        # Arrange
        handler = OxylabsProxyHandler(
            username="testuser",
            password="testpass",
            country_code="US",
            city="new york"
        )
        
        # Act
        url = handler.proxy_url
        
        # Assert
        assert url == "http://customer-testuser-cc-US-city-new_york:testpass@pr.oxylabs.io:7777"
    
    def test_build_proxy_url_with_state(self):
        """Test building a proxy URL with state."""
        # Arrange
        handler = OxylabsProxyHandler(
            username="testuser",
            password="testpass",
            country_code="US",
            state="us_new_york"
        )
        
        # Act
        url = handler.proxy_url
        
        # Assert
        assert url == "http://customer-testuser-cc-US-st-us_new_york:testpass@pr.oxylabs.io:7777"
    
    def test_build_proxy_url_with_session(self):
        """Test building a proxy URL with session ID and time."""
        # Arrange
        handler = OxylabsProxyHandler(
            username="testuser",
            password="testpass",
            session_id="test123",
            session_time=10
        )
        
        # Act
        url = handler.proxy_url
        
        # Assert
        assert url == "http://customer-testuser-sessid-test123-sesstime-10:testpass@pr.oxylabs.io:7777"
    
    def test_build_proxy_url_with_all_options(self):
        """Test building a proxy URL with all options."""
        # Arrange
        handler = OxylabsProxyHandler(
            username="testuser",
            password="testpass",
            country_code="US",
            city="new york",
            state="us_new_york",
            session_id="test123",
            session_time=10
        )
        
        # Act
        url = handler.proxy_url
        
        # Assert
        assert "customer-testuser" in url
        assert "cc-US" in url
        assert "city-new_york" in url
        assert "st-us_new_york" in url
        assert "sessid-test123" in url
        assert "sesstime-10" in url
    
    def test_get_proxy_handler(self):
        """Test getting a proxy handler for urllib."""
        # Arrange
        handler = OxylabsProxyHandler(
            username="testuser",
            password="testpass"
        )
        
        # Act
        proxy_handler = handler.get_proxy_handler()
        
        # Assert
        assert isinstance(proxy_handler, urllib.request.ProxyHandler)
        assert "http" in proxy_handler.proxies
        assert "https" in proxy_handler.proxies
    
    def test_get_proxy_dict(self):
        """Test getting a proxy dictionary for requests."""
        # Arrange
        handler = OxylabsProxyHandler(
            username="testuser",
            password="testpass"
        )
        
        # Act
        proxy_dict = handler.get_proxy_dict()
        
        # Assert
        assert isinstance(proxy_dict, dict)
        assert "http" in proxy_dict
        assert "https" in proxy_dict
        assert proxy_dict["http"] == proxy_dict["https"]
        assert proxy_dict["http"] == handler.proxy_url
    
    def test_get_aiohttp_proxy(self):
        """Test getting a proxy URL for aiohttp."""
        # Arrange
        handler = OxylabsProxyHandler(
            username="testuser",
            password="testpass"
        )
        
        # Act
        proxy_url = handler.get_aiohttp_proxy()
        
        # Assert
        assert proxy_url == handler.proxy_url


class TestConnectionPoolWithProxy:
    """Test class for connection pool with proxy integration."""

    def test_connection_pool_with_proxy(self):
        """Test creating a connection pool with proxy."""
        # Arrange
        proxy_config = {
            'username': 'testuser',
            'password': 'testpass',
            'country_code': 'US'
        }
        
        # Act
        pool = ConnectionPool(
            max_connections=10,
            use_proxy=True,
            proxy_config=proxy_config
        )
        
        # Assert
        assert pool.use_proxy is True
        assert pool.proxy_handler is not None
        assert pool.proxy_handler.username == 'testuser'
        assert pool.proxy_handler.password == 'testpass'
        assert pool.proxy_handler.country_code == 'US'
    
    def test_connection_pool_without_proxy(self):
        """Test creating a connection pool without proxy."""
        # Act
        pool = ConnectionPool(max_connections=10)
        
        # Assert
        assert pool.use_proxy is False
        assert pool.proxy_handler is None
    
    def test_connection_pool_with_invalid_proxy_config(self):
        """Test creating a connection pool with invalid proxy config."""
        # Arrange
        proxy_config = {
            # Missing username and password
            'country_code': 'US'
        }
        
        # Act
        pool = ConnectionPool(
            max_connections=10,
            use_proxy=True,
            proxy_config=proxy_config
        )
        
        # Assert
        assert pool.use_proxy is True
        assert pool.proxy_handler is not None
        # Should still create a handler with empty username/password
        assert pool.proxy_handler.username == ''
        assert pool.proxy_handler.password == ''
        assert pool.proxy_handler.country_code == 'US'


class TestSubstackDirectDownloaderWithProxy:
    """Test class for SubstackDirectDownloader with proxy integration."""

    def test_downloader_with_proxy(self):
        """Test creating a downloader with proxy."""
        # Arrange
        proxy_config = {
            'username': 'testuser',
            'password': 'testpass',
            'country_code': 'US'
        }
        
        # Act
        downloader = SubstackDirectDownloader(
            author="testauthor",
            use_proxy=True,
            proxy_config=proxy_config
        )
        
        # Assert
        assert downloader.use_proxy is True
        assert downloader.proxy_config is not None
        assert downloader.proxy_config['username'] == 'testuser'
        assert downloader.proxy_config['password'] == 'testpass'
        assert downloader.proxy_config['country_code'] == 'US'
        assert downloader.connection_pool.use_proxy is True
        assert downloader.connection_pool.proxy_handler is not None
    
    def test_downloader_without_proxy(self):
        """Test creating a downloader without proxy."""
        # Act
        downloader = SubstackDirectDownloader(author="testauthor")
        
        # Assert
        assert downloader.use_proxy is False
        assert downloader.proxy_config is None
        assert downloader.connection_pool.use_proxy is False
        assert downloader.connection_pool.proxy_handler is None
    
    def test_downloader_with_invalid_proxy_config(self):
        """Test creating a downloader with invalid proxy config."""
        # Act
        downloader = SubstackDirectDownloader(
            author="testauthor",
            use_proxy=True,
            proxy_config=None  # Invalid config
        )
        
        # Assert
        # Should disable proxy if config is invalid
        assert downloader.use_proxy is False
        assert downloader.proxy_config is None
        assert downloader.connection_pool.use_proxy is False
        assert downloader.connection_pool.proxy_handler is None
    
    @patch('src.utils.env_loader.get_oxylabs_config')
    def test_downloader_with_env_proxy_config(self, mock_get_config):
        """Test creating a downloader with proxy config from environment."""
        # Arrange
        mock_get_config.return_value = {
            'username': 'envuser',
            'password': 'envpass',
            'country_code': 'GB'
        }
        
        # Act
        downloader = SubstackDirectDownloader(
            author="testauthor",
            use_proxy=True,
            proxy_config=None  # Will try to load from environment
        )
        
        # Assert
        assert downloader.use_proxy is True
        assert downloader.proxy_config is not None
        assert downloader.proxy_config['username'] == 'envuser'
        assert downloader.proxy_config['password'] == 'envpass'
        assert downloader.proxy_config['country_code'] == 'GB'
        assert downloader.connection_pool.use_proxy is True
        assert downloader.connection_pool.proxy_handler is not None


class TestEnvLoaderIntegration:
    """Test class for environment loader integration with proxy."""

    @patch('os.getenv')
    def test_get_oxylabs_config(self, mock_getenv):
        """Test getting Oxylabs config from environment variables."""
        # Arrange
        mock_getenv.side_effect = lambda key, default=None: {
            'OXYLABS_USERNAME': 'envuser',
            'OXYLABS_PASSWORD': 'envpass',
            'OXYLABS_COUNTRY': 'GB',
            'OXYLABS_CITY': 'london',
            'OXYLABS_STATE': 'uk_london',
            'OXYLABS_SESSION_ID': 'envsession',
            'OXYLABS_SESSION_TIME': '15'
        }.get(key, default)
        
        # Act
        config = get_oxylabs_config()
        
        # Assert
        assert config['username'] == 'envuser'
        assert config['password'] == 'envpass'
        assert config['country_code'] == 'GB'
        assert config['city'] == 'london'
        assert config['state'] == 'uk_london'
        assert config['session_id'] == 'envsession'
        assert config['session_time'] == 15
    
    @patch('os.getenv')
    def test_get_oxylabs_config_empty(self, mock_getenv):
        """Test getting Oxylabs config with empty environment variables."""
        # Arrange
        mock_getenv.return_value = ''
        
        # Act
        config = get_oxylabs_config()
        
        # Assert
        assert config['username'] == ''
        assert config['password'] == ''
        assert config['country_code'] == ''
        assert config['city'] == ''
        assert config['state'] == ''
        assert config['session_id'] == ''
        assert config['session_time'] is None


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
