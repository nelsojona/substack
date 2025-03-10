"""
Substack API Newsletter Module

This module provides functions for interacting with the Substack newsletter API.
"""

import requests
import logging
import time
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_newsletter_post_metadata(
    subdomain: str, 
    slugs_only: bool = False, 
    start_offset: int = 0, 
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get metadata for posts from a Substack newsletter.
    
    Args:
        subdomain (str): The Substack subdomain (e.g., 'mattstoller' for mattstoller.substack.com)
        slugs_only (bool, optional): If True, only return post slugs. Defaults to False.
        start_offset (int, optional): Offset for pagination. Defaults to 0.
        limit (int, optional): Maximum number of posts to return. Defaults to 10.
    
    Returns:
        List[Dict[str, Any]]: A list of post metadata objects.
    
    Raises:
        ValueError: If the subdomain is invalid.
        requests.exceptions.RequestException: If there's an issue with the request.
    """
    url = f"https://{subdomain}.substack.com/api/v1/archive"
    params = {
        "sort": "new",
        "offset": start_offset,
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        posts = response.json()
        
        if slugs_only:
            return [{"slug": post.get("slug")} for post in posts]
        
        return posts
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise ValueError(f"Invalid Substack subdomain: {subdomain}")
        raise
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching newsletter posts: {e}")
        raise

def get_post_contents(
    subdomain: str, 
    slug: str, 
    html_only: bool = False
) -> str:
    """
    Get the contents of a specific Substack post.
    
    Args:
        subdomain (str): The Substack subdomain (e.g., 'mattstoller' for mattstoller.substack.com)
        slug (str): The post slug (e.g., 'how-to-get-rich-sabotaging-nuclear')
        html_only (bool, optional): If True, only return the HTML content. Defaults to False.
    
    Returns:
        str: The post content as HTML.
    
    Raises:
        ValueError: If the subdomain or slug is invalid.
        requests.exceptions.RequestException: If there's an issue with the request.
    """
    url = f"https://{subdomain}.substack.com/api/v1/posts/{slug}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        post_data = response.json()
        
        if html_only:
            return post_data.get("body_html", "")
        
        return post_data
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise ValueError(f"Invalid post: {subdomain}/{slug}")
        raise
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching post contents: {e}")
        raise
