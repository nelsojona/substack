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
        include_comments (bool): Whether to include comments in the output
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
        use_sitemap: bool = True,
        include_comments: bool = False
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
            include_comments (bool): Whether to include comments in the output. Defaults to False.
        """
        self.author = author
        self.base_url = f"https://{author}.substack.com"
        self.output_dir = os.path.join(output_dir, author)
        self.image_dir = os.path.join(self.output_dir, image_dir)
        self.verbose = verbose
        self.incremental = incremental
        self.use_sitemap = use_sitemap
        self.include_comments = include_comments
        
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
    
    async def _fetch_url(self, url: str, retries: int = 3) -> Optional[str]:
        """
        Fetch a URL using aiohttp with caching and throttling.
        
        Args:
            url (str): URL to fetch
            retries (int, optional): Number of retries. Defaults to 3.
        
        Returns:
            Optional[str]: Response HTML or None if failed
        """
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
                    
                    # Make the request
                    async with self.session.get(url) as response:
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
    
    async def extract_post_metadata(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from post HTML.
        
        Args:
            html (str): Post HTML
            url (str): Post URL
            
        Returns:
            Optional[Dict[str, Any]]: Post metadata or None if failed
        """
        try:
            # Parse the HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            title_elem = soup.select_one('h1.post-title')
            if not title_elem:
                title_elem = soup.select_one('h1')
            
            if not title_elem:
                logger.error(f"Could not find title for {url}")
                return None
            
            title = title_elem.get_text().strip()
            
            # Extract date
            date_elem = soup.select_one('time')
            if not date_elem:
                date_elem = soup.select_one('.post-date')
            
            if date_elem:
                date_str = date_elem.get_text().strip()
                try:
                    # Try to parse the date
                    date_obj = datetime.strptime(date_str, '%B %d, %Y')
                    formatted_date = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    # If parsing fails, use current date
                    logger.warning(f"Could not parse date '{date_str}' for {url}, using current date")
                    formatted_date = datetime.now().strftime('%Y-%m-%d')
            else:
                logger.warning(f"Could not find date for {url}, using current date")
                formatted_date = datetime.now().strftime('%Y-%m-%d')
            
            # Extract content
            content_elem = soup.select_one('div.post-content')
            if not content_elem:
                content_elem = soup.select_one('div.body')
            
            if not content_elem:
                logger.error(f"Could not find content for {url}")
                return None
            
            content_html = str(content_elem)
            
            # Extract author
            author_elem = soup.select_one('.post-author')
            if not author_elem:
                author_elem = soup.select_one('.author-name')
            
            author = author_elem.get_text().strip() if author_elem else self.author
            
            # Create metadata object
            metadata = {
                "title": title,
                "date": formatted_date,
                "author": author,
                "url": url,
                "content_html": content_html
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting metadata from {url}: {e}")
            return None
    
    def _store_post_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Store post metadata in the database.
        
        Args:
            metadata (Dict[str, Any]): Post metadata
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create post record
            post_data = {
                "title": metadata["title"],
                "date": metadata["date"],
                "author": metadata.get("author", self.author),
                "url": metadata["url"],
                "content_hash": hashlib.md5(metadata["content_html"].encode()).hexdigest()
            }
            
            # Store in database
            self.db.store_post(post_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing metadata: {e}")
            return False
    
    def set_auth_token(self, token: str) -> None:
        """
        Set the authentication token for accessing private content.
        
        Args:
            token (str): Substack authentication token
        """
        self.auth_token = token
        logger.info("Authentication token set")
        
        # If session already exists, update cookies
        if self.session:
            self.session.cookie_jar.update_cookies({
                "substack.sid": token,
                "substack-sid": token,
                "substack.authpub": self.author,
                "substack-auth": "1"
            })
            logger.info("Updated session cookies with authentication token")
    
    async def extract_image_urls(self, html: str, base_url: str) -> Set[str]:
        """
        Extract image URLs from HTML.
        
        Args:
            html (str): HTML content
            base_url (str): Base URL for resolving relative URLs
            
        Returns:
            Set[str]: Set of image URLs
        """
        image_urls = set()
        
        try:
            # Parse the HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all image tags
            for img in soup.find_all('img'):
                src = img.get('src')
                if src:
                    # Resolve relative URLs
                    if not src.startswith(('http://', 'https://')):
                        src = urljoin(base_url, src)
                    
                    image_urls.add(src)
            
            return image_urls
            
        except Exception as e:
            logger.error(f"Error extracting image URLs: {e}")
            return set()
    
    async def direct_fetch(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch post data directly using a simplified method.
        
        Args:
            url (str): Post URL
            
        Returns:
            Optional[Dict[str, Any]]: Post data or None if failed
        """
        try:
            logger.info(f"Using direct fetch method for {url}")
            
            # Extract post ID from URL
            post_id = url.split('/')[-1]
            
            # Construct API URL
            api_url = f"{self.base_url}/api/v1/posts/{post_id}"
            
            # Fetch post data from API
            async with self.session.get(api_url) as response:
                if response.status == 200:
                    post_data = await response.json()
                    
                    # Extract relevant fields
                    title = post_data.get("title", "")
                    body_html = post_data.get("body_html", "")
                    published_at = post_data.get("published_at", "")
                    
                    # Format date
                    try:
                        date_obj = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                        formatted_date = date_obj.strftime('%Y-%m-%d')
                    except (ValueError, AttributeError):
                        logger.warning(f"Could not parse date '{published_at}' for {url}, using current date")
                        formatted_date = datetime.now().strftime('%Y-%m-%d')
                    
                    # Create metadata object
                    metadata = {
                        "title": title,
                        "date": formatted_date,
                        "author": self.author,
                        "url": url,
                        "content_html": body_html,
                        "html": body_html
                    }
                    
                    return metadata
                else:
                    logger.error(f"API error {response.status} for {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error in direct fetch for {url}: {e}")
            return None
    
    async def tradecompanion_direct_fetch(self, url: str) -> Optional[str]:
        """
        Special fetch method for Trade Companion posts.
        
        Args:
            url (str): Post URL
            
        Returns:
            Optional[str]: HTML content or None if failed
        """
        try:
            logger.info(f"Using Trade Companion special fetch method for {url}")
            
            # Extract post ID from URL
            post_id = url.split('/')[-1]
            
            # Construct API URL with auth token
            api_url = f"{self.base_url}/api/v1/posts/{post_id}"
            
            # Add special headers for Trade Companion
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            }
            
            # Add cookies for authentication
            cookies = {
                "substack.sid": self.auth_token,
                "substack-sid": self.auth_token,
                "substack.authpub": self.author,
                "substack-auth": "1"
            }
            
            # Fetch post data from API
            async with self.session.get(api_url, headers=headers, cookies=cookies) as response:
                if response.status == 200:
                    post_data = await response.json()
                    
                    # Extract HTML content
                    body_html = post_data.get("body_html", "")
                    
                    # Create a full HTML document
                    title = post_data.get("title", "")
                    published_at = post_data.get("published_at", "")
                    
                    html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>{title}</title>
                        <meta name="date" content="{published_at}">
                    </head>
                    <body>
                        <h1 class="post-title">{title}</h1>
                        <time>{published_at}</time>
                        <div class="post-content">{body_html}</div>
                    </body>
                    </html>
                    """
                    
                    return html
                else:
                    logger.error(f"API error {response.status} for {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error in Trade Companion fetch for {url}: {e}")
            return None
    
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
        
        # Parse the XML content
        try:
            root = ET.fromstring(sitemap_content)
            
            # Extract URLs from sitemap
            namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for url_elem in root.findall(".//ns:url", namespace):
                loc_elem = url_elem.find("ns:loc", namespace)
                if loc_elem is not None:
                    url = loc_elem.text
                    
                    # Only include post URLs
                    if "/p/" in url:
                        post_urls.append(url)
            
            logger.info(f"Found {len(post_urls)} post URLs in sitemap")
            return post_urls
            
        except ET.ParseError as e:
            logger.error(f"Error parsing sitemap XML: {e}")
            return post_urls
    
    async def _find_post_urls_from_root_page(self) -> List[str]:
        """
        Find post URLs by parsing the root page.
        
        Returns:
            List[str]: List of post URLs
        """
        post_urls = []
        
        # Fetch the root page
        root_url = self.base_url
        html = await self._fetch_url(root_url)
        
        if not html:
            logger.warning(f"Could not fetch root page from {root_url}")
            return post_urls
        
        # Parse the HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all post links
        for a in soup.find_all('a', href=True):
            href = a['href']
            
            # Only include post URLs
            if "/p/" in href:
                # Resolve relative URLs
                if not href.startswith(('http://', 'https://')):
                    href = urljoin(root_url, href)
                
                post_urls.append(href)
        
        # Remove duplicates
        post_urls = list(set(post_urls))
        
        logger.info(f"Found {len(post_urls)} post URLs on root page")
        return post_urls
    
    async def _find_post_urls_from_standard_archive(self, max_pages: Optional[int] = None) -> List[str]:
        """
        Find post URLs by parsing the archive pages.
        
        Args:
            max_pages (Optional[int], optional): Maximum number of pages to scan.
                                              If None, scans all pages.
        
        Returns:
            List[str]: List of post URLs
        """
        post_urls = []
        page = 1
        
        while True:
            # Check if we've reached the maximum number of pages
            if max_pages and page > max_pages:
                break
            
            # Fetch the archive page
            archive_url = f"{self.base_url}/archive?sort=new&page={page}"
            html = await self._fetch_url(archive_url)
            
            if not html:
                logger.warning(f"Could not fetch archive page {page} from {archive_url}")
                break
            
            # Parse the HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all post links
            page_urls = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                
                # Only include post URLs
                if "/p/" in href:
                    # Resolve relative URLs
                    if not href.startswith(('http://', 'https://')):
                        href = urljoin(self.base_url, href)
                    
                    page_urls.append(href)
            
            # Remove duplicates
            page_urls = list(set(page_urls))
            
            # If we didn't find any new URLs, we've reached the end
            if not page_urls or all(url in post_urls for url in page_urls):
                break
            
            # Add new URLs to the list
            post_urls.extend(page_urls)
            
            logger.info(f"Found {len(page_urls)} post URLs on archive page {page}")
            
            # Increment page number
            page += 1
            
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(1)
        
        # Remove duplicates
        post_urls = list(set(post_urls))
        
        logger.info(f"Found {len(post_urls)} post URLs in archive")
        return post_urls
    
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
    
    async def extract_comments(self, url: str) -> List[Dict[str, Any]]:
        """
        Extract comments from a post.
        
        Args:
            url (str): Post URL
            
        Returns:
            List[Dict[str, Any]]: List of comment objects with their metadata and replies
        """
        logger.info(f"Extracting comments from post: {url}")
        
        # Fetch the post HTML
        html = await self._fetch_url(url)
        if not html:
            logger.error(f"Failed to fetch post for comment extraction: {url}")
            return []
        
        # Parse the HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Try to find the comments section
        comments_section = soup.select_one('div#comments')
        if not comments_section:
            # Try alternative selectors for comments section
            comments_section = soup.select_one('div.comments-section')
        
        if not comments_section:
            logger.info(f"No comments section found for post: {url}")
            return []
        
        # Extract comments data from JavaScript
        comments_data = self._extract_comments_from_js(html)
        if comments_data:
            logger.info(f"Found {len(comments_data)} comments from JavaScript data")
            return comments_data
        
        # If JavaScript extraction failed, try HTML extraction
        comments = []
        
        # Find all top-level comments
        comment_elements = comments_section.select('div.comment-thread > div.comment')
        
        logger.info(f"Found {len(comment_elements)} top-level comments in HTML")
        
        for comment_elem in comment_elements:
            comment = self._parse_comment_element(comment_elem)
            if comment:
                comments.append(comment)
        
        return comments
    
    def _extract_comments_from_js(self, html: str) -> List[Dict[str, Any]]:
        """
        Extract comments data from JavaScript in the HTML.
        
        Args:
            html (str): HTML content
            
        Returns:
            List[Dict[str, Any]]: List of comment objects
        """
        try:
            # Look for comments data in JavaScript
            # First try the preloaded state pattern
            preloaded_match = re.search(r'window\.__PRELOADED_STATE__ = JSON\.parse\("(.+?)"\);', html)
            if preloaded_match:
                json_str = preloaded_match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                preloaded_state = json.loads(json_str)
                
                # Look for comments in preloaded state
                if 'commentsByPostId' in preloaded_state:
                    # Get the post ID
                    post_id = None
                    if 'postBySlug' in preloaded_state and 'id' in preloaded_state['postBySlug']:
                        post_id = preloaded_state['postBySlug']['id']
                    elif 'post' in preloaded_state and 'id' in preloaded_state['post']:
                        post_id = preloaded_state['post']['id']
                    
                    if post_id and post_id in preloaded_state['commentsByPostId']:
                        comments_data = preloaded_state['commentsByPostId'][post_id]
                        return self._process_comments_data(comments_data)
            
            # Try Apollo state pattern
            apollo_match = re.search(r'window\.__APOLLO_STATE__ =\s*({.+?});', html, re.DOTALL)
            if apollo_match:
                apollo_state = json.loads(apollo_match.group(1))
                
                # Extract comments from Apollo state
                comments = []
                for key, value in apollo_state.items():
                    if isinstance(value, dict) and 'body' in value and 'parentCommentId' in value:
                        # This looks like a comment object
                        comment = {
                            'id': value.get('id'),
                            'body': value.get('body'),
                            'author': value.get('commenter', {}).get('name', 'Anonymous'),
                            'date': value.get('createdAt'),
                            'parent_id': value.get('parentCommentId'),
                            'replies': []
                        }
                        comments.append(comment)
                
                # Organize comments into a tree structure
                return self._organize_comments_tree(comments)
            
            # Try Next.js data pattern
            next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application\/json">(.+?)<\/script>', html, re.DOTALL)
            if next_data_match:
                next_data = json.loads(next_data_match.group(1))
                
                # Try to find comments in Next.js data
                if 'props' in next_data and 'pageProps' in next_data['props']:
                    page_props = next_data['props']['pageProps']
                    
                    # Look for comments in common locations
                    if 'comments' in page_props:
                        return self._process_comments_data(page_props['comments'])
                    elif 'post' in page_props and 'comments' in page_props['post']:
                        return self._process_comments_data(page_props['post']['comments'])
            
            return []
            
        except Exception as e:
            logger.error(f"Error extracting comments from JavaScript: {e}")
            return []
    
    def _process_comments_data(self, comments_data: List[Dict]) -> List[Dict[str, Any]]:
        """
        Process raw comments data from JavaScript.
        
        Args:
            comments_data (List[Dict]): Raw comments data
            
        Returns:
            List[Dict[str, Any]]: Processed comments with proper structure
        """
        processed_comments = []
        
        for comment in comments_data:
            processed_comment = {
                'id': comment.get('id'),
                'body': comment.get('body'),
                'author': comment.get('commenter', {}).get('name', 'Anonymous'),
                'date': comment.get('createdAt'),
                'parent_id': comment.get('parentCommentId'),
                'replies': []
            }
            
            processed_comments.append(processed_comment)
        
        # Organize into tree structure
        return self._organize_comments_tree(processed_comments)
    
    def _organize_comments_tree(self, comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Organize flat comments list into a tree structure with replies.
        
        Args:
            comments (List[Dict[str, Any]]): Flat list of comments
            
        Returns:
            List[Dict[str, Any]]: Tree structure with top-level comments and nested replies
        """
        # Create a map of comments by ID for quick lookup
        comment_map = {comment['id']: comment for comment in comments if 'id' in comment}
        
        # Organize into tree structure
        top_level_comments = []
        
        for comment in comments:
            # Skip comments without ID
            if 'id' not in comment:
                continue
                
            parent_id = comment.get('parent_id')
            
            if not parent_id:
                # This is a top-level comment
                top_level_comments.append(comment)
            else:
                # This is a reply
                if parent_id in comment_map:
                    parent = comment_map[parent_id]
                    if 'replies' not in parent:
                        parent['replies'] = []
                    parent['replies'].append(comment)
        
        return top_level_comments
    
    def _parse_comment_element(self, comment_elem) -> Dict[str, Any]:
        """
        Parse a comment element from HTML.
        
        Args:
            comment_elem: BeautifulSoup element representing a comment
            
        Returns:
            Dict[str, Any]: Comment data with metadata and replies
        """
        try:
            # Extract comment ID
            comment_id = comment_elem.get('id', '').replace('comment-', '')
            
            # Extract comment body
            body_elem = comment_elem.select_one('div.comment-body')
            body = body_elem.get_text().strip() if body_elem else ""
            
            # Extract author
            author_elem = comment_elem.select_one('div.comment-author')
            author = author_elem.get_text().strip() if author_elem else "Anonymous"
            
            # Extract date
            date_elem = comment_elem.select_one('div.comment-date')
            date = date_elem.get_text().strip() if date_elem else ""
            
            # Create comment object
            comment = {
                'id': comment_id,
                'body': body,
                'author': author,
                'date': date,
                'replies': []
            }
            
            # Extract replies
            replies_elem = comment_elem.select_one('div.comment-replies')
            if replies_elem:
                reply_elements = replies_elem.select('div.comment')
                for reply_elem in reply_elements:
                    reply = self._parse_comment_element(reply_elem)
                    if reply:
                        comment['replies'].append(reply)
            
            return comment
            
        except Exception as e:
            logger.error(f"Error parsing comment element: {e}")
            return None
    
    def _format_comments_markdown(self, comments: List[Dict[str, Any]], level: int = 0) -> str:
        """
        Format comments as markdown with proper indentation for replies.
        
        Args:
            comments (List[Dict[str, Any]]): List of comment objects
            level (int, optional): Current indentation level. Defaults to 0.
            
        Returns:
            str: Formatted markdown string
        """
        if not comments:
            return ""
            
        markdown = ""
        indent = "  " * level
        
        for comment in comments:
            # Add comment header with author and date
            author = comment.get('author', 'Anonymous')
            date = comment.get('date', '')
            if date:
                markdown += f"{indent}**{author}** - {date}\n\n"
            else:
                markdown += f"{indent}**{author}**\n\n"
            
            # Add comment body with proper indentation
            body = comment.get('body', '').strip()
            for line in body.split('\n'):
                markdown += f"{indent}{line}\n"
            
            markdown += "\n"
            
            # Add replies with increased indentation
            replies = comment.get('replies', [])
            if replies:
                markdown += self._format_comments_markdown(replies, level + 1)
                markdown += "\n"
        
        return markdown
    
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
            
            # Extract comments if enabled
            comments_markdown = ""
            if self.include_comments:
                logger.info(f"Extracting comments for post: {url}")
                comments = await self.extract_comments(url)
                
                if comments:
                    logger.info(f"Found {len(comments)} comments")
                    comments_markdown = "\n\n## Comments\n\n"
                    comments_markdown += self._format_comments_markdown(comments)
                else:
                    logger.info("No comments found")
            
            # Generate markdown with frontmatter
            markdown = f"""---
title: "{title}"
date: "{formatted_date}"
original_url: "{url}"
---

# {title}

{content_markdown}
{comments_markdown}"""
            
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

async def main():
    """Main entry point for the script."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Download Substack posts directly without API')
    parser.add_argument('--author', type=str, default=DEFAULT_AUTHOR, help='Substack author identifier')
    parser.add_argument('--output', type=str, default=DEFAULT_OUTPUT_DIR, help='Output directory')
    parser.add_argument('--image-dir', type=str, default=DEFAULT_IMAGE_DIR, help='Image directory (relative to output)')
    parser.add_argument('--token', type=str, help='Authentication token for private content')
    parser.add_argument('--url', type=str, help='Specific post URL to download')
    parser.add_argument('--force', action='store_true', help='Force re-download even if exists')
    parser.add_argument('--no-images', action='store_true', help='Skip downloading images')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--incremental', action='store_true', help='Enable incremental sync')
    parser.add_argument('--min-delay', type=float, default=DEFAULT_MIN_DELAY, help='Minimum delay between requests')
    parser.add_argument('--max-delay', type=float, default=DEFAULT_MAX_DELAY, help='Maximum delay between requests')
    parser.add_argument('--max-concurrency', type=int, default=DEFAULT_MAX_CONCURRENCY, help='Maximum concurrent requests')
    parser.add_argument('--max-image-concurrency', type=int, default=DEFAULT_MAX_IMAGE_CONCURRENCY, help='Maximum concurrent image downloads')
    parser.add_argument('--cache-ttl', type=int, default=DEFAULT_CACHE_TTL, help='Cache TTL in seconds')
    parser.add_argument('--max-posts', type=int, help='Maximum number of posts to download')
    parser.add_argument('--no-sitemap', action='store_true', help='Skip using sitemap.xml for post discovery')
    parser.add_argument('--direct', action='store_true', help='Use direct simplified method for downloading (can only be used with --url)')
    parser.add_argument('--include-comments', action='store_true', help='Include comments in the output')
    
    args = parser.parse_args()
    
    # Create downloader instance
    async with SubstackDirectDownloader(
        author=args.author,
        output_dir=args.output,
        image_dir=args.image_dir,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        max_concurrency=args.max_concurrency,
        max_image_concurrency=args.max_image_concurrency,
        cache_ttl=args.cache_ttl,
        verbose=args.verbose,
        incremental=args.incremental,
        use_sitemap=not args.no_sitemap,
        include_comments=args.include_comments
    ) as downloader:
        # Set authentication token if provided
        if args.token:
            downloader.set_auth_token(args.token)
        
        # Download a specific post if URL is provided
        if args.url:
            result = await downloader.download_post(
                url=args.url,
                force=args.force,
                download_images=not args.no_images,
                use_direct=args.direct
            )
            
            if result == "skipped":
                logger.info(f"Skipped post: {args.url}")
            elif result:
                logger.info(f"Successfully downloaded post: {args.url}")
            else:
                logger.error(f"Failed to download post: {args.url}")
                sys.exit(1)
        else:
            # Find and download all posts
            post_urls = await downloader.find_post_urls()
            
            # Limit the number of posts if specified
            if args.max_posts and len(post_urls) > args.max_posts:
                logger.info(f"Limiting to {args.max_posts} posts (found {len(post_urls)})")
                post_urls = post_urls[:args.max_posts]
            
            logger.info(f"Found {len(post_urls)} posts to download")
            
            # Download each post
            success_count = 0
            skipped_count = 0
            failed_count = 0
            
            for i, url in enumerate(post_urls):
                logger.info(f"Downloading post {i+1}/{len(post_urls)}: {url}")
                
                result = await downloader.download_post(
                    url=url,
                    force=args.force,
                    download_images=not args.no_images
                )
                
                if result == "skipped":
                    logger.info(f"Skipped post: {url}")
                    skipped_count += 1
                elif result:
                    logger.info(f"Successfully downloaded post: {url}")
                    success_count += 1
                else:
                    logger.error(f"Failed to download post: {url}")
                    failed_count += 1
            
            # Print summary
            logger.info(f"Download complete: {success_count} successful, {skipped_count} skipped, {failed_count} failed")

if __name__ == "__main__":
    asyncio.run(main())
