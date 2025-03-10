#!/usr/bin/env python3
"""
Proxy Handler Module

This module provides proxy handling functionality for HTTP requests,
specifically for integrating with Oxylabs proxy service.
"""

import logging
import urllib.request
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class OxylabsProxyHandler:
    """
    Handler for Oxylabs proxy integration.
    
    Attributes:
        username (str): Oxylabs username
        password (str): Oxylabs password
        country_code (Optional[str]): Country code in 2-letter format (e.g., US, GB)
        city (Optional[str]): City name in English (e.g., london, new_york)
        state (Optional[str]): US state name (e.g., us_california, us_new_york)
        session_id (Optional[str]): Session ID to maintain the same IP
        session_time (Optional[int]): Session time in minutes (max 30)
        proxy_url (str): The constructed proxy URL
    """
    
    def __init__(
        self,
        username: str,
        password: str,
        country_code: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        session_id: Optional[str] = None,
        session_time: Optional[int] = None
    ):
        """
        Initialize the Oxylabs proxy handler.
        
        Args:
            username (str): Oxylabs username
            password (str): Oxylabs password
            country_code (Optional[str]): Country code in 2-letter format (e.g., US, GB)
            city (Optional[str]): City name in English (e.g., london, new_york)
            state (Optional[str]): US state name (e.g., us_california, us_new_york)
            session_id (Optional[str]): Session ID to maintain the same IP
            session_time (Optional[int]): Session time in minutes (max 30)
        """
        self.username = username
        self.password = password
        self.country_code = country_code
        self.city = city
        self.state = state
        self.session_id = session_id
        self.session_time = session_time
        
        # Build the proxy URL
        self.proxy_url = self._build_proxy_url()
        
        logger.info(f"Initialized Oxylabs proxy handler with URL: {self.proxy_url}")
    
    def _build_proxy_url(self) -> str:
        """
        Build the Oxylabs proxy URL with the provided parameters.
        
        Returns:
            str: The proxy URL
        """
        # Start with the base username
        username_parts = [f"customer-{self.username}"]
        
        # Add country code if provided
        if self.country_code:
            username_parts.append(f"cc-{self.country_code}")
        
        # Add city if provided (requires country code)
        if self.city and self.country_code:
            # Replace spaces with underscores
            city = self.city.replace(' ', '_')
            username_parts.append(f"city-{city}")
        
        # Add state if provided
        if self.state:
            username_parts.append(f"st-{self.state}")
        
        # Add session ID if provided
        if self.session_id:
            username_parts.append(f"sessid-{self.session_id}")
        
        # Add session time if provided
        if self.session_time:
            username_parts.append(f"sesstime-{self.session_time}")
        
        # Join the username parts with hyphens
        username = "-".join(username_parts)
        
        # Return the full proxy URL
        return f"http://{username}:{self.password}@pr.oxylabs.io:7777"
    
    def get_proxy_handler(self) -> urllib.request.ProxyHandler:
        """
        Get a ProxyHandler for use with urllib.
        
        Returns:
            urllib.request.ProxyHandler: The proxy handler
        """
        return urllib.request.ProxyHandler({
            'http': self.proxy_url,
            'https': self.proxy_url
        })
    
    def get_proxy_dict(self) -> Dict[str, str]:
        """
        Get a proxy dictionary for use with requests or aiohttp.
        
        Returns:
            Dict[str, str]: The proxy dictionary
        """
        return {
            'http': self.proxy_url,
            'https': self.proxy_url
        }
    
    def get_aiohttp_proxy(self) -> str:
        """
        Get the proxy URL formatted for aiohttp.
        
        Returns:
            str: The proxy URL for aiohttp
        """
        return self.proxy_url
