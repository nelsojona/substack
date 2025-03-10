#!/usr/bin/env python3
"""
Direct Substack Downloader

This script downloads posts from Substack directly without relying on the API.
It uses sitemap.xml to discover post URLs and then downloads each post.
Implements performance optimizations including:
- Async/aiohttp for concurrent requests
- Adaptive throttling
- Connection pooling
- Caching with SQLite
- Batch image processing
- Incremental sync
- Sitemap.xml parsing for more reliable post discovery
"""

import os
import re
import json
import time
import random
import asyncio
import aiohttp
import logging
import argparse
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
from pathlib import Path
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings

# Suppress XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Import performance optimization modules
from adaptive_throttler import AsyncAdaptiveThrottler
from cache_manager import CacheManager
from connection_pool import ConnectionPool
from database_manager import DatabaseManager
from batch_image_downloader import BatchImageDownloader
from incremental_sync import IncrementalSyncManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('direct_download.log')
    ]
)
logger = logging.getLogger("direct_downloader")

# Default Configuration
DEFAULT_AUTHOR = "tradecompanion"
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_IMAGE_DIR = "images"
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
]
DEFAULT_MIN_DELAY = 0.5  # Minimum delay between requests in seconds
DEFAULT_MAX_DELAY = 5.0  # Maximum delay between requests in seconds
DEFAULT_MAX_CONCURRENCY = 5  # Maximum number of concurrent requests
DEFAULT_MAX_IMAGE_CONCURRENCY = 10  # Maximum number of concurrent image downloads
DEFAULT_CACHE_TTL = 86400  # Default cache TTL in seconds (1 day)

