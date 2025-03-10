#!/usr/bin/env python3
"""
Substack API Utilities Module

This module provides utility functions for working with Substack API objects.
It simplifies common operations and provides helper functions for extracting
and transforming data from Substack API responses.
"""

import re
import json
import logging
import datetime
from typing import Dict, List, Any, Optional, Union, Tuple
from urllib.parse import urlparse, urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_author_from_url(url: str) -> Optional[str]:
    """
    Extract the author identifier from a Substack URL.
    
    Args:
        url (str): The Substack URL.
    
    Returns:
        Optional[str]: The author identifier, or None if it couldn't be extracted.
    
    Examples:
        >>> extract_author_from_url("https://mattstoller.substack.com/p/how-to-get-rich")
        'mattstoller'
        >>> extract_author_from_url("https://mattstoller.substack.com/")
        'mattstoller'
    """
    try:
        parsed_url = urlparse(url)
        if 'substack.com' not in parsed_url.netloc:
            return None
        
        # Extract the subdomain (author)
        subdomain = parsed_url.netloc.split('.')[0]
        return subdomain
    except Exception as e:
        logger.error(f"Error extracting author from URL {url}: {e}")
        return None


def extract_slug_from_url(url: str) -> Optional[str]:
    """
    Extract the post slug from a Substack URL.
    
    Args:
        url (str): The Substack URL.
    
    Returns:
        Optional[str]: The post slug, or None if it couldn't be extracted.
    
    Examples:
        >>> extract_slug_from_url("https://mattstoller.substack.com/p/how-to-get-rich")
        'how-to-get-rich'
        >>> extract_slug_from_url("https://mattstoller.substack.com/")
        None
    """
    try:
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip('/').split('/')
        
        # Check if the URL has a post path (/p/slug)
        if len(path_parts) >= 2 and path_parts[0] == 'p':
            return path_parts[1]
        
        return None
    except Exception as e:
        logger.error(f"Error extracting slug from URL {url}: {e}")
        return None


def construct_post_url(author: str, slug: str) -> str:
    """
    Construct a Substack post URL from author and slug.
    
    Args:
        author (str): The Substack author identifier.
        slug (str): The post slug.
    
    Returns:
        str: The constructed URL.
    
    Examples:
        >>> construct_post_url("mattstoller", "how-to-get-rich")
        'https://mattstoller.substack.com/p/how-to-get-rich'
    """
    return f"https://{author}.substack.com/p/{slug}"


def construct_api_url(author: str, endpoint: str = "") -> str:
    """
    Construct a Substack API URL.
    
    Args:
        author (str): The Substack author identifier.
        endpoint (str, optional): The API endpoint. Defaults to "".
    
    Returns:
        str: The constructed API URL.
    
    Examples:
        >>> construct_api_url("mattstoller", "posts")
        'https://mattstoller.substack.com/api/v1/posts'
    """
    base_url = f"https://{author}.substack.com/api/v1"
    if endpoint:
        return f"{base_url}/{endpoint}"
    return base_url


def extract_post_id_from_api_response(post_data: Dict[str, Any]) -> str:
    """
    Extract the post ID from an API response.
    
    Args:
        post_data (Dict[str, Any]): The post data from the API.
    
    Returns:
        str: The post ID, or an empty string if it couldn't be extracted.
    """
    # Try different possible field names for the ID
    for field in ['id', 'post_id', '_id', 'postId']:
        if field in post_data:
            return str(post_data[field])
    
    return ""


def format_post_date(date_str: Optional[str], format_str: str = "%Y-%m-%d") -> Optional[str]:
    """
    Format a post date string.
    
    Args:
        date_str (Optional[str]): The date string from the API.
        format_str (str, optional): The output format. Defaults to "%Y-%m-%d".
    
    Returns:
        Optional[str]: The formatted date string, or None if it couldn't be formatted.
    
    Examples:
        >>> format_post_date("2023-01-01T12:00:00Z")
        '2023-01-01'
    """
    if not date_str:
        return None
    
    try:
        # Try parsing ISO format
        if 'T' in date_str:
            dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime(format_str)
        
        # Try parsing other common formats
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"]:
            try:
                dt = datetime.datetime.strptime(date_str, fmt)
                return dt.strftime(format_str)
            except ValueError:
                continue
        
        # If all parsing attempts fail, return the original string
        logger.warning(f"Could not parse date string: {date_str}")
        return date_str
    
    except Exception as e:
        logger.error(f"Error formatting date {date_str}: {e}")
        return None


