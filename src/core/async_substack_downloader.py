#!/usr/bin/env python3
"""
Async Substack Downloader Module

This module provides functionality for downloading Substack posts using asyncio/aiohttp.
It replaces the synchronous requests with asynchronous aiohttp and implements
semaphore control for concurrency limits.
"""

import os
import re
import json
import time
import asyncio
import logging
import aiohttp
from typing import Dict, List, Set, Any, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from connection_pool import ConnectionPool
from adaptive_throttler import AsyncAdaptiveThrottler
from markdown_converter import MarkdownConverter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("async_downloader")

class AsyncSubstackDownloader:
    """
    A class for downloading Substack posts asynchronously.
    
    Attributes:
        author (str): Substack author name.
        output_dir (str): Directory to save downloaded posts.
        max_concurrency (int): Maximum number of concurrent downloads.
        session (aiohttp.ClientSession): HTTP session for making requests.
        throttler (AsyncAdaptiveThrottler): Throttler for rate limiting.
        semaphore (asyncio.Semaphore): Semaphore for limiting concurrency.
        auth_token (str): Authentication token for accessing private content.
    """
    
    def __init__(
        self,
        author: str,
        output_dir: str = "output",
        max_concurrency: int = 5,
        min_delay: float = 0.5,
        max_delay: float = 5.0
    ):
        """
        Initialize the AsyncSubstackDownloader.
        
        Args:
            author (str): Substack author name.
            output_dir (str, optional): Directory to save downloaded posts. 
                                      Defaults to "output".
            max_concurrency (int, optional): Maximum number of concurrent downloads. 
                                           Defaults to 5.
            min_delay (float, optional): Minimum delay between requests in seconds. 
                                       Defaults to 0.5.
            max_delay (float, optional): Maximum delay between requests in seconds. 
                                       Defaults to 5.0.
        """
        self.author = author
        self.output_dir = output_dir
        self.max_concurrency = max_concurrency
        self.session = None
        self.throttler = AsyncAdaptiveThrottler(min_delay=min_delay, max_delay=max_delay)
        self.semaphore = None
        self.auth_token = None
        self.min_delay = min_delay
        self.max_delay = max_delay
        
        # Create the output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def __aenter__(self):
        """Async context manager entry."""
        # Create a session
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )
        
        # Create a semaphore
        self.semaphore = asyncio.Semaphore(self.max_concurrency)
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def set_auth_token(self, token: str) -> None:
        """
        Set the authentication token for accessing private content.
        
        Args:
            token (str): Authentication token.
        """
        self.auth_token = token
        
        # Update the session cookies if session exists
        if self.session:
            # Create a new cookie jar with the token
            cookies = {
                "substack.sid": token,
                "substack-sid": token
            }
            
            # Update the session's cookie jar
            await self.session.cookie_jar.update_cookies(cookies)
    
    async def _fetch_url(self, url: str, retries: int = 3) -> Optional[str]:
        """
        Fetch a URL and return the response text.
        
        Args:
            url (str): URL to fetch.
            retries (int, optional): Number of retries. Defaults to 3.
        
        Returns:
            Optional[str]: Response text, or None if the request failed.
        """
        # Extract the domain from the URL
        domain = urlparse(url).netloc
        
        # Throttle the request
        await self.throttler.async_throttle(domain)
        
        # Use the semaphore to limit concurrency
        async with self.semaphore:
            for attempt in range(retries):
                try:
                    start_time = time.time()
                    
                    # Create a dictionary of headers for the throttler
                    headers_dict = {}
                    
                    # Prepare cookies if auth token is set
                    cookies = {}
                    if self.auth_token:
                        cookies = {
                            "substack.sid": self.auth_token,
                            "substack-sid": self.auth_token
                        }
                    
                    # Make the request
                    async with self.session.get(url, cookies=cookies) as response:
                        # Calculate the response time
                        response_time = time.time() - start_time
                        
                        # Get headers as a dictionary
                        if hasattr(response, 'headers') and response.headers:
                            # Check if headers is a dict-like object
                            if hasattr(response.headers, 'items'):
                                headers_dict = dict(response.headers.items())
                        
                        # Update the throttler based on the response
                        await self.throttler.update_from_response(
                            status_code=response.status,
                            response_time=response_time,
                            rate_limit_headers=headers_dict,
                            domain=domain
                        )
                        
                        # Check if the request was successful
                        if response.status == 200:
                            return await response.text()
                        
                        # Handle rate limiting
                        if response.status == 429:
                            # Exponential backoff
                            wait_time = 2 ** attempt
                            logger.warning(f"Rate limited. Retrying in {wait_time} seconds...")
                            await asyncio.sleep(wait_time)
                            continue
                        
                        # Handle other errors
                        logger.error(f"Error fetching {url}: {response.status}")
                        return None
                
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"Error fetching {url}: {e}. Retrying ({attempt + 1}/{retries})...")
                    
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
            
            # All retries failed
            logger.error(f"Failed to fetch {url} after {retries} retries")
            return None
    
    async def find_post_urls(self, max_pages: int = 1) -> List[str]:
        """
        Find post URLs for the author.
        
        Args:
            max_pages (int, optional): Maximum number of pages to fetch. 
                                     Defaults to 1.
        
        Returns:
            List[str]: List of post URLs.
        """
        post_urls = []
        
        # Build the URL
        base_url = f"https://{self.author}.substack.com"
        archive_url = f"{base_url}/archive"
        
        # Fetch the archive pages
        for page in range(1, max_pages + 1):
            # Build the page URL
            page_url = f"{archive_url}?sort=new&page={page}" if page > 1 else archive_url
            
            # Fetch the page
            html = await self._fetch_url(page_url)
            
            if not html:
                break
            
            # Parse the HTML
            soup = BeautifulSoup(html, "html.parser")
            
            # Find post links - try different selectors that might match Substack's HTML structure
            post_links = soup.select("a.post-preview-title")
            if not post_links:
                post_links = soup.select("a[href*='/p/']")
            
            for post_link in post_links:
                href = post_link.get("href")
                
                if not href or not href.strip():
                    continue
                
                # Skip non-post links
                if "/p/" not in href:
                    continue
                
                # Make the URL absolute
                post_url = urljoin(base_url, href)
                
                # Add the URL to the list if not already present
                if post_url not in post_urls:
                    post_urls.append(post_url)
            
            # Check if there are more pages
            next_link = soup.select_one("a.next-page")
            if not next_link:
                # Alternative way to find the next page link
                next_link = soup.select_one("a[href*='archive?sort=new&page=']")
                
            if not next_link:
                break
        
        return post_urls
    
    async def direct_fetch(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Direct fetch method to reliably get full post content.
        
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
            token = self.auth_token
            cookies = {
                "substack.sid": token,
                "substack-sid": token,
                "substack.authpub": author,
                "substack.lli": "1"
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
                        
                        # Extract date (for simple implementation we'll just use today's date)
                        from datetime import datetime
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
                                content_elem = soup.select_one("div.body")
                                if content_elem:
                                    content_html = str(content_elem)
                                    logger.info(f"Found content using div.body selector (length: {len(content_html)})")
                                else:
                                    logger.error("Couldn't extract content with any method")
                                    content_html = "<p>Failed to extract content</p>"
                        
                        # Return the post data dictionary
                        return {
                            "title": title,
                            "date": formatted_date,
                            "url": url,
                            "content_html": content_html,
                            "html": html
                        }
                    else:
                        logger.error(f"Failed to fetch post with direct method: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error in direct_fetch: {e}")
            return None
            
    async def download_post(self, url: str, force: bool = False, download_images: bool = False, use_direct: bool = False) -> bool:
        """
        Download a post and save it as Markdown.
        
        Args:
            url (str): Post URL.
            force (bool, optional): Whether to force refresh the post. Defaults to False.
            download_images (bool, optional): Whether to download images. Defaults to False.
            use_direct (bool, optional): Use direct fetch method. Defaults to False.
            
        Returns:
            bool: True if the post was downloaded successfully, False otherwise.
        """
        # Get content using direct method if requested
        if use_direct:
            data = await self.direct_fetch(url)
            if data:
                title = data["title"]
                content_html = data["content_html"]
                
                # Convert HTML to Markdown
                markdown = MarkdownConverter.convert_html_to_markdown(content_html)
                
                # Extract slug from URL
                slug_match = re.search(r"/p/([^/]+)", url)
                if not slug_match:
                    logger.error(f"Could not extract slug from {url}")
                    return False
                
                slug = slug_match.group(1)
                
                # Save the Markdown file with date prefix
                markdown_file = os.path.join(self.output_dir, f"{data['date']}_{slug}.md")
                
                with open(markdown_file, "w", encoding="utf-8") as f:
                    f.write(markdown)
                
                return True
        
        # Otherwise use the standard method
        # Fetch the post page
        html = await self._fetch_url(url)
        
        if not html:
            return False
        
        # Parse the HTML
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract post title
        title_elem = soup.select_one("h1.post-title")
        if not title_elem:
            logger.error(f"Could not find post title for {url}")
            return False
        
        title = title_elem.get_text(strip=True)
        
        # Extract post slug
        slug_match = re.search(r"/p/([^/]+)", url)
        if not slug_match:
            logger.error(f"Could not extract slug from {url}")
            return False
        
        slug = slug_match.group(1)
        
        # Extract post content
        content_elem = soup.select_one("div.body")
        if not content_elem:
            logger.error(f"Could not find post content for {url}")
            return False
        
        # Convert HTML to Markdown
        markdown = MarkdownConverter.convert_html_to_markdown(str(content_elem))
        
        # Save the Markdown file
        markdown_file = os.path.join(self.output_dir, f"{slug}.md")
        
        with open(markdown_file, "w", encoding="utf-8") as f:
            f.write(markdown)
        
        return True
    
    async def download_all_posts(
        self,
        max_pages: int = 1,
        force_refresh: bool = False,
        max_posts: Optional[int] = None,
        download_images: bool = False,
        use_direct: bool = False
    ) -> Tuple[int, int, int]:
        """
        Download all posts for the author.
        
        Args:
            max_pages (int, optional): Maximum number of pages to fetch. Defaults to 1.
            force_refresh (bool, optional): Whether to force refresh posts. Defaults to False.
            max_posts (Optional[int], optional): Maximum number of posts to download. Defaults to None.
            download_images (bool, optional): Whether to download images. Defaults to False.
            use_direct (bool, optional): Use direct fetch method. Defaults to False.
        
        Returns:
            Tuple[int, int, int]: Tuple of (successful, failed, skipped) counts.
        """
        # Find post URLs
        post_urls = await self.find_post_urls(max_pages=max_pages)
        
        # Calculate how many posts to skip based on max_posts
        total_posts = len(post_urls)
        skipped = 0
        
        if max_posts is not None and max_posts < total_posts:
            skipped = total_posts - max_posts
            post_urls = post_urls[:max_posts]
        
        # Download the posts
        successful = 0
        failed = 0
        
        # Create tasks for downloading posts
        tasks = []
        
        for url in post_urls:
            # Check if the post already exists
            if not force_refresh:
                # Extract the slug
                slug_match = re.search(r"/p/([^/]+)", url)
                
                if slug_match:
                    slug = slug_match.group(1)
                    
                    # Check if the post file exists
                    markdown_file = os.path.join(self.output_dir, f"{slug}.md")
                    if os.path.exists(markdown_file):
                        skipped += 1
                        continue
            
            # Create a task for downloading the post
            tasks.append(self.download_post(
                url=url,
                force=force_refresh,
                download_images=download_images,
                use_direct=use_direct
            ))
        
        # Wait for all tasks to complete
        if tasks:
            results = await asyncio.gather(*tasks)
            
            # Count successful and failed downloads
            successful = sum(1 for result in results if result)
            failed = sum(1 for result in results if not result)
        
        return successful, failed, skipped


# Example usage
async def main():
    # Set up logging
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Create a downloader
    async with AsyncSubstackDownloader(
        author="example",
        output_dir="output",
        max_concurrency=5
    ) as downloader:
        # Set authentication token (optional)
        # downloader.set_auth_token("your-token-here")
        
        # Download all posts
        successful, failed, skipped = await downloader.download_all_posts(max_pages=1)
        
        print(f"Successfully downloaded {successful} posts")
        print(f"Failed to download {failed} posts")
        print(f"Skipped {skipped} posts")

if __name__ == "__main__":
    asyncio.run(main())
