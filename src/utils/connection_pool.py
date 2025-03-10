#!/usr/bin/env python3
"""
Connection Pool Module

This module provides connection pooling functionality for HTTP requests.
It configures aiohttp.ClientSession with connection pooling, reuses sessions across requests,
and optimizes keep-alive settings.
"""

import os
import random
import logging
import asyncio
from typing import Dict, List, Optional, Any, Union
from contextlib import asynccontextmanager

import aiohttp
from aiohttp import ClientSession, TCPConnector, ClientTimeout

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("connection_pool")

class ConnectionPool:
    """
    A class for managing connection pools for HTTP requests.
    
    Attributes:
        max_connections (int): Maximum number of connections in the pool.
        max_connections_per_host (int): Maximum number of connections per host.
        timeout (int): Timeout for HTTP requests in seconds.
        keep_alive (int): Keep-alive timeout in seconds.
        sessions (Dict[str, ClientSession]): Dictionary of named sessions.
        user_agents (List[str]): List of user agent strings to rotate.
    """
    
    def __init__(
        self,
        max_connections: int = 100,
        max_connections_per_host: int = 10,
        timeout: int = 30,
        keep_alive: int = 120
    ):
        """
        Initialize the ConnectionPool.
        
        Args:
            max_connections (int, optional): Maximum number of connections in the pool. 
                                           Defaults to 100.
            max_connections_per_host (int, optional): Maximum number of connections per host. 
                                                    Defaults to 10.
            timeout (int, optional): Timeout for HTTP requests in seconds. 
                                   Defaults to 30.
            keep_alive (int, optional): Keep-alive timeout in seconds. 
                                      Defaults to 120.
        """
        self.max_connections = max_connections
        self.max_connections_per_host = max_connections_per_host
        self.timeout = timeout
        self.keep_alive = keep_alive
        self.sessions: Dict[str, ClientSession] = {}
        
        # List of common user agents to rotate
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Android 11; Mobile; rv:68.0) Gecko/68.0 Firefox/89.0",
            "Mozilla/5.0 (Android 11; Mobile; LG-M255; rv:89.0) Gecko/89.0 Firefox/89.0"
        ]
    
    def get_random_user_agent(self) -> str:
        """
        Get a random user agent string.
        
        Returns:
            str: Random user agent string.
        """
        return random.choice(self.user_agents)
    
    async def create_session(
        self,
        name: str,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> ClientSession:
        """
        Create a new session with the given name.
        
        Args:
            name (str): Name of the session.
            headers (Optional[Dict[str, str]], optional): Headers to include in requests. 
                                                        Defaults to None.
            cookies (Optional[Dict[str, str]], optional): Cookies to include in requests. 
                                                        Defaults to None.
            timeout (Optional[int], optional): Timeout for requests in seconds. 
                                             Defaults to None (use self.timeout).
        
        Returns:
            ClientSession: The created session.
        """
        try:
            # Create a connector with the specified settings
            connector = TCPConnector(
                limit=self.max_connections,
                limit_per_host=self.max_connections_per_host,
                keepalive_timeout=self.keep_alive
            )
            
            # Set default headers if not provided
            if headers is None:
                headers = {}
            
            # Add a random user agent if not provided
            if "User-Agent" not in headers:
                headers["User-Agent"] = self.get_random_user_agent()
            
            # Create the session
            session = ClientSession(
                connector=connector,
                headers=headers,
                cookies=cookies,
                timeout=ClientTimeout(total=timeout or self.timeout)
            )
            
            # Store the session
            self.sessions[name] = session
            
            return session
        except Exception as e:
            logger.error(f"Error creating session {name}: {e}")
            raise
    
    async def get_session(self, name: str) -> Optional[ClientSession]:
        """
        Get a session by name.
        
        Args:
            name (str): Name of the session.
        
        Returns:
            Optional[ClientSession]: The session, or None if not found or closed.
        """
        try:
            session = self.sessions.get(name)
            
            # Check if the session exists and is not closed
            if session and not session.closed:
                return session
            
            # If the session is closed, remove it from the dict
            if session and session.closed:
                del self.sessions[name]
                
            return None
        except Exception as e:
            logger.error(f"Error getting session {name}: {e}")
            return None
    
    async def get_or_create_session(
        self,
        name: str,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> ClientSession:
        """
        Get a session by name, or create it if it doesn't exist.
        
        Args:
            name (str): Name of the session.
            headers (Optional[Dict[str, str]], optional): Headers to include in requests. 
                                                        Defaults to None.
            cookies (Optional[Dict[str, str]], optional): Cookies to include in requests. 
                                                        Defaults to None.
            timeout (Optional[int], optional): Timeout for requests in seconds. 
                                             Defaults to None (use self.timeout).
        
        Returns:
            ClientSession: The session.
        """
        try:
            # Try to get an existing session
            session = await self.get_session(name)
            
            # Create a new session if needed
            if session is None:
                session = await self.create_session(name, headers, cookies, timeout)
            
            return session
        except Exception as e:
            logger.error(f"Error getting or creating session {name}: {e}")
            # Create a new session as fallback
            return await self.create_session(name, headers, cookies, timeout)
    
    @asynccontextmanager
    async def session(
        self,
        name: str,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ):
        """
        Context manager for getting or creating a session.
        
        Args:
            name (str): Name of the session.
            headers (Optional[Dict[str, str]], optional): Headers to include in requests. 
                                                        Defaults to None.
            cookies (Optional[Dict[str, str]], optional): Cookies to include in requests. 
                                                        Defaults to None.
            timeout (Optional[int], optional): Timeout for requests in seconds. 
                                             Defaults to None (use self.timeout).
        
        Yields:
            ClientSession: The session.
        """
        session = None
        try:
            # Get or create the session
            session = await self.get_or_create_session(name, headers, cookies, timeout)
            
            # Yield the session
            yield session
        
        except Exception as e:
            logger.error(f"Error in session {name}: {e}")
            raise
        finally:
            pass  # Don't close the session here as it's managed by the pool
    
    async def close_session(self, name: str) -> bool:
        """
        Close a session by name.
        
        Args:
            name (str): Name of the session.
        
        Returns:
            bool: True if the session was closed, False if not found.
        """
        try:
            session = self.sessions.pop(name, None)
            
            if session:
                if not session.closed:
                    await session.close()
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error closing session {name}: {e}")
            return False
    
    async def close_all_sessions(self) -> int:
        """
        Close all sessions.
        
        Returns:
            int: Number of sessions closed.
        """
        count = 0
        
        try:
            # Close all sessions
            for name in list(self.sessions.keys()):
                if await self.close_session(name):
                    count += 1
            
            return count
        except Exception as e:
            logger.error(f"Error closing all sessions: {e}")
            return count


class OptimizedHttpClient:
    """
    A class for making optimized HTTP requests using a connection pool.
    
    Attributes:
        pool (ConnectionPool): The connection pool to use.
        session_name (str): Name of the session to use.
        default_headers (Dict[str, str]): Default headers to include in requests.
        default_timeout (int): Default timeout for requests in seconds.
        session (Optional[ClientSession]): The current session.
    """
    
    def __init__(
        self,
        pool: ConnectionPool,
        session_name: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30
    ):
        """
        Initialize the OptimizedHttpClient.
        
        Args:
            pool (ConnectionPool): The connection pool to use.
            session_name (str): Name of the session to use.
            headers (Optional[Dict[str, str]], optional): Default headers to include in requests. 
                                                        Defaults to None.
            timeout (int, optional): Default timeout for requests in seconds. 
                                   Defaults to 30.
        """
        self.pool = pool
        self.session_name = session_name
        self.default_headers = headers or {}
        self.default_timeout = timeout
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = await self.pool.get_or_create_session(
            self.session_name,
            headers=self.default_headers,
            cookies={},
            timeout=self.default_timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Don't close the session, as it's managed by the pool
        pass
    
    async def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> aiohttp.ClientResponse:
        """
        Make a GET request.
        
        Args:
            url (str): URL to request.
            headers (Optional[Dict[str, str]], optional): Headers to include in the request. 
                                                        Defaults to None.
            params (Optional[Dict[str, Any]], optional): Query parameters. 
                                                       Defaults to None.
            timeout (Optional[int], optional): Timeout for the request in seconds. 
                                             Defaults to None (use default_timeout).
        
        Returns:
            aiohttp.ClientResponse: The response.
        
        Raises:
            ValueError: If the session is not initialized.
        """
        if self.session is None:
            raise ValueError("Session not initialized. Use as a context manager.")
        
        # Merge headers
        merged_headers = self.default_headers.copy()
        if headers:
            merged_headers.update(headers)
        
        # Make the request
        return await self.session.get(
            url,
            headers=merged_headers,
            params=params,
            timeout=timeout
        )
    
    async def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> aiohttp.ClientResponse:
        """
        Make a POST request.
        
        Args:
            url (str): URL to request.
            headers (Optional[Dict[str, str]], optional): Headers to include in the request. 
                                                        Defaults to None.
            data (Optional[Dict[str, Any]], optional): Form data. 
                                                     Defaults to None.
            json (Optional[Dict[str, Any]], optional): JSON data. 
                                                     Defaults to None.
            params (Optional[Dict[str, Any]], optional): Query parameters. 
                                                       Defaults to None.
            timeout (Optional[int], optional): Timeout for the request in seconds. 
                                             Defaults to None (use default_timeout).
        
        Returns:
            aiohttp.ClientResponse: The response.
        
        Raises:
            ValueError: If the session is not initialized.
        """
        if self.session is None:
            raise ValueError("Session not initialized. Use as a context manager.")
        
        # Merge headers
        merged_headers = self.default_headers.copy()
        if headers:
            merged_headers.update(headers)
        
        # Make the request
        return await self.session.post(
            url,
            headers=merged_headers,
            data=data,
            json=json,
            params=params,
            timeout=timeout
        )


# Example usage
async def main():
    # Set up logging
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Create a connection pool
    pool = ConnectionPool(
        max_connections=100,
        max_connections_per_host=10,
        timeout=30,
        keep_alive=120
    )
    
    # Use the pool to make requests
    async with pool.session("example") as session:
        async with session.get("https://example.com") as response:
            print(f"Status: {response.status}")
            print(f"Content: {await response.text()}")
    
    # Use the optimized HTTP client
    async with OptimizedHttpClient(pool, "example_client") as client:
        async with await client.get("https://example.com") as response:
            print(f"Status: {response.status}")
            print(f"Content: {await response.text()}")
    
    # Close all sessions
    await pool.close_all_sessions()

if __name__ == "__main__":
    asyncio.run(main())
