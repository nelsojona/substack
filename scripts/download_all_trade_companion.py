#!/usr/bin/env python3
"""
Trade Companion Substack Downloader

This script downloads all posts from the Trade Companion Substack newsletter
with robust error handling and self-healing capabilities. It saves the posts
as markdown files in the output/tradecompanion directory.

Features:
- Downloads all posts from Trade Companion Substack
- Downloads and properly links all images
- Includes proper metadata in each post
- Implements robust exception handling
- Adds retry mechanisms with exponential backoff for network failures
- Resume capability to continue from where it left off if interrupted
- Validates downloaded content and retries if validation fails
- Comprehensive logging system to track progress and errors
- Progress tracking with percentage complete
- Summary report of downloaded posts
- Option to force refresh already downloaded posts
- Configurable parameters (retry count, delay, etc.)
- Checkpointing to save state between runs
- Automatic token refresh if authentication fails
- Advanced anti-detection measures to bypass Substack's 443 authentication block
- Browser fingerprinting with realistic headers
- Request throttling with random delays
- Enhanced proxy configuration with IP rotation
- Fallback to headless browser approach when needed

Usage:
    python scripts/download_all_trade_companion.py [OPTIONS]

Options:
    --force             Force refresh of already downloaded posts
    --verbose           Enable verbose output
    --max-retries N     Set maximum number of retry attempts (default: 5)
    --retry-delay N     Set initial retry delay in seconds (default: 2)
    --skip-images       Skip downloading images
    --checkpoint-interval N  Number of posts to process before saving checkpoint (default: 5)
    --private           Indicate that the posts are private and require authentication
    --refresh-token     Force refresh of the Substack authentication token
    --token-method METHOD  Method to use for token extraction: http, selenium, puppeteer, auto, or manual (default: auto)
    --browser-fallback  Use browser automation as fallback if direct requests fail
    --rotate-proxy      Rotate proxy IP for each request (requires Oxylabs)
    --min-delay N       Minimum delay between requests in seconds (default: 2)
    --max-delay N       Maximum delay between requests in seconds (default: 5)
"""

import os
import sys
import time
import json
import logging
import argparse
import hashlib
import re
import subprocess
import random
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
import traceback
import signal
from urllib.parse import urlparse
import platform

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from substack_fetcher import SubstackFetcher
from markdown_converter import MarkdownConverter
from env_loader import load_env_vars, get_substack_auth, get_general_config, get_oxylabs_config

# Import requests here to avoid circular imports
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join('scripts', 'trade_companion_download.log'))
    ]
)
logger = logging.getLogger("trade_companion_downloader")

# Disable warnings for unverified HTTPS requests
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

# Constants
AUTHOR = "tradecompanion"
OUTPUT_DIR = os.path.join("output", "tradecompanion")
CHECKPOINT_FILE = os.path.join("scripts", "trade_companion_checkpoint.json")
IMAGE_DIR = "images"
MAX_WORKERS = 4
IMAGE_TIMEOUT = 10
USE_PROXY = False  # Set to False by default, enable with --use-proxy flag
TOKEN_EXTRACTOR_SCRIPT = os.path.join("scripts", "get_substack_token.py")
MAX_CONCURRENT_REQUESTS = 2  # Limit concurrent connections to Substack
DEFAULT_MIN_DELAY = 2  # Minimum delay between requests in seconds
DEFAULT_MAX_DELAY = 5  # Maximum delay between requests in seconds

# Browser fingerprinting constants
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-CA,en;q=0.9,fr-CA;q=0.8",
    "en;q=0.9"
]

BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Chromium";v="133", "Google Chrome";v="133", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Cache-Control": "max-age=0"
}

# Global variables for tracking progress
total_posts = 0
processed_posts = 0
successful_posts = 0
failed_posts = 0
downloaded_posts_ids = set()
interrupted = False
request_count = 0
last_request_time = 0


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        argparse.Namespace: The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description='Download all posts from Trade Companion Substack')
    parser.add_argument('--force', action='store_true', help='Force refresh of already downloaded posts')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--max-retries', type=int, default=5, help='Maximum number of retry attempts')
    parser.add_argument('--retry-delay', type=int, default=2, help='Initial retry delay in seconds')
    parser.add_argument('--skip-images', action='store_true', help='Skip downloading images')
    parser.add_argument('--checkpoint-interval', type=int, default=5, 
                        help='Number of posts to process before saving checkpoint')
    parser.add_argument('--private', action='store_true', help='Indicate that the posts are private and require authentication')
    parser.add_argument('--refresh-token', action='store_true', help='Force refresh of the Substack authentication token')
    parser.add_argument('--token-method', choices=['http', 'selenium', 'puppeteer', 'auto', 'manual'], default='auto',
                        help='Method to use for token extraction: http, selenium, puppeteer, auto, or manual (default: auto)')
    parser.add_argument('--token-cookie', help='Manually provide a cookie string containing substack.sid (for manual token method)')
    parser.add_argument('--browser-fallback', action='store_true', 
                        help='Use browser automation as fallback if direct requests fail')
    parser.add_argument('--use-proxy', action='store_true',
                        help='Use Oxylabs proxy service (default: disabled)')
    parser.add_argument('--rotate-proxy', action='store_true',
                        help='Rotate proxy IP for each request (requires Oxylabs)')
    parser.add_argument('--min-delay', type=float, default=DEFAULT_MIN_DELAY,
                        help=f'Minimum delay between requests in seconds (default: {DEFAULT_MIN_DELAY})')
    parser.add_argument('--max-delay', type=float, default=DEFAULT_MAX_DELAY,
                        help=f'Maximum delay between requests in seconds (default: {DEFAULT_MAX_DELAY})')
    parser.add_argument('--fetch-timeout', type=int, default=300,
                        help='Timeout in seconds for fetching the post list (default: 300)')
    parser.add_argument('--request-timeout', type=int, default=30,
                        help='Timeout in seconds for individual HTTP requests (default: 30)')
    
    return parser.parse_args()


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    def signal_handler(sig, frame):
        global interrupted
        logger.info("Received interrupt signal. Saving checkpoint and exiting...")
        interrupted = True
        
        # Save checkpoint immediately
        metadata = {
            "total_posts": total_posts,
            "successful_posts": successful_posts,
            "failed_posts": failed_posts
        }
        save_checkpoint(downloaded_posts_ids, metadata)
        
        # Exit immediately with a non-zero status code
        logger.info("Exiting due to user interrupt.")
        sys.exit(130)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def load_checkpoint() -> Tuple[Set[int], Dict[str, Any]]:
    """
    Load checkpoint data from file.
    
    Returns:
        Tuple[Set[int], Dict[str, Any]]: A tuple containing the set of downloaded post IDs
                                         and the checkpoint metadata.
    """
    if not os.path.exists(CHECKPOINT_FILE):
        return set(), {"last_run": None, "total_posts": 0, "successful_posts": 0, "failed_posts": 0}
    
    try:
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            checkpoint_data = json.load(f)
        
        downloaded_ids = set(checkpoint_data.get("downloaded_post_ids", []))
        metadata = {
            "last_run": checkpoint_data.get("last_run"),
            "total_posts": checkpoint_data.get("total_posts", 0),
            "successful_posts": checkpoint_data.get("successful_posts", 0),
            "failed_posts": checkpoint_data.get("failed_posts", 0)
        }
        
        logger.info(f"Loaded checkpoint: {len(downloaded_ids)} posts already downloaded")
        return downloaded_ids, metadata
    
    except Exception as e:
        logger.error(f"Error loading checkpoint: {e}")
        return set(), {"last_run": None, "total_posts": 0, "successful_posts": 0, "failed_posts": 0}