def extract_images_from_html(html: str, base_url: str = "") -> List[str]:
    """
    Extract image URLs from HTML content.
    
    Args:
        html (str): The HTML content.
        base_url (str, optional): The base URL for resolving relative URLs. Defaults to "".
    
    Returns:
        List[str]: A list of image URLs.
    """
    if not html:
        return []
    
    try:
        # Use regex to find image URLs
        img_regex = r'<img[^>]+src=["\'](.*?)["\']'
        img_urls = re.findall(img_regex, html)
        
        # Resolve relative URLs if base_url is provided
        if base_url:
            img_urls = [urljoin(base_url, url) if not url.startswith(('http://', 'https://')) else url for url in img_urls]
        
        return img_urls
    
    except Exception as e:
        logger.error(f"Error extracting images from HTML: {e}")
        return []


def extract_newsletter_metadata(api_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract newsletter metadata from an API response.
    
    Args:
        api_response (Dict[str, Any]): The API response.
    
    Returns:
        Dict[str, Any]: The extracted newsletter metadata.
    """
    metadata = {
        "title": "",
        "description": "",
        "author": "",
        "logo_url": "",
        "cover_image_url": "",
        "subscribers_count": 0,
        "post_count": 0
    }
    
    try:
        # Extract newsletter metadata
        if "newsletter" in api_response:
            newsletter = api_response["newsletter"]
            metadata["title"] = newsletter.get("name", "")
            metadata["description"] = newsletter.get("description", "")
            
            # Extract author information
            if "author" in newsletter:
                metadata["author"] = newsletter["author"].get("name", "")
            
            # Extract logo and cover image
            metadata["logo_url"] = newsletter.get("logo_url", "")
            metadata["cover_image_url"] = newsletter.get("cover_image_url", "")
            
            # Extract subscriber and post counts
            metadata["subscribers_count"] = newsletter.get("subscribers_count", 0)
            metadata["post_count"] = newsletter.get("post_count", 0)
        
        return metadata
    
    except Exception as e:
        logger.error(f"Error extracting newsletter metadata: {e}")
        return metadata


def extract_post_metadata(post_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract post metadata from post data.
    
    Args:
        post_data (Dict[str, Any]): The post data.
    
    Returns:
        Dict[str, Any]: The extracted post metadata.
    """
    metadata = {
        "id": "",
        "title": "",
        "subtitle": "",
        "slug": "",
        "date": "",
        "author": "",
        "url": "",
        "is_paid": False,
        "is_public": True,
        "word_count": 0,
        "audio_url": "",
        "comments_count": 0,
        "likes_count": 0
    }
    
    try:
        # Extract basic metadata
        metadata["id"] = extract_post_id_from_api_response(post_data)
        metadata["title"] = post_data.get("title", "")
        metadata["subtitle"] = post_data.get("subtitle", "")
        metadata["slug"] = post_data.get("slug", "")
        
        # Format date
        if "post_date" in post_data:
            metadata["date"] = format_post_date(post_data["post_date"])
        elif "published_at" in post_data:
            metadata["date"] = format_post_date(post_data["published_at"])
        
        # Extract author information
        if "author" in post_data and isinstance(post_data["author"], dict):
            metadata["author"] = post_data["author"].get("name", "")
        
        # Extract URL
        metadata["url"] = post_data.get("canonical_url", "")
        if not metadata["url"] and metadata["slug"]:
            # Try to construct URL from slug
            author = extract_author_from_url(post_data.get("publication_url", ""))
            if author:
                metadata["url"] = construct_post_url(author, metadata["slug"])
        
        # Extract other metadata
        metadata["is_paid"] = post_data.get("is_paid", False)
        metadata["is_public"] = post_data.get("is_public", True)
        metadata["word_count"] = post_data.get("word_count", 0)
        metadata["audio_url"] = post_data.get("audio_url", "")
        metadata["comments_count"] = post_data.get("comments_count", 0)
        metadata["likes_count"] = post_data.get("likes_count", 0)
        
        return metadata
    
    except Exception as e:
        logger.error(f"Error extracting post metadata: {e}")
        return metadata


def extract_comments_from_api_response(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract comments from an API response.
    
    Args:
        api_response (Dict[str, Any]): The API response.
    
    Returns:
        List[Dict[str, Any]]: A list of comment objects.
    """
    comments = []
    
    try:
        # Check if the response contains comments
        if "comments" in api_response:
            raw_comments = api_response["comments"]
        elif "commentsByPostId" in api_response and "post" in api_response and "id" in api_response["post"]:
            post_id = api_response["post"]["id"]
            raw_comments = api_response["commentsByPostId"].get(post_id, [])
        else:
            return comments
        
        # Process each comment
        for comment in raw_comments:
            comment_obj = {
                "id": comment.get("id", ""),
                "body": comment.get("body", ""),
                "date": format_post_date(comment.get("created_at", "")),
                "author": "",
                "parent_id": comment.get("parent_id", None),
                "replies": []
            }
            
            # Extract author information
            if "commenter" in comment and isinstance(comment["commenter"], dict):
                comment_obj["author"] = comment["commenter"].get("name", "Anonymous")
            
            comments.append(comment_obj)
        
        # Organize comments into a tree structure
        return organize_comments_tree(comments)
    
    except Exception as e:
        logger.error(f"Error extracting comments from API response: {e}")
        return comments


def organize_comments_tree(comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Organize flat comments list into a tree structure with replies.
    
    Args:
        comments (List[Dict[str, Any]]): Flat list of comments.
    
    Returns:
        List[Dict[str, Any]]: Tree structure with top-level comments and nested replies.
    """
    # Create a map of comments by ID for quick lookup
    comment_map = {comment["id"]: comment for comment in comments if "id" in comment}
    
    # Organize into tree structure
    top_level_comments = []
    
    for comment in comments:
        # Skip comments without ID
        if "id" not in comment:
            continue
            
        parent_id = comment.get("parent_id")
        
        if not parent_id:
            # This is a top-level comment
            top_level_comments.append(comment)
        else:
            # This is a reply
            if parent_id in comment_map:
                parent = comment_map[parent_id]
                if "replies" not in parent:
                    parent["replies"] = []
                parent["replies"].append(comment)
    
    return top_level_comments


def format_comments_markdown(comments: List[Dict[str, Any]], level: int = 0) -> str:
    """
    Format comments as markdown with proper indentation for replies.
    
    Args:
        comments (List[Dict[str, Any]]): List of comment objects.
        level (int, optional): Current indentation level. Defaults to 0.
    
    Returns:
        str: Formatted markdown string.
    """
    if not comments:
        return ""
        
    markdown = ""
    indent = "  " * level
    
    for comment in comments:
        # Add comment header with author and date
        author = comment.get("author", "Anonymous")
        date = comment.get("date", "")
        if date:
            markdown += f"{indent}**{author}** - {date}\n\n"
        else:
            markdown += f"{indent}**{author}**\n\n"
        
        # Add comment body with proper indentation
        body = comment.get("body", "").strip()
        for line in body.split("\n"):
            markdown += f"{indent}{line}\n"
        
        markdown += "\n"
        
        # Add replies with increased indentation
        replies = comment.get("replies", [])
        if replies:
            markdown += format_comments_markdown(replies, level + 1)
            markdown += "\n"
    
    return markdown


def generate_frontmatter(metadata: Dict[str, Any]) -> str:
    """
    Generate frontmatter for a markdown file.
    
    Args:
        metadata (Dict[str, Any]): The post metadata.
    
    Returns:
        str: The generated frontmatter.
    """
    frontmatter = "---\n"
    
    # Add basic metadata
    title = metadata.get("title", "").replace('"', '\\"')
    frontmatter += f'title: "{title}"\n'
    
    if "subtitle" in metadata and metadata["subtitle"]:
        subtitle = metadata.get("subtitle", "").replace('"', '\\"')
        frontmatter += f'subtitle: "{subtitle}"\n'
    
    if "date" in metadata and metadata["date"]:
        frontmatter += f'date: "{metadata.get("date", "")}"\n'
    
    if "author" in metadata and metadata["author"]:
        frontmatter += f'author: "{metadata.get("author", "")}"\n'
    
    if "url" in metadata and metadata["url"]:
        frontmatter += f'original_url: "{metadata.get("url", "")}"\n'
    
    # Add additional metadata
    if "is_paid" in metadata:
        frontmatter += f'is_paid: {str(metadata.get("is_paid", False)).lower()}\n'
    
    if "word_count" in metadata and metadata["word_count"]:
        frontmatter += f'word_count: {metadata.get("word_count", 0)}\n'
    
    if "comments_count" in metadata and metadata["comments_count"]:
        frontmatter += f'comments_count: {metadata.get("comments_count", 0)}\n'
    
    if "likes_count" in metadata and metadata["likes_count"]:
        frontmatter += f'likes_count: {metadata.get("likes_count", 0)}\n'
    
    frontmatter += "---\n"
    return frontmatter


def generate_newsletter_index(newsletter_metadata: Dict[str, Any], posts_metadata: List[Dict[str, Any]]) -> str:
    """
    Generate a newsletter index markdown file.
    
    Args:
        newsletter_metadata (Dict[str, Any]): The newsletter metadata.
        posts_metadata (List[Dict[str, Any]]): List of post metadata.
    
    Returns:
        str: The generated markdown content.
    """
    # Generate frontmatter
    frontmatter = "---\n"
    title = newsletter_metadata.get("title", "").replace('"', '\\"')
    description = newsletter_metadata.get("description", "").replace('"', '\\"')
    frontmatter += f'title: "{title}"\n'
    frontmatter += f'description: "{description}"\n'
    frontmatter += f'author: "{newsletter_metadata.get("author", "")}"\n'
    frontmatter += f'date: "{datetime.datetime.now().strftime("%Y-%m-%d")}"\n'
    frontmatter += f'post_count: {newsletter_metadata.get("post_count", len(posts_metadata))}\n'
    frontmatter += f'subscribers_count: {newsletter_metadata.get("subscribers_count", 0)}\n'
    frontmatter += "---\n\n"
    
    # Generate header
    markdown = frontmatter
    markdown += f"# {newsletter_metadata.get('title', 'Newsletter Index')}\n\n"
    
    if newsletter_metadata.get("description"):
        markdown += f"{newsletter_metadata.get('description')}\n\n"
    
    # Add newsletter stats
    markdown += "## Newsletter Statistics\n\n"
    markdown += f"- **Posts**: {newsletter_metadata.get('post_count', len(posts_metadata))}\n"
    markdown += f"- **Subscribers**: {newsletter_metadata.get('subscribers_count', 0)}\n\n"
    
    # Add post list
    markdown += "## Posts\n\n"
    
    # Sort posts by date (newest first)
    sorted_posts = sorted(
        posts_metadata,
        key=lambda x: x.get("date", ""),
        reverse=True
    )
    
    for post in sorted_posts:
        date = post.get("date", "")
        title = post.get("title", "Untitled")
        url = post.get("url", "")
        
        if date and url:
            markdown += f"- [{date}] [{title}]({url})\n"
        elif url:
            markdown += f"- [{title}]({url})\n"
        else:
            markdown += f"- {title}\n"
    
    return markdown


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing invalid characters.
    
    Args:
        filename (str): The filename to sanitize.
    
    Returns:
        str: The sanitized filename.
    """
    # Replace invalid characters with underscores
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # Replace multiple spaces with a single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    # Trim the filename if it's too long
    if len(sanitized) > 100:
        sanitized = sanitized[:97] + '...'
    
    return sanitized


def generate_filename(metadata: Dict[str, Any]) -> str:
    """
    Generate a filename for a post.
    
    Args:
        metadata (Dict[str, Any]): The post metadata.
    
    Returns:
        str: The generated filename.
    """
    title = metadata.get("title", "Untitled")
    date = metadata.get("date", "")
    slug = metadata.get("slug", "")
    
    # Use slug if available, otherwise use sanitized title
    if slug:
        base_name = slug
    else:
        base_name = sanitize_filename(title)
    
    # Add date prefix if available
    if date:
        filename = f"{date}_{base_name}.md"
    else:
        filename = f"{base_name}.md"
    
    return filename


# Example usage
if __name__ == "__main__":
    # Example post data
    post_data = {
        "id": "12345",
        "title": "How to Get Rich Sabotaging Nuclear Power Plants",
        "subtitle": "A case study in monopoly and corruption",
        "slug": "how-to-get-rich-sabotaging-nuclear",
        "post_date": "2023-01-01T12:00:00Z",
        "author": {"name": "Matt Stoller"},
        "canonical_url": "https://mattstoller.substack.com/p/how-to-get-rich-sabotaging-nuclear",
        "is_paid": False,
        "is_public": True,
        "word_count": 2500,
        "comments_count": 15,
        "likes_count": 150
    }
    
    # Extract metadata
    metadata = extract_post_metadata(post_data)
    print(f"Post metadata: {json.dumps(metadata, indent=2)}")
    
    # Generate frontmatter
    frontmatter = generate_frontmatter(metadata)
    print(f"\nFrontmatter:\n{frontmatter}")
    
    # Generate filename
    filename = generate_filename(metadata)
    print(f"\nFilename: {filename}")
    
    # Extract author and slug from URL
    url = "https://mattstoller.substack.com/p/how-to-get-rich-sabotaging-nuclear"
    author = extract_author_from_url(url)
    slug = extract_slug_from_url(url)
    print(f"\nAuthor: {author}")
    print(f"Slug: {slug}")
    
    # Construct post URL
    constructed_url = construct_post_url(author, slug)
    print(f"\nConstructed URL: {constructed_url}")
    
    # Format date
    formatted_date = format_post_date("2023-01-01T12:00:00Z")
    print(f"\nFormatted date: {formatted_date}")
