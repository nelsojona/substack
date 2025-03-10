#!/usr/bin/env python3
"""
Substack Fetcher Module

This module handles fetching posts from the Substack API using the substack_api wrapper.
It provides functionality to retrieve all posts for a specified author, with support for
pagination, error handling, and retries.
"""

import time
import logging
import os
import json
from typing import List, Dict, Any, Optional, Union, Tuple
from urllib.parse import urlparse
import http.cookiejar

import requests
# Import functions from substack_api modules
from src.substack_api.newsletter import get_newsletter_post_metadata, get_post_contents

# Import environment variable loader
from src.utils.env_loader import load_env_vars, get_oxylabs_config

# Define a Substack class for backward compatibility with tests
class Substack:
    """
    A class for interacting with the Substack API.
    This is a wrapper around the Newsletter class for backward compatibility.
    """
    
    def __init__(self):
        """
        Initialize a Substack instance.
        """
        pass
    
    def get_posts(self, author, offset=0, limit=None):
        """
        Get posts for a specified author.
        
        Args:
            author (str): The Substack author identifier.
            offset (int, optional): Offset for pagination. Defaults to 0.
            limit (int, optional): Maximum number of posts to return. Defaults to None.
        
        Returns:
            List[Dict[str, Any]]: A list of post objects.
        """
        # Fetch posts from the Substack API
        return get_newsletter_post_metadata(author, slugs_only=False, start_offset=offset)


