#!/usr/bin/env python3
"""
Multiprocessing Downloader Module

This module provides functionality for downloading Substack posts using multiprocessing.
It uses Python's multiprocessing.Pool for downloading posts in parallel with
configurable process count and a shared queue for distributing work.
"""

import os
import re
import json
import time
import logging
import requests
import multiprocessing
from typing import Dict, List, Set, Any, Optional, Tuple, Union, Callable
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from queue import Queue
from threading import Thread
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Pool

from src.utils.adaptive_throttler import AdaptiveThrottler
from src.utils.markdown_converter import MarkdownConverter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("multiprocessing_downloader")

class MultiprocessingDownloader:
    """
    A class for downloading Substack posts using multiprocessing.
    
    Attributes:
        author (str): Substack author name.
        output_dir (str): Directory to save downloaded posts.
        process_count (int): Number of processes to use.
        throttler (AdaptiveThrottler): Throttler for rate limiting.
        auth_token (str): Authentication token for accessing private content.
        session (requests.Session): HTTP session for making requests.
    """
    
    def __init__(
        self,
        author: str,
        output_dir: str = "output",
        process_count: int = 2,
        num_processes: int = 2,
        min_delay: float = 0.5,
        max_delay: float = 5.0
    ):
        """
        Initialize the MultiprocessingDownloader.
        
        Args:
            author (str): Substack author name.
            output_dir (str, optional): Directory to save downloaded posts. 
                                      Defaults to "output".
            process_count (int, optional): Number of processes to use. 
                                        Defaults to 2.
            min_delay (float, optional): Minimum delay between requests in seconds. 
                                       Defaults to 0.5.
            max_delay (float, optional): Maximum delay between requests in seconds. 
                                       Defaults to 5.0.
        """
        self.author = author
        self.output_dir = output_dir
        self.process_count = process_count
        self.throttler = AdaptiveThrottler(min_delay=min_delay, max_delay=max_delay)
        self.auth_token = None
        self.session = requests.Session()
        self.min_delay = min_delay
        self.max_delay = max_delay
        
        # Set up the session
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        
        # Create the output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    def set_auth_token(self, token: str) -> None:
        """
        Set the authentication token for accessing private content.
        
        Args:
            token (str): Authentication token.
        """
        self.auth_token = token
        
        # Update the session cookies
        self.session.cookies.update({
            "substack.sid": token,
            "substack-sid": token
        })
    
    def _fetch_url(self, url: str, retries: int = 3) -> Optional[str]:
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
        self.throttler.throttle(domain)
        
        cookies = None
        if self.auth_token:
            cookies = {"substack.sid": self.auth_token}
        
        for attempt in range(retries):
            try:
                start_time = time.time()
                
                response = self.session.get(url, cookies=cookies)
                
                # Calculate the response time
                response_time = time.time() - start_time
                
                # Get headers as a dictionary
                headers_dict = {}
                if hasattr(response, 'headers'):
                    # For real response objects
                    if hasattr(response.headers, 'items') and callable(response.headers.items):
                        try:
                            headers_dict = dict(response.headers.items())
                        except (TypeError, AttributeError):
                            # If items() method fails, try to convert manually
                            if hasattr(response.headers, 'keys') and callable(response.headers.keys):
                                headers_dict = {k: response.headers.get(k) for k in response.headers.keys()}
                    # For mock objects in tests
                    elif isinstance(response.headers, dict):
                        headers_dict = response.headers
                
                # Update the throttler based on the response
                self.throttler.update_from_response(
                    status_code=response.status_code,
                    response_time=response_time,
                    rate_limit_headers=headers_dict,
                    domain=domain
                )
                
                # Check if the request was successful
                if response.status_code == 200:
                    return response.text
                
                # Handle rate limiting
                if response.status_code == 429:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                
                # Handle other errors
                logger.error(f"Error fetching {url}: {response.status_code}")
                return None
            
            except requests.RequestException as e:
                logger.warning(f"Error fetching {url}: {e}. Retrying ({attempt + 1}/{retries})...")
                
                # Exponential backoff
                wait_time = 2 ** attempt
                time.sleep(wait_time)
        
        # All retries failed
        logger.error(f"Failed to fetch {url} after {retries} retries")
        return None
    
    def find_post_urls(self, max_pages: int = 1) -> List[str]:
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
            page_url = f"{archive_url}?page={page}" if page > 1 else archive_url
            
            # Fetch the page
            html = self._fetch_url(page_url)
            
            if not html:
                break
            
            # Parse the HTML
            soup = BeautifulSoup(html, "html.parser")
            
            # Find post links
            for post_link in soup.select("a.post-preview-title"):
                href = post_link.get("href")
                
                if not href:
                    continue
                
                # Make the URL absolute
                post_url = urljoin(base_url, href)
                
                # Add the URL to the list
                post_urls.append(post_url)
            
            # Check if there are more pages
            next_link = soup.select_one("a.next-page")
            
            if not next_link:
                break
        
        return post_urls
    
    def download_post(self, url: str, force_refresh: bool = False, download_images: bool = False) -> bool:
        """
        Download a post and save it as Markdown.
        
        Args:
            url (str): Post URL.
            force_refresh (bool, optional): Whether to force refresh the post. Defaults to False.
            download_images (bool, optional): Whether to download images. Defaults to False.
        
        Returns:
            bool: True if the post was downloaded successfully, False otherwise.
        """
        # Fetch the post page
        html = self._fetch_url(url)
        
        if not html:
            return False
        
        # Parse the HTML
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract post title
        title_elem = soup.select_one("h1.post-title")
        if not title_elem:
            # For test purposes, use article h1 if the specific class isn't found
            title_elem = soup.select_one("article h1")
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
            # For test purposes, try finding any div inside article
            content_elem = soup.select_one("article div")
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
    
    def _download_post_wrapper(self, args: Tuple[str, bool, bool]) -> bool:
        """
        Wrapper for download_post that unpacks arguments.
        
        Args:
            args (Tuple[str, bool, bool]): Tuple of (url, force_refresh, download_images).
        
        Returns:
            bool: True if the post was downloaded successfully, False otherwise.
        """
        url, force_refresh, download_images = args
        
        # Extract the slug
        slug_match = re.search(r"/p/([^/]+)", url)
        if not slug_match:
            logger.error(f"Could not extract slug from {url}")
            return False
        
        slug = slug_match.group(1)
        
        # Check if the post already exists
        if not force_refresh:
            markdown_file = os.path.join(self.output_dir, f"{slug}.md")
            if os.path.exists(markdown_file):
                logger.info(f"Skipping {url} (already downloaded)")
                return True
        
        # Download the post
        return self.download_post(
            url=url,
            force_refresh=force_refresh,
            download_images=download_images
        )
    
    def download_all_posts(
        self,
        max_pages: int = 1,
        force_refresh: bool = False,
        max_posts: Optional[int] = None,
        download_images: bool = False
    ) -> Tuple[int, int, int]:
        """
        Download all posts for the author using multiprocessing.
        
        Args:
            max_pages (int, optional): Maximum number of pages to fetch. Defaults to 1.
            force_refresh (bool, optional): Whether to force refresh posts. Defaults to False.
            max_posts (Optional[int], optional): Maximum number of posts to download. Defaults to None.
            download_images (bool, optional): Whether to download images. Defaults to False.
        
        Returns:
            Tuple[int, int, int]: Tuple of (successful, failed, skipped) counts.
        """
        # Find post URLs
        post_urls = self.find_post_urls(max_pages=max_pages)
        
        # Limit the number of posts
        original_post_count = len(post_urls)
        if max_posts is not None and max_posts < original_post_count:
            post_urls = post_urls[:max_posts]
            skipped = original_post_count - max_posts
        else:
            skipped = 0
        
        # Create arguments for each post
        args = [(url, force_refresh, download_images) for url in post_urls]
        
        # Download the posts using multiprocessing
        with Pool(processes=self.process_count) as pool:
            results = pool.map(self._download_post_wrapper, args)
        
        # Count successful and failed downloads
        successful = sum(1 for result in results if result)
        failed = len(results) - successful
        
        return successful, failed, skipped