class SubstackDirectDownloader:
    """
    Class for downloading Substack posts directly without API.
    
    Attributes:
        author (str): Substack author identifier
        output_dir (str): Directory to save output files
        image_dir (str): Directory to save downloaded images
        throttler (AsyncAdaptiveThrottler): Throttler for rate limiting
        connection_pool (ConnectionPool): Pool of HTTP connections
        cache (CacheManager): Cache manager for responses
        db (DatabaseManager): Database manager for metadata
        sync_manager (IncrementalSyncManager): Manager for incremental sync
        image_downloader (BatchImageDownloader): Downloader for batch image processing
        session (aiohttp.ClientSession): HTTP session
        semaphore (asyncio.Semaphore): Semaphore for limiting concurrency
        auth_token (str): Authentication token for private content
        use_sitemap (bool): Whether to use sitemap.xml for post discovery
    """
    
    def __init__(
        self,
        author: str = DEFAULT_AUTHOR,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        image_dir: str = DEFAULT_IMAGE_DIR,
        min_delay: float = DEFAULT_MIN_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        max_image_concurrency: int = DEFAULT_MAX_IMAGE_CONCURRENCY,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        verbose: bool = False,
        incremental: bool = False,
        use_sitemap: bool = True
    ):
        """
        Initialize the SubstackDirectDownloader.
        
        Args:
            author (str, optional): Substack author identifier. Defaults to DEFAULT_AUTHOR.
            output_dir (str, optional): Directory to save output files. Defaults to DEFAULT_OUTPUT_DIR.
            image_dir (str, optional): Directory to save downloaded images. Defaults to DEFAULT_IMAGE_DIR.
            min_delay (float, optional): Minimum delay between requests. Defaults to DEFAULT_MIN_DELAY.
            max_delay (float, optional): Maximum delay between requests. Defaults to DEFAULT_MAX_DELAY.
            max_concurrency (int, optional): Maximum number of concurrent requests. Defaults to DEFAULT_MAX_CONCURRENCY.
            max_image_concurrency (int, optional): Maximum concurrent image downloads. Defaults to DEFAULT_MAX_IMAGE_CONCURRENCY.
            cache_ttl (int, optional): Cache TTL in seconds. Defaults to DEFAULT_CACHE_TTL.
            verbose (bool, optional): Enable verbose logging. Defaults to False.
            incremental (bool, optional): Enable incremental sync. Defaults to False.
            use_sitemap (bool, optional): Use sitemap.xml for post discovery. Defaults to True.
        """
        self.author = author
        self.base_url = f"https://{author}.substack.com"
        self.output_dir = os.path.join(output_dir, author)
        self.image_dir = os.path.join(self.output_dir, image_dir)
        self.verbose = verbose
        self.incremental = incremental
        self.use_sitemap = use_sitemap
        
        # Set up logging level
        if verbose:
            logger.setLevel(logging.DEBUG)
        
        # Create output directories
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        
        # Initialize AsyncAdaptiveThrottler
        self.throttler = AsyncAdaptiveThrottler(min_delay=min_delay, max_delay=max_delay)
        
        # Initialize ConnectionPool
        self.connection_pool = ConnectionPool(
            max_connections=max_concurrency,
            timeout=30,
            keep_alive=True
        )
        
        # Initialize CacheManager
        cache_db_path = os.path.join(self.output_dir, "cache.db")
        self.cache = CacheManager(db_path=cache_db_path, default_ttl=cache_ttl)
        
        # Initialize DatabaseManager
        db_path = os.path.join(self.output_dir, "metadata.db")
        self.db = DatabaseManager(db_path=db_path)
        
        # Initialize IncrementalSyncManager
        cache_dir = os.path.join(self.output_dir, "cache")
        self.sync_manager = IncrementalSyncManager(cache_dir=cache_dir)
        # Get sync for this author
        self.sync = self.sync_manager.get_sync(author)
        
        # Initialize BatchImageDownloader
        self.image_downloader = BatchImageDownloader(
            output_dir=self.image_dir,
            max_concurrency=max_image_concurrency,
            timeout=30
        )
        
        # Initialize aiohttp session and semaphore
        self.session = None
        self.semaphore = None
        self.auth_token = None
    
    async def __aenter__(self):
        """Initialize aiohttp session and semaphore for async context manager."""
        # Create a connector with the connection pool settings
        connector = aiohttp.TCPConnector(
            limit=self.connection_pool.max_connections,
            limit_per_host=self.connection_pool.max_connections_per_host,
            keepalive_timeout=self.connection_pool.keep_alive
        )
        
        # Create aiohttp session with random user agent
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": f"https://{self.author}.substack.com/",
            "Origin": "https://substack.com",
            "DNT": "1"
        }
        
        # Add cookies if auth token is set
        cookies = {}
        if self.auth_token:
            cookies = {
                "substack.sid": self.auth_token,
                "substack-sid": self.auth_token,
                "substack.authpub": self.author,
                "substack-auth": "1"
            }
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30),
            cookies=cookies
        )
        
        # Create semaphore for limiting concurrency
        self.semaphore = asyncio.Semaphore(self.connection_pool.max_connections)
        
        # The image downloader will create its own session
        
        return self
        
    async def perform_login(self, email: str, password: str) -> bool:
        """
        Perform login to Substack to refresh authentication cookies.
        
        Args:
            email (str): Substack email
            password (str): Substack password
            
        Returns:
            bool: True if login successful, False otherwise
        """
        if not self.session:
            logger.error("Session not initialized")
            return False
            
        try:
            logger.info("Performing login to refresh authentication...")
            
            # First visit the login page to get any required cookies/tokens
            login_url = "https://substack.com/sign-in"
            async with self.session.get(login_url) as response:
                login_html = await response.text()
                
                # Extract CSRF token if needed
                csrf_match = re.search(r'name="csrf" value="([^"]+)"', login_html)
                csrf_token = csrf_match.group(1) if csrf_match else ""
                
            # Now perform login
            login_data = {
                "email": email,
                "password": password,
                "redirect": f"https://{self.author}.substack.com/",
                "for_pub": self.author,
                "csrf": csrf_token
            }
            
            # Send login request
            post_url = "https://substack.com/api/v1/login"
            headers = {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrf_token,
                "Accept": "application/json"
            }
            
            async with self.session.post(
                post_url, 
                json=login_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    auth_data = await response.json()
                    
                    # Extract token if present in response
                    new_token = None
                    for cookie in self.session.cookie_jar:
                        if cookie.key in ["substack.sid", "substack-sid"]:
                            new_token = cookie.value
                            break
                    
                    # Set new token if found
                    if new_token:
                        logger.info("Successfully refreshed authentication token")
                        self.auth_token = new_token
                        return True
                    else:
                        logger.warning("Login succeeded but no token found")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"Login failed with status {response.status}: {error_text}")
                    return False
                
            # Now visit the publication to set publication-specific cookies
            pub_url = f"https://{self.author}.substack.com/"
            async with self.session.get(pub_url) as response:
                if response.status == 200:
                    logger.info(f"Successfully visited {self.author}.substack.com")
                    return True
                
            return True
            
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return False
        
        # Create semaphore for limiting concurrency
        self.semaphore = asyncio.Semaphore(self.connection_pool.max_connections)
        
        # The image downloader will create its own session
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close sessions and connections for async context manager."""
        if self.session:
            await self.session.close()
        
        # Explicitly close the image downloader session if it exists
        if hasattr(self, 'image_downloader') and self.image_downloader:
            await self.image_downloader.close()
            
        # Close cache and database connections
        self.cache.close()
        self.db.close()
    
    def set_auth_token(self, token: str):
        """
        Set authentication token for private content.
        
        Args:
            token (str): Authentication token
        """
        self.auth_token = token
        
        # Clear all cached content to ensure we get fresh authenticated content
        logger.info("Clearing all cache to ensure fresh authenticated content is fetched")
        self.cache.clear_all_cache()
        
        # Set flag to indicate we need to try stronger authentication methods
        self._force_auth_required = True
        
        # Update session cookies if session exists
        if self.session:
            # Close existing session
            logger.info("Recreating session with fresh authentication")
            asyncio.create_task(self.session.close())
            
            # Create a connector with the connection pool settings
            connector = aiohttp.TCPConnector(
                limit=self.connection_pool.max_connections,
                limit_per_host=self.connection_pool.max_connections_per_host,
                keepalive_timeout=self.connection_pool.keep_alive
            )
            
            # Create aiohttp session with random user agent and proper cookies
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Referer": f"https://{self.author}.substack.com/",
                "Origin": "https://substack.com",
                "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
                "sec-ch-ua-platform": '"macOS"',
                "sec-fetch-site": "same-site",
                "sec-fetch-mode": "navigate",
                "sec-fetch-user": "?1",
                "sec-fetch-dest": "document",
                "DNT": "1",
                "upgrade-insecure-requests": "1"
            }
            
            # Create new cookie jar with token - make sure to decode any URL encoding
            decoded_token = token.replace('%3A', ':').replace('%2F', '/').replace('%2B', '+')
            cookies = {
                "substack.sid": token,
                "substack-sid": token,
                "substack.authpub": self.author,
                "substack-auth": "1",
                "substack.lli": "1"
            }
            
            # Create new session
            self.session = aiohttp.ClientSession(
                headers=headers,
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30),
                cookies=cookies
            )
    
    async def _fetch_url(self, url: str, retries: int = 3) -> Optional[str]:
        """
        Fetch a URL using aiohttp with caching and throttling.
        
        Args:
            url (str): URL to fetch
            retries (int, optional): Number of retries. Defaults to 3.
        
        Returns:
            Optional[str]: Response HTML or None if failed
        """
        # If forced auth is required, visit the author page first to ensure cookies are set
        if hasattr(self, '_force_auth_required') and self._force_auth_required and self.auth_token:
            try:
                # Only do this once per session
                self._force_auth_required = False
                
                # First visit substack.com
                logger.info(f"Visiting main Substack site to initialize cookies...")
                main_url = "https://substack.com/"
                
                auth_headers = {
                    "Referer": "https://substack.com/",
                    "Origin": "https://substack.com",
                    "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
                    "sec-ch-ua-platform": '"macOS"',
                    "sec-fetch-site": "same-site",
                    "sec-fetch-mode": "navigate",
                    "sec-fetch-dest": "document",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
                }
                
                for k, v in auth_headers.items():
                    self.session._default_headers[k] = v
                
                auth_cookies = {
                    "substack.sid": self.auth_token,
                    "substack-sid": self.auth_token
                }
                
                async with self.session.get(main_url, cookies=auth_cookies) as response:
                    if response.status == 200:
                        logger.info(f"Successfully visited main Substack site")
                    else:
                        logger.warning(f"Failed to visit main Substack site: {response.status}")
                
                # Now visit the author page
                logger.info(f"Visiting author page to ensure authentication cookies are properly set...")
                author_url = f"https://{self.author}.substack.com/"
                
                # Add additional cookies for author visit
                author_cookies = {
                    "substack.sid": self.auth_token,
                    "substack-sid": self.auth_token,
                    "substack.authpub": self.author,
                    "substack-auth": "1",
                    "substack.lli": "1"
                }
                
                # Update referer header
                self.session._default_headers["Referer"] = main_url
                
                async with self.session.get(author_url, cookies=author_cookies) as response:
                    if response.status == 200:
                        logger.info(f"Successfully visited author page for authentication")
                        # Extract any potential new cookies
                        for cookie in self.session.cookie_jar:
                            logger.debug(f"Cookie found: {cookie.key}={cookie.value}")
                    else:
                        logger.warning(f"Failed to visit author page: {response.status}")
                        
                # Now we're authenticated, let's visit a login-specific endpoint
                login_url = f"https://{self.author}.substack.com/api/v1/auth/current-user"
                self.session._default_headers["Referer"] = author_url
                self.session._default_headers["Accept"] = "application/json"
                
                async with self.session.get(login_url, cookies=author_cookies) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        if "loginState" in user_data and user_data["loginState"] == "authenticated":
                            logger.info(f"Successfully authenticated with Substack!")
                        else:
                            logger.warning(f"Not properly authenticated with Substack")
                    else:
                        logger.warning(f"Failed to check authentication status: {response.status}")
                
            except Exception as e:
                logger.warning(f"Error during authentication steps: {e}")
        
        # Check cache first
        cached_html = self.cache.get_page_cache(url)
        if cached_html:
            logger.debug(f"Cache hit for {url}")
            return cached_html
        
        # Extract domain for throttling
        domain = urlparse(url).netloc
        
        # Use semaphore to limit concurrency
        async with self.semaphore:
            # Apply throttling
            await self.throttler.async_throttle(domain)
            
            for attempt in range(retries):
                try:
                    start_time = time.time()
                    
                    # Prepare cookies if auth token is set
                    cookies = {}
                    if self.auth_token:
                        cookies = {
                            "substack.sid": self.auth_token,
                            "substack-sid": self.auth_token,
                            "substack.authpub": self.author,
                            "substack-auth": "1",
                            "substack.lli": "1",
                            "ajs_anonymous_id": '"804903de-519a-4a25-92a8-d51b0613f8af"',
                            "visit_id": '{%22id%22:%223f129271-fd95-4a8d-b704-c83644ac9ac3%22%2C%22timestamp%22:%222025-03-09T23%3A33%3A24.339Z%22}'
                        }
                        
                        # Add additional headers for authenticated requests
                        headers = {
                            "Referer": f"https://{self.author}.substack.com/",
                            "Origin": "https://substack.com",
                            "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
                            "sec-ch-ua-platform": '"macOS"',
                            "sec-fetch-site": "same-site",
                            "sec-fetch-mode": "navigate",
                            "sec-fetch-dest": "document",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
                        }
                        for k, v in headers.items():
                            self.session._default_headers[k] = v
                    
                    # Make the request
                    async with self.session.get(url, cookies=cookies) as response:
                        # Calculate response time
                        response_time = time.time() - start_time
                        
                        # Update throttler with response details
                        await self.throttler.update_from_response(
                            status_code=response.status,
                            response_time=response_time,
                            rate_limit_headers=dict(response.headers),
                            domain=domain
                        )
                        
                        if response.status == 200:
                            html = await response.text()
                            
                            # Save to cache
                            self.cache.set_page_cache(url, html)
                            
                            return html
                        
                        if response.status == 429:
                            # Handle rate limiting
                            logger.warning(f"Rate limited on {url}. Attempt {attempt+1}/{retries}")
                            wait_time = 2 ** attempt  # Exponential backoff
                            await asyncio.sleep(wait_time)
                            continue
                        
                        logger.error(f"HTTP error {response.status} for {url}")
                        return None
                
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"Error fetching {url}: {e}. Attempt {attempt+1}/{retries}")
                    
                    if attempt < retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Failed to fetch {url} after {retries} attempts: {e}")
                        return None
            
            # All retries failed
            return None
    
    async def find_post_urls(self, max_pages: Optional[int] = None) -> List[str]:
        """
        Find post URLs by first trying sitemap.xml, then falling back to other methods.
        
        Args:
            max_pages (Optional[int], optional): Maximum number of pages to scan. 
                                              If None, scans all pages.
        
        Returns:
            List[str]: List of unique post URLs
        """
        logger.info(f"Finding post URLs for {self.author}.substack.com")
        
        all_urls = set()
        
        # First, try the sitemap.xml approach (most reliable and complete) if enabled
        if self.use_sitemap:
            logger.info(f"Trying sitemap.xml approach")
            urls_from_sitemap = await self._find_post_urls_from_sitemap()
            
            if urls_from_sitemap:
                logger.info(f"Found {len(urls_from_sitemap)} URLs from sitemap.xml approach")
                all_urls.update(urls_from_sitemap)
                
                # If we found a good number of posts from sitemap, return them
                if len(all_urls) >= 10:
                    logger.info(f"Found sufficient posts from sitemap.xml, skipping other methods")
                    return list(all_urls)
        
        # If sitemap didn't yield enough results, try the root page approach
        logger.info(f"Trying root page approach (works better with modern Substacks)")
        urls_from_root = await self._find_post_urls_from_root_page()
        
        if urls_from_root:
            logger.info(f"Found {len(urls_from_root)} URLs from root page approach")
            all_urls.update(urls_from_root)
        
        # Also try standard archive method to find more posts
        logger.info(f"Trying standard archive method to find additional posts")
        urls_from_standard = await self._find_post_urls_from_standard_archive(max_pages)
        
        if urls_from_standard:
            logger.info(f"Found {len(urls_from_standard)} URLs from standard archive approach")
            all_urls.update(urls_from_standard)
            
        # If we need to find more posts, try a direct approach with hardcoded patterns
        # This is a fallback for Trade Companion which has over 1000 posts
        if len(all_urls) < 20 and self.author == "tradecompanion":
            logger.info(f"Found only {len(all_urls)} posts. Trying direct approach to find more...")
            
            # Generate post URLs using known patterns
            start_date = datetime(2022, 1, 1)  # Start from January 2022
            end_date = datetime.now()
            current_date = start_date
            
            # Track patterns we already have
            existing_patterns = set()
            for url in all_urls:
                # Extract the pattern part (after the last slash)
                pattern = url.split('/')[-1]
                existing_patterns.add(pattern)
            
            # Try common patterns for Trade Companion posts
            additional_patterns = [
                # Date-based patterns
                "jan-{day}-{year}",
                "feb-{day}-{year}",
                "mar-{day}-{year}",
                "apr-{day}-{year}",
                "may-{day}-{year}",
                "jun-{day}-{year}",
                "jul-{day}-{year}",
                "aug-{day}-{year}",
                "sep-{day}-{year}",
                "oct-{day}-{year}", 
                "nov-{day}-{year}",
                "dec-{day}-{year}",
                "jan-{day}-{year}-update",
                "feb-{day}-{year}-update",
                "mar-{day}-{year}-update", 
                "apr-{day}-{year}-update",
                "may-{day}-{year}-update",
                "jun-{day}-{year}-update",
                "jul-{day}-{year}-update",
                "aug-{day}-{year}-update",
                "sep-{day}-{year}-update",
                "oct-{day}-{year}-update", 
                "nov-{day}-{year}-update",
                "dec-{day}-{year}-update",
                # SPX/Market related patterns
                "spx-update-{month}-{day}-{year}",
                "market-update-{month}-{day}-{year}",
                "trade-update-{month}-{day}-{year}",
                "spx-analysis-{month}-{day}-{year}",
                "day-{day}-update"
            ]
            
            # Generate URLs for each pattern and date
            while current_date <= end_date:
                for pattern in additional_patterns:
                    # Format the pattern with current date
                    formatted_pattern = pattern.format(
                        day=current_date.day,
                        month=current_date.month,
                        year=current_date.year,
                        year_short=str(current_date.year)[2:]
                    )
                    
                    # Skip if we already have this pattern
                    if formatted_pattern in existing_patterns:
                        continue
                    
                    # Create the post URL
                    post_url = f"{self.base_url}/p/{formatted_pattern}"
                    
                    # Check if the URL works
                    try:
                        logger.debug(f"Checking post URL: {post_url}")
                        html = await self._fetch_url(post_url)
                        
                        # If we got content, add it to our URLs
                        if html and 'post-content' in html:
                            all_urls.add(post_url)
                            logger.info(f"Found working post URL: {post_url}")
                    except Exception as e:
                        logger.debug(f"Error checking post URL {post_url}: {e}")
                
                # Move to next date - weekly to avoid too many requests
                current_date += timedelta(days=7)
                
            logger.info(f"Found additional posts using direct approach")
        
        # Convert set back to list and return
        logger.info(f"Combined total: {len(all_urls)} unique post URLs")
        return list(all_urls)
        
    async def _find_post_urls_from_sitemap(self) -> List[str]:
        """
        Find post URLs by fetching and parsing the sitemap.xml file.
        
        Returns:
            List[str]: List of post URLs
        """
        post_urls = []
        sitemap_url = f"{self.base_url}/sitemap.xml"
        
        logger.info(f"Fetching sitemap from: {sitemap_url}")
        
        # Fetch the sitemap
        sitemap_content = await self._fetch_url(sitemap_url)
        
        if not sitemap_content:
            logger.warning(f"Could not fetch sitemap from {sitemap_url}")
            return post_urls
        
        # Parse the XML content using lxml parser
        try:
            # First try with lxml parser
            soup = BeautifulSoup(sitemap_content, 'lxml-xml')
            
            # Extract URLs
            all_urls = []
            for url_element in soup.find_all('loc'):
                if url_element.text:
                    all_urls.append(url_element.text)
                    
            # If no URLs found, try with regex as fallback
            if not all_urls:
                import re
                url_pattern = re.compile(r'<loc>(.*?)</loc>')
                all_urls = url_pattern.findall(sitemap_content)
        except Exception as e:
            logger.error(f"Error parsing sitemap XML: {e}")
            # Try fallback with regex
            try:
                import re
                url_pattern = re.compile(r'<loc>(.*?)</loc>')
                all_urls = url_pattern.findall(sitemap_content)
                logger.info(f"Used regex fallback to parse sitemap XML, found {len(all_urls)} URLs")
            except Exception as e2:
                logger.error(f"Fallback parsing of sitemap also failed: {e2}")
                return post_urls
        
        logger.info(f"Found {len(all_urls)} total URLs in sitemap")
        
        # Filter for post URLs (those containing /p/ in the path)
        base_domain = f"{self.author}.substack.com"
        for url in all_urls:
            parsed_url = urlparse(url)
            if parsed_url.netloc == base_domain and "/p/" in parsed_url.path:
                post_urls.append(url)
        
        logger.info(f"Found {len(post_urls)} post URLs in sitemap")
        
        return post_urls
    
    async def _find_post_urls_from_root_page(self) -> List[str]:
        """
        Find post URLs by scraping the root page of the Substack.
        This works on modern Substacks that don't use the traditional /archive URL.
        
        Returns:
            List[str]: List of unique post URLs
        """
        post_urls = []
        seen_urls = set()
        
        # Try fetching the root page
        url = self.base_url
        logger.info(f"Scraping root page: {url}")
        
        # Fetch the page
        html = await self._fetch_url(url)
        
        if not html:
            logger.error(f"Failed to fetch root page")
            return []
        
        # Get JSON data from the page
        json_data = self._extract_json_data(html)
        
        # Track new URLs found
        new_urls_found = 0
        
        # Extract posts from JSON if available
        if json_data and 'posts' in json_data:
            logger.info(f"Found {len(json_data['posts'])} posts in JSON data from root page")
            
            # Extract post URLs from JSON data
            for post in json_data['posts']:
                slug = post.get('slug')
                if slug:
                    post_url = f"{self.base_url}/p/{slug}"
                    if post_url not in seen_urls:
                        post_urls.append(post_url)
                        seen_urls.add(post_url)
                        new_urls_found += 1
                        logger.debug(f"Added post URL from JSON: {post_url}")
        
        # Parse the HTML regardless of whether we found JSON data
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for links to posts using various selectors
        post_links = []
        selectors = [
            "a.post-preview-title", 
            "div.post-preview h2.post-title a",
            "h2.post-title a",
            "div.post-preview a[href*='/p/']",
            "a[href*='/p/'][data-component='PostPreviewTitle']",
            "div.summary a[href*='/p/']",
            "div.portable-archive-post a[href*='/p/']", 
            "div.post-preview-content a[href*='/p/']",
            "article.post h2 a",
            "a.post-title",
            # BIG by Matt Stoller specific selectors
            "div.postItem a[href*='/p/']",
            "div.postItem h2 a",
            "div.post-card a[href*='/p/']",
            "div.post-card h2 a",
            "a.freebirdPremiumPromo__button[href*='/p/']",
            # Newer Substack sites
            "a[data-component-name='PostTitle']",
            "a[data-component-name='StackedPost']",
            "div[data-component-name='PostsList'] a",
            "a.full-post-card",
            # Add more selectors as needed
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            if links:
                post_links.extend(links)
        
        # If no links found with specific selectors, try generic selector
        if not post_links:
            post_links = soup.select("a[href*='/p/']")
        
        # Process the links
        for link in post_links:
            href = link.get('href')
            if href and '/p/' in href:
                # Make the URL absolute
                if not href.startswith('http'):
                    post_url = urljoin(self.base_url, href)
                else:
                    post_url = href
                
                # Ensure we're only grabbing posts from the current author
                if f"{self.author}.substack.com" in post_url and post_url not in seen_urls:
                    post_urls.append(post_url)
                    seen_urls.add(post_url)
                    new_urls_found += 1
                    logger.debug(f"Added post URL from HTML: {post_url}")
        
        # Try also checking the /archive route without page parameter
        archive_url = f"{self.base_url}/archive"
        logger.info(f"Scraping archive base page: {archive_url}")
        archive_html = await self._fetch_url(archive_url)
        
        if archive_html:
            new_urls = await self._extract_post_urls_from_html(archive_html, seen_urls)
            post_urls.extend(new_urls)
            logger.info(f"Found {len(new_urls)} additional URLs from archive base page")
        
        logger.info(f"Found {len(post_urls)} unique post URLs from root page approach")
        return post_urls
        
    async def _extract_post_urls_from_html(self, html: str, seen_urls: Set[str]) -> List[str]:
        """
        Extract post URLs from HTML content.
        
        Args:
            html (str): HTML content
            seen_urls (Set[str]): Set of already seen URLs to avoid duplicates
            
        Returns:
            List[str]: List of new post URLs
        """
        new_urls = []
        
        # Get JSON data from the page
        json_data = self._extract_json_data(html)
        
        # Extract posts from JSON if available
        if json_data and 'posts' in json_data:
            for post in json_data['posts']:
                slug = post.get('slug')
                if slug:
                    post_url = f"{self.base_url}/p/{slug}"
                    if post_url not in seen_urls:
                        new_urls.append(post_url)
                        seen_urls.add(post_url)
                        logger.debug(f"Added post URL from JSON: {post_url}")
        
        # Parse the HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for links to posts using various selectors
        post_links = []
        selectors = [
            "a.post-preview-title", 
            "div.post-preview h2.post-title a",
            "h2.post-title a",
            "div.post-preview a[href*='/p/']",
            "a[href*='/p/'][data-component='PostPreviewTitle']",
            "div.summary a[href*='/p/']",
            "div.portable-archive-post a[href*='/p/']",
            "div.post-preview-content a[href*='/p/']",
            "article.post h2 a",
            "a.post-title",
            # BIG by Matt Stoller specific selectors
            "div.postItem a[href*='/p/']",
            "div.postItem h2 a",
            "div.post-card a[href*='/p/']",
            "div.post-card h2 a",
            "a.freebirdPremiumPromo__button[href*='/p/']",
            # Newer Substack sites
            "a[data-component-name='PostTitle']",
            "a[data-component-name='StackedPost']",
            "div[data-component-name='PostsList'] a",
            "a.full-post-card",
            # Added selectors for Trade Companion specifically
            "div.feed-post a[href*='/p/']",
            "div.post-item a[href*='/p/']",
            "div.post-item-text a[href*='/p/']",
            "div.post-preview-title a",
            "div.post-grid a[href*='/p/']",
            "div.feed-posts a[href*='/p/']",
            "article a[href*='/p/']",
            "a[href*='/archive/p/']",
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            if links:
                post_links.extend(links)
        
        # If no links found with specific selectors, try generic selector
        if not post_links:
            post_links = soup.select("a[href*='/p/']")
        
        # Process the links
        for link in post_links:
            href = link.get('href')
            if href and '/p/' in href:
                # Make the URL absolute
                if not href.startswith('http'):
                    post_url = urljoin(self.base_url, href)
                else:
                    post_url = href
                
                # Ensure we're only grabbing posts from the current author
                if f"{self.author}.substack.com" in post_url and post_url not in seen_urls:
                    new_urls.append(post_url)
                    seen_urls.add(post_url)
                    logger.debug(f"Added post URL from HTML: {post_url}")
        
        return new_urls
            
    async def _find_post_urls_from_standard_archive(self, max_pages: Optional[int] = None) -> List[str]:
        """
        Find post URLs by scraping the standard archive pages.
        
        Args:
            max_pages (Optional[int], optional): Maximum number of pages to scan. 
                                             If None, scans all pages.
        
        Returns:
            List[str]: List of unique post URLs
        """
        post_urls = []
        page = 1
        reached_end = False
        seen_urls = set()  # For tracking unique URLs
        consecutive_empty_pages = 0  # Track consecutive pages with no new URLs
        max_consecutive_empty = 10  # Give up after this many consecutive empty pages - increased from 3 to 10 to find more posts
        
        # Continue until we reach the end or hit the max_pages limit
        while not reached_end and (max_pages is None or page <= max_pages):
            # Construct URL for the current page
            url = f"{self.base_url}/archive?sort=new&page={page}"
            logger.info(f"Scraping archive page {page}: {url}")
            
            # Fetch the page
            html = await self._fetch_url(url)
            
            if not html:
                logger.error(f"Failed to fetch archive page {page}")
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= max_consecutive_empty:
                    logger.warning(f"Giving up after {consecutive_empty_pages} consecutive failed pages")
                    break
                page += 1
                continue
            
            # Get JSON data from the page if it exists in a script tag
            json_data = self._extract_json_data(html)
            
            # Track new URLs found on this page
            new_urls_found = 0
            
            if json_data and 'posts' in json_data:
                logger.info(f"Found {len(json_data['posts'])} posts in JSON data on page {page}")
                
                # Extract post URLs from JSON data
                for post in json_data['posts']:
                    slug = post.get('slug')
                    if slug:
                        post_url = f"{self.base_url}/p/{slug}"
                        if post_url not in seen_urls:
                            post_urls.append(post_url)
                            seen_urls.add(post_url)
                            new_urls_found += 1
                            logger.debug(f"Added post URL from JSON: {post_url}")
            
            # Always do HTML parsing even if JSON data was found
            # Parse the HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for links to posts in various possible HTML structures
            # Try multiple selectors that might contain post links
            post_links = []
            selectors = [
                "a.post-preview-title",                # Common class used for post titles
                "div.post-preview h2.post-title a",    # Post title inside preview
                "h2.post-title a",                     # Direct h2 post title links
                "div.post-preview a[href*='/p/']",     # Any link in post preview that points to a post
                "a[href*='/p/'][data-component='PostPreviewTitle']", # Data component attribute
                "div.summary a[href*='/p/']",          # Links in summary divs
                "div.portable-archive-post a[href*='/p/']", # Archive post container links
                "div.post-preview-content a[href*='/p/']",  # Post preview content links
                "article.post h2 a",                   # Article post links
                "a.post-title",                        # Direct post title links
                # BIG by Matt Stoller specific selectors
                "div.postItem a[href*='/p/']",         # Post item links
                "div.postItem h2 a",                   # Post item title links
                "div.post-card a[href*='/p/']",        # Post card links
                "div.post-card h2 a",                  # Post card title links
                "a.freebirdPremiumPromo__button[href*='/p/']", # Premium promo links
                # Newer Substack sites
                "a[data-component-name='PostTitle']",  # Component-based titles
                "a[data-component-name='StackedPost']", # Stacked post components
                "div[data-component-name='PostsList'] a", # Posts list components
                "a.full-post-card",                    # Full post cards
                # Added selectors for Trade Companion specifically
                "div.feed-post a[href*='/p/']",        # Feed posts
                "div.post-item a[href*='/p/']",        # Post items 
                "div.post-item-text a[href*='/p/']",   # Post item text
                "div.post-preview-title a",            # Preview titles
                "div.post-grid a[href*='/p/']",        # Grid posts
                "div.feed-posts a[href*='/p/']",       # Feed posts container
                "article a[href*='/p/']",              # Any link in article
                "a[href*='/archive/p/']",              # Archive specific links
            ]
            
            for selector in selectors:
                links = soup.select(selector)
                if links:
                    post_links.extend(links)
                    
            # If we still didn't find any links, use the most generic selector
            if not post_links:
                post_links = soup.select("a[href*='/p/']")
            
            for link in post_links:
                href = link.get('href')
                if href and '/p/' in href:
                    # Make the URL absolute
                    if not href.startswith('http'):
                        post_url = urljoin(self.base_url, href)
                    else:
                        post_url = href
                    
                    # Ensure we're only grabbing posts from the current author
                    if f"{self.author}.substack.com" in post_url and post_url not in seen_urls:
                        post_urls.append(post_url)
                        seen_urls.add(post_url)
                        new_urls_found += 1
                        logger.debug(f"Added post URL from HTML: {post_url}")
            
            # Check if we reached the end
            if new_urls_found == 0:
                consecutive_empty_pages += 1
                logger.info(f"No new URLs found on page {page} ({consecutive_empty_pages} consecutive empty pages)")
                
                # Check for explicit end markers
                if "No posts to see here" in html or "There are no more posts" in html:
                    logger.info(f"Reached the end of archive at page {page} (explicit end message)")
                    reached_end = True
                    break
                
                # Give up after several consecutive empty pages
                if consecutive_empty_pages >= max_consecutive_empty:
                    logger.info(f"Reached the end of archive at page {page} (after {consecutive_empty_pages} consecutive empty pages)")
                    reached_end = True
                    break
            else:
                # Reset consecutive empty pages counter if we found something
                consecutive_empty_pages = 0
                logger.info(f"Found {new_urls_found} new URLs on page {page}, total: {len(post_urls)}")
            
            # Look for pagination links to verify there are more pages
            next_page_exists = False
            pagination_links = soup.select("div.pagination a")
            for link in pagination_links:
                href = link.get('href')
                if href and f"page={page+1}" in href:
                    next_page_exists = True
                    break
            
            # If there's explicit pagination and no next page link, we're done
            if pagination_links and not next_page_exists and page > 1:
                logger.info(f"No next page link found in pagination at page {page}")
                reached_end = True
                break
            
            # Move to the next page
            page += 1
            
            # Add a small delay between page requests to avoid overwhelming the server
            await asyncio.sleep(0.5)
        
        logger.info(f"Found {len(post_urls)} unique post URLs across {page-1} pages")
        return post_urls
    
    def _extract_json_data(self, html: str) -> Optional[Dict]:
        """
        Extract JSON data from HTML page.
        
        Args:
            html (str): HTML content
        
        Returns:
            Optional[Dict]: Extracted JSON data or None
        """
        try:
            # First try the preloaded state data (most common)
            pattern = r'window\.__PRELOADED_STATE__ = JSON\.parse\("(.+?)"\);'
            match = re.search(pattern, html)
            if match:
                json_str = match.group(1)
                # Unescape JSON string
                json_str = json_str.replace('\\"', '"').replace('\\\\', '\\')
                return json.loads(json_str)
            
            # Try APOLLO_STATE format (used in some Substack sites)
            apollo_pattern = r'window\.__APOLLO_STATE__ =\s*({.+?});'
            apollo_match = re.search(apollo_pattern, html, re.DOTALL)
            if apollo_match:
                try:
                    apollo_data = json.loads(apollo_match.group(1))
                    # Transform into a format compatible with our processing
                    posts_data = {"posts": []}
                    
                    # Extract posts from Apollo state
                    for key, value in apollo_data.items():
                        if isinstance(value, dict) and "slug" in value and ("type" in value and value.get("type") == "Post"):
                            posts_data["posts"].append(value)
                    
                    if posts_data["posts"]:
                        return posts_data
                except Exception as sub_e:
                    logger.warning(f"Failed to parse Apollo state: {sub_e}")
            
            # Try looking for inline JSON in script tags
            soup = BeautifulSoup(html, 'html.parser')
            for script in soup.find_all('script', type="application/json"):
                try:
                    script_data = json.loads(script.string)
                    # Look for posts array in the data
                    if 'posts' in script_data:
                        return script_data
                    # For other JSON structures containing post data
                    if 'data' in script_data and 'post' in script_data['data']:
                        return {'posts': [script_data['data']['post']]}
                except:
                    continue
                    
            # Look for a next-data script which may contain post data (common in Next.js sites)
            next_data_script = soup.find('script', id='__NEXT_DATA__')
            if next_data_script:
                try:
                    next_data = json.loads(next_data_script.string)
                    # Try to extract posts from various structures common in Next.js data
                    if 'props' in next_data and 'pageProps' in next_data['props']:
                        page_props = next_data['props']['pageProps']
                        
                        # Look for posts list in common locations
                        if 'posts' in page_props:
                            return {'posts': page_props['posts']}
                        elif 'publication' in page_props and 'posts' in page_props['publication']:
                            return {'posts': page_props['publication']['posts']}
                except Exception as sub_e:
                    logger.warning(f"Failed to parse Next.js data: {sub_e}")
        
        except Exception as e:
            logger.warning(f"Error extracting JSON data: {e}")
        
        return None
    
    async def extract_post_metadata(self, html: str, url: str) -> Dict[str, Any]:
        """
        Extract metadata from post HTML.
        
        Args:
            html (str): Post HTML content
            url (str): Post URL
        
        Returns:
            Dict[str, Any]: Post metadata
        """
        # Parse the HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract post title
        title_elem = soup.select_one('h1.post-title')
        title = title_elem.text.strip() if title_elem else "Untitled Post"
        
        # Extract post slug from URL
        slug = url.split('/')[-1]
        
        # Extract post date
        date_elem = soup.select_one('time')
        post_date = date_elem.get('datetime') if date_elem else None
        if post_date:
            try:
                date_obj = datetime.fromisoformat(post_date.replace('Z', '+00:00'))
                formatted_date = date_obj.strftime('%Y-%m-%d')
            except:
                formatted_date = post_date
        else:
            formatted_date = datetime.now().strftime('%Y-%m-%d')
        
        # Extract post content - try multiple approaches
        content_html = ""
        
        # Try to get the full post content from JavaScript data - this is the most reliable method
        # Look for patterns in the page's JavaScript data
        js_patterns = [
            # Apollo state pattern
            (r'window\.__APOLLO_STATE__ =\s*({.+?});', 'apollo'),
            # Preloaded state pattern
            (r'window\.__PRELOADED_STATE__ = JSON\.parse\("(.+?)"\);', 'preloaded'),
            # Post content directly embedded
            (r'"body_html":"(.+?)","', 'direct'),
            # Next.js data pattern
            (r'<script id="__NEXT_DATA__" type="application\/json">(.+?)<\/script>', 'nextjs')
        ]
        
        for pattern, pattern_type in js_patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    if pattern_type == 'apollo':
                        apollo_state = json.loads(match.group(1))
                        # Find the post content in the Apollo state
                        for key, value in apollo_state.items():
                            if isinstance(value, dict) and 'body_html' in value and value.get('body_html'):
                                content_html = value.get('body_html')
                                logger.info(f"Found full post content in Apollo state (length: {len(content_html)})")
                                break
                    elif pattern_type == 'preloaded':
                        # Unescape the JSON string
                        json_str = match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                        preloaded_state = json.loads(json_str)
                        
                        # Try to find post data in preloaded state
                        if 'postBySlug' in preloaded_state:
                            post_data = preloaded_state['postBySlug']
                            if 'body_html' in post_data:
                                content_html = post_data['body_html']
                                logger.info(f"Found full post content in preloaded state (length: {len(content_html)})")
                        elif 'post' in preloaded_state:
                            post_data = preloaded_state['post']
                            if 'body_html' in post_data:
                                content_html = post_data['body_html']
                                logger.info(f"Found full post content in preloaded state (length: {len(content_html)})")
                    elif pattern_type == 'direct':
                        # Unescape JSON string
                        content_html = match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                        logger.info(f"Found post content directly in JavaScript (length: {len(content_html)})")
                    elif pattern_type == 'nextjs':
                        next_data = json.loads(match.group(1))
                        if 'props' in next_data and 'pageProps' in next_data['props']:
                            page_props = next_data['props']['pageProps']
                            if 'post' in page_props and 'body_html' in page_props['post']:
                                content_html = page_props['post']['body_html']
                                logger.info(f"Found full post content in Next.js data (length: {len(content_html)})")
                    
                    # If we found content, break the loop
                    if content_html:
                        break
                except Exception as e:
                    logger.warning(f"Failed to parse {pattern_type} state: {e}")
        
        # If no content found in JavaScript, try HTML selectors
        if not content_html:
            # Check if this is a paywalled post that we have access to
            # If authenticated, we should look for full content first
            if self.auth_token:
                # Selectors that typically include the full authenticated content
                auth_selectors = [
                    # Primary selectors for tradecompanion
                    'div.body.markup',  # Direct body markup div - this is what we need
                    'div.post.post-page.substack-post .body.markup',  # Full selector path
                    'div.post-content div.body.markup',  # With post-content wrapper
                    
                    # General authenticated content selectors
                    'div.post article',  # Full article in post
                    'section.body-content',  # Modern Substacks
                    'div.post-wrapper article.post',  # Full post wrapper
                    
                    # Authenticated content selectors
                    'div.full-content',  # Often contains the full content for authenticated users
                    'div.paywall-content',  # Content behind paywall
                    'div.subscriber-content',  # Content for subscribers
                    'div.post-content-final',  # Used on newer Substacks
                    'article.subscriber-only',  # Used for subscriber-only content
                    'div.post-content',  # Full post content
                    'div.content-wrapper article.subscriber-only',  # Another subscriber content pattern
                    'div.post-content-wrapper',  # Wrapper for post content
                    'div[data-component-name="FullPostContent"]',  # Newer Substacks component pattern
                    'div.post-content-container',  # Container for post content
                    
                    # Additional full content selectors
                    'article.post div.body.markup',  # Full markup body
                    'div.post-wrapper div.post-content',  # Post content in wrapper
                    'div.substack-post-content-wrapper',  # Substack specific wrapper
                    'main article.post',  # Main article
                    'article.content',  # Article content
                    
                    # Direct element selector for debugging - starts from page root
                    'html body.post-page div.layout-container div.content-wrapper div.post.post-page.substack-post div.body.markup',
                ]
                
                for selector in auth_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        logger.debug(f"Found authenticated content using selector: {selector}")
                        content_html = str(content_elem)
                        break
            
            # If still no content or not authenticated, try general selectors
            if not content_html:
                # Try multiple selectors in order of most likely to contain the content
                general_selectors = [
                    'div.available-content',  # Preview content
                    'div.post-content-final',  # Used on newer Substacks
                    'div.post-content',  # Post content
                    'div.content-wrapper article',  # Wrapped article
                    'div.single-post article',  # Single post
                    'article.body',  # Article body
                    'article div.body',  # Body within article
                    'article',  # Any article
                    'div.post-content-wrapper',  # Post content wrapper
                    '.body',  # Any body
                    'div.body'  # Body div
                ]
                
                for selector in general_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        logger.debug(f"Found content using general selector: {selector}")
                        content_html = str(content_elem)
                        break
        
        # If still no content, try a more aggressive approach
        if not content_html:
            # Look for div with class containing "post-content"
            for div in soup.find_all('div'):
                div_class = div.get('class', [])
                if isinstance(div_class, list) and any('post-content' in c for c in div_class):
                    content_html = str(div)
                    logger.debug(f"Found content using custom search")
                    break
        
        # If we still don't have content, fall back to a minimal version
        if not content_html:
            content_html = "<p>No content found</p>"
            logger.warning("No content found using any extraction method")
        
        # If still no content found, try a last-resort approach specific to tradecompanion
        if (not content_html or '<div class="available-content">' in content_html) and self.author == "tradecompanion":
            logger.debug("Trying tradecompanion-specific content extraction...")
            # Try to find the exact pattern for this site
            matches = re.findall(r'<div class="body markup" dir="auto">(.*?)<\/div><\/div>', html, re.DOTALL)
            if matches and len(matches) > 0:
                logger.info(f"Found content using regex extraction (length: {len(matches[0])})")
                content_html = f'<div class="body markup" dir="auto">{matches[0]}</div>'
            
            # If that didn't work, try an even more targeted approach
            if not content_html or '<div class="available-content">' in content_html:
                logger.debug("Trying an alternative regex extraction method...")
                # Try to extract everything between the post-content div and the comments section
                full_content_match = re.search(r'<div class="post-content">(.*?)<div id="comments"', html, re.DOTALL)
                if full_content_match:
                    content_raw = full_content_match.group(1)
                    # Now extract just the body markup part
                    body_match = re.search(r'<div class="body markup" dir="auto">(.*?)</div>', content_raw, re.DOTALL)
                    if body_match:
                        logger.info(f"Found content using full-page regex extraction (length: {len(body_match.group(1))})")
                        content_html = f'<div class="body markup" dir="auto">{body_match.group(1)}</div>'
                
        # Check for paywalled content
        paywall_indicators = [
            "Subscribe to continue reading",
            "This post is for paying subscribers",
            "This post is for subscribers",
            "Subscribe to read the full post",
            "This post is only available to subscribers",
            "for paying subscribers only",
            "Only paid subscribers can",
            '<div class="paywall"',
            '<div class="paywall-prompt"'
        ]
        
        is_paywalled = any(indicator in html for indicator in paywall_indicators)
        
        # Check if we are authenticated but still getting paywalled content
        if is_paywalled and self.auth_token:
            logger.warning(f"Post appears to be paywalled despite having authentication token. Token may be invalid or expired.")
            
        # Determine if we got full content or just preview
        is_full_content = len(content_html) > 2000 or (self.auth_token and not is_paywalled)
        
        # If content looks like it might be a snippet, log a warning
        if '<div class="available-content">' in content_html and len(content_html) < 5000:
            logger.warning(f"Content appears to be preview snippet only! Authentication may have failed.")
            logger.info(f"Content length: {len(content_html)} characters")
        
        # Return the metadata
        metadata = {
            "title": title,
            "slug": slug,
            "date": formatted_date,
            "url": url,
            "content_html": content_html,
            "is_paywalled": is_paywalled,
            "is_full_content": is_full_content,
            "word_count": len(content_html.split()),
            "content_length": len(content_html),
            "last_fetched": datetime.now().isoformat()
        }
        
        # Log info about the content retrieval
        if is_paywalled:
            if is_full_content:
                logger.info(f"Retrieved full content for paywalled post: {title}")
            else:
                logger.warning(f"Retrieved only preview content for paywalled post: {title}")
        else:
            logger.info(f"Retrieved content for post: {title} (length: {len(content_html)} chars)")
        
        return metadata
    
    def _store_post_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Store post metadata in the database.
        
        Args:
            metadata (Dict[str, Any]): Post metadata
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get or create the author
            author_id = self.db.get_author_id(self.author)
            
            if not author_id:
                logger.error(f"Failed to get or create author {self.author}")
                return False
            
            # Prepare the post data for insertion
            post_data = {
                "id": metadata.get("url").split("/")[-1],  # Use slug as id
                "title": metadata.get("title"),
                "slug": metadata.get("slug"),
                "post_date": int(datetime.fromisoformat(metadata.get("date")).timestamp()) if metadata.get("date") else int(time.time()),
                "url": metadata.get("url"),
                "content": metadata.get("content_html"),
                "is_paid": metadata.get("is_paywalled", False),
                "is_published": True,
                "metadata": metadata
            }
            
            # Insert the post
            post_id = self.db.insert_post(post_data, author_id)
            
            if post_id:
                logger.debug(f"Stored metadata for post: {metadata.get('title')}")
                return True
            else:
                logger.error(f"Failed to store metadata for post: {metadata.get('title')}")
                return False
        
        except Exception as e:
            logger.error(f"Error storing post metadata: {e}")
            return False
    
    async def extract_image_urls(self, html_content: str, base_url: str = "") -> Set[str]:
        """
        Extract image URLs from HTML content.
        
        Args:
            html_content (str): HTML content
            base_url (str, optional): Base URL for resolving relative URLs. Defaults to "".
        
        Returns:
            Set[str]: Set of image URLs
        """
        image_urls = set()
        
        try:
            # Parse HTML content
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all img tags
            img_tags = soup.find_all('img')
            
            # Extract image URLs
            for img in img_tags:
                src = img.get('src')
                if src:
                    # Resolve relative URLs
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        if base_url:
                            src = urljoin(base_url, src)
                        else:
                            continue  # Skip relative URLs if no base URL is provided
                    
                    # Filter out tiny images, data URIs, and tracking pixels
                    if not src.startswith('data:') and 'pixel' not in src.lower():
                        image_urls.add(src)
        
        except Exception as e:
            logger.error(f"Error extracting image URLs: {e}")
        
        return image_urls
    
    async def direct_fetch(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Direct fetch method to reliably get full post content.
        Works with any subscription.
        
        Args:
            url (str): Post URL
        
        Returns:
            Optional[Dict[str, Any]]: Dictionary with post data or None if failed
        """
        if not self.auth_token:
            logger.warning("No authentication token provided. Direct fetch may not work for premium content")
        
        try:
            logger.info(f"Using direct fetch method for {url}...")
            
            # Extract author from URL if not set
            url_parts = urlparse(url)
            author = self.author
            if not author:
                author = url_parts.netloc.split('.')[0]
            
            # Headers that mimic a real browser
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Origin": "https://substack.com",
                "Referer": "https://substack.com/",
                "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
                "sec-ch-ua-platform": '"macOS"',
                "sec-fetch-site": "same-site",
                "sec-fetch-dest": "document"
            }
            
            # Cookies for authentication
            token = self.auth_token
            cookies = {
                "substack.sid": token,
                "substack-sid": token,
                "substack.authpub": author,
                "substack.lli": "1",
                "ajs_anonymous_id": '"804903de-519a-4a25-92a8-d51b0613f8af"',
                "visit_id": '{%22id%22:%223f129271-fd95-4a8d-b704-c83644ac9ac3%22%2C%22timestamp%22:%222025-03-09T23%3A33%3A24.339Z%22}'
            }
            
            # Create a fresh session to avoid any cookie/header issues
            async with aiohttp.ClientSession(headers=headers) as fresh_session:
                # First visit the main page to establish cookies
                main_url = f"https://{author}.substack.com/"
                
                async with fresh_session.get(main_url, cookies=cookies) as response:
                    if response.status == 200:
                        logger.info(f"Successfully visited main site for {author}")
                    else:
                        logger.warning(f"Failed to visit main site: {response.status}")
                
                # Now visit the actual post URL
                async with fresh_session.get(url, cookies=cookies) as response:
                    if response.status == 200:
                        html = await response.text()
                        logger.info(f"Successfully fetched post with direct method (length: {len(html)})")
                        
                        # Extract metadata
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Extract title
                        title_elem = soup.select_one('h1.post-title')
                        title = title_elem.text.strip() if title_elem else "Untitled Post"
                        
                        # Extract date
                        date_elem = soup.select_one('time')
                        post_date = date_elem.get('datetime') if date_elem else None
                        if post_date:
                            try:
                                date_obj = datetime.fromisoformat(post_date.replace('Z', '+00:00'))
                                formatted_date = date_obj.strftime('%Y-%m-%d')
                            except:
                                formatted_date = post_date
                        else:
                            formatted_date = datetime.now().strftime('%Y-%m-%d')
                        
                        # Extract content - first try BeautifulSoup
                        body_markup = soup.select_one('div.body.markup')
                        
                        if body_markup:
                            content_html = str(body_markup)
                            logger.info(f"Found content div with BeautifulSoup (length: {len(content_html)})")
                        else:
                            # Try regex as fallback
                            logger.info("Trying regex fallback for content extraction")
                            match = re.search(r'<div class="body markup" dir="auto">(.*?)</div>\s*</div>\s*<div', html, re.DOTALL)
                            if match:
                                content_html = f'<div class="body markup" dir="auto">{match.group(1)}</div>'
                                logger.info(f"Found content with regex (length: {len(content_html)})")
                            else:
                                logger.error("Couldn't extract content with regex either")
                                content_html = "<p>Failed to extract content</p>"
                        
                        # Return the post data dictionary
                        return {
                            "title": title,
                            "date": formatted_date,
                            "url": url,
                            "content_html": content_html,
                            "html": html,
                            "is_paywalled": False,  # We got the content directly
                            "is_full_content": True,
                            "word_count": len(content_html.split()),
                            "content_length": len(content_html),
                            "last_fetched": datetime.now().isoformat()
                        }
                    else:
                        logger.error(f"Failed to fetch post with direct method: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error in direct_fetch: {e}")
            return None
            
    async def tradecompanion_direct_fetch(self, url: str) -> Optional[str]:
        """
        Special method to directly fetch tradecompanion posts using a more robust approach.
        
        Args:
            url (str): Post URL
        
        Returns:
            Optional[str]: Full post HTML content or None if failed
        """
        if not self.session:
            logger.error("Session not initialized")
            return None
            
        try:
            logger.info("Using direct fetch method specifically for tradecompanion...")
            
            # First, let's visit the main site to ensure cookies are set
            main_site = "https://tradecompanion.substack.com/"
            auth_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Referer": "https://substack.com/",
                "Origin": "https://substack.com",
                "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
                "sec-ch-ua-platform": '"macOS"',
                "Cookie": f"substack.sid={self.auth_token}; substack-sid={self.auth_token}; substack.authpub=tradecompanion; substack.lli=1"
            }
            
            # Fresh request - don't use session to avoid any possible issues
            async with aiohttp.ClientSession(headers=auth_headers) as fresh_session:
                async with fresh_session.get(main_site) as response:
                    if response.status == 200:
                        logger.info("Successfully visited main site")
                    else:
                        logger.warning(f"Failed to visit main site: {response.status}")
                
                # Now visit the actual post URL
                async with fresh_session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        logger.info(f"Successfully fetched post with special method (length: {len(html)})")
                        
                        # Try to extract the full content directly using regex
                        full_content_match = re.search(r'<div class="body markup" dir="auto">(.*?)</div>\s*</div>\s*</?div', html, re.DOTALL)
                        if full_content_match:
                            content = full_content_match.group(1)
                            logger.info(f"Successfully extracted full content with regex (length: {len(content)})")
                            return html
                        
                        return html
                    else:
                        logger.error(f"Failed to fetch post with special method: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error in tradecompanion_direct_fetch: {e}")
            return None
    
    async def download_post(self, url: str, force: bool = False, download_images: bool = True, use_direct: bool = False) -> bool:
        """
        Download a post and save it as markdown.
        
        Args:
            url (str): Post URL
            force (bool, optional): Force re-download even if exists. Defaults to False.
            download_images (bool, optional): Download images. Defaults to True.
            use_direct (bool, optional): Use direct fetch method. Defaults to False.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Downloading post: {url}")
        
        # Extract slug from URL to use in filename
        slug = url.split('/')[-1]
        
        # Check if in database and skip if not changed (incremental mode)
        if self.incremental and not force:
            if self.sync.is_post_synced(url):
                logger.info(f"Skipping already synced post: {slug}")
                return "skipped"  # Return "skipped" instead of True to track skipped posts
        
        # Skip if already downloaded (unless force=True)
        if not force:
            existing_files = [f for f in os.listdir(self.output_dir) if f.endswith(f"_{slug}.md")]
            if existing_files:
                logger.info(f"Skipping already downloaded post: {slug}")
                return "skipped"  # Return "skipped" instead of True to track skipped posts
        
        # Get post content and metadata
        metadata = None
        html = None
        
        # Try direct fetch method if requested
        if use_direct:
            logger.info(f"Using direct fetch method for {url}...")
            post_data = await self.direct_fetch(url)
            if post_data:
                metadata = post_data
                html = post_data["html"]
        
        # For tradecompanion, try the special method if direct method wasn't used or failed
        if (not metadata or not html) and self.author == "tradecompanion" and self.auth_token:
            html = await self.tradecompanion_direct_fetch(url)
            if html:
                # Extract metadata from HTML
                metadata = await self.extract_post_metadata(html, url)
            
        # If both special methods failed or weren't used, fall back to normal fetch
        if not html:
            # Fetch the post
            html = await self._fetch_url(url)
            if html:
                # Extract metadata from HTML
                metadata = await self.extract_post_metadata(html, url)
        
        # If we failed to get content, exit
        if not html or not metadata:
            logger.error(f"Failed to fetch post: {url}")
            return False
        
        try:
            # Get metadata fields
            title = metadata["title"]
            formatted_date = metadata["date"]
            content_html = metadata["content_html"]
            
            # Store metadata in database
            self._store_post_metadata(metadata)
            
            # Update the last sync time
            if self.incremental:
                self.sync.mark_post_synced(url)
                # Save the state after each post is synced
                self.sync._save_state()
            
            # Process images if enabled
            if download_images:
                logger.info(f"Processing images for post: {title}")
                
                # Extract image URLs from HTML
                image_urls = await self.extract_image_urls(content_html, self.base_url)
                logger.info(f"Found {len(image_urls)} images to download")
                
                if image_urls:
                    # Download images in batch
                    image_map = await self.image_downloader.download_images_batch(
                        urls=list(image_urls),
                        prefix=slug,
                        verbose=self.verbose
                    )
                    
                    # Update image URLs in content
                    content_soup = BeautifulSoup(content_html, 'html.parser')
                    for img in content_soup.find_all('img'):
                        src = img.get('src')
                        if src and src in image_map:
                            # Update the image src attribute
                            img['src'] = image_map[src]
                    
                    # Update content_html with the modified image paths
                    content_html = str(content_soup)
            
            # Try to convert HTML to proper markdown
            try:
                from markdownify import markdownify
                content_markdown = markdownify(content_html)
            except ImportError:
                # If markdownify is not available, use a simpler conversion
                logger.warning("Warning: markdownify not available, using basic HTML")
                content_markdown = content_html
            
            # Generate markdown with frontmatter
            markdown = f"""---
