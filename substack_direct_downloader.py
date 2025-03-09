#!/usr/bin/env python3
"""
Direct Substack Downloader

This script downloads posts from Substack directly without relying on the API.
It first scrapes the archive page to find post URLs, then downloads each post.
"""

import os
import requests
from bs4 import BeautifulSoup
import json
import re
import time
import random
from datetime import datetime
import logging
import sys
import urllib.parse
import hashlib
from pathlib import Path

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

# Configuration
AUTHOR = "tradecompanion"
OUTPUT_DIR = f"output/{AUTHOR}"
IMAGE_DIR = f"{OUTPUT_DIR}/images"
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
]
MIN_DELAY = 2  # Minimum delay between requests in seconds
MAX_DELAY = 5  # Maximum delay between requests in seconds

def throttle_request():
    """Apply random delay between requests to avoid being detected as a bot"""
    delay = MIN_DELAY + random.random() * (MAX_DELAY - MIN_DELAY)
    logger.debug(f"Throttling request: sleeping for {delay:.2f} seconds")
    time.sleep(delay)


def create_session():
    """Create and configure requests session with random user agent"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    })
    return session


def find_post_urls(max_pages=10):
    """Find post URLs by scraping the Substack archive pages"""
    logger.info(f"Scraping archive pages for {AUTHOR}.substack.com")
    
    # Create a session with random user agent
    session = create_session()
    
    post_urls = []
    for page in range(1, max_pages + 1):
        # Construct URL for the current page
        url = f"https://{AUTHOR}.substack.com/archive?sort=new&page={page}"
        logger.info(f"Scraping archive page {page}: {url}")
        
        # Apply throttling
        throttle_request()
        
        try:
            # Fetch the page
            response = session.get(url, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch archive page {page}: {response.status_code}")
                break
            
            # Get JSON data from the page if it exists in a script tag
            json_data = extract_json_data(response.text)
            if json_data and 'posts' in json_data:
                logger.info(f"Found {len(json_data['posts'])} posts in JSON data on page {page}")
                
                # Extract post URLs from JSON data
                for post in json_data['posts']:
                    slug = post.get('slug')
                    if slug:
                        post_url = f"https://{AUTHOR}.substack.com/p/{slug}"
                        post_urls.append(post_url)
                        logger.debug(f"Added post URL: {post_url}")
            
            # Fallback to HTML parsing if no JSON data found
            if not json_data or 'posts' not in json_data:
                # Parse the HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for links to posts in various possible HTML structures
                for link in soup.select('a[href*="/p/"]'):
                    href = link.get('href')
                    if href and '/p/' in href:
                        if not href.startswith('http'):
                            post_url = f"https://{AUTHOR}.substack.com{href}"
                        else:
                            post_url = href
                        
                        # Ensure we're only grabbing posts from the current author
                        if f"{AUTHOR}.substack.com" in post_url:
                            post_urls.append(post_url)
                            logger.debug(f"Added post URL: {post_url}")
            
            # Check if we reached the end
            if "No posts to see here" in response.text or "There are no more posts" in response.text:
                logger.info(f"Reached the end of archive at page {page}")
                break
            
            # Success!
            logger.info(f"Successfully processed page {page}, total URLs found: {len(post_urls)}")
            
        except Exception as e:
            logger.error(f"Error processing page {page}: {e}")
            break
    
    # Remove duplicates while preserving order
    unique_urls = []
    for url in post_urls:
        if url not in unique_urls:
            unique_urls.append(url)
    
    logger.info(f"Found {len(unique_urls)} unique post URLs")
    return unique_urls


def extract_json_data(html):
    """Extract JSON data from the HTML page if available"""
    try:
        # Look for JSON data in script tags
        pattern = r'window\.__PRELOADED_STATE__ = JSON\.parse\("(.+?)"\);'
        match = re.search(pattern, html)
        if match:
            json_str = match.group(1)
            # Unescape JSON string
            json_str = json_str.replace('\\"', '"').replace('\\\\', '\\')
            return json.loads(json_str)
    except Exception as e:
        logger.warning(f"Error extracting JSON data: {e}")
    
    return None


def download_post(url, force=False):
    """Download a post from Substack and save it as markdown"""
    logger.info(f"Downloading post: {url}")
    
    # Create output directories if they don't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    
    # Extract slug from URL to use in filename
    slug = url.split('/')[-1]
    
    # Skip if already downloaded (unless force=True)
    existing_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(f"_{slug}.md")]
    if existing_files and not force:
        logger.info(f"Skipping already downloaded post: {slug}")
        return True
    
    # Apply throttling
    throttle_request()
    
    # Set up session with random user agent and authentication if available
    session = create_session()
    
    # Add authentication cookies if available (from .env file)
    try:
        from env_loader import load_env_vars, get_substack_auth
        load_env_vars()
        auth_info = get_substack_auth()
        if auth_info.get('token'):
            logger.info("Using authentication token from .env file")
            # Set the authentication cookie
            session.cookies.set("substack.sid", auth_info.get('token'), domain=f"{AUTHOR}.substack.com", path="/")
            # Also try setting it for the main domain
            session.cookies.set("substack.sid", auth_info.get('token'), domain="substack.com", path="/")
    except ImportError:
        logger.warning("env_loader module not found, continuing without authentication")
    
    # Fetch the post
    try:
        logger.info(f"Fetching content for {url}")
        response = session.get(url, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch post: HTTP {response.status_code}")
            return False
        
        # Parse the HTML
        logger.debug("Parsing HTML content...")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract post title
        title_elem = soup.select_one('h1.post-title')
        title = title_elem.text.strip() if title_elem else "Untitled Post"
        logger.info(f"Post title: {title}")
        
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
        logger.info(f"Post date: {formatted_date}")
        
        # Extract post content - try multiple approaches to get the full content
        content_html = ""
        
        # First check if the content is embedded in JavaScript
        # Look for the full post content in JavaScript variable
        match = re.search(r'window\.__APOLLO_STATE__ =\s*({.+?});', response.text, re.DOTALL)
        if match:
            try:
                apollo_state = json.loads(match.group(1))
                # Find the post content in the Apollo state
                for key, value in apollo_state.items():
                    if isinstance(value, dict) and 'body_html' in value and value.get('body_html'):
                        content_html = value.get('body_html')
                        logger.info("Found post content in Apollo state")
                        break
            except Exception as e:
                logger.warning(f"Failed to parse Apollo state: {e}")
        
        # If no content found in JavaScript, try HTML selectors
        if not content_html:
            # Try multiple selectors in order of most likely to contain the full content
            selectors = [
                'div.available-content',
                'div.post-content-final',  # This appears to be used on newer Substacks
                'div.post-content',
                'div.content-wrapper article',
                'div.single-post article',
                'article div.body',
                'article',
                '.body',
                'div.body'
            ]
            
            for selector in selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    logger.debug(f"Found content using selector: {selector}")
                    content_html = str(content_elem)
                    break
        
        # If still no content, try a more aggressive approach - grab everything in the post container
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
        
        # Additional check to ensure we're getting the full content
        logger.info(f"Content length: {len(content_html)} characters")
        
        # Check for paywalled content indicators
        if "Subscribe to continue reading" in response.text or "This post is for paying subscribers" in response.text:
            logger.warning("Warning: This post may be paywalled and we might only have a preview")
        
        # Try to convert HTML to proper markdown
        logger.debug("Converting to markdown...")
        try:
            from markdownify import markdownify
            content_markdown = markdownify(content_html)
        except ImportError:
            # If markdownify is not available, use a simpler conversion
            logger.warning("Warning: markdownify not available, using basic HTML")
            content_markdown = content_html
        
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
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # Save the file
        logger.info(f"Saving to {filepath}...")
        try:
            # Make sure the output directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Save the file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown)
                
            # Verify the file was saved
            if os.path.exists(filepath):
                logger.info(f"File saved successfully: {os.path.getsize(filepath)} bytes")
            else:
                logger.error(f"File wasn't created: {filepath}")
        except Exception as e:
            logger.error(f"Error saving file: {e}")
        
        logger.info(f"Post downloaded successfully: {title}")
        return True
        
    except Exception as e:
        logger.error(f"Error downloading post {url}: {e}")
        return False


def download_all_posts(max_pages=10, force_refresh=False, max_posts=None):
    """Download all posts from the Substack site"""
    logger.info(f"Starting download of posts from {AUTHOR}.substack.com")
    
    # Get post URLs
    post_urls = find_post_urls(max_pages)
    
    # Limit the number of posts if specified
    if max_posts:
        post_urls = post_urls[:max_posts]
    
    # Download each post
    successful = 0
    failed = 0
    skipped = 0
    
    for i, url in enumerate(post_urls):
        logger.info(f"Processing post {i+1}/{len(post_urls)}: {url}")
        
        result = download_post(url, force=force_refresh)
        if result is True:
            successful += 1
        else:
            failed += 1
        
        # Simple progress display
        progress = (i + 1) / len(post_urls) * 100
        logger.info(f"Progress: {progress:.1f}% ({i+1}/{len(post_urls)})")
    
    # Print summary
    logger.info("=" * 50)
    logger.info(f"Download summary for {AUTHOR}.substack.com:")
    logger.info(f"Total posts processed: {len(post_urls)}")
    logger.info(f"Successfully downloaded: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Skipped (already downloaded): {skipped}")
    logger.info("=" * 50)
    
    return successful, failed, skipped


if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Download posts from Substack')
    parser.add_argument('--author', default=AUTHOR, help=f'Substack author identifier (default: {AUTHOR})')
    parser.add_argument('--max-pages', type=int, default=10, help='Maximum number of archive pages to scan (default: 10)')
    parser.add_argument('--max-posts', type=int, help='Maximum number of posts to download')
    parser.add_argument('--force', action='store_true', help='Force refresh of already downloaded posts')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--url', help='Download a specific URL instead of scanning archive')
    
    args = parser.parse_args()
    
    # Update configuration based on arguments
    AUTHOR = args.author
    OUTPUT_DIR = f"output/{AUTHOR}"
    IMAGE_DIR = f"{OUTPUT_DIR}/images"
    
    # Set log level based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Download specific URL or all posts
    if args.url:
        logger.info(f"Downloading specific URL: {args.url}")
        download_post(args.url, force=args.force)
    else:
        download_all_posts(max_pages=args.max_pages, force_refresh=args.force, max_posts=args.max_posts)