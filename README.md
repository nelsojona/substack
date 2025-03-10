# Substack to Markdown CLI

A command-line tool that fetches posts from Substack using the Substack API wrapper and converts them to Markdown format.

## Overview

This tool allows you to easily download and convert Substack posts to Markdown format, making it useful for:

- Creating local backups of your Substack content
- Migrating content to other platforms
- Analyzing or processing Substack content offline
- Archiving posts in a portable, plain-text format
- Accessing and converting private/subscriber-only content

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Install from source

```bash
# Clone the repository
git clone https://github.com/nelsojona/substack.git
cd substack

# Install dependencies
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env
# Edit .env file with your credentials and configuration
```

### Environment Variables

The tool supports loading configuration from environment variables using a `.env` file. This is especially useful for storing sensitive information like authentication credentials and proxy configuration.

To use environment variables:

1. Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file with your credentials and configuration:
   ```
   # Substack Authentication
   SUBSTACK_EMAIL=your-email@example.com
   SUBSTACK_PASSWORD=your-password
   SUBSTACK_TOKEN=your-auth-token

   # Oxylabs Proxy Configuration
   OXYLABS_USERNAME=your-username
   OXYLABS_PASSWORD=your-password
   OXYLABS_COUNTRY=US
   OXYLABS_CITY=new_york
   OXYLABS_STATE=us_new_york
   OXYLABS_SESSION_ID=random-session-id
   OXYLABS_SESSION_TIME=10

   # General Configuration
   DEFAULT_OUTPUT_DIR=./markdown_output
   DEFAULT_IMAGE_DIR=./images
   DEFAULT_MAX_IMAGE_WORKERS=4
   DEFAULT_IMAGE_TIMEOUT=10
   ```

3. The tool will automatically load these environment variables when run.

Note: Command-line arguments take precedence over environment variables.

## CLI Instructions

The Substack to Markdown tool provides a comprehensive command-line interface (CLI) for converting Substack posts to Markdown format. Here's how to use it effectively:

### Basic Usage

There are multiple scripts available with different capabilities:

#### 1. Standard Converter

```bash
python substack_to_md.py --author <author_identifier>
```

#### 2. Direct Downloader (Recommended)

The direct downloader offers better performance and uses sitemap.xml for more reliable post discovery:

```bash
python substack_direct_downloader.py --author <author_identifier>
```

#### 3. Optimized CLI

```bash
python optimized_substack_cli.py download --author <author_identifier>
```

Where `<author_identifier>` is the Substack author's username or subdomain (e.g., "big" for "big.substack.com" which is Matt Stoller's BIG newsletter).

### Command Structure

The general command structure for the direct downloader:

```bash
python substack_direct_downloader.py --author <author> [options]
```

### Common Usage Patterns

The examples below use the recommended `substack_direct_downloader.py` script.

#### 1. Basic Fetching

Fetch all posts from a specific author and save them to the default output directory:

```bash
python substack_direct_downloader.py --author big
```

#### 2. Specifying Output Location

Save posts to a specific directory:

```bash
python substack_direct_downloader.py --author big --output ./my_posts
```

#### 3. Limiting Post Count

Fetch only the 5 most recent posts:

```bash
python substack_direct_downloader.py --author big --max-posts 5
```

#### 4. Detailed Output

Enable verbose mode to see detailed progress information:

```bash
python substack_direct_downloader.py --author big --verbose
```

#### 5. Single Post Processing

Process a specific post by its URL:

```bash
python substack_direct_downloader.py --author big --url https://big.substack.com/p/how-to-get-rich-sabotaging-nuclear
```

#### 6. Using Sitemap for Efficient Post Discovery

By default, the direct downloader uses sitemap.xml for efficient post discovery. You can disable this feature if needed:

```bash
python substack_direct_downloader.py --author big --no-sitemap
```

#### 7. Controlling Concurrency

Adjust the number of concurrent downloads for better performance:

```bash
python substack_direct_downloader.py --author big --max-concurrency 10 --max-image-concurrency 20
```

#### 8. Force Refresh