title: "{title}"
date: "{formatted_date}"
original_url: "{url}"
---

# {title}

{content_markdown}
"""
            
            # Generate filename
            filename = f"{formatted_date}_{slug}.md"
            filepath = os.path.join(self.output_dir, filename)
            
            # Save the file
            logger.info(f"Saving to {filepath}...")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            # Verify the file was saved
            if os.path.exists(filepath):
                logger.info(f"File saved successfully: {os.path.getsize(filepath)} bytes")
            else:
                logger.error(f"File wasn't created: {filepath}")
                return False
            
            logger.info(f"Post downloaded successfully: {title}")
            return True
        
        except Exception as e:
            logger.error(f"Error processing post {url}: {e}")
            return False
    
    async def download_all_posts(
        self,
        max_pages: Optional[int] = None,
        force_refresh: bool = False,
        max_posts: Optional[int] = None,
        download_images: bool = True,
        use_direct: bool = False
    ) -> Tuple[int, int, int]:
        """
        Download all posts for the author.
        
        Args:
            max_pages (Optional[int], optional): Maximum archive pages to scan. Defaults to None.
            force_refresh (bool, optional): Force re-download posts. Defaults to False.
            max_posts (Optional[int], optional): Maximum number of posts. Defaults to None.
            download_images (bool, optional): Download images. Defaults to True.
            use_direct (bool, optional): Use direct fetch method. Defaults to False.
        
        Returns:
            Tuple[int, int, int]: (successful, failed, skipped) counts
        """
        logger.info(f"Starting download of posts from {self.author}.substack.com")
        
        # No need to do anything for start sync with the current implementation
        
        # Get post URLs
        post_urls = await self.find_post_urls(max_pages)
        
        # Exit if no URLs found
        if not post_urls:
            logger.warning(f"No post URLs found for {self.author}.substack.com")
            return 0, 0, 0
        
        # Limit the number of posts if specified
        if max_posts is not None:
            post_urls = post_urls[:max_posts]
        
        # Download each post concurrently with semaphore control
        tasks = []
        for url in post_urls:
            tasks.append(self.download_post(
                url=url,
                force=force_refresh,
                download_images=download_images,
                use_direct=use_direct
            ))
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        successful = 0
        failed = 0
        skipped = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error downloading post {post_urls[i]}: {result}")
                failed += 1
            elif result == "skipped":
                skipped += 1
            elif result is True:
                successful += 1
            else:
                failed += 1
        
        # Update sync completion time if in incremental mode
        if self.incremental:
            logger.info(f"Updating incremental sync time for {self.author}...")
            self.sync.update_sync_time()
            # Force an immediate save
            self.sync._save_state()
        
        # Print summary
        logger.info("=" * 50)
        logger.info(f"Download summary for {self.author}.substack.com:")
        logger.info(f"Total posts processed: {len(post_urls)}")
        logger.info(f"Successfully downloaded: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Skipped (already downloaded): {skipped}")
        logger.info("=" * 50)
        
        return successful, failed, skipped


async def direct_content_fetch(url: str, token: str = None):
    """
    Directly fetch content from a Substack post URL using a simplified approach.
    
    Args:
        url (str): Post URL to fetch
        token (str): Authentication token
    
    Returns:
        dict: Dictionary with post content and metadata
    """
    if not token:
        # Use the default token if none provided
        token = "s%3AN4m_2WeCcjjQaC4xkLvZ8ANHcRN7Fua2.igySoAeXZmVtYyTC085IR49LpujV7AnEoIgv%2FnZMcy4"
    
    # Extract author from URL
    url_parts = urlparse(url)
    author = url_parts.netloc.split('.')[0]
    
    # Headers that mimic a real browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Origin": "https://substack.com",
        "Referer": "https://substack.com/",
        "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-site": "same-site",
        "sec-fetch-dest": "document"
    }
    
    # Cookies for authentication
    cookies = {
        "substack.sid": token,
        "substack-sid": token,
        "substack.authpub": author,
        "substack.lli": "1",
        "ajs_anonymous_id": '"804903de-519a-4a25-92a8-d51b0613f8af"',
        "visit_id": '{%22id%22:%223f129271-fd95-4a8d-b704-c83644ac9ac3%22%2C%22timestamp%22:%222025-03-09T23%3A33%3A24.339Z%22}'
    }
    
    # Extract results
    content = None
    title = None
    date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # Make the request
        async with aiohttp.ClientSession(headers=headers) as session:
            # First visit the main page
            main_url = f"https://{author}.substack.com/"
            async with session.get(main_url, cookies=cookies) as response:
                if response.status != 200:
                    logger.error(f"Failed to visit main page: {response.status}")
                    return None
                
                logger.info("Successfully visited main page")
                
            # Now get the actual post    
            async with session.get(url, cookies=cookies) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch post: {response.status}")
                    return None
                
                html = await response.text()
                logger.info(f"Successfully fetched post (length: {len(html)})")
                
                # Extract the post content
                soup = BeautifulSoup(html, 'html.parser')
                
                # First try to extract the title
                title_elem = soup.select_one('h1.post-title')
                if title_elem:
                    title = title_elem.text.strip()
                else:
                    # Fallback to page title
                    title_elem = soup.select_one('title')
                    title = title_elem.text.strip() if title_elem else "Untitled Post"
                
                # Extract post date
                date_elem = soup.select_one('time')
                if date_elem and date_elem.get('datetime'):
                    try:
                        date_obj = datetime.fromisoformat(date_elem.get('datetime').replace('Z', '+00:00'))
                        date = date_obj.strftime('%Y-%m-%d')
                    except:
                        pass
                
                # First try BeautifulSoup to find the content
                body_markup = soup.select_one('div.body.markup')
                
                if body_markup:
                    logger.info(f"Found content div (length: {len(str(body_markup))})")
                    content = str(body_markup)
                else:
                    logger.warning("Couldn't find content with BeautifulSoup, trying regex")
                    # Try regex as fallback
                    match = re.search(r'<div class="body markup" dir="auto">(.*?)</div>\s*</div>\s*<div', html, re.DOTALL)
                    if match:
                        content = f'<div class="body markup" dir="auto">{match.group(1)}</div>'
                        logger.info(f"Found content with regex (length: {len(content)})")
                    else:
                        logger.error("Couldn't extract content with regex either")
                        content = "<p>Failed to extract content</p>"
                
                return {
                    "title": title,
                    "date": date,
                    "url": url,
                    "html": html,
                    "content_html": content
                }
                
    except Exception as e:
        logger.error(f"Error downloading post: {e}")
        return None

async def main():
    """Main function for running from command line."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Download posts from Substack with performance optimizations')
    parser.add_argument('--author', default=DEFAULT_AUTHOR, help=f'Substack author identifier (default: {DEFAULT_AUTHOR})')
    parser.add_argument('--output', default=DEFAULT_OUTPUT_DIR, help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})')
    parser.add_argument('--max-pages', type=int, help='Maximum number of archive pages to scan (default: scan all pages)')
    parser.add_argument('--max-posts', type=int, help='Maximum number of posts to download')
    parser.add_argument('--force', action='store_true', help='Force refresh of already downloaded posts')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--url', help='Download a specific URL instead of scanning archive')
    parser.add_argument('--no-images', action='store_true', help='Skip downloading images')
    parser.add_argument('--min-delay', type=float, default=DEFAULT_MIN_DELAY, help=f'Minimum delay between requests (default: {DEFAULT_MIN_DELAY})')
    parser.add_argument('--max-delay', type=float, default=DEFAULT_MAX_DELAY, help=f'Maximum delay between requests (default: {DEFAULT_MAX_DELAY})')
    parser.add_argument('--max-concurrency', type=int, default=DEFAULT_MAX_CONCURRENCY, help=f'Maximum concurrent requests (default: {DEFAULT_MAX_CONCURRENCY})')
    parser.add_argument('--max-image-concurrency', type=int, default=DEFAULT_MAX_IMAGE_CONCURRENCY, help=f'Maximum concurrent image downloads (default: {DEFAULT_MAX_IMAGE_CONCURRENCY})')
    parser.add_argument('--token', help='Substack authentication token for private content')
    parser.add_argument('--incremental', action='store_true', help='Only download new or updated content')
    parser.add_argument('--async-mode', action='store_true', help='Use async/aiohttp for downloading (default: True)')
    parser.add_argument('--clear-cache', action='store_true', help='Clear cache before starting')
    parser.add_argument('--use-sitemap', action='store_true', help='Use sitemap.xml for post discovery (default: True)')
    parser.add_argument('--no-sitemap', action='store_true', help='Skip using sitemap.xml for post discovery')
    parser.add_argument('--direct', action='store_true', help='Use direct simplified method for downloading (can only be used with --url)')
    
    args = parser.parse_args()
    
    # If direct method is selected, use the simplified direct fetcher
    if args.direct and args.url:
        logger.info(f"Using direct simplified method to download: {args.url}")
        
        # Get token from args or .env
        token = args.token
        if not token:
            try:
                from env_loader import load_env_vars, get_substack_auth
                load_env_vars()
                auth_info = get_substack_auth()
                token = auth_info.get('token')
            except ImportError:
                # Use hardcoded token as fallback
                token = "s%3AN4m_2WeCcjjQaC4xkLvZ8ANHcRN7Fua2.igySoAeXZmVtYyTC085IR49LpujV7AnEoIgv%2FnZMcy4"
        
        # Use direct fetch
        result = await direct_content_fetch(args.url, token)
        
        if result:
            # Create output directory
            author = urlparse(args.url).netloc.split('.')[0]
            output_dir = os.path.join(args.output, author)
            os.makedirs(output_dir, exist_ok=True)
            
            # Create markdown content
            content_html = result['content_html']
            title = result['title']
            date = result['date']
            
            # Try to convert HTML to proper markdown
            try:
                from markdownify import markdownify
                content_markdown = markdownify(content_html)
            except ImportError:
                # If markdownify is not available, use a simpler conversion
                logger.warning("Warning: markdownify not available, using basic HTML")
                content_markdown = content_html
            
            # Generate markdown with frontmatter
            markdown = f"""---
title: "{title}"
date: "{date}"
original_url: "{args.url}"
---

# {title}

{content_markdown}
"""
            
            # Generate filename
            slug = args.url.split('/')[-1]
            filename = f"{date}_{slug}.md"
            filepath = os.path.join(output_dir, filename)
            
            # Save the file
            logger.info(f"Saving to {filepath}...")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            # Verify the file was saved
            if os.path.exists(filepath):
                logger.info(f"File saved successfully: {os.path.getsize(filepath)} bytes")
                logger.info("Download successful")
            else:
                logger.error(f"File wasn't created: {filepath}")
        else:
            logger.error("Download failed")
        
        return
    
    # Use the full downloader class for other operations
    # Determine whether to download images
    download_images = not args.no_images
    
    # Determine whether to use sitemap
    # If both --use-sitemap and --no-sitemap are provided, respect --no-sitemap
    use_sitemap = True
    if args.no_sitemap:
        use_sitemap = False
    elif args.use_sitemap:
        use_sitemap = True
        
    # Create and configure the downloader
    async with SubstackDirectDownloader(
        author=args.author,
        output_dir=args.output,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        max_concurrency=args.max_concurrency,
        max_image_concurrency=args.max_image_concurrency,
        verbose=args.verbose,
        incremental=args.incremental,
        use_sitemap=use_sitemap
    ) as downloader:
        # Set authentication token if provided
        if args.token:
            downloader.set_auth_token(args.token)
        else:
            # Try to load from env_loader if available
            try:
                # Force clear all cache every time to ensure fresh content
                api_count, page_count = downloader.cache.clear_all_cache()
                logger.info(f"Pre-emptively cleared {api_count} API and {page_count} page cache entries")
                
                from env_loader import load_env_vars, get_substack_auth
                load_env_vars()
                auth_info = get_substack_auth()
                
                # Get token from .env
                token = auth_info.get('token')
                email = auth_info.get('email')
                password = auth_info.get('password')
                
                if token:
                    logger.info("Using authentication token from .env file")
                    # Make sure to update token with the latest one (from command line)
                    token = "s%3AN4m_2WeCcjjQaC4xkLvZ8ANHcRN7Fua2.igySoAeXZmVtYyTC085IR49LpujV7AnEoIgv%2FnZMcy4"
                    downloader.set_auth_token(token)
                    
                    # Force re-authentication by visiting login page
                    if email and password:
                        logger.info("Performing additional authentication steps to ensure full content access")
                        await downloader.perform_login(email, password)
            except ImportError:
                logger.debug("env_loader module not found, continuing without authentication")
        
        # Clear cache if requested
        if args.clear_cache:
            api_count, page_count = downloader.cache.clear_all_cache()
            logger.info(f"Cleared {api_count} API and {page_count} page cache entries")
        
        # Download specific URL or all posts
        if args.url:
            logger.info(f"Downloading specific URL: {args.url}")
            result = await downloader.download_post(
                url=args.url,
                force=args.force,
                download_images=download_images,
                use_direct=args.direct
            )
            if result:
                logger.info("Download successful")
            else:
                logger.error("Download failed")
        else:
            await downloader.download_all_posts(
                max_pages=args.max_pages,
                force_refresh=args.force,
                max_posts=args.max_posts,
                download_images=download_images,
                use_direct=args.direct
            )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Download interrupted by user")
        sys.exit(0)