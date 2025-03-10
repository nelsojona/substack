#!/usr/bin/env python3
"""
Fetch and parse sitemap.xml from a Substack site to extract all post URLs.
"""

import sys
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

def fetch_sitemap(url):
    """Fetch sitemap.xml and return the content."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching sitemap: {e}")
        sys.exit(1)

def parse_sitemap(content):
    """Parse sitemap XML content and extract post URLs."""
    # Parse XML
    try:
        # Remove namespace to simplify parsing
        content = content.replace(' xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"', '')
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        sys.exit(1)
    
    # Extract URLs
    urls = []
    for url_element in root.findall(".//url/loc"):
        urls.append(url_element.text)
    
    return urls

def filter_post_urls(urls, base_domain):
    """Filter URLs to include only post URLs from the specified domain."""
    post_urls = []
    for url in urls:
        parsed_url = urlparse(url)
        if parsed_url.netloc == base_domain and "/p/" in parsed_url.path:
            post_urls.append(url)
    
    return post_urls

def main():
    """Main function to fetch and parse sitemap."""
    # Get Substack URL from command line or use default
    substack_url = "https://tradecompanion.substack.com"
    
    # Extract domain from URL
    parsed_url = urlparse(substack_url)
    base_domain = parsed_url.netloc
    
    # Construct sitemap URL
    sitemap_url = f"{substack_url}/sitemap.xml"
    
    print(f"Fetching sitemap from: {sitemap_url}")
    
    # Fetch sitemap
    sitemap_content = fetch_sitemap(sitemap_url)
    
    # Parse sitemap
    all_urls = parse_sitemap(sitemap_content)
    
    # Filter post URLs
    post_urls = filter_post_urls(all_urls, base_domain)
    
    # Print results
    print(f"Total URLs in sitemap: {len(all_urls)}")
    print(f"Total post URLs: {len(post_urls)}")
    
    # Print sample of post URLs
    print("\nSample of post URLs:")
    for url in post_urls[:10]:
        print(f"  {url}")
    
    # Save all post URLs to file
    output_file = "tradecompanion_posts.txt"
    with open(output_file, "w") as f:
        for url in post_urls:
            f.write(f"{url}\n")
    
    print(f"\nAll post URLs saved to: {output_file}")

if __name__ == "__main__":
    main()