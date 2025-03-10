#!/usr/bin/env python3
"""
Compile Substack Authors' Content for LLM Use

This script finds all downloaded Substack content in the output directory,
extracts the content and metadata, and compiles it into a format optimized
for LLM context loading. The compiled data is saved in JSON format.

Usage:
    python compile_substack_for_llm.py [--output OUTPUT] [--authors AUTHORS [AUTHORS ...]]

Arguments:
    --output: Path to the output JSON file (default: substack_compiled.json)
    --authors: List of author directories to include (default: all authors)
    --max-length: Maximum character length for each post (default: 100000)
    --clean-images: Whether to replace image references with placeholders (default: True)
"""

import os
import re
import json
import argparse
import logging
from pathlib import Path
import yaml
from datetime import datetime
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('compile_substack.log')
    ]
)
logger = logging.getLogger("substack_compiler")

def parse_frontmatter(content):
    """
    Parse YAML frontmatter from markdown content
    
    Args:
        content (str): Markdown content with frontmatter
        
    Returns:
        tuple: (dict of frontmatter, content without frontmatter)
    """
    # Check if the content starts with a frontmatter delimiter
    if not content.startswith('---'):
        return {}, content
    
    # Find the second frontmatter delimiter
    end_delimiter = content.find('---', 3)
    if end_delimiter == -1:
        return {}, content
    
    # Extract the frontmatter and the content
    frontmatter_text = content[3:end_delimiter].strip()
    remaining_content = content[end_delimiter + 3:].strip()
    
    try:
        # Parse the frontmatter as YAML
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            frontmatter = {}
    except Exception as e:
        logger.warning(f"Error parsing frontmatter: {e}")
        frontmatter = {}
        
    return frontmatter, remaining_content

def clean_image_references(content, author):
    """
    Replace image references with a standardized placeholder
    
    Args:
        content (str): Markdown content with image references
        author (str): Author name for reference
        
    Returns:
        str: Content with image references replaced by placeholders
    """
    # Pattern to find markdown image references: ![alt text](path/to/image)
    pattern = r'!\[(.*?)\]\((.*?)\)'
    
    # Replace with placeholder
    replacement = r'[IMAGE: \1]'
    
    # Perform the replacement
    return re.sub(pattern, replacement, content)

def truncate_content(content, max_length=100000):
    """
    Truncate content to a maximum length
    
    Args:
        content (str): The content to truncate
        max_length (int): Maximum content length
        
    Returns:
        str: Truncated content
    """
    if len(content) > max_length:
        # Truncate and add note
        truncated = content[:max_length]
        truncated += f"\n\n[NOTE: Content truncated to {max_length} characters]"
        return truncated
    return content

def process_markdown_file(file_path, author, max_length=100000, clean_images=True):
    """
    Process a markdown file to extract metadata and content
    
    Args:
        file_path (str): Path to the markdown file
        author (str): Name of the author
        max_length (int): Maximum content length
        clean_images (bool): Whether to clean image references
        
    Returns:
        dict: Processed post data
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract filename without extension
        filename = os.path.basename(file_path)
        
        # Extract frontmatter and content
        frontmatter, markdown_content = parse_frontmatter(content)
        
        # Extract date from frontmatter or filename
        date = frontmatter.get('date', '')
        if not date and '_' in filename:
            # Try to get date from filename format: YYYY-MM-DD_slug.md
            date_part = filename.split('_')[0]
            if re.match(r'\d{4}-\d{2}-\d{2}', date_part):
                date = date_part
        
        # Extract title from frontmatter or first heading
        title = frontmatter.get('title', '')
        if not title:
            # Try to get title from first heading
            heading_match = re.search(r'^# (.*?)$', markdown_content, re.MULTILINE)
            if heading_match:
                title = heading_match.group(1)
            else:
                # Use filename as last resort
                title = filename.replace('.md', '').replace('_', ' ').title()
        
        # Clean content if requested
        if clean_images:
            markdown_content = clean_image_references(markdown_content, author)
        
        # Truncate content if necessary
        markdown_content = truncate_content(markdown_content, max_length)
        
        # Create post data structure
        post_data = {
            'title': title,
            'date': date,
            'author': author,
            'url': frontmatter.get('original_url', ''),
            'slug': os.path.basename(file_path).replace('.md', ''),
            'content': markdown_content
        }
        
        return post_data
        
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return None

def compile_author_content(author_dir, output_dir="compiled", max_length=100000, clean_images=True):
    """
    Compile all posts from an author directory
    
    Args:
        author_dir (str): Path to the author directory
        output_dir (str): Directory to save compiled output
        max_length (int): Maximum content length per post
        clean_images (bool): Whether to clean image references
        
    Returns:
        dict: Author data with all processed posts
    """
    author = os.path.basename(author_dir)
    logger.info(f"Processing author: {author}")
    
    # Find all markdown files in the author directory
    markdown_files = list(Path(author_dir).glob('*.md'))
    
    if not markdown_files:
        logger.warning(f"No markdown files found for author: {author}")
        return None
    
    # Process each file
    posts = []
    for file_path in tqdm(markdown_files, desc=f"Processing {author}'s posts"):
        post_data = process_markdown_file(
            file_path, 
            author, 
            max_length=max_length, 
            clean_images=clean_images
        )
        if post_data:
            posts.append(post_data)
    
    # Sort posts by date (newest first)
    try:
        posts.sort(key=lambda x: x.get('date', ''), reverse=True)
    except Exception as e:
        logger.warning(f"Error sorting posts by date: {e}")
    
    # Compile author data
    author_data = {
        'author': author,
        'post_count': len(posts),
        'posts': posts
    }
    
    return author_data

def main():
    """Main function to process and compile Substack content"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Compile Substack content for LLM use")
    parser.add_argument('--output', default='substack_compiled.json', help='Output JSON file path')
    parser.add_argument('--authors', nargs='+', help='List of author directories to include')
    parser.add_argument('--max-length', type=int, default=100000, help='Maximum character length for each post')
    parser.add_argument('--clean-images', action='store_true', default=True, help='Replace image references with placeholders')
    
    args = parser.parse_args()
    
    # Define input and output paths
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    output_file = args.output
    
    # Find all author directories if not specified
    if args.authors:
        author_dirs = [os.path.join(base_dir, author) for author in args.authors]
    else:
        author_dirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir) 
                      if os.path.isdir(os.path.join(base_dir, d))]
    
    # Process each author directory
    compiled_data = {
        'metadata': {
            'compiled_date': datetime.now().isoformat(),
            'author_count': len(author_dirs),
            'total_posts': 0
        },
        'authors': []
    }
    
    total_posts = 0
    
    for author_dir in author_dirs:
        author_data = compile_author_content(
            author_dir, 
            max_length=args.max_length, 
            clean_images=args.clean_images
        )
        if author_data:
            compiled_data['authors'].append(author_data)
            total_posts += author_data['post_count']
    
    # Update metadata
    compiled_data['metadata']['total_posts'] = total_posts
    
    # Save the compiled data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(compiled_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Compiled {total_posts} posts from {len(compiled_data['authors'])} authors to {output_file}")

if __name__ == "__main__":
    main()