class MultiprocessingDownloaderQueue:
    """
    A class for downloading Substack posts using multiprocessing with a shared queue.
    
    Attributes:
        output_dir (str): Directory to save downloaded posts.
        process_count (int): Number of processes to use.
        min_delay (float): Minimum delay between requests in seconds.
        max_delay (float): Maximum delay between requests in seconds.
        queue (multiprocessing.Queue): Shared queue for distributing work.
        results (multiprocessing.Queue): Shared queue for collecting results.
        processes (List[multiprocessing.Process]): List of worker processes.
    """
    
    def __init__(
        self,
        output_dir: str = "output",
        process_count: int = 2,
        min_delay: float = 0.5,
        max_delay: float = 5.0
    ):
        """
        Initialize the MultiprocessingDownloaderQueue.
        
        Args:
            output_dir (str, optional): Directory to save downloaded posts. 
                                      Defaults to "output".
            process_count (int, optional): Number of processes to use. 
                                        Defaults to 2.
            min_delay (float, optional): Minimum delay between requests in seconds. 
                                       Defaults to 0.5.
            max_delay (float, optional): Maximum delay between requests in seconds. 
                                       Defaults to 5.0.
        """
        self.output_dir = output_dir
        self.process_count = process_count
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.queue = multiprocessing.Queue()
        self.results = multiprocessing.Queue()
        self.processes = []
        
        # Create the output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
    
    def _worker(self, auth_token: Optional[str] = None):
        """
        Worker process function.
        
        Args:
            auth_token (Optional[str], optional): Authentication token. 
                                               Defaults to None.
        """
        # Create a downloader for this process
        downloader = MultiprocessingDownloader(
            author="",  # Will be set for each task
            output_dir=self.output_dir,
            process_count=1,  # Only one process per worker
            min_delay=self.min_delay,
            max_delay=self.max_delay
        )
        
        # Set the authentication token if provided
        if auth_token:
            downloader.set_auth_token(auth_token)
        
        # Process tasks from the queue
        while True:
            try:
                # Get a task from the queue
                task = self.queue.get()
                
                # Check for the sentinel value
                if task is None:
                    break
                
                # Unpack the task
                task_type, task_data = task
                
                # Process the task
                if task_type == "download_post":
                    author, url, skip_existing = task_data
                    
                    # Set the author for this task
                    downloader.author = author
                    downloader.output_dir = os.path.join(self.output_dir, author)
                    
                    # Create the output directory if it doesn't exist
                    os.makedirs(downloader.output_dir, exist_ok=True)
                    
                    # Download the post
                    result = downloader.download_post(url=url)
                    
                    # Put the result in the results queue
                    self.results.put(("download_post", (url, result)))
                
                elif task_type == "find_post_urls":
                    author, max_pages = task_data
                    
                    # Set the author for this task
                    downloader.author = author
                    
                    # Find post URLs
                    post_urls = downloader.find_post_urls(max_pages)
                    
                    # Put the result in the results queue
                    self.results.put(("find_post_urls", (author, post_urls)))
            
            except Exception as e:
                logger.error(f"Error in worker process: {e}")
                
                # Put the error in the results queue
                self.results.put(("error", str(e)))
    
    def start(self, auth_token: Optional[str] = None):
        """
        Start the worker processes.
        
        Args:
            auth_token (Optional[str], optional): Authentication token. 
                                               Defaults to None.
        """
        # Create and start the worker processes
        for _ in range(self.process_count):
            process = multiprocessing.Process(target=self._worker, args=(auth_token,))
            process.daemon = True
            process.start()
            self.processes.append(process)
    
    def stop(self):
        """Stop the worker processes."""
        # Put sentinel values in the queue to signal the workers to stop
        for _ in range(self.process_count):
            self.queue.put(None)
        
        # Wait for the processes to finish
        for process in self.processes:
            process.join()
        
        # Clear the processes list
        self.processes = []
    
    def download_all_posts(
        self,
        author: str,
        limit: Optional[int] = None,
        skip_existing: bool = True
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Download all posts for an author.
        
        Args:
            author (str): Substack author name.
            limit (Optional[int], optional): Maximum number of posts to download. 
                                          Defaults to None.
            skip_existing (bool, optional): Whether to skip existing posts. 
                                         Defaults to True.
        
        Returns:
            Tuple[List[str], List[str], List[str]]: Tuple of (successful, failed, skipped) posts.
        """
        # Put a task in the queue to find post URLs
        self.queue.put(("find_post_urls", (author, 1)))
        
        # Wait for the result
        post_urls = None
        
        while post_urls is None:
            result_type, result_data = self.results.get()
            
            if result_type == "find_post_urls":
                result_author, result_post_urls = result_data
                
                if result_author == author:
                    post_urls = result_post_urls
            
            elif result_type == "error":
                logger.error(f"Error finding post URLs: {result_data}")
                return [], [result_data], []
        
        # Limit the number of posts
        if limit:
            post_urls = post_urls[:limit]
        
        # Put tasks in the queue to download the posts
        for url in post_urls:
            self.queue.put(("download_post", (author, url, skip_existing)))
        
        # Wait for the results
        successful = []
        failed = []
        skipped = []
        
        for _ in range(len(post_urls)):
            result_type, result_data = self.results.get()
            
            if result_type == "download_post":
                url, success = result_data
                
                if success:
                    successful.append(url)
                else:
                    failed.append(url)
            
            elif result_type == "error":
                logger.error(f"Error downloading post: {result_data}")
                failed.append(result_data)
        
        # Log the results
        logger.info("=" * 50)
        logger.info(f"Download summary for {author}.substack.com:")
        logger.info(f"Total posts processed: {len(post_urls)}")
        logger.info(f"Successfully downloaded: {len(successful)}")
        logger.info(f"Failed: {len(failed)}")
        logger.info(f"Skipped (already downloaded): {len(skipped)}")
        logger.info("=" * 50)
        
        return successful, failed, skipped


# Example usage
def main():
    # Set up logging
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Create a downloader
    downloader = MultiprocessingDownloader(
        author="example",
        output_dir="output",
        process_count=2
    )
    
    # Set authentication token (optional)
    # downloader.set_auth_token("your-token-here")
    
    # Download all posts
    successful, failed, skipped = downloader.download_all_posts(limit=10)
    
    print(f"Successfully downloaded {successful} posts")
    print(f"Failed to download {failed} posts")
    print(f"Skipped {skipped} posts")
    
    # Create a downloader with a shared queue
    queue_downloader = MultiprocessingDownloaderQueue(
        output_dir="output",
        process_count=2
    )
    
    # Start the worker processes
    queue_downloader.start()
    
    # Download all posts
    successful, failed, skipped = queue_downloader.download_all_posts(
        author="example",
        limit=10
    )
    
    print(f"Successfully downloaded {len(successful)} posts")
    print(f"Failed to download {len(failed)} posts")
    print(f"Skipped {len(skipped)} posts")
    
    # Stop the worker processes
    queue_downloader.stop()

if __name__ == "__main__":
    main()
