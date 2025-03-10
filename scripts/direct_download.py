#!/usr/bin/env python3
"""
Direct download script for Substack posts

This is a simplified script to download a Substack post directly without the complex class.
It uses direct requests to fetch the content.
"""

import os
import re
import aiohttp
import asyncio
import logging
from pathlib import Path
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("direct_downloader")

async def download_tradecompanion_post(url):
    """
    Download a single post using direct authentication.
    """
    try:
        # Use your token from the request
        token = "s%3AN4m_2WeCcjjQaC4xkLvZ8ANHcRN7Fua2.igySoAeXZmVtYyTC085IR49LpujV7AnEoIgv%2FnZMcy4"
        
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
            "substack.authpub": "tradecompanion",
            "substack.lli": "1",
            "ajs_anonymous_id": '"804903de-519a-4a25-92a8-d51b0613f8af"',
            "visit_id": '{%22id%22:%223f129271-fd95-4a8d-b704-c83644ac9ac3%22%2C%22timestamp%22:%222025-03-09T23%3A33%3A24.339Z%22}'
        }
        
        # Make the request
        async with aiohttp.ClientSession(headers=headers) as session:
            # First visit the main page
            main_url = "https://tradecompanion.substack.com/"
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
                
                # Save the full HTML for debugging
                with open("full_page.html", "w", encoding="utf-8") as f:
                    f.write(html)
                    
                # Extract the post content
                soup = BeautifulSoup(html, 'html.parser')
                
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
                
                # Save the content
                with open("post_content.html", "w", encoding="utf-8") as f:
                    f.write(content)
                
                return html
                
    except Exception as e:
        logger.error(f"Error downloading post: {e}")
        return None

async def main():
    url = "https://tradecompanion.substack.com/p/multi-month-breakout-in-spx-just-bc6"
    result = await download_tradecompanion_post(url)
    if result:
        logger.info("Successfully downloaded post")
    else:
        logger.error("Failed to download post")

if __name__ == "__main__":
    asyncio.run(main())