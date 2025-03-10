#!/usr/bin/env python3
"""
Substack to Markdown CLI Tool

This command-line tool fetches posts from Substack using the Substack API wrapper
and converts them to Markdown format. It allows users to specify an author,
output directory, and other options.

Usage:
    python substack_to_md.py --author <author_identifier> [--output <directory>] [--limit <number>] [--verbose]

Example:
    python substack_to_md.py --author mattstoller --output ./my_posts --limit 5 --verbose
"""

import os
import sys
import argparse
import logging
import re
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from tqdm import tqdm

from src.core.substack_fetcher import SubstackFetcher, Post
from src.utils.markdown_converter import MarkdownConverter
from src.utils.env_loader import load_env_vars, get_substack_auth, get_general_config, get_oxylabs_config

# Load environment variables from .env file
load_env_vars()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_arguments(use_env_defaults: bool = True) -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Args:
        use_env_defaults (bool, optional): Whether to use environment variables for default values. Defaults to True.
    
    Returns:
        argparse.Namespace: The parsed command-line arguments.
    """
    # Get default values from environment variables if requested
    if use_env_defaults:
        general_config = get_general_config()
        substack_auth = get_substack_auth()
    else:
        # Use empty defaults for testing
        general_config = {
            'output_dir': '.',
            'image_dir': 'images',
            'max_image_workers': 4,
            'image_timeout': 10
        }
        substack_auth = {
            'email': '',
            'password': '',
            'token': ''
        }
    
    parser = argparse.ArgumentParser(description='Convert Substack posts to Markdown')
    
    # Required arguments
    parser.add_argument('--author', required=True, help='Substack author identifier (username or subdomain)')
    
    # Optional arguments
    parser.add_argument('--output', default=general_config['output_dir'], 
                        help=f'Output directory (default: {general_config["output_dir"]})')
    parser.add_argument('--limit', type=int, help='Limit number of posts to fetch')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--use-post-objects', action='store_true', help='Use Post objects directly (enhanced mode)')
    parser.add_argument('--url', help='Process a single post by URL instead of fetching all posts from an author')
    parser.add_argument('--slug', help='Process a single post by slug instead of fetching all posts from an author')
    
    # Authentication arguments
    auth_group = parser.add_argument_group('Authentication options (for accessing private content)')
    auth_group.add_argument('--email', default=substack_auth['email'] or None, 
                           help='Substack account email')
    auth_group.add_argument('--password', default=substack_auth['password'] or None, 
                           help='Substack account password')
    auth_group.add_argument('--token', default=substack_auth['token'] or None, 
                           help='Substack authentication token')
    auth_group.add_argument('--cookies-file', help='Path to a file containing cookies')
    auth_group.add_argument('--save-cookies', help='Save cookies to a file after authentication')
    auth_group.add_argument('--private', action='store_true', help='Indicate that the post is private and requires authentication')
    
    # Image downloading arguments
    image_group = parser.add_argument_group('Image downloading options')
    image_group.add_argument('--download-images', action='store_true', help='Download and embed images in the Markdown')
    image_group.add_argument('--image-dir', default=general_config['image_dir'], 
                            help=f'Directory to save downloaded images (default: {general_config["image_dir"]})')
    image_group.add_argument('--image-base-url', default='', help='Base URL for image references in Markdown (default: relative paths)')
    image_group.add_argument('--max-image-workers', type=int, default=general_config['max_image_workers'], 
                            help=f'Maximum number of concurrent image downloads (default: {general_config["max_image_workers"]})')
    image_group.add_argument('--image-timeout', type=int, default=general_config['image_timeout'], 
                            help=f'Timeout for image download requests in seconds (default: {general_config["image_timeout"]})')
    
    return parser.parse_args()


def sanitize_filename(title: str) -> str:
    """
    Sanitize a string to be used as a filename.
    
    Args:
        title (str): The string to sanitize.
    
    Returns:
        str: The sanitized filename.
    """
    # Replace invalid filename characters with underscores
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', title)
    
    # Replace multiple spaces with a single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    # Trim to a reasonable length
    if len(sanitized) > 100:
        sanitized = sanitized[:97] + '...'
    
    return sanitized.strip()


def generate_filename(post: Union[Dict[str, Any], Post]) -> str:
    """
    Generate a filename for a post based on its title and date.
    
    Args:
        post (Union[Dict[str, Any], Post]): The post object or Post instance.
    
    Returns:
        str: The generated filename.
    """
    # Handle Post objects
    if isinstance(post, Post):
        # Get metadata from the Post object
        metadata = post._post_data if post._post_data else {}
        title = metadata.get('title', 'Untitled Post')
        post_date = metadata.get('post_date')
    else:
        # Handle dictionary objects
        title = post.get('title', 'Untitled Post')
        post_date = post.get('post_date')
    
    # Process the date
    if post_date:
        try:
            # Parse the date string and format it as YYYY-MM-DD
            date_obj = datetime.fromisoformat(post_date.replace('Z', '+00:00'))
            date_str = date_obj.strftime('%Y-%m-%d')
            
            # Combine date and title
            filename = f"{date_str}_{sanitize_filename(title)}.md"
        except (ValueError, TypeError):
            # Fallback if date parsing fails
            filename = f"{sanitize_filename(title)}.md"
    else:
        # Fallback if no date is available
        filename = f"{sanitize_filename(title)}.md"
    
    return filename


def save_markdown_to_file(markdown_content: str, filename: str, output_dir: str, verbose: bool = False) -> bool:
    """
    Save Markdown content to a file.
    
    Args:
        markdown_content (str): The Markdown content to save.
        filename (str): The filename to use.
        output_dir (str): The output directory.
        verbose (bool, optional): Enable verbose output. Defaults to False.
    
    Returns:
        bool: True if the file was saved successfully, False otherwise.
    """
    try:
        # Create the output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Construct the full file path
        file_path = os.path.join(output_dir, filename)
        
        # Write the Markdown content to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        if verbose:
            logger.info(f"Saved Markdown to {file_path}")
        
        return True
    
    except OSError as e:
        logger.error(f"Error saving file {filename}: {e}")
        return False


def process_posts(posts: List[Dict[str, Any]], output_dir: str, verbose: bool = False,
                 download_images: bool = False, image_dir: str = "images",
                 image_base_url: str = "", max_image_workers: int = 4,
                 image_timeout: int = 10) -> int:
    """
    Process a list of posts, converting them to Markdown and saving them to files.
    
    Args:
        posts (List[Dict[str, Any]]): The list of posts to process.
        output_dir (str): The output directory.
        verbose (bool, optional): Enable verbose output. Defaults to False.
        download_images (bool, optional): Whether to download and embed images. Defaults to False.
        image_dir (str, optional): Directory to save downloaded images. Defaults to "images".
        image_base_url (str, optional): Base URL for image references in Markdown. Defaults to "".
        max_image_workers (int, optional): Maximum number of concurrent image downloads. Defaults to 4.
        image_timeout (int, optional): Timeout for image download requests in seconds. Defaults to 10.
    
    Returns:
        int: The number of posts successfully processed.
    """
    if not posts:
        logger.warning("No posts to process")
        return 0
    
    # Initialize the Markdown converter
    converter = MarkdownConverter(
        download_images=download_images,
        image_dir=image_dir,
        image_base_url=image_base_url,
        max_workers=max_image_workers,
        timeout=image_timeout
    )
    
    # Initialize counter for successful conversions
    successful_count = 0
    
    # Process each post with a progress bar
    for post in tqdm(posts, desc="Converting posts", disable=not verbose):
        title = post.get('title', 'Untitled Post')
        
        if verbose:
            logger.info(f"Processing post: {title}")
        
        # Get the HTML content
        html_content = post.get('body_html')
        
        if not html_content:
            logger.warning(f"No HTML content found for post: {title}")
            continue
        
        # Convert HTML to Markdown
        markdown_content = converter.convert_html_to_markdown(html_content, verbose)
        
        if not markdown_content:
            logger.warning(f"Failed to convert HTML to Markdown for post: {title}")
            continue
        
        # Add metadata to the Markdown content
        markdown_content = add_metadata_to_markdown(post, markdown_content)
        
        # Generate a filename for the post
        filename = generate_filename(post)
        
        # Save the Markdown content to a file
        if save_markdown_to_file(markdown_content, filename, output_dir, verbose):
            successful_count += 1
        
        # Add a small delay to avoid overwhelming the system
        time.sleep(0.1)
    
    return successful_count


def process_post_objects(post_objects: List[Post], fetcher: SubstackFetcher, output_dir: str, verbose: bool = False,
                        download_images: bool = False, image_dir: str = "images",
                        image_base_url: str = "", max_image_workers: int = 4,
                        image_timeout: int = 10) -> int:
    """
    Process a list of Post objects, converting them to Markdown and saving them to files.
    
    Args:
        post_objects (List[Post]): The list of Post objects to process.
        fetcher (SubstackFetcher): The SubstackFetcher instance.
        output_dir (str): The output directory.
        verbose (bool, optional): Enable verbose output. Defaults to False.
        download_images (bool, optional): Whether to download and embed images. Defaults to False.
        image_dir (str, optional): Directory to save downloaded images. Defaults to "images".
        image_base_url (str, optional): Base URL for image references in Markdown. Defaults to "".
        max_image_workers (int, optional): Maximum number of concurrent image downloads. Defaults to 4.
        image_timeout (int, optional): Timeout for image download requests in seconds. Defaults to 10.
    
    Returns:
        int: The number of posts successfully processed.
    """
    if not post_objects:
        logger.warning("No posts to process")
        return 0
    
    # Initialize the Markdown converter
    converter = MarkdownConverter(
        download_images=download_images,
        image_dir=image_dir,
        image_base_url=image_base_url,
        max_workers=max_image_workers,
        timeout=image_timeout
    )
    
    # Initialize counter for successful conversions
    successful_count = 0
    
    # Process each post with a progress bar
    for post in tqdm(post_objects, desc="Converting posts", disable=not verbose):
        # Get metadata
        metadata = fetcher.get_post_metadata(post, verbose)
        if not metadata:
            logger.warning(f"Failed to get metadata for post: {post}")
            continue
        
        title = metadata.get('title', 'Untitled Post')
        
        if verbose:
            logger.info(f"Processing post: {title}")
        
        # Get the HTML content
        html_content = fetcher.get_post_content(post, verbose)
        
        if not html_content:
            logger.warning(f"No HTML content found for post: {title}")
            continue
        
        # Convert HTML to Markdown
        markdown_content = converter.convert_html_to_markdown(html_content, verbose)
        
        if not markdown_content:
            logger.warning(f"Failed to convert HTML to Markdown for post: {title}")
            continue
        
        # Add metadata to the Markdown content
        markdown_content = add_metadata_to_markdown(metadata, markdown_content)
        
        # Generate a filename for the post
        filename = generate_filename(post)
        
        # Save the Markdown content to a file
        if save_markdown_to_file(markdown_content, filename, output_dir, verbose):
            successful_count += 1
        
        # Add a small delay to avoid overwhelming the system
        time.sleep(0.1)
    
    return successful_count


def add_metadata_to_markdown(post: Union[Dict[str, Any], Post], markdown_content: str) -> str:
    """
    Add post metadata to the Markdown content as front matter.
    
    Args:
        post (Union[Dict[str, Any], Post]): The post object or Post instance.
        markdown_content (str): The Markdown content.
    
    Returns:
        str: The Markdown content with added metadata.
    """
    # Extract metadata from the post
    if isinstance(post, Post):
        # Get metadata from the Post object
        metadata = post._post_data if post._post_data else {}
        title = metadata.get('title', 'Untitled Post')
        subtitle = metadata.get('subtitle', '')
        author_data = metadata.get('author', {})
        author = author_data.get('name', '') if isinstance(author_data, dict) else ''
        post_date = metadata.get('post_date', '')
        url = metadata.get('canonical_url', '')
    else:
        # Handle dictionary objects
        title = post.get('title', 'Untitled Post')
        subtitle = post.get('subtitle', '')
        author = post.get('author', {}).get('name', '')
        post_date = post.get('post_date', '')
        url = post.get('canonical_url', '')
    
    # Format the date
    if post_date:
        try:
            # Parse the date string and format it as YYYY-MM-DD
            date_obj = datetime.fromisoformat(post_date.replace('Z', '+00:00'))
            post_date = date_obj.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            pass
    
    # Create front matter
    front_matter = [
        '---',
        f'title: "{title}"'
    ]
    
    if subtitle:
        front_matter.append(f'subtitle: "{subtitle}"')
    
    if author:
        front_matter.append(f'author: "{author}"')
    
    if post_date:
        front_matter.append(f'date: "{post_date}"')
    
    if url:
        front_matter.append(f'original_url: "{url}"')
    
    front_matter.append('---\n')
    
    # Combine front matter with Markdown content
    return '\n'.join(front_matter) + markdown_content


def process_single_post(fetcher: SubstackFetcher, url: str, output_dir: str, verbose: bool = False,
                       download_images: bool = False, image_dir: str = "images",
                       image_base_url: str = "", max_image_workers: int = 4,
                       image_timeout: int = 10) -> int:
    """
    Process a single post by URL.
    
    Args:
        fetcher (SubstackFetcher): The SubstackFetcher instance.
        url (str): The URL of the post to process.
        output_dir (str): The output directory.
        verbose (bool, optional): Enable verbose output. Defaults to False.
        download_images (bool, optional): Whether to download and embed images. Defaults to False.
        image_dir (str, optional): Directory to save downloaded images. Defaults to "images".
        image_base_url (str, optional): Base URL for image references in Markdown. Defaults to "".
        max_image_workers (int, optional): Maximum number of concurrent image downloads. Defaults to 4.
        image_timeout (int, optional): Timeout for image download requests in seconds. Defaults to 10.
    
    Returns:
        int: 1 if the post was successfully processed, 0 otherwise.
    """
    if verbose:
        logger.info(f"Processing post by URL: {url}")
    
    # Get the Post object
    post = fetcher.get_post_by_url(url, verbose)
    if not post:
        logger.error(f"Failed to get post by URL: {url}")
        return 0
    
    # Process the post
    return process_post_objects(
        [post], fetcher, output_dir, verbose,
        download_images=download_images,
        image_dir=image_dir,
        image_base_url=image_base_url,
        max_image_workers=max_image_workers,
        image_timeout=image_timeout
    )


def process_single_post_by_slug(fetcher: SubstackFetcher, author: str, slug: str, output_dir: str, verbose: bool = False,
                               download_images: bool = False, image_dir: str = "images",
                               image_base_url: str = "", max_image_workers: int = 4,
                               image_timeout: int = 10) -> int:
    """
    Process a single post by slug.
    
    Args:
        fetcher (SubstackFetcher): The SubstackFetcher instance.
        author (str): The author identifier.
        slug (str): The slug of the post to process.
        output_dir (str): The output directory.
        verbose (bool, optional): Enable verbose output. Defaults to False.
        download_images (bool, optional): Whether to download and embed images. Defaults to False.
        image_dir (str, optional): Directory to save downloaded images. Defaults to "images".
        image_base_url (str, optional): Base URL for image references in Markdown. Defaults to "".
        max_image_workers (int, optional): Maximum number of concurrent image downloads. Defaults to 4.
        image_timeout (int, optional): Timeout for image download requests in seconds. Defaults to 10.
    
    Returns:
        int: 1 if the post was successfully processed, 0 otherwise.
    """
    if verbose:
        logger.info(f"Processing post by slug: {slug}")
    
    # Get the Post object
    post = fetcher.get_post_by_slug(author, slug, verbose)
    if not post:
        logger.error(f"Failed to get post by slug: {slug}")
        return 0
    
    # Process the post
    return process_post_objects(
        [post], fetcher, output_dir, verbose,
        download_images=download_images,
        image_dir=image_dir,
        image_base_url=image_base_url,
        max_image_workers=max_image_workers,
        image_timeout=image_timeout
    )


def process_private_post(fetcher: SubstackFetcher, url: str, output_dir: str, verbose: bool = False,
                        download_images: bool = False, image_dir: str = "images",
                        image_base_url: str = "", max_image_workers: int = 4,
                        image_timeout: int = 10) -> int:
    """
    Process a private post using authenticated session.
    
    Args:
        fetcher (SubstackFetcher): The SubstackFetcher instance.
        url (str): The URL of the private post to process.
        output_dir (str): The output directory.
        verbose (bool, optional): Enable verbose output. Defaults to False.
        download_images (bool, optional): Whether to download and embed images. Defaults to False.
        image_dir (str, optional): Directory to save downloaded images. Defaults to "images".
        image_base_url (str, optional): Base URL for image references in Markdown. Defaults to "".
        max_image_workers (int, optional): Maximum number of concurrent image downloads. Defaults to 4.
        image_timeout (int, optional): Timeout for image download requests in seconds. Defaults to 10.
    
    Returns:
        int: 1 if the post was successfully processed, 0 otherwise.
    """
    if not fetcher.is_authenticated:
        logger.error("Authentication required to access private posts")
        return 0
    
    if verbose:
        logger.info(f"Processing private post: {url}")
    
    # Fetch the private post
    post_data, post_content = fetcher.fetch_private_post(url, verbose)
    
    if not post_data or not post_content:
        logger.error(f"Failed to fetch private post: {url}")
        return 0
    
    # Initialize the Markdown converter
    converter = MarkdownConverter(
        download_images=download_images,
        image_dir=image_dir,
        image_base_url=image_base_url,
        max_workers=max_image_workers,
        timeout=image_timeout
    )
    
    # Convert HTML to Markdown
    markdown_content = converter.convert_html_to_markdown(post_content, verbose)
    
    if not markdown_content:
        logger.error(f"Failed to convert HTML to Markdown for post: {post_data.get('title', 'Unknown')}")
        return 0
    
    # Add metadata to the Markdown content
    markdown_content = add_metadata_to_markdown(post_data, markdown_content)
    
    # Generate a filename for the post
    filename = generate_filename(post_data)
    
    # Save the Markdown content to a file
    if save_markdown_to_file(markdown_content, filename, output_dir, verbose):
        return 1
    
    return 0


def main() -> int:
    """
    Main function to run the CLI tool.
    
    Returns:
        int: Exit code (0 for success, non-zero for failure).
    """
    try:
        # Parse command-line arguments
        args = parse_arguments(use_env_defaults=True)
        
        # Set up logging level based on verbose flag
        if args.verbose:
            logging.getLogger().setLevel(logging.INFO)
        else:
            logging.getLogger().setLevel(logging.WARNING)
        
        # Get Oxylabs configuration
        oxylabs_config = get_oxylabs_config()
        use_proxy = bool(oxylabs_config['username'] and oxylabs_config['password'])
        
        # Initialize the Substack fetcher with proxy if configured
        fetcher = SubstackFetcher(use_proxy=use_proxy)
        
        if use_proxy and args.verbose:
            logger.info("Using Oxylabs proxy for requests")
        
        # Get authentication credentials from environment variables if not provided via CLI
        substack_auth = get_substack_auth()
        email = args.email or substack_auth['email']
        password = args.password or substack_auth['password']
        token = args.token or substack_auth['token']
        
        # Handle authentication if provided
        if email or password or token or args.cookies_file or args.private:
            if args.verbose:
                logger.info("Authenticating with Substack...")
            
            # Authenticate with the provided credentials
            auth_success = fetcher.authenticate(
                email=email,
                password=password,
                token=token,
                cookies_file=args.cookies_file
            )
            
            if not auth_success:
                logger.error("Authentication failed")
                return 1
            
            if args.verbose:
                logger.info("Authentication successful")
            
            # Save cookies if requested
            if args.save_cookies and auth_success:
                if fetcher.save_cookies(args.save_cookies):
                    logger.info(f"Cookies saved to {args.save_cookies}")
                else:
                    logger.warning(f"Failed to save cookies to {args.save_cookies}")
        
        # Get general configuration from environment variables
        general_config = get_general_config()
        
        # Use environment variables for image processing if not provided via CLI
        image_dir = args.image_dir or general_config['image_dir']
        max_image_workers = args.max_image_workers or general_config['max_image_workers']
        image_timeout = args.image_timeout or general_config['image_timeout']
        
        # Process a single post by URL if specified
        if args.url:
            if args.private:
                successful_count = process_private_post(
                    fetcher, args.url, args.output, args.verbose,
                    download_images=args.download_images,
                    image_dir=image_dir,
                    image_base_url=args.image_base_url,
                    max_image_workers=max_image_workers,
                    image_timeout=image_timeout
                )
            else:
                successful_count = process_single_post(
                    fetcher, args.url, args.output, args.verbose,
                    download_images=args.download_images,
                    image_dir=image_dir,
                    image_base_url=args.image_base_url,
                    max_image_workers=max_image_workers,
                    image_timeout=image_timeout
                )
            
            # Print summary
            print(f"\nSummary:")
            print(f"- Post URL: {args.url}")
            print(f"- Successfully converted and saved: {successful_count}")
            print(f"- Output directory: {os.path.abspath(args.output)}")
            
            return 0 if successful_count > 0 else 1
        
        # Process a single post by slug if specified
        if args.slug:
            if args.private:
                url = f"https://{args.author}.substack.com/p/{args.slug}"
                successful_count = process_private_post(
                    fetcher, url, args.output, args.verbose,
                    download_images=args.download_images,
                    image_dir=image_dir,
                    image_base_url=args.image_base_url,
                    max_image_workers=max_image_workers,
                    image_timeout=image_timeout
                )
            else:
                successful_count = process_single_post_by_slug(
                    fetcher, args.author, args.slug, args.output, args.verbose,
                    download_images=args.download_images,
                    image_dir=image_dir,
                    image_base_url=args.image_base_url,
                    max_image_workers=max_image_workers,
                    image_timeout=image_timeout
                )
            
            # Print summary
            print(f"\nSummary:")
            print(f"- Post slug: {args.slug}")
            print(f"- Successfully converted and saved: {successful_count}")
            print(f"- Output directory: {os.path.abspath(args.output)}")
            
            return 0 if successful_count > 0 else 1
        
        # Fetch posts
        logger.info(f"Fetching posts for author: {args.author}")
        
        # Use enhanced mode with Post objects if specified
        if args.use_post_objects:
            post_objects = fetcher.fetch_post_objects(args.author, args.limit, args.verbose)
            
            if not post_objects:
                logger.error(f"No posts found for author: {args.author}")
                return 1
            
            logger.info(f"Fetched {len(post_objects)} posts")
            
            # Process post objects
            successful_count = process_post_objects(
                post_objects, fetcher, args.output, args.verbose,
                download_images=args.download_images,
                image_dir=image_dir,
                image_base_url=args.image_base_url,
                max_image_workers=max_image_workers,
                image_timeout=image_timeout
            )
            
            # Print summary
            print(f"\nSummary:")
            print(f"- Total posts fetched: {len(post_objects)}")
            print(f"- Successfully converted and saved: {successful_count}")
            print(f"- Failed: {len(post_objects) - successful_count}")
            print(f"- Output directory: {os.path.abspath(args.output)}")
        else:
            # Use legacy mode with dictionary objects
            posts = fetcher.fetch_posts(args.author, args.limit, args.verbose)
            
            if not posts:
                logger.error(f"No posts found for author: {args.author}")
                return 1
            
            logger.info(f"Fetched {len(posts)} posts")
            
            # Process posts
            successful_count = process_posts(
                posts, args.output, args.verbose,
                download_images=args.download_images,
                image_dir=image_dir,
                image_base_url=args.image_base_url,
                max_image_workers=max_image_workers,
                image_timeout=image_timeout
            )
            
            # Print summary
            print(f"\nSummary:")
            print(f"- Total posts fetched: {len(posts)}")
            print(f"- Successfully converted and saved: {successful_count}")
            print(f"- Failed: {len(posts) - successful_count}")
            print(f"- Output directory: {os.path.abspath(args.output)}")
        
        return 0
    
    except ValueError as e:
        logger.error(f"Error: {e}")
        return 1
    
    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return 1
    
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