# Define a simple Post class to replace the missing substack_api.post.Post
class Post:
    """
    A simple class to represent a Substack post.
    """
    
    def __init__(self, url: str):
        """
        Initialize a Post object.
        
        Args:
            url (str): The URL of the post.
        """
        self.url = url
        self._metadata = None
        self._content = None
    
    def __str__(self) -> str:
        return f"Post: {self.url}"
    
    def __repr__(self) -> str:
        return f"Post(url={self.url})"
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get the metadata of the post.
        
        Returns:
            Dict[str, Any]: The metadata of the post.
        """
        if self._metadata is None:
            # Extract the subdomain and slug from the URL
            parts = self.url.split('/')
            if len(parts) < 5:
                raise ValueError(f"Invalid post URL: {self.url}")
            
            subdomain = parts[2].split('.')[0]
            slug = parts[4]
            
            # Get the post metadata
            posts = get_newsletter_post_metadata(subdomain, slugs_only=False)
            for post in posts:
                if post.get('slug') == slug:
                    self._metadata = post
                    break
            
            if self._metadata is None:
                raise ValueError(f"Post not found: {self.url}")
        
        return self._metadata
    
    def get_content(self) -> str:
        """
        Get the HTML content of the post.
        
        Returns:
            str: The HTML content of the post.
        """
        if self._content is None:
            # Extract the subdomain and slug from the URL
            parts = self.url.split('/')
            if len(parts) < 5:
                raise ValueError(f"Invalid post URL: {self.url}")
            
            subdomain = parts[2].split('.')[0]
            slug = parts[4]
            
            # Get the post content
            self._content = get_post_contents(subdomain, slug, html_only=True)
        
        return self._content

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SubstackFetcher:
    """
    A class for fetching posts from Substack using the substack_api wrapper.
    
    Attributes:
        client (Substack): The Substack API client.
        max_retries (int): Maximum number of retry attempts for API requests.
        retry_delay (int): Delay in seconds between retry attempts.
        posts_cache (Dict[str, Post]): Cache of Post objects by URL.
        session (requests.Session): Session for making authenticated requests.
        is_authenticated (bool): Whether the fetcher is authenticated.
        auth_cookies (Dict[str, str]): Authentication cookies.
        auth_token (str): Authentication token.
        cookies_file (str): Path to the cookies file.
    """
    
    def __init__(self, max_retries: int = 3, retry_delay: int = 2, use_proxy: bool = False):
        """
        Initialize the SubstackFetcher with a Substack API client.
        
        Args:
            max_retries (int, optional): Maximum number of retry attempts. Defaults to 3.
            retry_delay (int, optional): Delay in seconds between retry attempts. Defaults to 2.
            use_proxy (bool, optional): Whether to use the Oxylabs proxy. Defaults to False.
        """
        self.client = Substack()  # For backward compatibility with tests
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.posts_cache = {}  # Cache for Post objects
        
        # Authentication attributes
        self.session = requests.Session()
        self.is_authenticated = False
        self.auth_cookies = {}
        self.auth_token = ""
        self.cookies_file = ""
        
        # Load environment variables
        load_env_vars()
        
        # Set up proxy if requested
        self.use_proxy = use_proxy
        if use_proxy:
            self._setup_proxy()
    
    def _setup_proxy(self):
        """
        Set up the Oxylabs proxy configuration.
        """
        # Get Oxylabs configuration from environment variables
        oxylabs_config = get_oxylabs_config()
        
        # Check if all required configuration is present
        if not oxylabs_config['username'] or not oxylabs_config['password']:
            logger.warning("Oxylabs proxy configuration is incomplete. Proxy will not be used.")
            return
        
        # Construct proxy URL
        proxy_url = f"http://{oxylabs_config['username']}:{oxylabs_config['password']}@customer-{oxylabs_config['username']}.oxylabs.io:10000"
        
        # Set up proxy for the session
        self.session.proxies = {
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
        
        if oxylabs_config['session_id']:
            headers['X-Oxylabs-Session-ID'] = oxylabs_config['session_id']
        
        if oxylabs_config['session_time'] is not None:
            headers['X-Oxylabs-Session-Time'] = str(oxylabs_config['session_time'])
        
        # Update session headers
        self.session.headers.update(headers)
        
        logger.info("Oxylabs proxy configured successfully")
    
    def authenticate(self, email: str = "", password: str = "", token: str = "", 
                     cookies_file: str = "", cookies: Dict[str, str] = None) -> bool:
        """
        Authenticate with Substack to access private content.
        
        Args:
            email (str, optional): Substack account email. Defaults to "".
            password (str, optional): Substack account password. Defaults to "".
            token (str, optional): Substack authentication token. Defaults to "".
            cookies_file (str, optional): Path to a file containing cookies. Defaults to "".
            cookies (Dict[str, str], optional): Dictionary of cookies. Defaults to None.
        
        Returns:
            bool: True if authentication was successful, False otherwise.
        """
        # Reset authentication state
        self.is_authenticated = False
        self.auth_cookies = {}
        self.auth_token = ""
        self.cookies_file = ""
        
        # Try to authenticate with the provided credentials
        if token:
            # Authenticate with token
            self.auth_token = token
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.is_authenticated = self._verify_authentication()
        
        elif cookies:
            # Authenticate with cookies dictionary
            self.auth_cookies = cookies
            for name, value in cookies.items():
                self.session.cookies.set(name, value)
            self.is_authenticated = self._verify_authentication()
        
        elif cookies_file:
            # Authenticate with cookies file
            if os.path.exists(cookies_file):
                self.cookies_file = cookies_file
                try:
                    # Load cookies from file
                    cookie_jar = http.cookiejar.MozillaCookieJar(cookies_file)
                    cookie_jar.load()
                    self.session.cookies = cookie_jar
                    self.is_authenticated = self._verify_authentication()
                except Exception as e:
                    logger.error(f"Error loading cookies from file: {e}")
                    return False
            else:
                logger.error(f"Cookies file not found: {cookies_file}")
                return False
        
        elif email and password:
            # Authenticate with email and password
            # Note: This is a simplified implementation and may not work with Substack's actual login flow
            # In a real implementation, you would need to handle CSRF tokens, redirects, etc.
            login_url = "https://substack.com/api/v1/login"
            login_data = {
                "email": email,
                "password": password,
                "redirect": "/"
            }
            
            try:
                response = self.session.post(login_url, json=login_data)
                if response.status_code == 200:
                    # Extract authentication token or cookies
                    if "token" in response.json():
                        self.auth_token = response.json()["token"]
                        self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                    
                    # Store cookies
                    self.auth_cookies = dict(response.cookies)
                    
                    self.is_authenticated = self._verify_authentication()
                else:
                    logger.error(f"Login failed with status code: {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Error during login: {e}")
                return False
        
        return self.is_authenticated
    
    def save_cookies(self, cookies_file: str) -> bool:
        """
        Save the current session cookies to a file.
        
        Args:
            cookies_file (str): Path to the file where cookies will be saved.
        
        Returns:
            bool: True if cookies were saved successfully, False otherwise.
        """
        if not self.is_authenticated:
            logger.warning("Not authenticated, no cookies to save")
            return False
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(cookies_file)), exist_ok=True)
            
            # Save cookies to file
            cookie_jar = http.cookiejar.MozillaCookieJar(cookies_file)
            for cookie in self.session.cookies:
                cookie_jar.set_cookie(cookie)
            cookie_jar.save()
            
            self.cookies_file = cookies_file
            return True
        except Exception as e:
            logger.error(f"Error saving cookies to file: {e}")
            return False
    
    def _verify_authentication(self) -> bool:
        """
        Verify that the authentication credentials are valid.
        
        Returns:
            bool: True if authentication is valid, False otherwise.
        """
        # Try to access a private endpoint to verify authentication
        try:
            # This is a simplified check and may need to be adjusted based on Substack's API
            response = self.session.get("https://substack.com/api/v1/me")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error verifying authentication: {e}")
            return False
    
    def fetch_posts(self, author: str, limit: Optional[int] = None, verbose: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all posts for a specified author.
        
        Args:
            author (str): The Substack author identifier (username or subdomain).
            limit (int, optional): Maximum number of posts to fetch. Defaults to None (all posts).
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            List[Dict[str, Any]]: A list of post objects.
        
        Raises:
            ValueError: If the author identifier is invalid.
            ConnectionError: If there's an issue connecting to the Substack API.
        """
        if verbose:
            logger.info(f"Fetching posts for author: {author}")
        
        all_posts = []
        offset = 0
        
        try:
            while True:
                # Attempt to fetch posts with retries
                posts = self._fetch_with_retry(author, offset, verbose)
                
                if not posts:
                    break
                
                all_posts.extend(posts)
                
                if verbose:
                    logger.info(f"Fetched {len(posts)} posts (total: {len(all_posts)})")
                
                # Check if we've reached the limit
                if limit and len(all_posts) >= limit:
                    all_posts = all_posts[:limit]
                    break
                
                # Update offset for pagination
                offset += len(posts)
                
                # Check if we've fetched all posts
                if len(posts) < 10:  # Substack API typically returns 10 posts per page
                    break
            
            if verbose:
                logger.info(f"Successfully fetched {len(all_posts)} posts for {author}")
            
            return all_posts
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to Substack API: {e}")
            raise ConnectionError(f"Failed to connect to Substack API: {e}")
        
        except Exception as e:
            logger.error(f"Unexpected error fetching posts: {e}")
            raise
    
    def fetch_post_objects(self, author: str, limit: Optional[int] = None, verbose: bool = False) -> List[Post]:
        """
        Fetch all posts for a specified author and return Post objects.
        
        Args:
            author (str): The Substack author identifier (username or subdomain).
            limit (int, optional): Maximum number of posts to fetch. Defaults to None (all posts).
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            List[Post]: A list of Post objects.
        
        Raises:
            ValueError: If the author identifier is invalid.
            ConnectionError: If there's an issue connecting to the Substack API.
        """
        # First fetch the post data
        post_data = self.fetch_posts(author, limit, verbose)
        
        # Convert to Post objects
        post_objects = []
        for post in post_data:
            # Get the post URL
            url = post.get('canonical_url')
            if not url:
                if verbose:
                    logger.warning(f"No URL found for post: {post.get('title', 'Unknown')}")
                continue
            
            # Create or get from cache a Post object
            post_obj = self.get_post_by_url(url, verbose)
            if post_obj:
                post_objects.append(post_obj)
        
        return post_objects
    
    def get_post_by_url(self, url: str, verbose: bool = False) -> Optional[Post]:
        """
        Get a Post object for a specific URL.
        
        Args:
            url (str): The URL of the post.
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            Optional[Post]: The Post object, or None if the post could not be retrieved.
        """
        # Check if the post is already in the cache
        if url in self.posts_cache:
            return self.posts_cache[url]
        
        # Create a new Post object
        try:
            post = self._create_post_with_retry(url, verbose)
            if post:
                # Add to cache
                self.posts_cache[url] = post
                return post
            return None
        except Exception as e:
            if verbose:
                logger.error(f"Error creating Post object for URL {url}: {e}")
            return None
    
    def get_post_by_slug(self, author: str, slug: str, verbose: bool = False) -> Optional[Post]:
        """
        Get a Post object for a specific author and slug.
        
        Args:
            author (str): The Substack author identifier (username or subdomain).
            slug (str): The slug of the post.
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            Optional[Post]: The Post object, or None if the post could not be retrieved.
        """
        # Construct the URL
        url = f"https://{author}.substack.com/p/{slug}"
        return self.get_post_by_url(url, verbose)
    
    def get_post_content(self, post: Union[Post, str], verbose: bool = False) -> Optional[str]:
        """
        Get the HTML content of a post.
        
        Args:
            post (Union[Post, str]): The Post object or URL of the post.
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            Optional[str]: The HTML content of the post, or None if the content could not be retrieved.
        """
        # If post is a string (URL), get the Post object
        if isinstance(post, str):
            post_obj = self.get_post_by_url(post, verbose)
            if not post_obj:
                return None
        else:
            post_obj = post
        
        # Get the content
        try:
            return self._get_post_content_with_retry(post_obj, verbose)
        except Exception as e:
            if verbose:
                logger.error(f"Error getting content for post {post_obj}: {e}")
            return None
    
    def get_post_metadata(self, post: Union[Post, str], verbose: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get the metadata of a post.
        
        Args:
            post (Union[Post, str]): The Post object or URL of the post.
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            Optional[Dict[str, Any]]: The metadata of the post, or None if the metadata could not be retrieved.
        """
        # If post is a string (URL), get the Post object
        if isinstance(post, str):
            post_obj = self.get_post_by_url(post, verbose)
            if not post_obj:
                return None
        else:
            post_obj = post
        
        # Get the metadata
        try:
            return self._get_post_metadata_with_retry(post_obj, verbose)
        except Exception as e:
            if verbose:
                logger.error(f"Error getting metadata for post {post_obj}: {e}")
            return None
    
    def fetch_private_post(self, url: str, verbose: bool = False) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetch a private post using authenticated session.
        
        Args:
            url (str): The URL of the private post.
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            Tuple[Optional[Dict[str, Any]], Optional[str]]: A tuple containing the post metadata and content,
                or (None, None) if the post could not be retrieved.
        """
        if not self.is_authenticated:
            logger.error("Authentication required to access private posts")
            return None, None
        
        if verbose:
            logger.info(f"Fetching private post: {url}")
        
        try:
            # Extract post ID from URL
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.strip('/').split('/')
            if len(path_parts) < 2 or path_parts[0] != 'p':
                logger.error(f"Invalid post URL format: {url}")
                return None, None
            
            post_slug = path_parts[1]
            hostname = parsed_url.netloc
            
            # Fetch post data
            api_url = f"https://{hostname}/api/v1/posts/{post_slug}"
            response = self.session.get(api_url)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch private post: {response.status_code}")
                return None, None
            
            post_data = response.json()
            
            # Fetch post content
            content_url = f"https://{hostname}/api/v1/posts/{post_slug}/content"
            content_response = self.session.get(content_url)
            
            if content_response.status_code != 200:
                logger.error(f"Failed to fetch private post content: {content_response.status_code}")
                return post_data, None
            
            post_content = content_response.json().get('body_html', '')
            
            return post_data, post_content
        
        except Exception as e:
            logger.error(f"Error fetching private post: {e}")
            return None, None
    
    def _fetch_with_retry(self, author: str, offset: int = 0, verbose: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch posts with retry logic.
        
        Args:
            author (str): The Substack author identifier.
            offset (int, optional): Offset for pagination. Defaults to 0.
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            List[Dict[str, Any]]: A list of post objects.
        
        Raises:
            ValueError: If the author identifier is invalid.
            ConnectionError: If all retry attempts fail.
        """
        retries = 0
        last_exception = None
        
        while retries <= self.max_retries:
            try:
                # Use the client's get_posts method
                posts = self.client.get_posts(author, offset=offset)
                return posts
            
            except requests.exceptions.HTTPError as e:
                last_exception = e
                if e.response.status_code == 404:
                    raise ValueError(f"Invalid author identifier: {author}")
                
                if e.response.status_code == 429:
                    # Rate limiting - wait longer before retrying
                    retry_delay = self.retry_delay * (retries + 1) * 2
                    if verbose:
                        logger.warning(f"Rate limited. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    # Other HTTP errors
                    if retries < self.max_retries:
                        if verbose:
                            logger.warning(f"HTTP error: {e}. Retrying ({retries+1}/{self.max_retries})...")
                        time.sleep(self.retry_delay)
                    else:
                        logger.error(f"Failed after {self.max_retries} retries: {e}")
                        raise ConnectionError(f"Failed to fetch posts after {self.max_retries} retries: {e}")
            
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                last_exception = e
                # Network-related errors
                if retries < self.max_retries:
                    if verbose:
                        logger.warning(f"Connection error: {e}. Retrying ({retries+1}/{self.max_retries})...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed after {self.max_retries} retries: {e}")
                    raise ConnectionError(f"Failed to fetch posts after {self.max_retries} retries: {e}")
            
            except Exception as e:
                last_exception = e
                if verbose:
                    logger.error(f"Unexpected error: {e}")
                if retries < self.max_retries:
                    time.sleep(self.retry_delay)
                else:
                    raise
            
            retries += 1
        
        # If we get here, we've exceeded the max retries
        if last_exception:
            raise ConnectionError(f"Failed to fetch posts after {self.max_retries} retries: {last_exception}")
        return []
    
    def _create_post_with_retry(self, url: str, verbose: bool = False) -> Optional[Post]:
        """
        Create a Post object with retry logic.
        
        Args:
            url (str): The URL of the post.
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            Optional[Post]: The Post object, or None if the post could not be created.
        """
        retries = 0
        
        while retries <= self.max_retries:
            try:
                # Create a Post object
                post = Post(url)
                return post
            
            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 404:
                    if verbose:
                        logger.warning(f"Post not found: {url}")
                    return None
                
                if e.response and e.response.status_code == 429:
                    # Rate limiting - wait longer before retrying
                    retry_delay = self.retry_delay * (retries + 1) * 2
                    if verbose:
                        logger.warning(f"Rate limited. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    # Other HTTP errors
                    if retries < self.max_retries:
                        if verbose:
                            logger.warning(f"HTTP error: {e}. Retrying ({retries+1}/{self.max_retries})...")
                        time.sleep(self.retry_delay)
                    else:
                        if verbose:
                            logger.error(f"Failed to create Post after {self.max_retries} retries: {e}")
                        return None
            
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # Network-related errors
                if retries < self.max_retries:
                    if verbose:
                        logger.warning(f"Connection error: {e}. Retrying ({retries+1}/{self.max_retries})...")
                    time.sleep(self.retry_delay)
                else:
                    if verbose:
                        logger.error(f"Failed to create Post after {self.max_retries} retries: {e}")
                    return None
            
            except Exception as e:
                if verbose:
                    logger.error(f"Unexpected error creating Post: {e}")
                return None
            
            retries += 1
        
        return None
    
    def _get_post_content_with_retry(self, post: Post, verbose: bool = False) -> Optional[str]:
        """
        Get post content with retry logic.
        
        Args:
            post (Post): The Post object.
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            Optional[str]: The HTML content of the post, or None if the content could not be retrieved.
        """
        retries = 0
        
        while retries <= self.max_retries:
            try:
                # Get the content
                content = post.get_content()
                return content
            
            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    # Rate limiting - wait longer before retrying
                    retry_delay = self.retry_delay * (retries + 1) * 2
                    if verbose:
                        logger.warning(f"Rate limited. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    # Other HTTP errors
                    if retries < self.max_retries:
                        if verbose:
                            logger.warning(f"HTTP error: {e}. Retrying ({retries+1}/{self.max_retries})...")
                        time.sleep(self.retry_delay)
                    else:
                        if verbose:
                            logger.error(f"Failed to get content after {self.max_retries} retries: {e}")
                        return None
            
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # Network-related errors
                if retries < self.max_retries:
                    if verbose:
                        logger.warning(f"Connection error: {e}. Retrying ({retries+1}/{self.max_retries})...")
                    time.sleep(self.retry_delay)
                else:
                    if verbose:
                        logger.error(f"Failed to get content after {self.max_retries} retries: {e}")
                    return None
            
            except Exception as e:
                if verbose:
                    logger.error(f"Unexpected error getting content: {e}")
                return None
            
            retries += 1
        
        return None
    
    def _get_post_metadata_with_retry(self, post: Post, verbose: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get post metadata with retry logic.
        
        Args:
            post (Post): The Post object.
            verbose (bool, optional): Enable verbose output. Defaults to False.
        
        Returns:
            Optional[Dict[str, Any]]: The metadata of the post, or None if the metadata could not be retrieved.
        """
        retries = 0
        
        while retries <= self.max_retries:
            try:
                # Get the metadata
                metadata = post.get_metadata()
                return metadata
            
            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    # Rate limiting - wait longer before retrying
                    retry_delay = self.retry_delay * (retries + 1) * 2
                    if verbose:
                        logger.warning(f"Rate limited. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    # Other HTTP errors
                    if retries < self.max_retries:
                        if verbose:
                            logger.warning(f"HTTP error: {e}. Retrying ({retries+1}/{self.max_retries})...")
                        time.sleep(self.retry_delay)
                    else:
                        if verbose:
                            logger.error(f"Failed to get metadata after {self.max_retries} retries: {e}")
                        return None
            
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # Network-related errors
                if retries < self.max_retries:
                    if verbose:
                        logger.warning(f"Connection error: {e}. Retrying ({retries+1}/{self.max_retries})...")
                    time.sleep(self.retry_delay)
                else:
                    if verbose:
                        logger.error(f"Failed to get metadata after {self.max_retries} retries: {e}")
                    return None
            
            except Exception as e:
                if verbose:
                    logger.error(f"Unexpected error getting metadata: {e}")
                return None
            
            retries += 1
        
        return None


if __name__ == "__main__":
    # Example usage
    fetcher = SubstackFetcher()
    try:
        # Example 1: Fetch posts as dictionaries
        posts = fetcher.fetch_posts("mattstoller", limit=5, verbose=True)
        print(f"Fetched {len(posts)} posts")
        for post in posts:
            print(f"- {post.get('title')}")
        
        # Example 2: Fetch posts as Post objects
        post_objects = fetcher.fetch_post_objects("mattstoller", limit=2, verbose=True)
        print(f"\nFetched {len(post_objects)} post objects")
        for post_obj in post_objects:
            metadata = fetcher.get_post_metadata(post_obj, verbose=True)
            if metadata:
                print(f"- {metadata.get('title')}")
                content = fetcher.get_post_content(post_obj, verbose=True)
                if content:
                    print(f"  Content length: {len(content)} characters")
        
        # Example 3: Get a post by URL
        post_url = "https://mattstoller.substack.com/p/how-to-get-rich-sabotaging-nuclear"
        post_obj = fetcher.get_post_by_url(post_url, verbose=True)
        if post_obj:
            metadata = fetcher.get_post_metadata(post_obj, verbose=True)
            if metadata:
                print(f"\nPost by URL: {metadata.get('title')}")
        
        # Example 4: Get a post by slug
        post_obj = fetcher.get_post_by_slug("mattstoller", "how-to-get-rich-sabotaging-nuclear", verbose=True)
        if post_obj:
            metadata = fetcher.get_post_metadata(post_obj, verbose=True)
            if metadata:
                print(f"\nPost by slug: {metadata.get('title')}")
        
        # Example 5: Authenticate and fetch private content
        # Note: This is just an example and would require valid credentials
        # fetcher.authenticate(email="your-email@example.com", password="your-password", verbose=True)
        # private_post_url = "https://example.substack.com/p/private-post-slug"
        # post_data, post_content = fetcher.fetch_private_post(private_post_url, verbose=True)
        # if post_data and post_content:
        #     print(f"\nPrivate post: {post_data.get('title')}")
        #     print(f"  Content length: {len(post_content)} characters")
    
    except Exception as e:
        print(f"Error: {e}")
