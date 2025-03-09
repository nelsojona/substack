#!/usr/bin/env python3
"""
Markdown Converter Module

This module handles the conversion of HTML content to Markdown format using the
markdownify library. It provides functionality to convert Substack post content
while preserving formatting, links, and images.
"""

import logging
import re
import os
import hashlib
import urllib.parse
from typing import Optional, List, Dict, Tuple, Set
import concurrent.futures
import requests
from bs4 import BeautifulSoup

from markdownify import markdownify as md

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarkdownConverter:
    """
    A class for converting HTML content to Markdown format.
    
    Attributes:
        heading_style (str): The style to use for headings ('ATX' or 'SETEXT').
        strip (list): HTML elements to strip from the output.
        convert (dict): Custom conversion functions for specific HTML elements.
        download_images (bool): Whether to download and embed images.
        image_dir (str): Directory to save downloaded images.
        image_base_url (str): Base URL for image references in Markdown.
        max_workers (int): Maximum number of concurrent image downloads.
        timeout (int): Timeout for image download requests in seconds.
        user_agent (str): User agent string for image download requests.
    """
    
    def __init__(self, heading_style: str = "ATX", strip_comments: bool = True,
                 download_images: bool = False, image_dir: str = "images",
                 image_base_url: str = "", max_workers: int = 4, timeout: int = 10):
        """
        Initialize the MarkdownConverter with specific settings.
        
        Args:
            heading_style (str, optional): The style to use for headings. Defaults to "ATX".
            strip_comments (bool, optional): Whether to strip HTML comments. Defaults to True.
            download_images (bool, optional): Whether to download and embed images. Defaults to False.
            image_dir (str, optional): Directory to save downloaded images. Defaults to "images".
            image_base_url (str, optional): Base URL for image references in Markdown. Defaults to "".
            max_workers (int, optional): Maximum number of concurrent image downloads. Defaults to 4.
            timeout (int, optional): Timeout for image download requests in seconds. Defaults to 10.
        """
        self.heading_style = heading_style
        self.strip = ["script", "style"]
        if strip_comments:
            self.strip.append("comment")
        
        # Image downloading settings
        self.download_images = download_images
        self.image_dir = image_dir
        self.image_base_url = image_base_url
        self.max_workers = max_workers
        self.timeout = timeout
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        
        # Cache for downloaded images
        self.downloaded_images = {}
    
    def _heading_callback(self, element, text):
        """
        Custom callback for heading conversion.
        
        Args:
            element: The HTML element being converted.
            text: The text content of the element.
        
        Returns:
            str: The Markdown heading.
        """
        # Get the heading level (h1 -> 1, h2 -> 2, etc.)
        level = int(element.name[1])
        
        # Create the appropriate number of # characters
        hashes = '#' * level
        
        # Return the Markdown heading
        return f"{hashes} {text}\n"
    
    def convert_html_to_markdown(self, html_content: str, verbose: bool = False,
                                 base_url: str = "", post_title: str = "") -> Optional[str]:
        """
        Convert HTML content to Markdown format.
        
        Args:
            html_content (str): The HTML content to convert.
            verbose (bool, optional): Enable verbose output. Defaults to False.
            base_url (str, optional): Base URL for resolving relative image URLs. Defaults to "".
            post_title (str, optional): Title of the post for image directory naming. Defaults to "".
        
        Returns:
            Optional[str]: The converted Markdown content, or None if conversion fails.
        """
        if not html_content:
            logger.warning("Empty HTML content provided for conversion")
            return None
        
        try:
            if verbose:
                logger.info("Converting HTML content to Markdown")
            
            # Create a sanitized post title for image directory naming
            sanitized_title = self._sanitize_filename(post_title) if post_title else ""
            
            # Download images if enabled
            image_map = {}
            if self.download_images:
                if verbose:
                    logger.info("Downloading and embedding images")
                
                # Extract image URLs from HTML
                image_urls = self._extract_image_urls(html_content, base_url)
                
                if verbose:
                    logger.info(f"Found {len(image_urls)} images to download")
                
                # Download images and get mapping of original URLs to local paths
                image_map = self._download_images(image_urls, sanitized_title, verbose)
                
                # Replace image URLs in HTML content
                html_content = self._replace_image_urls_in_html(html_content, image_map)
            
            # Convert HTML to Markdown with custom heading conversion
            markdown_content = md(
                html_content,
                heading_style=self.heading_style,
                strip=self.strip,
                heading_callback=self._heading_callback
            )
            
            # Post-process the Markdown content
            markdown_content = self._post_process_markdown(markdown_content)
            
            if verbose:
                logger.info("HTML conversion completed successfully")
            
            return markdown_content
        
        except Exception as e:
            logger.error(f"Error converting HTML to Markdown: {e}")
            return None
    
    def _extract_image_urls(self, html_content: str, base_url: str = "") -> Set[str]:
        """
        Extract image URLs from HTML content.
        
        Args:
            html_content (str): The HTML content to extract image URLs from.
            base_url (str, optional): Base URL for resolving relative image URLs. Defaults to "".
        
        Returns:
            Set[str]: A set of image URLs.
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
                            src = urllib.parse.urljoin(base_url, src)
                        else:
                            continue  # Skip relative URLs if no base URL is provided
                    
                    # Add to set of image URLs
                    image_urls.add(src)
        
        except Exception as e:
            logger.error(f"Error extracting image URLs: {e}")
        
        return image_urls
    
    def _download_images(self, image_urls: Set[str], post_title: str = "",
                         verbose: bool = False) -> Dict[str, str]:
        """
        Download images and return a mapping of original URLs to local paths.
        
        Args:
            image_urls (Set[str]): A set of image URLs to download.
            post_title (str, optional): Title of the post for image directory naming. Defaults to "".
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            Dict[str, str]: A mapping of original URLs to local paths.
        """
        image_map = {}
        
        if not image_urls:
            return image_map
        
        # Create image directory
        image_dir = self.image_dir
        if post_title:
            image_dir = os.path.join(self.image_dir, post_title)
        
        os.makedirs(image_dir, exist_ok=True)
        
        # Download images concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit download tasks
            future_to_url = {
                executor.submit(self._download_image, url, image_dir, verbose): url
                for url in image_urls
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    local_path = future.result()
                    if local_path:
                        image_map[url] = local_path
                except Exception as e:
                    if verbose:
                        logger.error(f"Error downloading image {url}: {e}")
        
        return image_map
    
    def _download_image(self, url: str, image_dir: str, verbose: bool = False) -> Optional[str]:
        """
        Download a single image and return its local path.
        
        Args:
            url (str): The URL of the image to download.
            image_dir (str): Directory to save the image.
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            Optional[str]: The local path of the downloaded image, or None if download fails.
        """
        # Check if image has already been downloaded
        if url in self.downloaded_images:
            return self.downloaded_images[url]
        
        try:
            # Generate a filename based on the URL
            filename = self._generate_image_filename(url)
            local_path = os.path.join(image_dir, filename)
            
            # Check if file already exists
            if os.path.exists(local_path):
                if verbose:
                    logger.info(f"Image already exists: {local_path}")
                self.downloaded_images[url] = local_path
                return local_path
            
            # Download the image
            headers = {'User-Agent': self.user_agent}
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Save the image
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            if verbose:
                logger.info(f"Downloaded image: {url} -> {local_path}")
            
            # Cache the downloaded image
            self.downloaded_images[url] = local_path
            
            return local_path
        
        except Exception as e:
            if verbose:
                logger.error(f"Error downloading image {url}: {e}")
            return None
    
    def _generate_image_filename(self, url: str) -> str:
        """
        Generate a filename for an image based on its URL.
        
        Args:
            url (str): The URL of the image.
        
        Returns:
            str: A filename for the image.
        """
        # Extract the original filename and extension
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        original_filename = os.path.basename(path)
        
        # Extract extension
        _, ext = os.path.splitext(original_filename)
        if not ext:
            ext = '.jpg'  # Default extension
        
        # Generate a hash of the URL
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Create a filename
        if original_filename and len(original_filename) <= 50:
            # Use original filename with hash
            filename = f"{url_hash}_{original_filename}"
        else:
            # Use hash only
            filename = f"{url_hash}{ext}"
        
        return filename
    
    def _replace_image_urls_in_html(self, html_content: str, image_map: Dict[str, str]) -> str:
        """
        Replace image URLs in HTML content with local paths.
        
        Args:
            html_content (str): The HTML content to process.
            image_map (Dict[str, str]): A mapping of original URLs to local paths.
        
        Returns:
            str: The HTML content with image URLs replaced.
        """
        if not image_map:
            return html_content
        
        try:
            # Parse HTML content
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all img tags
            img_tags = soup.find_all('img')
            
            # Replace image URLs
            for img in img_tags:
                src = img.get('src')
                if src and src in image_map:
                    local_path = image_map[src]
                    
                    # Convert local path to relative path or URL
                    if self.image_base_url:
                        # Use base URL
                        img['src'] = os.path.join(self.image_base_url, os.path.basename(local_path))
                    else:
                        # Use relative path
                        img['src'] = local_path
            
            return str(soup)
        
        except Exception as e:
            logger.error(f"Error replacing image URLs in HTML: {e}")
            return html_content
    
    def _post_process_markdown(self, markdown_content: str) -> str:
        """
        Perform post-processing on the converted Markdown content.
        
        Args:
            markdown_content (str): The raw converted Markdown content.
        
        Returns:
            str: The post-processed Markdown content.
        """
        # Remove leading whitespace from lines
        markdown_content = re.sub(r'^\s+', '', markdown_content, flags=re.MULTILINE)
        
        # Fix multiple consecutive blank lines (replace with at most 2)
        markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
        
        # Fix heading format (# to ## for h2, etc.)
        markdown_content = re.sub(r'#\n\n# ', '## ', markdown_content)
        markdown_content = re.sub(r'##\n\n# ', '### ', markdown_content)
        markdown_content = re.sub(r'###\n\n# ', '#### ', markdown_content)
        markdown_content = re.sub(r'####\n\n# ', '##### ', markdown_content)
        markdown_content = re.sub(r'#####\n\n# ', '###### ', markdown_content)
        
        # Fix spacing around headers
        markdown_content = re.sub(r'([^\n])(#{1,6} )', r'\1\n\n\2', markdown_content)
        markdown_content = re.sub(r'(#{1,6} .*?\n)([^\n])', r'\1\n\2', markdown_content)
        
        # Fix spacing around lists
        markdown_content = re.sub(r'([^\n])(\n[*-] )', r'\1\n\2', markdown_content)
        
        # Fix spacing around blockquotes
        markdown_content = re.sub(r'([^\n])(\n> )', r'\1\n\2', markdown_content)
        
        # Fix spacing after lists
        markdown_content = re.sub(r'(\n[*-] .*?\n)([^\n*-])', r'\1\n\2', markdown_content)
        
        # Fix image links (ensure they're on their own line)
        markdown_content = re.sub(r'([^\n])(\!\[)', r'\1\n\n\2', markdown_content)
        markdown_content = re.sub(r'(\]\])([^\n])', r'\1\n\n\2', markdown_content)
        
        return markdown_content
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a string to be used as a filename.
        
        Args:
            filename (str): The string to sanitize.
        
        Returns:
            str: The sanitized filename.
        """
        # Replace invalid filename characters with underscores
        sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename)
        
        # Replace multiple spaces with a single space
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        # Trim to a reasonable length
        if len(sanitized) > 50:
            sanitized = sanitized[:47] + '...'
        
        return sanitized.strip()


if __name__ == "__main__":
    # Example usage
    converter = MarkdownConverter(download_images=True)
    
    # Sample HTML content
    sample_html = """
    <h1>Sample Substack Post</h1>
    <p>This is a <strong>sample</strong> post with some <em>formatting</em>.</p>
    <h2>Section 1</h2>
    <p>Here's a list:</p>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
        <li>Item 3</li>
    </ul>
    <p>And here's a <a href="https://example.com">link</a>.</p>
    <blockquote>
        <p>This is a blockquote.</p>
    </blockquote>
    <p>And an image:</p>
    <figure>
        <img src="https://example.com/image.jpg" alt="Example Image">
        <figcaption>Image caption</figcaption>
    </figure>
    """
    
    # Convert HTML to Markdown
    markdown_result = converter.convert_html_to_markdown(
        sample_html,
        verbose=True,
        base_url="https://example.com",
        post_title="Sample Post"
    )
    
    # Print the result
    if markdown_result:
        print("\nConverted Markdown:\n")
        print(markdown_result)
    else:
        print("Conversion failed.")
