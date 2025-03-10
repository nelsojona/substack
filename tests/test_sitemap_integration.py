import unittest
import unittest.mock
import asyncio
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

# Import the module to test
from substack_direct_downloader import SubstackDirectDownloader

class TestSitemapIntegration(unittest.TestCase):
    """Test cases for the sitemap integration in SubstackDirectDownloader."""
    
    def setUp(self):
        """Set up test fixtures, if any."""
        # Create temp directory for testing
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Tear down test fixtures, if any."""
        # Remove temp directory
        shutil.rmtree(self.test_dir)
    
    @patch('substack_direct_downloader.ConnectionPool')
    @patch('substack_direct_downloader.CacheManager')
    @patch('substack_direct_downloader.DatabaseManager')
    @patch('substack_direct_downloader.IncrementalSyncManager')
    @patch('substack_direct_downloader.BatchImageDownloader')
    @patch('substack_direct_downloader.AsyncAdaptiveThrottler')
    def test_init_with_sitemap(self, mock_throttler, mock_image_downloader, mock_sync_manager, 
                  mock_db, mock_cache, mock_conn_pool):
        """Test constructor with sitemap settings."""
        # Configure mocks
        mock_conn_pool.return_value.max_connections = 5
        mock_conn_pool.return_value.max_connections_per_host = 2
        mock_conn_pool.return_value.keep_alive = 30
        
        # Mock the sync manager's get_sync method
        mock_sync_manager_instance = mock_sync_manager.return_value
        mock_sync_manager_instance.get_sync.return_value = MagicMock()
        
        # Create instance with default settings
        downloader = SubstackDirectDownloader(
            author="testauthor",
            output_dir=self.test_dir
        )
        
        # Check sitemap attribute is enabled by default
        self.assertTrue(downloader.use_sitemap, "use_sitemap should default to True")
        
        # Create instance with sitemap disabled
        downloader_no_sitemap = SubstackDirectDownloader(
            author="testauthor",
            output_dir=self.test_dir,
            use_sitemap=False
        )
        
        # Check sitemap attribute is disabled
        self.assertFalse(downloader_no_sitemap.use_sitemap, "use_sitemap should be False when set")
    
    @patch('aiohttp.ClientSession')
    @patch('substack_direct_downloader.SubstackDirectDownloader._fetch_url')
    @patch('substack_direct_downloader.ConnectionPool')
    @patch('substack_direct_downloader.CacheManager')
    @patch('substack_direct_downloader.DatabaseManager')
    @patch('substack_direct_downloader.IncrementalSyncManager')
    @patch('substack_direct_downloader.BatchImageDownloader')
    @patch('substack_direct_downloader.AsyncAdaptiveThrottler')
    def test_find_post_urls_with_sitemap(self, mock_throttler, mock_image_downloader, mock_sync_manager, 
                                     mock_db, mock_cache, mock_conn_pool, mock_fetch_url, mock_session):
        """Test the find_post_urls method with sitemap enabled."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Configure mocks
            mock_conn_pool.return_value.max_connections = 5
            mock_conn_pool.return_value.max_connections_per_host = 2
            mock_conn_pool.return_value.keep_alive = 30
            
            # Mock the sync manager's get_sync method
            mock_sync_manager_instance = mock_sync_manager.return_value
            mock_sync_manager_instance.get_sync.return_value = MagicMock()
            
            # Mock fetch_url to return sitemap XML
            mock_fetch_url.return_value = """<?xml version="1.0" encoding="UTF-8"?>
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
               <url>
                  <loc>https://testauthor.substack.com/p/sitemap-post-1</loc>
                  <lastmod>2023-01-01</lastmod>
               </url>
               <url>
                  <loc>https://testauthor.substack.com/p/sitemap-post-2</loc>
                  <lastmod>2023-01-02</lastmod>
               </url>
               <url>
                  <loc>https://testauthor.substack.com/p/sitemap-post-3</loc>
                  <lastmod>2023-01-03</lastmod>
               </url>
               <url>
                  <loc>https://testauthor.substack.com/about</loc>
                  <lastmod>2023-01-04</lastmod>
               </url>
            </urlset>
            """
            
            # Create and test the downloader
            async def run_test():
                # Create the downloader without using async context manager
                downloader = SubstackDirectDownloader(
                    author="testauthor",
                    output_dir=self.test_dir,
                    use_sitemap=True
                )
                
                # Configure connector outside of the __aenter__ method
                downloader.session = mock_session
                mock_session.close = AsyncMock()  # Mock session.close to be awaitable
                downloader.semaphore = asyncio.Semaphore(5)
                
                # Test find_post_urls
                urls = await downloader.find_post_urls()
                
                # Check that the expected URLs were found
                expected_urls = [
                    'https://testauthor.substack.com/p/sitemap-post-1',
                    'https://testauthor.substack.com/p/sitemap-post-2',
                    'https://testauthor.substack.com/p/sitemap-post-3'
                ]
                
                # Check that all expected URLs are in the result
                for url in expected_urls:
                    self.assertIn(url, urls)
                
                # Check that non-post URL was not included
                self.assertNotIn('https://testauthor.substack.com/about', urls)
            
            # Run the test
            loop.run_until_complete(run_test())
            
            # Check that the fetch_url method was called for the sitemap
            # We don't verify it was called only once, since it uses multiple methods
            mock_fetch_url.assert_any_call('https://testauthor.substack.com/sitemap.xml')
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    
    @patch('aiohttp.ClientSession')
    @patch('substack_direct_downloader.SubstackDirectDownloader._fetch_url')
    @patch('substack_direct_downloader.ConnectionPool')
    @patch('substack_direct_downloader.CacheManager')
    @patch('substack_direct_downloader.DatabaseManager')
    @patch('substack_direct_downloader.IncrementalSyncManager')
    @patch('substack_direct_downloader.BatchImageDownloader')
    @patch('substack_direct_downloader.AsyncAdaptiveThrottler')
    def test_sitemap_with_fallback(self, mock_throttler, mock_image_downloader, mock_sync_manager, 
                                mock_db, mock_cache, mock_conn_pool, mock_fetch_url, mock_session):
        """Test the sitemap with fallback to other methods when not enough posts found."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Configure mocks
            mock_conn_pool.return_value.max_connections = 5
            mock_conn_pool.return_value.max_connections_per_host = 2
            mock_conn_pool.return_value.keep_alive = 30
            
            # Mock the sync manager's get_sync method
            mock_sync_manager_instance = mock_sync_manager.return_value
            mock_sync_manager_instance.get_sync.return_value = MagicMock()
            
            # Mock fetch_url to return different responses for different URLs
            def fetch_url_side_effect(url):
                if 'sitemap.xml' in url:
                    # Only 2 posts in sitemap - not enough to skip other methods
                    return """<?xml version="1.0" encoding="UTF-8"?>
                    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                       <url>
                          <loc>https://testauthor.substack.com/p/sitemap-post-1</loc>
                          <lastmod>2023-01-01</lastmod>
                       </url>
                       <url>
                          <loc>https://testauthor.substack.com/p/sitemap-post-2</loc>
                          <lastmod>2023-01-02</lastmod>
                       </url>
                       <url>
                          <loc>https://testauthor.substack.com/about</loc>
                          <lastmod>2023-01-04</lastmod>
                       </url>
                    </urlset>
                    """
                elif url == 'https://testauthor.substack.com':
                    # Root page
                    return """
                    <html>
                    <body>
                        <a href="/p/root-post-1">Root Post 1</a>
                        <a href="/p/root-post-2">Root Post 2</a>
                    </body>
                    </html>
                    """
                elif 'archive' in url:
                    # Archive page
                    return """
                    <html>
                    <body>
                        <a href="/p/archive-post-1">Archive Post 1</a>
                        <a href="/p/archive-post-2">Archive Post 2</a>
                    </body>
                    </html>
                    """
                return None
            
            mock_fetch_url.side_effect = fetch_url_side_effect
            
            # Create and test the downloader
            async def run_test():
                # Create the downloader without using async context manager
                downloader = SubstackDirectDownloader(
                    author="testauthor",
                    output_dir=self.test_dir,
                    use_sitemap=True
                )
                
                # Configure connector outside of the __aenter__ method
                downloader.session = mock_session
                mock_session.close = AsyncMock()  # Mock session.close to be awaitable
                downloader.semaphore = asyncio.Semaphore(5)
                
                # Test find_post_urls
                urls = await downloader.find_post_urls()
                
                # Expected URLs from all methods
                expected_urls = [
                    'https://testauthor.substack.com/p/sitemap-post-1',
                    'https://testauthor.substack.com/p/sitemap-post-2',
                    'https://testauthor.substack.com/p/root-post-1',
                    'https://testauthor.substack.com/p/root-post-2',
                    'https://testauthor.substack.com/p/archive-post-1',
                    'https://testauthor.substack.com/p/archive-post-2'
                ]
                
                # Check that all expected URLs are in the result
                for url in expected_urls:
                    self.assertIn(url, urls)
                
                # Check that non-post URL was not included
                self.assertNotIn('https://testauthor.substack.com/about', urls)
            
            # Run the test
            loop.run_until_complete(run_test())
            
            # Check that fetch_url was called multiple times (sitemap + other methods)
            self.assertTrue(mock_fetch_url.call_count >= 3)
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    
    @patch('aiohttp.ClientSession')
    @patch('substack_direct_downloader.SubstackDirectDownloader._fetch_url')
    @patch('substack_direct_downloader.ConnectionPool')
    @patch('substack_direct_downloader.CacheManager')
    @patch('substack_direct_downloader.DatabaseManager')
    @patch('substack_direct_downloader.IncrementalSyncManager')
    @patch('substack_direct_downloader.BatchImageDownloader')
    @patch('substack_direct_downloader.AsyncAdaptiveThrottler')
    def test_sitemap_disabled(self, mock_throttler, mock_image_downloader, mock_sync_manager, 
                            mock_db, mock_cache, mock_conn_pool, mock_fetch_url, mock_session):
        """Test when sitemap is disabled."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Configure mocks
            mock_conn_pool.return_value.max_connections = 5
            mock_conn_pool.return_value.max_connections_per_host = 2
            mock_conn_pool.return_value.keep_alive = 30
            
            # Mock the sync manager's get_sync method
            mock_sync_manager_instance = mock_sync_manager.return_value
            mock_sync_manager_instance.get_sync.return_value = MagicMock()
            
            # Mock fetch_url to return different responses for different URLs
            def fetch_url_side_effect(url):
                if 'sitemap.xml' in url:
                    # This should never be called since sitemap is disabled
                    return None
                elif url == 'https://testauthor.substack.com':
                    # Root page
                    return """
                    <html>
                    <body>
                        <a href="/p/root-post-1">Root Post 1</a>
                        <a href="/p/root-post-2">Root Post 2</a>
                    </body>
                    </html>
                    """
                elif 'archive' in url:
                    # Archive page
                    return """
                    <html>
                    <body>
                        <a href="/p/archive-post-1">Archive Post 1</a>
                        <a href="/p/archive-post-2">Archive Post 2</a>
                    </body>
                    </html>
                    """
                return None
            
            mock_fetch_url.side_effect = fetch_url_side_effect
            
            # Create and test the downloader
            async def run_test():
                # Create the downloader without using async context manager
                downloader = SubstackDirectDownloader(
                    author="testauthor",
                    output_dir=self.test_dir,
                    use_sitemap=False  # Explicitly disable sitemap
                )
                
                # Configure connector outside of the __aenter__ method
                downloader.session = mock_session
                mock_session.close = AsyncMock()  # Mock session.close to be awaitable
                downloader.semaphore = asyncio.Semaphore(5)
                
                # Test find_post_urls
                urls = await downloader.find_post_urls()
                
                # Expected URLs from non-sitemap methods
                expected_urls = [
                    'https://testauthor.substack.com/p/root-post-1',
                    'https://testauthor.substack.com/p/root-post-2',
                    'https://testauthor.substack.com/p/archive-post-1',
                    'https://testauthor.substack.com/p/archive-post-2'
                ]
                
                # Check that all expected URLs are in the result
                for url in expected_urls:
                    self.assertIn(url, urls)
            
            # Run the test
            loop.run_until_complete(run_test())
            
            # Verify sitemap was not requested
            for call in mock_fetch_url.call_args_list:
                args, kwargs = call
                self.assertNotIn('sitemap.xml', args[0], "sitemap.xml should not be requested when disabled")
        finally:
            loop.close()
            asyncio.set_event_loop(None)

if __name__ == '__main__':
    unittest.main()