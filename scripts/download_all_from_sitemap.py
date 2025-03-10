#!/usr/bin/env python3
"""
Download All Posts from Sitemap

This script uses the sitemap.xml approach to find all posts from a Substack author
and downloads them using the direct method for full content retrieval.
"""

import os
import sys
import asyncio
import argparse
import logging
from bs4 import BeautifulSoup
import aiohttp
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sitemap_download.log')
    ]
)
logger = logging.getLogger("sitemap_downloader")

# Global default token - can be overridden via command line
token = "s%3AN4m_2WeCcjjQaC4xkLvZ8ANHcRN7Fua2.igySoAeXZmVtYyTC085IR49LpujV7AnEoIgv%2FnZMcy4"

async def fetch_sitemap(author, verbose=False):
    """Fetch the sitemap.xml and extract all post URLs."""
    sitemap_url = f"https://{author}.substack.com/sitemap.xml"
    
    if verbose:
        logger.info(f"Fetching sitemap from: {sitemap_url}")
    
    # Create a session and fetch the sitemap
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(sitemap_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch sitemap: {response.status}")
                    return []
                
                sitemap_content = await response.text()
                
                # Parse the XML content
                soup = BeautifulSoup(sitemap_content, 'lxml-xml')
                
                # Extract all URLs
                post_urls = []
                base_domain = f"{author}.substack.com"
                
                for url_elem in soup.find_all('loc'):
                    url = url_elem.text
                    parsed_url = urlparse(url)
                    
                    # Filter for post URLs (those containing /p/ in the path)
                    if parsed_url.netloc == base_domain and "/p/" in parsed_url.path:
                        post_urls.append(url)
                
                if verbose:
                    logger.info(f"Found {len(post_urls)} post URLs in sitemap")
                
                return post_urls
                
        except Exception as e:
            logger.error(f"Error fetching sitemap: {e}")
            return []

async def download_image(session, url, output_path, verbose=False):
    """Download an image from a URL."""
    try:
        async with session.get(url) as response:
            if response.status != 200:
                if verbose:
                    logger.warning(f"Failed to download image: {url}")
                return None
            
            # Read the image data
            image_data = await response.read()
            
            # Save the image
            with open(output_path, "wb") as f:
                f.write(image_data)
            
            if verbose:
                logger.info(f"Downloaded image: {url} -> {output_path}")
            
            return output_path
            
    except Exception as e:
        if verbose:
            logger.warning(f"Error downloading image: {url} - {e}")
        return None

async def download_post(url, verbose=False, download_images=True):
    """Download a single post using the direct downloader with HTML to Markdown conversion."""
    import os
    import re
    import hashlib
    import aiohttp
    from datetime import datetime
    from urllib.parse import urlparse, urljoin
    from bs4 import BeautifulSoup
    
    # Extract author and slug from URL for file naming
    parsed_url = urlparse(url)
    author = parsed_url.netloc.split('.')[0]
    slug = parsed_url.path.split('/')[-1]
    
    try:
        if verbose:
            logger.info(f"Downloading: {url}")
        
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
        
        # Cookies for authentication (use the global token)
        global token
        cookies = {
            "substack.sid": token,
            "substack-sid": token,
            "substack.authpub": author,
            "substack.lli": "1"
        }
        
        # Create output directories
        output_dir = os.path.join("output", author)
        images_dir = os.path.join(output_dir, "images")
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(images_dir, exist_ok=True)
        
        # Direct fetch approach
        async with aiohttp.ClientSession(headers=headers) as session:
            # First visit the main page to establish cookies
            main_url = f"https://{author}.substack.com/"
            
            async with session.get(main_url, cookies=cookies) as response:
                if response.status != 200:
                    logger.warning(f"Failed to visit main site for {author}: {response.status}")
            
            # Now get the actual post
            async with session.get(url, cookies=cookies) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch post: {response.status}")
                    return False
                
                html = await response.text()
                
                # Extract metadata using BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract title
                title_elem = soup.select_one('h1.post-title')
                title = title_elem.text.strip() if title_elem else "Untitled Post"
                
                # Extract date
                date_elem = soup.select_one('time')
                if date_elem and date_elem.get('datetime'):
                    try:
                        date_obj = datetime.fromisoformat(date_elem.get('datetime').replace('Z', '+00:00'))
                        formatted_date = date_obj.strftime('%Y-%m-%d')
                    except:
                        formatted_date = datetime.now().strftime('%Y-%m-%d')
                else:
                    formatted_date = datetime.now().strftime('%Y-%m-%d')
                
                # Extract content - first try BeautifulSoup
                body_markup = soup.select_one('div.body.markup')
                
                if body_markup:
                    content_html = str(body_markup)
                    if verbose:
                        logger.info(f"Found content div with BeautifulSoup (length: {len(content_html)})")
                else:
                    # Try regex as fallback
                    if verbose:
                        logger.info("Trying regex fallback for content extraction")
                    match = re.search(r'<div class="body markup" dir="auto">(.*?)</div>\s*</div>\s*<div', html, re.DOTALL)
                    if match:
                        content_html = f'<div class="body markup" dir="auto">{match.group(1)}</div>'
                        if verbose:
                            logger.info(f"Found content with regex (length: {len(content_html)})")
                    else:
                        logger.error("Couldn't extract content with regex either")
                        content_html = "<p>Failed to extract content</p>"
                
                # Process images if enabled
                if download_images:
                    # Parse the content to find images
                    content_soup = BeautifulSoup(content_html, 'html.parser')
                    images = content_soup.find_all('img')
                    
                    if images and verbose:
                        logger.info(f"Found {len(images)} images to download")
                    
                    # Download and replace images
                    for img in images:
                        src = img.get('src')
                        if not src or src.startswith('data:'):
                            continue
                        
                        # Make absolute URL if needed
                        if not src.startswith(('http://', 'https://')):
                            src = urljoin(url, src)
                        
                        # Generate filename for image
                        img_hash = hashlib.md5(src.encode()).hexdigest()[:10]
                        img_ext = os.path.splitext(src)[1]
                        if not img_ext:
                            img_ext = '.jpg'  # Default extension
                        
                        img_filename = f"{slug}_{img_hash}{img_ext}"
                        img_path = os.path.join(images_dir, img_filename)
                        
                        # Download image
                        local_path = await download_image(session, src, img_path, verbose)
                        
                        if local_path:
                            # Update image source to local path
                            rel_path = os.path.join("images", img_filename)
                            img['src'] = rel_path
                    
                    # Update content_html with the modified image paths
                    content_html = str(content_soup)
                
                # Convert HTML to Markdown
                try:
                    from markdownify import markdownify
                    content_markdown = markdownify(content_html)
                except ImportError:
                    # If markdownify is not available, fallback to a simple conversion
                    logger.warning("markdownify not installed, using basic HTML. Install with: pip install markdownify")
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
                
                # Save the file
                filename = f"{formatted_date}_{slug}.md"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(markdown)
                
                if verbose:
                    logger.info(f"Saved to {filepath} ({os.path.getsize(filepath)} bytes)")
                
                return True
                
    except Exception as e:
        logger.error(f"Error downloading post {url}: {e}")
        return False

async def download_batch(urls, batch_size=3, verbose=False, download_images=True):
    """Download posts in batches to avoid overwhelming the server."""
    successful = 0
    failed = 0
    
    # Process in batches
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i+batch_size]
        
        if verbose:
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(urls) + batch_size - 1)//batch_size}, posts {i+1}-{min(i+batch_size, len(urls))}")
        
        # Create tasks for each post in the batch
        tasks = []
        for url in batch:
            tasks.append(download_post(url, verbose, download_images))
        
        # Wait for all tasks in the batch to complete
        results = await asyncio.gather(*tasks)
        
        # Count results
        successful += sum(1 for r in results if r)
        failed += sum(1 for r in results if not r)
        
        # Small delay between batches to avoid rate limiting
        await asyncio.sleep(1)
    
    return successful, failed

