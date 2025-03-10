#!/usr/bin/env python3
"""
Batch Processor Module

This module provides functionality for batch processing multiple Substack authors.
It reads a configuration file and processes each author in parallel using multiprocessing.
"""

import os
import json
import yaml
import logging
import asyncio
import multiprocessing
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("batch_processor")

class BatchProcessor:
    """
    A class for batch processing multiple Substack authors.
    
    Attributes:
        config_path (str): Path to the batch configuration file
        output_dir (str): Base output directory for all authors
        max_processes (int): Maximum number of concurrent processes
        config (Dict): The loaded configuration
    """
    
    def __init__(
        self,
        config_path: str,
        output_dir: str = "output",
        max_processes: int = 2
    ):
        """
        Initialize the BatchProcessor.
        
        Args:
            config_path (str): Path to the batch configuration file (JSON or YAML)
            output_dir (str, optional): Base output directory. Defaults to "output".
            max_processes (int, optional): Maximum number of concurrent processes. Defaults to 2.
        """
        self.config_path = config_path
        self.output_dir = output_dir
        self.max_processes = max_processes
        self.config = self._load_config()
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load the batch configuration from a file.
        
        Returns:
            Dict[str, Any]: The loaded configuration
        
        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            ValueError: If the configuration file format is invalid
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        # Determine file format based on extension
        file_ext = os.path.splitext(self.config_path)[1].lower()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if file_ext == '.json':
                    config = json.load(f)
                elif file_ext in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                else:
                    raise ValueError(f"Unsupported configuration file format: {file_ext}")
            
            # Validate the configuration
            self._validate_config(config)
            
            return config
        
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format in configuration file: {self.config_path}")
        except yaml.YAMLError:
            raise ValueError(f"Invalid YAML format in configuration file: {self.config_path}")
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate the batch configuration.
        
        Args:
            config (Dict[str, Any]): The configuration to validate
        
        Raises:
            ValueError: If the configuration is invalid
        """
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")
        
        if "authors" not in config:
            raise ValueError("Configuration must contain an 'authors' key")
        
        if not isinstance(config["authors"], list):
            raise ValueError("The 'authors' key must be a list")
        
        for i, author in enumerate(config["authors"]):
            if not isinstance(author, dict):
                raise ValueError(f"Author at index {i} must be a dictionary")
            
            if "identifier" not in author:
                raise ValueError(f"Author at index {i} must have an 'identifier' key")
    
    def process_author(self, author_config: Dict[str, Any]) -> bool:
        """
        Process a single author.
        
        Args:
            author_config (Dict[str, Any]): The author configuration
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            from src.core.substack_direct_downloader import SubstackDirectDownloader
            import asyncio
            
            # Extract author configuration
            author_id = author_config["identifier"]
            output_dir = author_config.get("output_dir", os.path.join(self.output_dir, author_id))
            max_posts = author_config.get("max_posts", None)
            include_comments = author_config.get("include_comments", False)
            download_images = not author_config.get("no_images", False)
            use_sitemap = not author_config.get("no_sitemap", False)
            token = author_config.get("token", None)
            incremental = author_config.get("incremental", False)
            force = author_config.get("force", False)
            verbose = author_config.get("verbose", False)
            min_delay = author_config.get("min_delay", 0.5)
            max_delay = author_config.get("max_delay", 5.0)
            max_concurrency = author_config.get("max_concurrency", 5)
            max_image_concurrency = author_config.get("max_image_concurrency", 10)
            
            # Set up logging level
            if verbose:
                logger.setLevel(logging.DEBUG)
            
            logger.info(f"Processing author: {author_id}")
            
            # Create a new event loop for this process
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Define the async processing function
            async def process():
                async with SubstackDirectDownloader(
                    author=author_id,
                    output_dir=output_dir,
                    min_delay=min_delay,
                    max_delay=max_delay,
                    max_concurrency=max_concurrency,
                    max_image_concurrency=max_image_concurrency,
                    verbose=verbose,
                    incremental=incremental,
                    use_sitemap=use_sitemap,
                    include_comments=include_comments
                ) as downloader:
                    # Set authentication token if provided
                    if token:
                        downloader.set_auth_token(token)
                    
                    # Find and download all posts
                    post_urls = await downloader.find_post_urls()
                    
                    # Limit the number of posts if specified
                    if max_posts and len(post_urls) > max_posts:
                        logger.info(f"Limiting to {max_posts} posts (found {len(post_urls)})")
                        post_urls = post_urls[:max_posts]
                    
                    logger.info(f"Found {len(post_urls)} posts to download for {author_id}")
                    
                    # Download each post
                    success_count = 0
                    skipped_count = 0
                    failed_count = 0
                    
                    for i, url in enumerate(post_urls):
                        logger.info(f"Downloading post {i+1}/{len(post_urls)}: {url}")
                        
                        result = await downloader.download_post(
                            url=url,
                            force=force,
                            download_images=download_images
                        )
                        
                        if result == "skipped":
                            logger.info(f"Skipped post: {url}")
                            skipped_count += 1
                        elif result:
                            logger.info(f"Successfully downloaded post: {url}")
                            success_count += 1
                        else:
                            logger.error(f"Failed to download post: {url}")
                            failed_count += 1
                    
                    # Print summary
                    logger.info(f"Download complete for {author_id}: {success_count} successful, {skipped_count} skipped, {failed_count} failed")
                    
                    return success_count > 0
            
            # Run the async function in the new event loop
            result = loop.run_until_complete(process())
            
            # Close the event loop
            loop.close()
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing author {author_config.get('identifier', 'unknown')}: {e}")
            return False
    
    def process_all(self) -> Dict[str, bool]:
        """
        Process all authors in the configuration.
        
        Returns:
            Dict[str, bool]: A dictionary mapping author identifiers to success status
        """
        results = {}
        
        # Get the list of authors
        authors = self.config.get("authors", [])
        
        if not authors:
            logger.warning("No authors found in configuration")
            return results
        
        logger.info(f"Processing {len(authors)} authors with {self.max_processes} processes")
        
        # Use multiprocessing to process authors in parallel
        if self.max_processes > 1 and len(authors) > 1:
            # Create a pool of workers
            with multiprocessing.Pool(processes=min(self.max_processes, len(authors))) as pool:
                # Process each author in parallel
                results_list = pool.map(self.process_author, authors)
                
                # Map results to author identifiers
                for author, result in zip(authors, results_list):
                    results[author["identifier"]] = result
        else:
            # Process authors sequentially
            for author in authors:
                results[author["identifier"]] = self.process_author(author)
        
        # Print summary
        success_count = sum(1 for result in results.values() if result)
        logger.info(f"Batch processing complete: {success_count}/{len(authors)} authors processed successfully")
        
        return results


