#!/usr/bin/env python3
"""
Tests for the adaptive_throttler module.
"""

import time
import asyncio
import unittest
from unittest.mock import patch, MagicMock

try:
    from unittest import IsolatedAsyncioTestCase
except ImportError:
    from tests.unittest_compat import IsolatedAsyncioTestCase

from src.utils.adaptive_throttler import AdaptiveThrottler


class TestAdaptiveThrottler(unittest.TestCase):
    """Test cases for the AdaptiveThrottler class."""

    def setUp(self):
        """Set up test fixtures."""
        self.throttler = AdaptiveThrottler(min_delay=0.1, max_delay=1.0)
    
    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.throttler.min_delay, 0.1)
        self.assertEqual(self.throttler.max_delay, 1.0)
        self.assertEqual(self.throttler.current_delay, 0.1)
        self.assertEqual(self.throttler.rate_limit_hits, 0)
        self.assertEqual(len(self.throttler.domains), 0)
    
    def test_register_domain(self):
        """Test registering a domain."""
        self.throttler.register_domain("example.com", min_delay=0.2, max_delay=2.0)
        
        self.assertIn("example.com", self.throttler.domains)
        self.assertEqual(self.throttler.domains["example.com"]["min_delay"], 0.2)
        self.assertEqual(self.throttler.domains["example.com"]["max_delay"], 2.0)
        self.assertEqual(self.throttler.domains["example.com"]["current_delay"], 0.2)
        self.assertEqual(self.throttler.domains["example.com"]["rate_limit_hits"], 0)
    
    def test_throttle(self):
        """Test throttling."""
        # Mock time.sleep to avoid actual delays
        with patch('time.sleep') as mock_sleep:
            # Test global throttling
            delay = self.throttler.throttle()
            self.assertGreaterEqual(delay, self.throttler.min_delay)
            self.assertLessEqual(delay, self.throttler.max_delay)
            
            # Test domain-specific throttling
            self.throttler.register_domain("example.com", min_delay=0.2, max_delay=2.0)
            delay = self.throttler.throttle("example.com")
            self.assertGreaterEqual(delay, 0.2)
            self.assertLessEqual(delay, 2.0)
    
    def test_update_from_response(self):
        """Test updating from response."""
        # Test rate limit hit
        self.throttler.update_from_response(status_code=429, response_time=0.5)
        self.assertEqual(self.throttler.rate_limit_hits, 1)
        self.assertGreater(self.throttler.current_delay, 0.1)
        
        # Test domain-specific rate limit hit
        self.throttler.register_domain("example.com")
        self.throttler.update_from_response(status_code=429, response_time=0.5, domain="example.com")
        self.assertEqual(self.throttler.domains["example.com"]["rate_limit_hits"], 1)
        self.assertGreater(self.throttler.domains["example.com"]["current_delay"], 
                          self.throttler.domains["example.com"]["min_delay"])
    
    def test_process_rate_limit_headers(self):
        """Test processing rate limit headers."""
        settings = {
            'min_delay': 0.1,
            'max_delay': 1.0,
            'current_delay': 0.1
        }
        
        # Test with low remaining requests
        headers = {
            'X-RateLimit-Limit': '100',
            'X-RateLimit-Remaining': '5',
            'X-RateLimit-Reset': str(int(time.time()) + 60)
        }
        
        self.throttler._process_rate_limit_headers(headers, settings)
        self.assertGreater(settings['current_delay'], 0.1)
    
    def test_get_stats(self):
        """Test getting stats."""
        # Test global stats
        stats = self.throttler.get_stats()
        self.assertEqual(stats['domain'], 'global')
        self.assertEqual(stats['min_delay'], 0.1)
        self.assertEqual(stats['max_delay'], 1.0)
        
        # Test domain-specific stats
        self.throttler.register_domain("example.com")
        stats = self.throttler.get_stats("example.com")
        self.assertEqual(stats['domain'], 'example.com')
        self.assertEqual(stats['min_delay'], 0.1)
        self.assertEqual(stats['max_delay'], 1.0)


class TestAsyncAdaptiveThrottler(IsolatedAsyncioTestCase):
    """Test cases for the async methods of AdaptiveThrottler."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.throttler = AdaptiveThrottler(min_delay=0.01, max_delay=0.1)
    
    async def test_async_throttle(self):
        """Test async throttling."""
        # Test global throttling
        delay = await self.throttler.async_throttle()
        self.assertGreaterEqual(delay, self.throttler.min_delay)
        self.assertLessEqual(delay, self.throttler.max_delay)
        
        # Test domain-specific throttling
        self.throttler.register_domain("example.com", min_delay=0.02, max_delay=0.2)
        delay = await self.throttler.async_throttle("example.com")
        self.assertGreaterEqual(delay, 0.02)
        self.assertLessEqual(delay, 0.2)


if __name__ == '__main__':
    unittest.main()