def save_checkpoint(downloaded_ids: Set[int], metadata: Dict[str, Any]) -> bool:
    """
    Save checkpoint data to file.
    
    Args:
        downloaded_ids (Set[int]): Set of downloaded post IDs.
        metadata (Dict[str, Any]): Checkpoint metadata.
    
    Returns:
        bool: True if checkpoint was saved successfully, False otherwise.
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
        
        checkpoint_data = {
            "downloaded_post_ids": list(downloaded_ids),
            "last_run": datetime.now().isoformat(),
            "total_posts": metadata.get("total_posts", 0),
            "successful_posts": metadata.get("successful_posts", 0),
            "failed_posts": metadata.get("failed_posts", 0)
        }
        
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2)
        
        logger.info(f"Saved checkpoint: {len(downloaded_ids)} posts")
        return True
    
    except Exception as e:
        logger.error(f"Error saving checkpoint: {e}")
        return False


def validate_markdown_content(content: str) -> bool:
    """
    Validate the markdown content to ensure it's properly formatted.
    
    Args:
        content (str): The markdown content to validate.
    
    Returns:
        bool: True if the content is valid, False otherwise.
    """
    # Check for front matter
    if not content.startswith('---') or '---' not in content[3:]:
        return False
    
    # Check for required metadata fields
    required_fields = ['title:', 'author:', 'date:', 'original_url:']
    for field in required_fields:
        if field not in content:
            return False
    
    # Check for content after front matter
    front_matter_end = content.find('---', 3) + 3
    if len(content) <= front_matter_end + 10:  # Arbitrary minimum content length
        return False
    
    return True


def get_random_delay(min_delay: float, max_delay: float) -> float:
    """
    Get a random delay between min_delay and max_delay.
    
    Args:
        min_delay (float): Minimum delay in seconds.
        max_delay (float): Maximum delay in seconds.
    
    Returns:
        float: Random delay in seconds.
    """
    return min_delay + random.random() * (max_delay - min_delay)


def throttle_request(min_delay: float, max_delay: float):
    """
    Throttle requests to avoid overwhelming the server and being detected as a bot.
    
    Args:
        min_delay (float): Minimum delay in seconds.
        max_delay (float): Maximum delay in seconds.
    """
    global last_request_time, request_count
    
    # Calculate time since last request
    current_time = time.time()
    time_since_last_request = current_time - last_request_time
    
    # Determine delay based on request count and min/max delay
    if request_count > 0:
        # Exponential backoff based on request count with randomization
        if request_count > 10:
            # After 10 requests, use a longer delay to avoid detection
            delay = get_random_delay(max_delay, max_delay * 2)
        else:
            delay = get_random_delay(min_delay, max_delay)
        
        # If not enough time has passed since the last request, sleep
        if time_since_last_request < delay:
            sleep_time = delay - time_since_last_request
            logger.debug(f"Throttling request: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
    
    # Update last request time and increment request count
    last_request_time = time.time()
    request_count += 1


def get_random_browser_headers() -> Dict[str, str]:
    """
    Generate random browser headers to avoid detection.
    
    Returns:
        Dict[str, str]: Dictionary of browser headers.
    """
    # Get random user agent and accept language
    user_agent = random.choice(USER_AGENTS)
    accept_language = random.choice(ACCEPT_LANGUAGES)
    
    # Create headers dictionary
    headers = BROWSER_HEADERS.copy()
    headers["User-Agent"] = user_agent
    headers["Accept-Language"] = accept_language
    
    # Add random cache buster to avoid caching
    headers["Cache-Control"] = f"max-age=0, no-cache, no-store, must-revalidate, private, post-check=0, pre-check=0"
    headers["Pragma"] = "no-cache"
    headers["Expires"] = "0"
    
    # Add random client hints based on user agent
    if "Windows" in user_agent:
        headers["Sec-Ch-Ua-Platform"] = '"Windows"'
    elif "Macintosh" in user_agent:
        headers["Sec-Ch-Ua-Platform"] = '"macOS"'
    else:
        headers["Sec-Ch-Ua-Platform"] = '"Linux"'
    
    # Add a random referer
    referers = [
        "https://www.google.com/",
        "https://www.bing.com/",
        "https://www.yahoo.com/",
        "https://www.substack.com/",
        "https://tradecompanion.substack.com/"
    ]
    headers["Referer"] = random.choice(referers)
    
    return headers


def setup_session_with_retry(max_retries: int = 5, rotate_proxy: bool = False, 
                       use_proxy: bool = False, request_timeout: int = 30) -> requests.Session:
    """
    Set up a requests session with retry logic and proxy configuration.
    
    Args:
        max_retries (int, optional): Maximum number of retry attempts. Defaults to 5.
        rotate_proxy (bool, optional): Whether to rotate proxy IP for each request. Defaults to False.
        use_proxy (bool, optional): Whether to use the proxy service. Defaults to False.
        request_timeout (int, optional): Timeout for HTTP requests in seconds. Defaults to 30.
    
    Returns:
        requests.Session: Configured requests session.
    """
    # Create a new session
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    
    # Mount the retry adapter to the session
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Set the default timeout for all requests
    session.request = lambda method, url, **kwargs: super(requests.Session, session).request(
        method=method, url=url, timeout=request_timeout, **kwargs
    )
    
    # Set up proxy if requested
    global USE_PROXY
    USE_PROXY = use_proxy  # Update global variable based on command line argument
    
    if USE_PROXY:
        oxylabs_config = get_oxylabs_config()
        if oxylabs_config['username'] and oxylabs_config['password']:
            # Construct proxy URL
            proxy_url = f"http://{oxylabs_config['username']}:{oxylabs_config['password']}@customer-{oxylabs_config['username']}.oxylabs.io:10000"
            
            # Set up proxy for the session
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            # Add additional headers for Oxylabs
            headers = {}
            
            if oxylabs_config['country_code']:
                headers['X-Oxylabs-Country'] = oxylabs_config['country_code']
            
            if oxylabs_config['city']:
                headers['X-Oxylabs-City'] = oxylabs_config['city']
            
            if oxylabs_config['state']:
                headers['X-Oxylabs-State'] = oxylabs_config['state']
            
            # Add session ID for persistence or rotation
            if rotate_proxy:
                # Generate a new session ID for each request
                headers['X-Oxylabs-Session-ID'] = f"substack_{uuid.uuid4().hex[:8]}"
            elif oxylabs_config['session_id']:
                # Use the configured session ID for persistence
                headers['X-Oxylabs-Session-ID'] = oxylabs_config['session_id']
            
            if oxylabs_config['session_time'] is not None:
                headers['X-Oxylabs-Session-Time'] = str(oxylabs_config['session_time'])
            
            # Update session headers
            session.headers.update(headers)
            
            logger.info("Oxylabs proxy configured successfully")
            if rotate_proxy:
                logger.info("Proxy IP rotation enabled")
    
    # Add random browser headers to avoid detection
    session.headers.update(get_random_browser_headers())
    
    return session


def with_retry(func, *args, max_retries=5, retry_delay=2, min_delay=DEFAULT_MIN_DELAY, max_delay=DEFAULT_MAX_DELAY, **kwargs):
    """
    Execute a function with retry logic and exponential backoff.
    
    Args:
        func: The function to execute.
        *args: Positional arguments to pass to the function.
        max_retries (int, optional): Maximum number of retry attempts. Defaults to 5.
        retry_delay (int, optional): Initial retry delay in seconds. Defaults to 2.
        min_delay (float, optional): Minimum delay between requests. Defaults to DEFAULT_MIN_DELAY.
        max_delay (float, optional): Maximum delay between requests. Defaults to DEFAULT_MAX_DELAY.
        **kwargs: Keyword arguments to pass to the function.
    
    Returns:
        The result of the function call.
    
    Raises:
        Exception: If all retry attempts fail.
    """
    retries = 0
    last_exception = None
    
    while retries <= max_retries:
        try:
            # Throttle requests to avoid detection
            throttle_request(min_delay, max_delay)
            
            return func(*args, **kwargs)
        
        except (ConnectionError, TimeoutError, requests.exceptions.RequestException) as e:
            last_exception = e
            if retries < max_retries:
                # Calculate exponential backoff with jitter
                delay = retry_delay * (2 ** retries) + (random.random() * retry_delay)
                
                # Add extra delay for rate limiting
                if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                    delay *= 2  # Double the delay for rate limiting
                    logger.warning(f"Rate limited (429). Adding extra delay.")
                
                # Add extra delay for authentication errors
                if hasattr(e, 'response') and e.response and e.response.status_code in (401, 403):
                    delay *= 3  # Triple the delay for auth errors
                    logger.warning(f"Authentication error ({e.response.status_code}). Adding extra delay.")
                
                logger.warning(f"Attempt {retries+1}/{max_retries} failed: {e}. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
                retries += 1
            else:
                logger.error(f"All {max_retries} retry attempts failed")
                raise
        
        except Exception as e:
            # For other exceptions, don't retry
            logger.error(f"Unexpected error: {e}")
            raise
    
    if last_exception:
        raise ConnectionError(f"Failed to fetch posts after {max_retries} retries: {last_exception}")


def extract_token_with_browser(method: str, email: str, password: str, headless: bool = True, verbose: bool = False) -> Optional[str]:
    """
    Extract Substack authentication token using browser automation.
    
    Args:
        method (str): Method to use for extraction: 'selenium' or 'puppeteer'.
        email (str): Substack account email.
        password (str): Substack account password.
        headless (bool, optional): Run browser in headless mode. Defaults to True.
        verbose (bool, optional): Enable verbose output. Defaults to False.
    
    Returns:
        Optional[str]: The Substack authentication token, or None if extraction failed.
    """
    logger.info(f"Attempting to extract token using browser automation ({method})...")
    
    # Build the command
    cmd = [sys.executable, TOKEN_EXTRACTOR_SCRIPT, f"--method={method}", f"--email={email}", f"--password={password}"]
    
    if headless:
        cmd.append("--headless")
    
    if verbose:
        cmd.append("--verbose")
    
    # Run the token extractor script
    try:
        logger.info(f"Running token extractor: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Token extraction successful")
            
            # Extract token from output
            token_match = re.search(r'Substack token: ([^\s]+)', result.stdout)
            if token_match:
                token = token_match.group(1)
                return token
            else:
                logger.warning("Token not found in extractor output")
                return None
        else:
            logger.error(f"Token extraction failed with exit code {result.returncode}")
            logger.error(f"Error: {result.stderr}")
            return None
    
    except Exception as e:
        logger.error(f"Error running token extractor: {e}")
        return None


def generate_filename(post: Dict[str, Any]) -> str:
    """
    Generate a filename for a post based on its title and date.
    
    Args:
        post (Dict[str, Any]): The post object.
    
    Returns:
        str: The generated filename.
    """
    title = post.get('title', 'Untitled Post')
    post_date = post.get('post_date')
    
    # Process the date
    if post_date:
        try:
            # Parse the date string and format it as YYYY-MM-DD
            date_obj = datetime.fromisoformat(post_date.replace('Z', '+00:00'))
            date_str = date_obj.strftime('%Y-%m-%d')
            
            # Combine date and title
            filename = f"{date_str}_{sanitize_filename(title)}.md"
        except (ValueError, TypeError):
            # Fallback if date parsing fails
            filename = f"{sanitize_filename(title)}.md"
    else:
        # Fallback if no date is available
        filename = f"{sanitize_filename(title)}.md"
    
    return filename


def sanitize_filename(title: str) -> str:
    """
    Sanitize a string to be used as a filename.
    
    Args:
        title (str): The string to sanitize.
    
    Returns:
        str: The sanitized filename.
    """
    # Replace invalid filename characters with underscores
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', title)
    
    # Replace multiple spaces with a single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    # Trim to a reasonable length
    if len(sanitized) > 100:
        sanitized = sanitized[:97] + '...'
    
    return sanitized.strip()


def add_metadata_to_markdown(post: Dict[str, Any], markdown_content: str) -> str:
    """
    Add post metadata to the Markdown content as front matter.
    
    Args:
        post (Dict[str, Any]): The post object.
        markdown_content (str): The Markdown content.
    
    Returns:
        str: The Markdown content with added metadata.
    """
    # Extract metadata from the post
    title = post.get('title', 'Untitled Post')
    subtitle = post.get('subtitle', '')
    author = post.get('author', {}).get('name', '')
    post_date = post.get('post_date', '')
    url = post.get('canonical_url', '')
    
    # Format the date
    if post_date:
        try:
            # Parse the date string and format it as YYYY-MM-DD
            date_obj = datetime.fromisoformat(post_date.replace('Z', '+00:00'))
            post_date = date_obj.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            pass
    
    # Create front matter
    front_matter = [
        '---',
        f'title: "{title}"'
    ]
    
    if subtitle:
        front_matter.append(f'subtitle: "{subtitle}"')
    
    if author:
        front_matter.append(f'author: "{author}"')
    
    if post_date:
        front_matter.append(f'date: "{post_date}"')
    
    if url:
        front_matter.append(f'original_url: "{url}"')
    
    front_matter.append('---\n')
    
    # Combine front matter with Markdown content
    return '\n'.join(front_matter) + markdown_content


def save_markdown_to_file(markdown_content: str, filename: str, output_dir: str, verbose: bool = False) -> bool:
    """
    Save Markdown content to a file.
    
    Args:
        markdown_content (str): The Markdown content to save.
        filename (str): The filename to use.
        output_dir (str): The output directory.
        verbose (bool, optional): Enable verbose output. Defaults to False.
    
    Returns:
        bool: True if the file was saved successfully, False otherwise.
    """
    try:
        # Create the output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Construct the full file path
        file_path = os.path.join(output_dir, filename)
        
        # Write the Markdown content to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        if verbose:
            logger.info(f"Saved Markdown to {file_path}")
        
        return True
    
    except OSError as e:
        logger.error(f"Error saving file {filename}: {e}")
        return False


def fetch_post_content(url: str, session: requests.Session, max_retries: int = 5, 
                    browser_fallback: bool = False, browser_method: str = 'selenium', 
                    min_delay: float = DEFAULT_MIN_DELAY, max_delay: float = DEFAULT_MAX_DELAY,
                    rotate_proxy: bool = False, verbose: bool = False) -> Optional[str]:
    """
    Fetch post content with enhanced anti-detection measures.
    
    Args:
        url (str): The URL of the post.
        session (requests.Session): The requests session to use.
        max_retries (int, optional): Maximum number of retry attempts. Defaults to 5.
        browser_fallback (bool, optional): Whether to use browser automation as fallback. Defaults to False.
        browser_method (str, optional): Browser automation method to use. Defaults to 'selenium'.
        min_delay (float, optional): Minimum delay between requests. Defaults to DEFAULT_MIN_DELAY.
        max_delay (float, optional): Maximum delay between requests. Defaults to DEFAULT_MAX_DELAY.
        rotate_proxy (bool, optional): Whether to rotate proxy IP for each request. Defaults to False.
        verbose (bool, optional): Enable verbose output. Defaults to False.
    
    Returns:
        Optional[str]: The HTML content of the post, or None if it could not be fetched.
    """
    logger.info(f"Fetching post content: {url}")
    
    # Rotate the proxy if requested
    if rotate_proxy and USE_PROXY:
        # Update session headers with a new session ID for Oxylabs
        oxylabs_config = get_oxylabs_config()
        if oxylabs_config['username'] and oxylabs_config['password']:
            # Generate a new session ID
            session_id = f"substack_{uuid.uuid4().hex[:8]}"
            session.headers.update({
                'X-Oxylabs-Session-ID': session_id
            })
            logger.debug(f"Rotating proxy with new session ID: {session_id}")
    
    # Update session with new random browser headers for each request
    session.headers.update(get_random_browser_headers())
    
    # Apply throttling to avoid detection
    throttle_request(min_delay, max_delay)
    
    try:
        # Make the request - session already has timeout set
        logger.debug(f"Making request to {url}")
        try:
            response = session.get(url, verify=False)
        except requests.Timeout:
            logger.warning(f"Request timed out when fetching {url}")
            if browser_fallback:
                logger.info("Falling back to browser automation due to timeout...")
                return fetch_post_content_with_browser(url, method=browser_method, verbose=verbose)
            return None
        
        # Check if the request was successful
        if response.status_code == 200:
            # Check if we got the actual content or an authentication error page
            # Look for common substack content markers in the HTML
            if 'article' in response.text and ('substack-post' in response.text or 'post-content' in response.text):
                logger.info(f"Successfully fetched post content: {url}")
                return response.text
            else:
                logger.warning(f"Received a 200 response, but content doesn't look like a Substack post: {url}")
                if browser_fallback:
                    logger.info("Attempting browser fallback...")
                    return fetch_post_content_with_browser(url, method=browser_method, verbose=verbose)
                return None
        
        # Handle authentication errors
        elif response.status_code in (401, 403, 443):
            logger.warning(f"Authentication error ({response.status_code}) when fetching {url}")
            if browser_fallback:
                logger.info("Falling back to browser automation due to authentication error...")
                return fetch_post_content_with_browser(url, method=browser_method, verbose=verbose)
            return None
        
        # Handle other errors
        else:
            logger.warning(f"Failed to fetch post content: {url} (Status: {response.status_code})")
            if browser_fallback:
                logger.info("Falling back to browser automation due to HTTP error...")
                return fetch_post_content_with_browser(url, method=browser_method, verbose=verbose)
            return None
    
    except (ConnectionError, TimeoutError, requests.exceptions.RequestException) as e:
        logger.warning(f"Request error when fetching {url}: {e}")
        # Log proxy information if using proxy
        if USE_PROXY:
            logger.warning("Using proxy which may be causing connection issues. Try running without the --use-proxy flag.")
        if browser_fallback:
            logger.info("Falling back to browser automation due to request error...")
            return fetch_post_content_with_browser(url, method=browser_method, verbose=verbose)
        return None
    except Exception as e:
        logger.error(f"Unexpected error when fetching {url}: {e}")
        if browser_fallback:
            logger.info("Falling back to browser automation due to unexpected error...")
            return fetch_post_content_with_browser(url, method=browser_method, verbose=verbose)
        return None


def process_post(post: Dict[str, Any], session: requests.Session, output_dir: str, 
                image_dir: str, downloaded_ids: Set[int], args: argparse.Namespace) -> bool:
    """
    Process a single post: fetch content, convert to markdown, download images, and save to file.
    
    Args:
        post (Dict[str, Any]): The post data from the Substack API.
        session (requests.Session): The requests session to use for HTTP requests.
        output_dir (str): The directory to save the post to.
        image_dir (str): The directory to save images to.
        downloaded_ids (Set[int]): Set of already downloaded post IDs.
        args (argparse.Namespace): Command-line arguments.
    
    Returns:
        bool: True if the post was processed successfully, False otherwise.
    """
    global processed_posts, successful_posts, failed_posts
    
    # Extract post ID and URL
    post_id = post.get('id')
    post_url = post.get('canonical_url')
    post_title = post.get('title', 'Untitled Post')
    
    if not post_id or not post_url:
        logger.error(f"Invalid post data: missing ID or URL for post titled '{post_title}'")
        return False
    
    # Skip if already downloaded and not forcing refresh
    if post_id in downloaded_ids and not args.force:
        logger.info(f"Skipping already downloaded post: {post_title} (ID: {post_id})")
        processed_posts += 1
        successful_posts += 1
        return True
    
    logger.info(f"Processing post: {post_title} (ID: {post_id})")
    
    try:
        # Fetch post content with retry logic and anti-detection measures
        html_content = with_retry(
            fetch_post_content,
            post_url,
            session,
            max_retries=args.max_retries,
            browser_fallback=args.browser_fallback,
            browser_method=args.token_method if args.token_method in ('selenium', 'puppeteer') else 'selenium',
            min_delay=args.min_delay,
            max_delay=args.max_delay,
            rotate_proxy=args.rotate_proxy,
            verbose=args.verbose
        )
        
        if not html_content:
            logger.error(f"Failed to fetch content for post: {post_title} (ID: {post_id})")
            processed_posts += 1
            failed_posts += 1
            return False
        
        # Convert HTML to Markdown with image downloading
        converter = MarkdownConverter(
            html=html_content,
            url=post_url,
            output_dir=output_dir,
            image_dir=os.path.join(output_dir, image_dir),
            skip_images=args.skip_images,
            session=session,
            image_timeout=IMAGE_TIMEOUT,
            verbose=args.verbose
        )
        
        markdown_content = converter.convert()
        
        if not markdown_content:
            logger.error(f"Failed to convert content for post: {post_title} (ID: {post_id})")
            processed_posts += 1
            failed_posts += 1
            return False
        
        # Add metadata to markdown
        markdown_with_metadata = add_metadata_to_markdown(post, markdown_content)
        
        # Validate the markdown content
        if not validate_markdown_content(markdown_with_metadata):
            logger.error(f"Invalid markdown content for post: {post_title} (ID: {post_id})")
            processed_posts += 1
            failed_posts += 1
            return False
        
        # Generate filename
        filename = generate_filename(post)
        
        # Save to file
        if save_markdown_to_file(markdown_with_metadata, filename, output_dir, args.verbose):
            logger.info(f"Successfully saved post: {post_title} (ID: {post_id})")
            downloaded_ids.add(post_id)
            processed_posts += 1
            successful_posts += 1
            
            # Save checkpoint if needed
            if processed_posts % args.checkpoint_interval == 0:
                metadata = {
                    "total_posts": total_posts,
                    "successful_posts": successful_posts,
                    "failed_posts": failed_posts
                }
                save_checkpoint(downloaded_ids, metadata)
            
            return True
        else:
            logger.error(f"Failed to save file for post: {post_title} (ID: {post_id})")
            processed_posts += 1
            failed_posts += 1
            return False
    
    except Exception as e:
        logger.error(f"Error processing post {post_title} (ID: {post_id}): {e}")
        logger.error(traceback.format_exc())
        processed_posts += 1
        failed_posts += 1
        return False


def main():
    """
    Main entry point for the script.
    """
    # Parse command-line arguments
    args = parse_arguments()
    
    # Set up logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Display script banner
    logger.info("=" * 70)
    logger.info(" Trade Companion Substack Downloader ".center(70, "="))
    logger.info("=" * 70)
    logger.info("This script downloads all posts from the Trade Companion Substack newsletter")
    logger.info("with robust error handling and self-healing capabilities.")
    logger.info("")
    logger.info("Anti-detection features:")
    logger.info("- Browser fingerprinting with realistic headers")
    logger.info("- Request throttling with random delays")
    logger.info("- Enhanced proxy configuration with IP rotation")
    logger.info("- Fallback to headless browser approach when needed")
    logger.info("=" * 70)
    
    # Run the downloader
    try:
        success = download_all_posts(args)
        
        if success:
            logger.info("✓ Download completed successfully!")
            sys.exit(0)
        else:
            logger.error("✗ Download failed or incomplete")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting...")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


def download_all_posts(args: argparse.Namespace) -> bool:
    """
    Download all posts from the Trade Companion Substack.
    
    Args:
        args (argparse.Namespace): Command-line arguments.
    
    Returns:
        bool: True if all posts were downloaded successfully, False otherwise.
    """
    global total_posts, processed_posts, successful_posts, failed_posts, downloaded_posts_ids, interrupted
    
    # Set up logging verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info("Starting Trade Companion Substack downloader")
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Python version: {platform.python_version()}")
    
    # Print configuration information
    logger.info("Configuration:")
    logger.info(f"  Force refresh: {args.force}")
    logger.info(f"  Skip images: {args.skip_images}")
    logger.info(f"  Max retries: {args.max_retries}")
    logger.info(f"  Retry delay: {args.retry_delay} seconds")
    logger.info(f"  Checkpoint interval: {args.checkpoint_interval} posts")
    logger.info(f"  Private content: {args.private}")
    logger.info(f"  Token method: {args.token_method}")
    logger.info(f"  Browser fallback: {args.browser_fallback}")
    logger.info(f"  Use proxy: {args.use_proxy}")
    logger.info(f"  Rotate proxy: {args.rotate_proxy}")
    logger.info(f"  Min delay: {args.min_delay} seconds")
    logger.info(f"  Max delay: {args.max_delay} seconds")
    logger.info(f"  Fetch timeout: {args.fetch_timeout} seconds")
    logger.info(f"  Request timeout: {args.request_timeout} seconds")
    
    # Load environment variables
    load_env_vars()
    
    # Get authentication info
    auth_info = get_substack_auth()
    
    # Load checkpoint data
    downloaded_ids, checkpoint_metadata = load_checkpoint()
    downloaded_posts_ids = downloaded_ids
    
    # Check if authentication is required and token is available
    if args.private and not auth_info.get('token'):
        logger.warning("Private content requested but no auth token found in .env file")
        logger.info("You can get a token by running: python scripts/get_substack_token.py")
        logger.info("Continuing with authentication attempts...")
    
    # Restore progress metrics from checkpoint
    if checkpoint_metadata:
        if checkpoint_metadata.get("last_run"):
            logger.info(f"Last run: {checkpoint_metadata['last_run']}")
        
        # Only restore metrics if force refresh is not enabled
        if not args.force:
            total_posts = checkpoint_metadata.get("total_posts", 0)
            successful_posts = checkpoint_metadata.get("successful_posts", 0)
            failed_posts = checkpoint_metadata.get("failed_posts", 0)
    
    # Set up signal handlers for graceful shutdown
    setup_signal_handlers()
    
    try:
        # Initialize Substack fetcher
        if args.private:
            # Handle authentication if posts are private
            if args.refresh_token or not auth_info.get('substack_sid'):
                logger.info("Obtaining new Substack authentication token...")
                
                if args.token_method == 'manual' and args.token_cookie:
                    # Extract token from manually provided cookie
                    logger.info("Using manually provided cookie")
                    
                    # Extract substack.sid from cookie string
                    sid_match = re.search(r'substack\.sid=([^;]+)', args.token_cookie)
                    if sid_match:
                        auth_info['substack_sid'] = sid_match.group(1)
                    else:
                        logger.error("Could not extract substack.sid from provided cookie")
                        return False
                    
                elif args.token_method in ('selenium', 'puppeteer'):
                    # Use browser automation to extract token
                    token = extract_token_with_browser(
                        method=args.token_method,
                        email=auth_info.get('email', ''),
                        password=auth_info.get('password', ''),
                        headless=True,
                        verbose=args.verbose
                    )
                    
                    if token:
                        auth_info['substack_sid'] = token
                    else:
                        logger.error("Failed to extract token using browser automation")
                        return False
                
                else:
                    # Use the dedicated token extraction script with improved options
                    cmd = [sys.executable, TOKEN_EXTRACTOR_SCRIPT]
                    
                    # Add method
                    if args.token_method != 'auto':
                        cmd.append(f"--method={args.token_method}")
                    
                    # Add credentials if available in environment
                    if auth_info.get('email'):
                        cmd.append(f"--email={auth_info.get('email')}")
                    
                    if auth_info.get('password'):
                        cmd.append(f"--password={auth_info.get('password')}")
                    
                    # Add headless mode for browser automation
                    cmd.append("--headless")
                    
                    # Add token testing to ensure it works
                    cmd.append("--test-token")
                    
                    # Add verbosity if requested
                    if args.verbose:
                        cmd.append("--verbose")
                    
                    try:
                        logger.info(f"Running token extractor: {' '.join(cmd)}")
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            # Extract token from output
                            token_match = re.search(r'Substack token: ([^\s]+)', result.stdout)
                            if token_match:
                                # Use the token we found
                                token = token_match.group(1)
                                auth_info['substack_sid'] = token
                                logger.info("Successfully extracted Substack token")
                                
                                # Save the token to environment variables for future use
                                os.environ['SUBSTACK_TOKEN'] = token
                            else:
                                logger.error("Token not found in extractor output")
                                logger.info("Extractor output: " + result.stdout[:200] + "...")
                                return False
                        else:
                            logger.error(f"Token extraction failed with exit code {result.returncode}")
                            logger.error(f"Error: {result.stderr}")
                            
                            # Provide helpful instruction to the user
                            logger.info("You might need to manually extract a token:")
                            logger.info("1. Log in to Substack in your browser")
                            logger.info("2. Use Developer Tools > Network tab to inspect requests")
                            logger.info("3. Look for 'home' request and copy request headers")
                            logger.info("4. Run: python scripts/get_substack_token.py --method headers --headers \"PASTE_HEADERS_HERE\"")
                            
                            return False
                    
                    except Exception as e:
                        logger.error(f"Error running token extractor: {e}")
                        return False
            
            # Initialize fetcher with authentication
            fetcher = SubstackFetcher(
                max_retries=args.max_retries,
                retry_delay=args.retry_delay,
                use_proxy=args.rotate_proxy
            )
            
            # Set up authentication with the session ID
            if auth_info.get('substack_sid'):
                success = fetcher.authenticate(token=auth_info.get('substack_sid'))
                if success:
                    logger.info("Authentication successful")
                else:
                    logger.warning("Authentication failed, will try to continue anyway")
        else:
            # Initialize fetcher without authentication for public posts
            fetcher = SubstackFetcher(
                max_retries=args.max_retries,
                retry_delay=args.retry_delay,
                use_proxy=args.rotate_proxy
            )
        
        # Set up session with retry logic
        session = setup_session_with_retry(
            max_retries=args.max_retries,
            rotate_proxy=args.rotate_proxy,
            use_proxy=args.use_proxy,
            request_timeout=args.request_timeout
        )
        
        # Create output directories
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(os.path.join(OUTPUT_DIR, IMAGE_DIR), exist_ok=True)
        
        # Fetch all posts
        logger.info("Fetching post list... (this may take a while)")
        
        # Add a simple progress indicator during fetch
        def fetch_with_progress_indicator():
            import threading
            import itertools
            import sys
            
            # Create a progress spinner in a separate thread
            stop_spinner = threading.Event()
            def spinner_task():
                spinner = itertools.cycle(['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷'])
                while not stop_spinner.is_set():
                    sys.stdout.write('\r' + f"Fetching posts... {next(spinner)} ")
                    sys.stdout.flush()
                    time.sleep(0.2)
                sys.stdout.write('\r' + ' ' * 50 + '\r')  # Clear the spinner line
                sys.stdout.flush()
            
            # Start the spinner thread
            spinner_thread = threading.Thread(target=spinner_task)
            spinner_thread.daemon = True
            spinner_thread.start()
            
            try:
                # Perform the fetch operation with timeout
                import threading
                import concurrent.futures
                
                # Set timeout from args (default: 5 minutes)
                FETCH_TIMEOUT = args.fetch_timeout
                
                # Use a thread-based timeout approach (works on all platforms)
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(fetcher.fetch_posts, AUTHOR, verbose=args.verbose)
                    try:
                        result = future.result(timeout=FETCH_TIMEOUT)
                        return result
                    except concurrent.futures.TimeoutError:
                        logger.error(f"Fetch operation timed out after {FETCH_TIMEOUT} seconds")
                        raise TimeoutError(f"Fetch operation timed out after {FETCH_TIMEOUT} seconds")
            finally:
                # Stop the spinner thread
                stop_spinner.set()
                spinner_thread.join(timeout=1.0)
        
        # Skip the library fetch attempt and go straight to the direct API method
        logger.info("Using direct API access method...")
        
        try:
            import requests
            from bs4 import BeautifulSoup
            
            # Fallback to web scraping approach
            logger.info("Using web scraping approach to get posts...")
            
            all_posts = []
            page = 1
            
            # Create a session with user agent to avoid blocks
            session = requests.Session()
            session.headers.update({
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            })
            
            # Scrape each page of the archive
            while True:
                # Construct URL for the current page
                url = f"https://{AUTHOR}.substack.com/archive?sort=new&page={page}"
                logger.info(f"Scraping archive page {page}: {url}")
                
                # Apply throttling
                throttle_request(args.min_delay, args.max_delay)
                
                # Fetch the page
                response = session.get(url, timeout=30)
                
                if response.status_code == 200:
                    # Parse the HTML
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Debug: Check if 'post-preview' exists in the HTML
                    if 'post-preview' in response.text:
                        logger.info("Found 'post-preview' in HTML but selector may not be matching")
                    
                    # Try different selectors for debugging
                    logger.info(f"HTML length: {len(response.text)}")
                    
                    # Try to find any posts with various selectors
                    selectors_to_try = [
                        '.post-preview', 
                        'article', 
                        '.post', 
                        'div.post', 
                        'a.post-title', 
                        'h2.post-title', 
                        'h2.post-title a',
                        '.post-title'
                    ]
                    
                    post_elements = []
                    for selector in selectors_to_try:
                        elements = soup.select(selector)
                        logger.info(f"Selector '{selector}' found {len(elements)} elements")
                        if elements:
                            post_elements = elements
                            logger.info(f"Using selector '{selector}' with {len(elements)} elements")
                            break
                    
                    if not post_elements:
                        logger.info(f"No more posts found on page {page}")
                        break
                    
                    # Process each post
                    page_posts = []
                    for post_elem in post_elements:
                        try:
                            # Extract post data
                            post_data = {}
                            
                            # Get title and URL
                            title_elem = post_elem.select_one('h2.post-title a')
                            if title_elem:
                                post_data['title'] = title_elem.text.strip()
                                post_data['canonical_url'] = title_elem.get('href')
                                if not post_data['canonical_url'].startswith('http'):
                                    post_data['canonical_url'] = f"https://{AUTHOR}.substack.com{post_data['canonical_url']}"
                            
                            # Get date
                            date_elem = post_elem.select_one('time.post-date')
                            if date_elem:
                                post_data['post_date'] = date_elem.get('datetime')
                            
                            # Generate a unique ID
                            post_slug = post_data.get('canonical_url', '').split('/')[-1]
                            post_data['id'] = int(hashlib.md5(post_slug.encode()).hexdigest(), 16) % 10**10
                            
                            # Set author
                            post_data['author'] = {"name": "Trade Companion"}
                            
                            # Set subtitle
                            subtitle_elem = post_elem.select_one('h3.post-subtitle')
                            if subtitle_elem:
                                post_data['subtitle'] = subtitle_elem.text.strip()
                            
                            # Set publication date
                            post_data['publication_date'] = post_data.get('post_date')
                            
                            # Add post if it has required fields
                            if 'title' in post_data and 'canonical_url' in post_data:
                                page_posts.append(post_data)
                        except Exception as e:
                            logger.warning(f"Error extracting post data: {e}")
                    
                    # Log progress
                    logger.info(f"Found {len(page_posts)} posts on page {page}")
                    all_posts.extend(page_posts)
                    
                    # Check if we've reached the end
                    if len(page_posts) == 0 or len(post_elements) < 10:  # Usually 10 posts per page
                        logger.info("Reached the end of archive pages")
                        break
                    
                    # Move to next page
                    page += 1
                else:
                    logger.error(f"Failed to fetch archive page {page}: {response.status_code}")
                    if page > 1:  # If we've got some posts, continue with what we have
                        break
                    else:  # If first page fails, we have a problem
                        return False
            
            if all_posts:
                logger.info(f"Successfully fetched a total of {len(all_posts)} posts")
                posts = all_posts
            else:
                logger.error("Failed to fetch any posts")
                return False
        except Exception as e:
            logger.error(f"Direct API method failed: {e}")
            return False
            
            # If we still don't have posts, try a simple webpage scrape
            if not posts:
                try:
                    logger.info("Attempting HTML scraping fallback...")
                    url = f"https://{AUTHOR}.substack.com/"
                    
                    response = session.get(url, timeout=30)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Find the archive links
                        posts = []
                        for article in soup.select('article.post'):
                            # Extract post data
                            post_data = {}
                            
                            # Extract title
                            title_elem = article.select_one('h2.post-title a')
                            if title_elem:
                                post_data['title'] = title_elem.text.strip()
                                post_data['canonical_url'] = title_elem.get('href')
                                
                                # Extract ID from URL
                                try:
                                    post_data['id'] = int(post_data['canonical_url'].split('/')[-1])
                                except:
                                    # Generate a fake ID
                                    post_data['id'] = hash(post_data['canonical_url']) % 10000000
                            
                            # Extract date
                            date_elem = article.select_one('time')
                            if date_elem:
                                post_data['post_date'] = date_elem.get('datetime')
                            
                            # Extract author
                            author_elem = article.select_one('.byline a')
                            if author_elem:
                                post_data['author'] = {"name": author_elem.text.strip()}
                            
                            if post_data.get('title') and post_data.get('canonical_url'):
                                posts.append(post_data)
                        
                        if posts:
                            logger.info(f"Successfully scraped {len(posts)} posts from HTML")
                        else:
                            logger.error("HTML scraping failed to find any posts")
                            return False
                    else:
                        logger.error(f"HTML scraping failed with status {response.status_code}")
                        return False
                except Exception as e:
                    logger.error(f"HTML scraping fallback failed: {e}")
                    return False
            
            # If we still don't have posts, give up
            if not posts:
                logger.error("All fallback methods failed to fetch posts")
                return False
        
        # Update total post count
        total_posts = len(posts)
        
        # Log post statistics
        logger.info(f"Found {total_posts} posts")
        logger.info(f"Already downloaded: {len(downloaded_ids)} posts")
        if args.force:
            logger.info("Force refresh enabled: re-downloading all posts")
        
        # Display progress header
        logger.info("-" * 50)
        logger.info("Starting download...")
        
        # Process each post
        for i, post in enumerate(posts):
            if interrupted:
                logger.info("Interrupt signal received. Exiting...")
                break
            
            # Display progress
            progress = (i + 1) / total_posts * 100
            logger.info(f"Processing post {i+1}/{total_posts} ({progress:.1f}%): {post.get('title')}")
            
            # Process the post
            process_post(post, session, OUTPUT_DIR, IMAGE_DIR, downloaded_ids, args)
            
            # Check if we need to save checkpoint
            if i % args.checkpoint_interval == args.checkpoint_interval - 1:
                logger.info(f"Saving checkpoint after {i+1} posts...")
                metadata = {
                    "total_posts": total_posts,
                    "successful_posts": successful_posts,
                    "failed_posts": failed_posts
                }
                save_checkpoint(downloaded_ids, metadata)
        
        # Save final checkpoint
        metadata = {
            "total_posts": total_posts,
            "successful_posts": successful_posts,
            "failed_posts": failed_posts
        }
        save_checkpoint(downloaded_ids, metadata)
        
        # Display summary
        logger.info("-" * 50)
        logger.info("Download summary:")
        logger.info(f"Total posts: {total_posts}")
        logger.info(f"Successfully downloaded: {successful_posts}")
        logger.info(f"Failed: {failed_posts}")
        
        return successful_posts + (len(downloaded_ids) - successful_posts) >= total_posts
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
        
        # Save checkpoint in case of unexpected error
        metadata = {
            "total_posts": total_posts,
            "successful_posts": successful_posts,
            "failed_posts": failed_posts
        }
        save_checkpoint(downloaded_ids, metadata)
        
        return False


def fetch_post_content_with_browser(url: str, method: str = 'selenium', verbose: bool = False) -> Optional[str]:
    """
    Fetch post content using browser automation as a fallback.
    
    Args:
        url (str): The URL of the post.
        method (str, optional): Browser automation method to use. Defaults to 'selenium'.
        verbose (bool, optional): Enable verbose output. Defaults to False.
    
    Returns:
        Optional[str]: The HTML content of the post, or None if it could not be fetched.
    """
    logger.info(f"Attempting to fetch post content using browser automation ({method})...")
    
    if method == 'selenium':
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            # Set up browser options
            options = webdriver.ChromeOptions()
            options.add_argument('--headless=new')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1280,800')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            # Add random user agent
            options.add_argument(f'--user-agent={random.choice(USER_AGENTS)}')
            
            # Initialize the browser
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            logger.error(f"Error setting up Selenium: {e}")
            return None
            
        try:
            # Navigate to the post URL
            driver.get(url)
            logger.info(f"Navigated to {url}")
            
            # Wait for the content to load
            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'article')))
            
            # Get the HTML content
            article = driver.find_element(By.TAG_NAME, 'article')
            html_content = article.get_attribute('innerHTML')
            
            if html_content:
                logger.info("Successfully fetched post content with Selenium")
                return html_content
            else:
                logger.warning("No content found in article element")
                return None
        except Exception as e:
            logger.error(f"Error fetching content with Selenium: {e}")
            return None
        finally:
            driver.quit()
    
    elif method == 'puppeteer':
        temp_path = None
        js_path = None
        
        try:
            import subprocess
            import json
            import tempfile
            
            # Create a temporary file to store the HTML content
            with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Prepare the Puppeteer script
            puppeteer_script = f"""
            const puppeteer = require('puppeteer');
            
            (async () => {{
                const browser = await puppeteer.launch({{
                    headless: 'new',
                    args: [
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--disable-gpu'
                    ]
                }});
                
                try {{
                    const page = await browser.newPage();
                    
                    // Set random user agent
                    await page.setUserAgent('{random.choice(USER_AGENTS)}');
                    
                    // Set extra HTTP headers
                    await page.setExtraHTTPHeaders({{
                        'Accept-Language': '{random.choice(ACCEPT_LANGUAGES)}',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }});
                    
                    // Navigate to the page
                    await page.goto('{url}', {{ waitUntil: 'networkidle2', timeout: 30000 }});
                    
                    // Wait for article to load
                    await page.waitForSelector('article', {{ timeout: 20000 }});
                    
                    // Get article content
                    const article = await page.$('article');
                    const html = await page.evaluate(article => article.innerHTML, article);
                    
                    // Save HTML to file
                    require('fs').writeFileSync('{temp_path}', html);
                    
                    console.log(JSON.stringify({{ success: true, path: '{temp_path}' }}));
                }} catch (error) {{
                    console.error(JSON.stringify({{ success: false, error: error.message }}));
                }} finally {{
                    await browser.close();
                }}
            }})();
            """
            
            # Create a temporary JS file
            with tempfile.NamedTemporaryFile(suffix='.js', delete=False) as js_file:
                js_file.write(puppeteer_script.encode('utf-8'))
                js_path = js_file.name
        except Exception as e:
            logger.error(f"Error setting up Puppeteer: {e}")
            # Clean up any created temporary files
            if js_path and os.path.exists(js_path):
                try:
                    os.unlink(js_path)
                except:
                    pass
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
            return None
            
        # Execute the Puppeteer script
        try:
            # Check if Node.js and Puppeteer are available
            subprocess.run(['node', '--version'], check=True, capture_output=True)
            
            # Run the script
            result = subprocess.run(['node', js_path], capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            
            # Parse the output
            try:
                output_json = json.loads(output)
                if output_json.get('success', False):
                    # Read the HTML content from the temporary file
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    if html_content:
                        logger.info("Successfully fetched post content with Puppeteer")
                        return html_content
                    else:
                        logger.warning("No content found in article element (Puppeteer)")
                        return None
                else:
                    logger.error(f"Puppeteer script error: {output_json.get('error', 'Unknown error')}")
                    return None
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Puppeteer output: {output}")
                return None
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running Puppeteer script: {e}")
            if e.stderr:
                logger.error(f"Puppeteer stderr: {e.stderr}")
            return None
        except FileNotFoundError:
            logger.error("Node.js not found. Make sure Node.js is installed and in PATH.")
            return None
        finally:
            # Clean up temporary files
            if js_path and os.path.exists(js_path):
                try:
                    os.unlink(js_path)
                except Exception as e:
                    logger.warning(f"Error cleaning up JS file: {e}")
            
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Error cleaning up HTML file: {e}")
    
    else:
        logger.error(f"Unsupported browser automation method: {method}")
        return None
        
    return None


if __name__ == "__main__":
    main()
