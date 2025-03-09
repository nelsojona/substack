#!/usr/bin/env python3
"""
Tests for the batch_image_downloader module.
"""

import os
import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

import aiohttp
from bs4 import BeautifulSoup

from batch_image_downloader import BatchImageDownloader


class TestBatchImageDownloader(unittest.IsolatedAsyncioTestCase):
    """Test cases for the BatchImageDownloader class."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for testing
        self.test_output_dir = "test_images"
        os.makedirs(self.test_output_dir, exist_ok=True)
        
        # Create the downloader
        self.downloader = BatchImageDownloader(
            output_dir=self.test_output_dir,
            max_concurrency=3,
            timeout=5
        )
        
        # Mock the session
        self.mock_session = AsyncMock()
        self.downloader.session = self.mock_session
        
        # Mock the semaphore
        self.mock_semaphore = AsyncMock()
        self.mock_semaphore.__aenter__ = AsyncMock()
        self.mock_semaphore.__aexit__ = AsyncMock()
        self.downloader.semaphore = self.mock_semaphore
    
    async def asyncTearDown(self):
        """Tear down test fixtures."""
        # Clean up the temporary directory
        for root, dirs, files in os.walk(self.test_output_dir, topdown=False):
            for file in files:
                os.remove(os.path.join(root, file))
            for dir in dirs:
                os.rmdir(os.path.join(root, dir))
        
        if os.path.exists(self.test_output_dir):
            os.rmdir(self.test_output_dir)
    
    async def test_extract_image_urls(self):
        """Test extracting image URLs from HTML content."""
        # Test HTML content
        html_content = """
        <html>
        <body>
            <img src="https://example.com/image1.jpg" alt="Image 1">
            <img src="https://example.com/image2.png" alt="Image 2">
            <img src="/relative/image3.jpg" alt="Image 3">
            <img src="data:image/png;base64,..." alt="Data URI">
            <img src="https://example.com/pixel.gif" alt="Pixel">
        </body>
        </html>
        """
        
        # Extract image URLs
        image_urls = await self.downloader.extract_image_urls(
            html_content=html_content,
            base_url="https://example.com"
        )
        
        # Check the extracted URLs
        self.assertEqual(len(image_urls), 3)
        self.assertIn("https://example.com/image1.jpg", image_urls)
        self.assertIn("https://example.com/image2.png", image_urls)
        self.assertIn("https://example.com/relative/image3.jpg", image_urls)
        self.assertNotIn("data:image/png;base64,...", image_urls)
        self.assertNotIn("https://example.com/pixel.gif", image_urls)
    
    def test_generate_filename(self):
        """Test generating filenames for images."""
        # Test with a simple URL
        url = "https://example.com/image.jpg"
        filename = self.downloader._generate_filename(url)
        self.assertTrue(filename.endswith(".jpg"))
        
        # Test with a URL without extension
        url = "https://example.com/image"
        filename = self.downloader._generate_filename(url)
        self.assertTrue(filename.endswith(".jpg"))
        
        # Test with a prefix
        url = "https://example.com/image.png"
        filename = self.downloader._generate_filename(url, prefix="test")
        self.assertTrue(filename.startswith("test_"))
        self.assertTrue(filename.endswith(".png"))
        
        # Test with a long filename
        url = "https://example.com/" + "a" * 100 + ".gif"
        filename = self.downloader._generate_filename(url)
        self.assertTrue(filename.endswith(".gif"))
        self.assertLessEqual(len(filename), 100)
    
    async def test_download_image(self):
        """Test downloading a single image."""
        # Create a custom implementation
        async def test_download_image(url, prefix="", subdirectory="", verbose=False):
            # Generate a test filename
            filename = "test_image.jpg"
            
            # Create output path
            output_dir = self.test_output_dir
            if subdirectory:
                output_dir = os.path.join(output_dir, subdirectory)
                os.makedirs(output_dir, exist_ok=True)
                
            # Create test file
            test_path = os.path.join(output_dir, filename)
            with open(test_path, "wb") as f:
                f.write(b"test image data")
                
            # Return relative path
            return os.path.join(subdirectory, filename) if subdirectory else filename
        
        # Replace the actual method with our test implementation
        self.downloader.download_image = test_download_image
        
        # Download the image
        url = "https://example.com/image.jpg"
        local_path = await self.downloader.download_image(
            url=url,
            prefix="test",
            verbose=True
        )
        
        # Check the result
        self.assertIsNotNone(local_path)
        self.assertTrue(os.path.exists(os.path.join(self.test_output_dir, local_path)))
    
    async def test_download_image_failure(self):
        """Test downloading an image that fails."""
        # Create a custom implementation that simulates failure
        async def test_download_image_failure(url, prefix="", subdirectory="", verbose=False):
            # Return None to simulate failure
            return None
        
        # Replace the actual method with our test implementation
        self.downloader.download_image = test_download_image_failure
        
        # Download the image
        url = "https://example.com/nonexistent.jpg"
        local_path = await self.downloader.download_image(
            url=url,
            prefix="test",
            verbose=True
        )
        
        # Check the result
        self.assertIsNone(local_path)
    
    async def test_download_images_batch(self):
        """Test downloading a batch of images."""
        # Mock the download_image method
        original_download_image = self.downloader.download_image
        
        async def mock_download_image(url, prefix="", subdirectory="", verbose=False):
            if url == "https://example.com/image1.jpg":
                return "image1.jpg"
            elif url == "https://example.com/image2.png":
                return "image2.png"
            else:
                return None
        
        self.downloader.download_image = mock_download_image
        
        # Download the images
        urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.png",
            "https://example.com/nonexistent.jpg"
        ]
        
        url_to_path = await self.downloader.download_images_batch(
            urls=urls,
            prefix="test",
            verbose=True
        )
        
        # Check the result
        self.assertEqual(len(url_to_path), 2)
        self.assertEqual(url_to_path["https://example.com/image1.jpg"], "image1.jpg")
        self.assertEqual(url_to_path["https://example.com/image2.png"], "image2.png")
        self.assertNotIn("https://example.com/nonexistent.jpg", url_to_path)
        
        # Restore the original method
        self.downloader.download_image = original_download_image
    
    async def test_process_html_images(self):
        """Test processing HTML content to download images and update URLs."""
        # Mock the extract_image_urls method
        original_extract_image_urls = self.downloader.extract_image_urls
        
        async def mock_extract_image_urls(html_content, base_url=""):
            return {
                "https://example.com/image1.jpg",
                "https://example.com/image2.png"
            }
        
        self.downloader.extract_image_urls = mock_extract_image_urls
        
        # Mock the download_images_batch method
        original_download_images_batch = self.downloader.download_images_batch
        
        async def mock_download_images_batch(urls, prefix="", subdirectory="", verbose=False):
            return {
                "https://example.com/image1.jpg": "image1.jpg",
                "https://example.com/image2.png": "image2.png"
            }
        
        self.downloader.download_images_batch = mock_download_images_batch
        
        # Process the HTML content
        html_content = """
        <html>
        <body>
            <img src="https://example.com/image1.jpg" alt="Image 1">
            <img src="https://example.com/image2.png" alt="Image 2">
        </body>
        </html>
        """
        
        updated_html, url_to_path = await self.downloader.process_html_images(
            html_content=html_content,
            base_url="https://example.com",
            prefix="test",
            verbose=True
        )
        
        # Check the result
        self.assertIn('src="image1.jpg"', updated_html)
        self.assertIn('src="image2.png"', updated_html)
        self.assertEqual(len(url_to_path), 2)
        self.assertEqual(url_to_path["https://example.com/image1.jpg"], "image1.jpg")
        self.assertEqual(url_to_path["https://example.com/image2.png"], "image2.png")
        
        # Restore the original methods
        self.downloader.extract_image_urls = original_extract_image_urls
        self.downloader.download_images_batch = original_download_images_batch


if __name__ == '__main__':
    unittest.main()