async def main():
    parser = argparse.ArgumentParser(description="Download all posts from a Substack author using sitemap")
    parser.add_argument("--author", required=True, help="Substack author identifier (e.g. 'tradecompanion')")
    parser.add_argument("--batch-size", type=int, default=3, help="Number of posts to download in parallel (default: 3)")
    parser.add_argument("--max-posts", type=int, help="Maximum number of posts to download")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--no-images", action="store_true", help="Skip downloading images")
    parser.add_argument("--token", help="Substack authentication token (if different from default)")
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Start timer
    import time
    start_time = time.time()
    
    # Fetch all post URLs from sitemap
    logger.info(f"Finding all posts for {args.author} from sitemap...")
    post_urls = await fetch_sitemap(args.author, args.verbose)
    
    if not post_urls:
        logger.error(f"No posts found for {args.author}")
        return
    
    # Limit the number of posts if specified
    if args.max_posts and len(post_urls) > args.max_posts:
        logger.info(f"Limiting to {args.max_posts} posts (out of {len(post_urls)} total)")
        post_urls = post_urls[:args.max_posts]
    
    # Override the token if provided
    if args.token:
        global token
        token = args.token
        logger.info(f"Using custom authentication token: {token[:10]}...")
    
    # Download all posts
    logger.info(f"Downloading {len(post_urls)} posts with batch size {args.batch_size}...")
    successful, failed = await download_batch(
        post_urls, 
        args.batch_size, 
        args.verbose,
        not args.no_images
    )
    
    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    
    # Print summary
    logger.info("=" * 50)
    logger.info(f"Download summary for {args.author}:")
    logger.info(f"Total posts: {len(post_urls)}")
    logger.info(f"Successfully downloaded: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Time elapsed: {elapsed_time:.2f} seconds")
    logger.info("=" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Download interrupted by user")
        sys.exit(0)