def create_example_config(output_path: str) -> None:
    """
    Create an example batch configuration file.
    
    Args:
        output_path (str): Path to save the example configuration
    """
    example_config = {
        "authors": [
            {
                "identifier": "mattstoller",
                "output_dir": "output/mattstoller",
                "max_posts": 10,
                "include_comments": True,
                "no_images": False,
                "incremental": True,
                "verbose": True
            },
            {
                "identifier": "tradecompanion",
                "max_posts": 5,
                "include_comments": False,
                "token": "your-auth-token-here"
            },
            {
                "identifier": "another-author",
                "max_concurrency": 10,
                "max_image_concurrency": 20
            }
        ],
        "global_settings": {
            "min_delay": 1.0,
            "max_delay": 5.0,
            "max_concurrency": 5,
            "max_image_concurrency": 10
        }
    }
    
    # Determine file format based on extension
    file_ext = os.path.splitext(output_path)[1].lower()
    
    with open(output_path, 'w', encoding='utf-8') as f:
        if file_ext == '.json':
            json.dump(example_config, f, indent=2)
        elif file_ext in ['.yaml', '.yml']:
            yaml.dump(example_config, f, default_flow_style=False)
        else:
            raise ValueError(f"Unsupported configuration file format: {file_ext}")
    
    logger.info(f"Example configuration saved to {output_path}")


# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch process multiple Substack authors")
    parser.add_argument("--config", required=True, help="Path to batch configuration file")
    parser.add_argument("--output", default="output", help="Base output directory")
    parser.add_argument("--processes", type=int, default=2, help="Maximum number of concurrent processes")
    parser.add_argument("--create-example", action="store_true", help="Create an example configuration file")
    
    args = parser.parse_args()
    
    if args.create_example:
        create_example_config(args.config)
    else:
        processor = BatchProcessor(
            config_path=args.config,
            output_dir=args.output,
            max_processes=args.processes
        )
        
        processor.process_all()