Force refresh existing posts:

```bash
python substack_direct_downloader.py --author big --force
```

### Handling Images

By default, the direct downloader saves images locally. You can disable this:

```bash
python substack_direct_downloader.py --author big --no-images
```

Control the number of concurrent image downloads:

```bash
python substack_direct_downloader.py --author big --max-image-concurrency 15
```

### Including Comments

To include post comments in the Markdown output:

```bash
python substack_direct_downloader.py --author big --include-comments
```

This will add a "Comments" section at the end of each post with all comments and replies properly formatted.

### Accessing Private Content

To access private/subscriber-only content with the direct downloader, you can use an authentication token:

```bash
python substack_direct_downloader.py --author big --token your-auth-token --url https://big.substack.com/p/private-post-slug
```

To obtain a Substack authentication token, you can use the provided script:

```bash
python scripts/get_substack_token.py
```

This will guide you through the process of obtaining an authentication token from your browser session.

### Command-line Arguments

#### For substack_to_md.py

| Argument | Description | Required | Default |
|----------|-------------|----------|---------|
| `--author` | Substack author identifier (username or subdomain) | Yes | - |
| `--output` | Output directory for Markdown files | No | Current directory |
| `--limit` | Maximum number of posts to fetch | No | All posts |
| `--verbose` | Enable verbose output | No | False |
| `--use-post-objects` | Use enhanced mode with direct Post object methods | No | False |
| `--url` | Process a single post by URL | No | - |
| `--slug` | Process a single post by slug | No | - |
| `--async-mode` | Use async/aiohttp for downloading | No | False |
| `--processes` | Number of processes to use for multiprocessing | No | 2 |
| `--min-delay` | Minimum delay between requests in seconds | No | 0.5 |
| `--max-delay` | Maximum delay between requests in seconds | No | 5.0 |
| `--incremental` | Only download new or updated content | No | False |

#### For substack_direct_downloader.py (Recommended)

| Argument | Description | Required | Default |
|----------|-------------|----------|---------|
| `--author` | Substack author identifier | No | "tradecompanion" |
| `--output` | Output directory | No | "output" |
| `--max-pages` | Maximum number of archive pages to scan | No | Scan all pages |
| `--max-posts` | Maximum number of posts to download | No | All posts |
| `--force` | Force refresh of already downloaded posts | No | False |
| `--verbose` | Enable verbose output | No | False |
| `--url` | Download a specific URL instead of scanning archive | No | - |
| `--no-images` | Skip downloading images | No | False |
| `--min-delay` | Minimum delay between requests in seconds | No | 0.5 |
| `--max-delay` | Maximum delay between requests in seconds | No | 5.0 |
| `--max-concurrency` | Maximum concurrent requests | No | 5 |
| `--max-image-concurrency` | Maximum concurrent image downloads | No | 10 |
| `--token` | Substack authentication token for private content | No | - |
| `--incremental` | Only download new or updated content | No | False |
| `--async-mode` | Use async/aiohttp for downloading | No | True |
| `--clear-cache` | Clear cache before starting | No | False |
| `--use-sitemap` | Use sitemap.xml for post discovery | No | True |
| `--no-sitemap` | Skip using sitemap.xml for post discovery | No | False |
| `--include-comments` | Include post comments in the output | No | False |

### Authentication Arguments

| Argument | Description | Required | Default |
|----------|-------------|----------|---------|
| `--email` | Substack account email | No | - |
| `--password` | Substack account password | No | - |
| `--token` | Substack authentication token | No | - |
| `--cookies-file` | Path to a file containing cookies | No | - |
| `--save-cookies` | Save cookies to a file after authentication | No | - |
| `--private` | Indicate that the post is private and requires authentication | No | False |

### Image Downloading Arguments

| Argument | Description | Required | Default |
|----------|-------------|----------|---------|
| `--download-images` | Download and embed images in the Markdown | No | False |
| `--image-dir` | Directory to save downloaded images | No | `images` |
| `--image-base-url` | Base URL for image references in Markdown | No | Relative paths |
| `--max-image-workers` | Maximum number of concurrent image downloads | No | 4 |
| `--image-timeout` | Timeout for image download requests in seconds | No | 10 |

