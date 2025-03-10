#!/usr/bin/env python3
"""
Script to download Substack posts using URLs from sitemap.
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path

# Import the SubstackDirectDownloader class
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from substack_direct_downloader import SubstackDirectDownloader

async def download_posts_from_file(url_file, author="tradecompanion", output_dir="output", 
                                  image_dir="images", force=False, max_posts=None, 
                                  download_images=True, verbose=False):
    """
    Download posts using URLs from a file.
    
    Args:
        url_file (str): Path to the file containing post URLs.
        author (str, optional): Substack author identifier. Defaults to "tradecompanion".
        output_dir (str, optional): Output directory. Defaults to "output".
        image_dir (str, optional): Image directory. Defaults to "images".
        force (bool, optional): Force refresh of already downloaded posts. Defaults to False.
        max_posts (int, optional): Maximum number of posts to download. Defaults to None.
        download_images (bool, optional): Download images. Defaults to True.
        verbose (bool, optional): Enable verbose output. Defaults to False.
    
    Returns:
        tuple: (successful, failed, skipped) counts
    """
    # Read post URLs from file
    try:
        with open(url_file, 'r') as f:
            post_urls = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading URL file: {e}")
        return 0, 0, 0
    
    print(f"Found {len(post_urls)} post URLs in file")
    
    # Limit to max_posts if specified
    if max_posts is not None:
        post_urls = post_urls[:max_posts]
        print(f"Limiting to {max_posts} posts")
    
    # Initialize the downloader
    async with SubstackDirectDownloader(
        author=author,
        output_dir=output_dir,
        image_dir=image_dir,
        verbose=verbose,
        incremental=True
    ) as downloader:
        # Load authentication token from .env if available
        try:
            from env_loader import load_env_vars, get_substack_auth
            load_env_vars()
            auth_info = get_substack_auth()
            if auth_info.get('token'):
                print("Using authentication token from .env file")
                downloader.set_auth_token(auth_info.get('token'))
        except ImportError:
            print("env_loader module not found, continuing without authentication")
        
        # Download each post
        tasks = []
        for url in post_urls:
            tasks.append(downloader.download_post(
                url=url,
                force=force,
                download_images=download_images
            ))
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        successful = 0
        failed = 0
        skipped = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Error downloading post {post_urls[i]}: {result}")
                failed += 1
            elif result == "skipped":
                skipped += 1
            elif result is True:
                successful += 1
            else:
                failed += 1
        
        # Print summary
        print("=" * 50)
        print(f"Download summary for {author}.substack.com:")
        print(f"Total posts processed: {len(post_urls)}")
        print(f"Successfully downloaded: {successful}")
        print(f"Failed: {failed}")
        print(f"Skipped (already downloaded): {skipped}")
        print("=" * 50)
        
        return successful, failed, skipped

def main():
    """Main function to parse arguments and download posts."""
    parser = argparse.ArgumentParser(description='Download Substack posts using URLs from a file')
    parser.add_argument('--file', default='tradecompanion_posts.txt', help='File containing post URLs')
    parser.add_argument('--author', default='tradecompanion', help='Substack author identifier')
    parser.add_argument('--output', default='output', help='Output directory')
    parser.add_argument('--force', action='store_true', help='Force refresh of already downloaded posts')
    parser.add_argument('--max-posts', type=int, help='Maximum number of posts to download')
    parser.add_argument('--skip-first', type=int, default=0, help='Skip the first N posts')
    parser.add_argument('--no-images', action='store_true', help='Skip downloading images')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Check if URL file exists
    if not os.path.exists(args.file):
        print(f"Error: URL file '{args.file}' not found")
        sys.exit(1)
    
    try:
        # Read post URLs from file
        with open(args.file, 'r') as f:
            all_post_urls = [line.strip() for line in f if line.strip()]
        
        # Skip first N posts if specified
        if args.skip_first > 0:
            if args.skip_first >= len(all_post_urls):
                print(f"Error: skip_first ({args.skip_first}) is greater than or equal to the total number of posts ({len(all_post_urls)})")
                sys.exit(1)
            
            print(f"Skipping the first {args.skip_first} posts")
            post_urls = all_post_urls[args.skip_first:]
        else:
            post_urls = all_post_urls
        
        # Limit to max_posts if specified
        if args.max_posts is not None:
            post_urls = post_urls[:args.max_posts]
            print(f"Limiting to {args.max_posts} posts (after skipping)")
        
        # Save filtered URLs to a temporary file
        temp_file = f"{args.file}.temp"
        with open(temp_file, 'w') as f:
            for url in post_urls:
                f.write(f"{url}\n")
        
        # Run the async download function
        asyncio.run(download_posts_from_file(
            url_file=temp_file,
            author=args.author,
            output_dir=args.output,
            force=args.force,
            max_posts=None,  # We've already filtered the posts
            download_images=not args.no_images,
            verbose=args.verbose
        ))
        
        # Clean up the temporary file
        try:
            os.remove(temp_file)
        except:
            pass
    except KeyboardInterrupt:
        print("Download interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()