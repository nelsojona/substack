#!/usr/bin/env python3
"""
Tests for the connection_pool module.
"""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock

import aiohttp
from aiohttp import ClientSession, TCPConnector, ClientTimeout

from connection_pool import ConnectionPool, OptimizedHttpClient


class TestConnectionPool(unittest.IsolatedAsyncioTestCase):
    """Test cases for the ConnectionPool class."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create a connection pool
        self.pool = ConnectionPool(
            max_connections=50,
            max_connections_per_host=5,
            timeout=10,
            keep_alive=60
        )
    
    async def asyncTearDown(self):
        """Tear down test fixtures."""
        # Close all sessions
        await self.pool.close_all_sessions()
    
    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.pool.max_connections, 50)
        self.assertEqual(self.pool.max_connections_per_host, 5)
        self.assertEqual(self.pool.timeout, 10)
        self.assertEqual(self.pool.keep_alive, 60)
        self.assertEqual(len(self.pool.sessions), 0)
        self.assertGreater(len(self.pool.user_agents), 0)
    
    def test_get_random_user_agent(self):
        """Test getting a random user agent."""
        user_agent = self.pool.get_random_user_agent()
        self.assertIn(user_agent, self.pool.user_agents)
    
    async def test_create_session(self):
        """Test creating a session."""
        # Create a session directly
        session = await self.pool.create_session("test_session")
        
        # Check the result
        self.assertIsNotNone(session)
        self.assertIn("test_session", self.pool.sessions)
        
        # Verify it's an aiohttp ClientSession
        self.assertIsInstance(session, aiohttp.ClientSession)
        
        # Clean up by closing the session
        await session.close()
    
    async def test_get_session(self):
        """Test getting a session."""
        # Create a session directly
        created_session = await self.pool.create_session("test_session")
        
        # Get the session
        session = await self.pool.get_session("test_session")
        
        # Check the result - should get the same session we created
        self.assertEqual(session, created_session)
        
        # Get a non-existent session
        session = await self.pool.get_session("nonexistent_session")
        self.assertIsNone(session)
        
        # Close the session
        await created_session.close()
        
        # Get a closed session
        session = await self.pool.get_session("test_session")
        self.assertIsNone(session)
    
    async def test_get_or_create_session(self):
        """Test getting or creating a session."""
        # Get or create a session (should create)
        session1 = await self.pool.get_or_create_session("test_session")
        
        # Check the result
        self.assertIsNotNone(session1)
        self.assertIn("test_session", self.pool.sessions)
        
        # Get or create the same session (should get)
        session2 = await self.pool.get_or_create_session("test_session")
        
        # Check the result - should be the same object
        self.assertEqual(session1, session2)
        
        # Close the sessions to clean up
        await session1.close()
    
    async def test_session_context_manager(self):
        """Test using the session context manager."""
        # Use the session context manager
        async with self.pool.session("test_session") as session:
            # Check the result
            self.assertIsNotNone(session)
            self.assertIn("test_session", self.pool.sessions)
            self.assertIsInstance(session, aiohttp.ClientSession)
            
        # Session should still be in the pool (not closed by context manager)
        self.assertIn("test_session", self.pool.sessions)
        
        # Get the session and close it to clean up
        session = self.pool.sessions["test_session"]
        if not session.closed:
            await session.close()
    
    async def test_close_session(self):
        """Test closing a session."""
        # Create a session
        session = await self.pool.create_session("test_session")
        
        # Make sure it's in the pool
        self.assertIn("test_session", self.pool.sessions)
        
        # Close the session
        result = await self.pool.close_session("test_session")
        
        # Check the result
        self.assertTrue(result)
        self.assertNotIn("test_session", self.pool.sessions)
        self.assertTrue(session.closed)
    
    async def test_close_all_sessions(self):
        """Test closing all sessions."""
        # Create multiple sessions
        session1 = await self.pool.create_session("test_session1")
        session2 = await self.pool.create_session("test_session2")
        
        # Make sure they're in the pool
        self.assertEqual(len(self.pool.sessions), 2)
        
        # Close all sessions
        count = await self.pool.close_all_sessions()
        
        # Check the result
        self.assertEqual(count, 2)
        self.assertEqual(len(self.pool.sessions), 0)
        self.assertTrue(session1.closed)
        self.assertTrue(session2.closed)


class TestOptimizedHttpClient(unittest.IsolatedAsyncioTestCase):
    """Test cases for the OptimizedHttpClient class."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create a connection pool
        self.pool = ConnectionPool(
            max_connections=50,
            max_connections_per_host=5,
            timeout=10,
            keep_alive=60
        )
        
        # Create an HTTP client
        self.client = OptimizedHttpClient(
            pool=self.pool,
            session_name="test_client",
            headers={"User-Agent": "Test User Agent"},
            timeout=20
        )
    
    async def asyncTearDown(self):
        """Tear down test fixtures."""
        # Close all sessions
        await self.pool.close_all_sessions()
    
    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.client.pool, self.pool)
        self.assertEqual(self.client.session_name, "test_client")
        self.assertEqual(self.client.default_headers, {"User-Agent": "Test User Agent"})
        self.assertEqual(self.client.default_timeout, 20)
    
    @patch.object(ConnectionPool, 'get_or_create_session')
    async def test_context_manager(self, mock_get_or_create_session):
        """Test using the client as a context manager."""
        # Mock the get_or_create_session method
        mock_session = MagicMock()
        mock_get_or_create_session.return_value = mock_session
        
        # Use the client as a context manager
        async with self.client as client:
            # Check the result
            self.assertEqual(client.session, mock_session)
        
        # Check that get_or_create_session was called with the correct arguments
        mock_get_or_create_session.assert_called_once_with(
            "test_client",
            headers={"User-Agent": "Test User Agent"},
            cookies={},
            timeout=20
        )
    
    @patch.object(ConnectionPool, 'get_or_create_session')
    async def test_get(self, mock_get_or_create_session):
        """Test making a GET request."""
        # Mock the get_or_create_session method
        mock_session = MagicMock()
        mock_session.get = AsyncMock()
        mock_get_or_create_session.return_value = mock_session
        
        # Set the session
        self.client.session = mock_session
        
        # Make a GET request
        await self.client.get(
            url="https://example.com",
            headers={"Accept": "application/json"},
            params={"param": "value"},
            timeout=30
        )
        
        # Check that session.get was called with the correct arguments
        mock_session.get.assert_called_once_with(
            "https://example.com",
            headers={"User-Agent": "Test User Agent", "Accept": "application/json"},
            params={"param": "value"},
            timeout=30
        )
    
    @patch.object(ConnectionPool, 'get_or_create_session')
    async def test_post(self, mock_get_or_create_session):
        """Test making a POST request."""
        # Mock the get_or_create_session method
        mock_session = MagicMock()
        mock_session.post = AsyncMock()
        mock_get_or_create_session.return_value = mock_session
        
        # Set the session
        self.client.session = mock_session
        
        # Make a POST request
        await self.client.post(
            url="https://example.com",
            headers={"Content-Type": "application/json"},
            data={"key": "value"},
            json={"json_key": "json_value"},
            params={"param": "value"},
            timeout=30
        )
        
        # Check that session.post was called with the correct arguments
        mock_session.post.assert_called_once_with(
            "https://example.com",
            headers={"User-Agent": "Test User Agent", "Content-Type": "application/json"},
            data={"key": "value"},
            json={"json_key": "json_value"},
            params={"param": "value"},
            timeout=30
        )


if __name__ == '__main__':
    unittest.main()