## Features

- Fetches all posts for a specified Substack author
- Converts HTML content to Markdown format
- Preserves formatting, links, and images
- Handles pagination to retrieve all available posts
- Provides progress reporting and error handling
- Saves each post as a separate Markdown file
- Supports direct integration with the Substack API wrapper
- Allows processing individual posts by URL or slug
- Includes caching for improved performance
- Supports authenticated access to private/subscriber-only content
- Downloads and embeds images locally for offline viewing
- Extracts and includes post comments with proper threading
- Extracts newsletter metadata for better organization
- Utilizes optimized performance with async, multiprocessing, and adaptive throttling
- Offers incremental sync to efficiently update content
- Implements robust error handling and recovery mechanisms

## Enhanced Mode

The tool supports an enhanced mode that uses direct Post object methods from the Substack API wrapper. This mode provides several advantages:

- More direct integration with the Substack API
- Better error handling and retries
- Support for processing individual posts by URL or slug
- Caching of Post objects for improved performance

To use enhanced mode, add the `--use-post-objects` flag to your command:

```bash
python substack_to_md.py --author mattstoller --use-post-objects
```

## Authentication Methods

The tool supports several methods for authenticating with Substack to access private content:

### Email and Password

You can provide your Substack account email and password directly:

```bash
python substack_to_md.py --author mattstoller --email your-email@example.com --password your-password --private
```

Note: This method may not always work due to Substack's authentication flow, which may include CSRF tokens, captchas, or other security measures.

### Authentication Token

If you have a Substack authentication token, you can use it directly:

```bash
python substack_to_md.py --author mattstoller --token your-auth-token --private
```

### Cookies File

You can use a cookies file exported from your browser:

```bash
python substack_to_md.py --author mattstoller --cookies-file path/to/cookies.txt --private
```

The cookies file should be in the Mozilla/Netscape format, which can be exported using browser extensions like "Cookie Quick Manager" for Firefox or "EditThisCookie" for Chrome.

### Saving Cookies

After authenticating, you can save the cookies for future use:

```bash
python substack_to_md.py --author mattstoller --email your-email@example.com --password your-password --save-cookies path/to/cookies.txt --private
```

This will save the cookies to the specified file, which you can then use for future authentication.

## Dependencies

- [substack_api](https://github.com/NHagar/substack_api): Python wrapper for the Substack API
- [markdownify](https://github.com/matthewwithanm/python-markdownify): Library for converting HTML to Markdown
- argparse: Standard library for parsing command-line arguments
- requests: HTTP library for Python
- tqdm: Progress bar library for Python

## Error Handling

The tool includes robust error handling for:

- API connection issues
- Rate limiting
- Invalid author identifiers
- File system errors
- HTML parsing and conversion issues
- Post retrieval errors
- Authentication failures

## Future Enhancements

Planned future enhancements include:

- Custom Markdown templates
- Batch processing for multiple authors
- Filtering posts by date range
- Export to other formats (e.g., PDF, HTML)
- Integration with Oxylabs for proxying requests to avoid rate limiting
- Utility functions for working with Substack API objects
- Enhanced caching mechanism for API responses

## Performance Optimizations

The direct downloader script (`substack_direct_downloader.py`) includes several performance optimizations:

- **Sitemap-based Discovery**: Uses sitemap.xml to efficiently find all posts
- **Async/Concurrent Requests**: Uses asyncio/aiohttp for non-blocking concurrent downloads
- **Caching**: Implements caching layer to speed up repeated fetches and reduce API load
- **Adaptive Throttling**: Dynamically adjusts delays based on response times and rate limits
- **Parallel Image Processing**: Downloads images concurrently with configurable limits
- **Connection Pooling**: Reuses connections for better performance
- **Incremental Sync**: Only downloads new or updated content
- **Database Optimizations**: Uses bulk operations and indexing for faster metadata retrieval

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
