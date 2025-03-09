#!/usr/bin/env python3
"""
Batch Image Downloader Module

This module provides functionality for downloading images in parallel batches.
It gathers all image URLs upfront and downloads them using asyncio.gather with concurrency limits.
"""

import os
import re
import asyncio
import logging
import hashlib
import aiohttp
from typing import Dict, List, Set, Tuple, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("batch_image_downloader")

class BatchImageDownloader:
    """
    A class for downloading images in parallel batches.
    
    Attributes:
        output_dir (str): Directory to save downloaded images.
        max_concurrency (int): Maximum number of concurrent downloads.
        timeout (int): Timeout for HTTP requests in seconds.
        session (aiohttp.ClientSession): HTTP session for making requests.
        semaphore (asyncio.Semaphore): Semaphore for limiting concurrency.
    """
    
    def __init__(self, output_dir: str = "images", max_concurrency: int = 5, timeout: int = 30):
        """
        Initialize the BatchImageDownloader.
        
        Args:
            output_dir (str, optional): Directory to save downloaded images. 
                                      Defaults to "images".
            max_concurrency (int, optional): Maximum number of concurrent downloads. 
                                           Defaults to 5.
            timeout (int, optional): Timeout for HTTP requests in seconds. 
                                   Defaults to 30.
        """
        self.output_dir = output_dir
        self.max_concurrency = max_concurrency
        self.timeout = timeout
        self.session = None
        self.semaphore = None
        
        # Create the output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        self.semaphore = asyncio.Semaphore(self.max_concurrency)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def extract_image_urls(self, html_content: str, base_url: str = "") -> Set[str]:
        """
        Extract image URLs from HTML content.
        
        Args:
            html_content (str): HTML content to extract image URLs from.
            base_url (str, optional): Base URL for resolving relative URLs. 
                                    Defaults to "".
        
        Returns:
            Set[str]: Set of image URLs.
        """
        image_urls = set()
        
        # Parse the HTML content
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Find all image tags
        for img in soup.find_all("img"):
            src = img.get("src")
            
            if not src:
                continue
            
            # Skip data URIs
            if src.startswith("data:"):
                continue
            
            # Skip small images like tracking pixels
            if "pixel" in src.lower() or "tracking" in src.lower() or "analytics" in src.lower():
                continue
            
            # Resolve relative URLs
            if base_url and not src.startswith(("http://", "https://")):
                src = urljoin(base_url, src)
            
            # Add the URL to the set
            image_urls.add(src)
        
        return image_urls
    
    def _generate_filename(self, url: str, prefix: str = "") -> str:
        """
        Generate a filename for an image URL.
        
        Args:
            url (str): Image URL.
            prefix (str, optional): Prefix for the filename. Defaults to "".
        
        Returns:
            str: Generated filename.
        """
        # Parse the URL
        parsed_url = urlparse(url)
        
        # Get the path component
        path = parsed_url.path
        
        # Extract the filename from the path
        filename = os.path.basename(path)
        
        # If the filename is empty or doesn't have an extension, generate a hash-based filename
        if not filename or "." not in filename:
            # Generate a hash of the URL
            hash_obj = hashlib.md5(url.encode())
            filename = hash_obj.hexdigest()[:10] + ".jpg"  # Default to .jpg
        
        # Add the prefix if provided
        if prefix:
            filename = f"{prefix}_{filename}"
        
        # Ensure the filename is not too long
        if len(filename) > 100:
            # Truncate the filename while preserving the extension
            name, ext = os.path.splitext(filename)
            filename = name[:90] + ext
        
        return filename
    
    async def download_image(self, url: str, prefix: str = "", subdirectory: str = "", verbose: bool = False) -> Optional[str]:
        """
        Download an image from a URL.
        
        Args:
            url (str): Image URL.
            prefix (str, optional): Prefix for the filename. Defaults to "".
            subdirectory (str, optional): Subdirectory within output_dir to save the image. 
                                        Defaults to "".
            verbose (bool, optional): Whether to log verbose output. Defaults to False.
        
        Returns:
            Optional[str]: Local path to the downloaded image, or None if download failed.
        """
        if not url:
            logger.warning("Empty URL provided for image download")
            return None
            
        # Initialize session and semaphore if needed
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            )
            
        if not self.semaphore:
            self.semaphore = asyncio.Semaphore(self.max_concurrency)
        
        # Generate a filename for the image
        filename = self._generate_filename(url, prefix)
        
        # Create the subdirectory if provided
        if subdirectory:
            output_dir = os.path.join(self.output_dir, subdirectory)
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = self.output_dir
        
        # Full path to save the image
        local_path = os.path.join(output_dir, filename)
        
        # Use the semaphore to limit concurrency
        async with self.semaphore:
            try:
                # Download the image
                async with self.session.get(url) as response:
                    if response.status != 200:
                        if verbose:
                            logger.warning(f"Failed to download image: {url} (status: {response.status})")
                        return None
                    
                    # Read the image data
                    image_data = await response.read()
                    
                    # Save the image
                    with open(local_path, "wb") as f:
                        f.write(image_data)
                    
                    if verbose:
                        logger.info(f"Downloaded image: {url} -> {local_path}")
                    
                    # Return the relative path
                    return os.path.join(subdirectory, filename) if subdirectory else filename
            
            except Exception as e:
                if verbose:
                    logger.error(f"Error downloading image: {url} - {str(e)}")
                return None
    
    async def download_images_batch(self, urls: List[str], prefix: str = "", subdirectory: str = "", verbose: bool = False) -> Dict[str, str]:
        """
        Download a batch of images in parallel.
        
        Args:
            urls (List[str]): List of image URLs to download.
            prefix (str, optional): Prefix for the filenames. Defaults to "".
            subdirectory (str, optional): Subdirectory within output_dir to save the images. 
                                        Defaults to "".
            verbose (bool, optional): Whether to log verbose output. Defaults to False.
        
        Returns:
            Dict[str, str]: Dictionary mapping URLs to local paths.
        """
        if not urls:
            return {}
        
        if verbose:
            logger.info(f"Downloading {len(urls)} images in parallel")
        
        # Download all images in parallel
        tasks = [
            self.download_image(url, prefix, subdirectory, verbose)
            for url in urls
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Create a dictionary mapping URLs to local paths
        url_to_path = {}
        for url, result in zip(urls, results):
            if result:
                url_to_path[url] = result
        
        if verbose:
            logger.info(f"Downloaded {len(url_to_path)} of {len(urls)} images successfully")
        
        return url_to_path
    
    async def process_html_images(self, html_content: str, base_url: str = "", prefix: str = "", verbose: bool = False) -> Tuple[str, Dict[str, str]]:
        """
        Process HTML content to download images and update URLs.
        
        Args:
            html_content (str): HTML content to process.
            base_url (str, optional): Base URL for resolving relative URLs. 
                                    Defaults to "".
            prefix (str, optional): Prefix for the filenames. Defaults to "".
            verbose (bool, optional): Whether to log verbose output. Defaults to False.
        
        Returns:
            Tuple[str, Dict[str, str]]: Tuple of (updated HTML content, URL to path mapping).
        """
        # Extract image URLs
        image_urls = await self.extract_image_urls(html_content, base_url)
        
        if verbose:
            logger.info(f"Found {len(image_urls)} images in HTML content")
        
        # Download the images
        url_to_path = await self.download_images_batch(
            list(image_urls),
            prefix=prefix,
            verbose=verbose
        )
        
        # Update the HTML content with local paths
        updated_html = html_content
        for url, path in url_to_path.items():
            # Replace the URL with the local path
            updated_html = updated_html.replace(f'src="{url}"', f'src="{path}"')
            updated_html = updated_html.replace(f"src='{url}'", f"src='{path}'")
        
        return updated_html, url_to_path


# Example usage
async def main():
    # Set up logging
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Create a batch image downloader
    async with BatchImageDownloader(output_dir="images", max_concurrency=5) as downloader:
        # Example HTML content
        html_content = """
        <html>
        <body>
            <img src="https://example.com/image1.jpg" alt="Image 1">
            <img src="https://example.com/image2.png" alt="Image 2">
            <img src="/relative/image3.jpg" alt="Image 3">
        </body>
        </html>
        """
        
        # Process the HTML content
        updated_html, url_to_path = await downloader.process_html_images(
            html_content=html_content,
            base_url="https://example.com",
            prefix="example",
            verbose=True
        )
        
        print(f"Updated HTML: {updated_html}")
        print(f"URL to path mapping: {url_to_path}")

if __name__ == "__main__":
    asyncio.run(main())
