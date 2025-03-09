#!/usr/bin/env python3
"""
Incremental Sync Module

This module provides functionality for incremental synchronization of Substack posts.
It stores the last sync timestamp and implements differential downloads.
"""

import os
import json
import time
import logging
from typing import Dict, List, Set, Any, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("incremental_sync")

class IncrementalSync:
    """
    A class for managing incremental synchronization of Substack posts.
    
    Attributes:
        author (str): Substack author name.
        cache_dir (str): Directory to store sync state.
        state_file (str): Path to the sync state file.
        last_sync (int): Timestamp of the last sync.
        synced_posts (Set[str]): Set of synced post IDs.
    """
    
    def __init__(self, author: str, cache_dir: str = ".cache"):
        """
        Initialize the IncrementalSync.
        
        Args:
            author (str): Substack author name.
            cache_dir (str, optional): Directory to store sync state. 
                                     Defaults to ".cache".
        """
        self.author = author
        self.cache_dir = cache_dir
        self.state_file = os.path.join(cache_dir, f"{author}_sync_state.json")
        self.last_sync = 0
        self.synced_posts: Set[str] = set()
        
        # Create the cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
        
        # Load the sync state
        self._load_state()
    
    def _load_state(self) -> None:
        """Load the sync state from the state file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                
                self.last_sync = state.get("last_sync", 0)
                self.synced_posts = set(state.get("synced_posts", []))
                
                logger.info(f"Loaded sync state for {self.author}: last_sync={datetime.fromtimestamp(self.last_sync).isoformat()} {len(self.synced_posts)} synced posts")
            else:
                logger.info(f"No sync state found for {self.author}, starting fresh")
        except Exception as e:
            logger.error(f"Error loading sync state: {e}")
    
    def _save_state(self) -> None:
        """Save the sync state to the state file."""
        try:
            state = {
                "last_sync": self.last_sync,
                "synced_posts": list(self.synced_posts)
            }
            
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
            
            logger.info(f"Saved sync state for {self.author}: last_sync={datetime.fromtimestamp(self.last_sync).isoformat()} {len(self.synced_posts)} synced posts")
        except Exception as e:
            logger.error(f"Error saving sync state: {e}")
    
    def get_last_sync_time(self) -> datetime:
        """
        Get the last sync time as a datetime object.
        
        Returns:
            datetime: Last sync time.
        """
        if self.last_sync == 0:
            return datetime.min
        
        return datetime.fromtimestamp(self.last_sync)
    
    def is_post_synced(self, post_id: str) -> bool:
        """
        Check if a post has been synced.
        
        Args:
            post_id (str): Post ID.
        
        Returns:
            bool: True if the post has been synced, False otherwise.
        """
        return post_id in self.synced_posts
    
    def mark_post_synced(self, post_id: str) -> None:
        """
        Mark a post as synced.
        
        Args:
            post_id (str): Post ID.
        """
        self.synced_posts.add(post_id)
    
    def filter_new_posts(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter posts to only include new or updated posts since the last sync.
        
        Args:
            posts (List[Dict[str, Any]]): List of posts.
        
        Returns:
            List[Dict[str, Any]]: List of new or updated posts.
        """
        if self.last_sync == 0:
            logger.info(f"First sync for {self.author}, including all {len(posts)} posts")
            return posts
        
        new_posts = []
        
        for post in posts:
            post_id = post.get("id")
            post_date_str = post.get("post_date")
            
            if not post_id or not post_date_str:
                continue
            
            # Parse the post date
            try:
                post_date = datetime.fromisoformat(post_date_str.replace("Z", "+00:00"))
                post_timestamp = post_date.timestamp()
            except (ValueError, TypeError):
                # If we can't parse the date, assume it's new
                post_timestamp = time.time()
            
            # Include the post if it's new or updated since the last sync
            if post_timestamp > self.last_sync or not self.is_post_synced(post_id):
                new_posts.append(post)
        
        logger.info(f"Filtered {len(posts)} posts to {len(new_posts)} new or updated posts since {datetime.fromtimestamp(self.last_sync).isoformat()}")
        
        return new_posts
    
    def update_sync_time(self) -> None:
        """Update the last sync time to the current time."""
        self.last_sync = int(time.time())
        self._save_state()
    
    def reset_sync_state(self) -> None:
        """Reset the sync state."""
        self.last_sync = 0
        self.synced_posts = set()
        self._save_state()
        logger.info(f"Reset sync state for {self.author}")
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """
        Get sync statistics.
        
        Returns:
            Dict[str, Any]: Sync statistics.
        """
        return {
            "author": self.author,
            "last_sync": self.last_sync,
            "last_sync_time": datetime.fromtimestamp(self.last_sync).isoformat(),
            "synced_posts_count": len(self.synced_posts),
            "synced_posts": list(self.synced_posts)
        }


class IncrementalSyncManager:
    """
    A class for managing multiple IncrementalSync instances.
    
    Attributes:
        cache_dir (str): Directory to store sync state.
        syncs (Dict[str, IncrementalSync]): Dictionary of IncrementalSync instances.
    """
    
    def __init__(self, cache_dir: str = ".cache"):
        """
        Initialize the IncrementalSyncManager.
        
        Args:
            cache_dir (str, optional): Directory to store sync state. 
                                     Defaults to ".cache".
        """
        self.cache_dir = cache_dir
        self.syncs: Dict[str, IncrementalSync] = {}
        
        # Create the cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
    
    def get_sync(self, author: str) -> IncrementalSync:
        """
        Get an IncrementalSync instance for an author.
        
        Args:
            author (str): Substack author name.
        
        Returns:
            IncrementalSync: IncrementalSync instance.
        """
        if author not in self.syncs:
            self.syncs[author] = IncrementalSync(author, self.cache_dir)
        
        return self.syncs[author]
    
    def reset_all_syncs(self) -> None:
        """Reset all sync states."""
        for sync in self.syncs.values():
            sync.reset_sync_state()
        
        logger.info("Reset sync state for all authors")
    
    def get_all_sync_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get sync statistics for all authors.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of sync statistics.
        """
        return {author: sync.get_sync_stats() for author, sync in self.syncs.items()}


# Example usage
def main():
    # Set up logging
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Create a sync manager
    manager = IncrementalSyncManager(cache_dir=".cache")
    
    # Get a sync for an author
    sync = manager.get_sync("example_author")
    
    # Create some example posts
    posts = [
        {
            "id": "post1",
            "title": "Post 1",
            "post_date": "2023-01-01T12:00:00Z"
        },
        {
            "id": "post2",
            "title": "Post 2",
            "post_date": "2023-01-02T12:00:00Z"
        },
        {
            "id": "post3",
            "title": "Post 3",
            "post_date": "2023-01-03T12:00:00Z"
        }
    ]
    
    # Filter new posts
    new_posts = sync.filter_new_posts(posts)
    print(f"New posts: {new_posts}")
    
    # Mark posts as synced
    for post in new_posts:
        sync.mark_post_synced(post["id"])
    
    # Update the sync time
    sync.update_sync_time()
    
    # Get sync stats
    stats = sync.get_sync_stats()
    print(f"Sync stats: {stats}")
    
    # Reset the sync state
    sync.reset_sync_state()
    
    # Get all sync stats
    all_stats = manager.get_all_sync_stats()
    print(f"All sync stats: {all_stats}")

if __name__ == "__main__":
    main()
