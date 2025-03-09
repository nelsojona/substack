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
git clone https://github.com/yourusername/substack-to-markdown.git
cd substack-to-markdown

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

The most basic command requires only the author's identifier:

```bash
python substack_to_md.py --author <author_identifier>
```

Where `<author_identifier>` is the Substack author's username or subdomain (e.g., "mattstoller" for "mattstoller.substack.com").

### Command Structure

The general command structure is:

```bash
python substack_to_md.py --author <author> [options]
```

### Common Usage Patterns

#### 1. Basic Fetching

Fetch all posts from a specific author and save them to the current directory:

```bash
python substack_to_md.py --author mattstoller
```

#### 2. Specifying Output Location

Save posts to a specific directory:

```bash
python substack_to_md.py --author mattstoller --output ./my_posts
```

#### 3. Limiting Post Count

Fetch only the 5 most recent posts:

```bash
python substack_to_md.py --author mattstoller --limit 5
```

#### 4. Detailed Output

Enable verbose mode to see detailed progress information:

```bash
python substack_to_md.py --author mattstoller --verbose
```

#### 5. Single Post Processing

Process a specific post by its URL:

```bash
python substack_to_md.py --author mattstoller --url https://mattstoller.substack.com/p/how-to-get-rich-sabotaging-nuclear
```

Or by its slug:

```bash
python substack_to_md.py --author mattstoller --slug how-to-get-rich-sabotaging-nuclear
```

#### 6. Enhanced Mode

Use direct Post object methods for better integration with the Substack API:

```bash
python substack_to_md.py --author mattstoller --use-post-objects
```

### Downloading Images

Download and embed images locally:

```bash
python substack_to_md.py --author mattstoller --download-images
```

Specify a custom directory for downloaded images:

```bash
python substack_to_md.py --author mattstoller --download-images --image-dir ./images/mattstoller
```

Use a base URL for image references (useful for web publishing):

```bash
python substack_to_md.py --author mattstoller --download-images --image-base-url https://example.com/images
```

Control the number of concurrent image downloads:

```bash
python substack_to_md.py --author mattstoller --download-images --max-image-workers 8
```

### Accessing Private Content

To access private/subscriber-only content, you need to authenticate with Substack. The tool supports several authentication methods:

#### Using Email and Password

```bash
python substack_to_md.py --author mattstoller --email your-email@example.com --password your-password --private --url https://mattstoller.substack.com/p/private-post-slug
```

#### Using Authentication Token

```bash
python substack_to_md.py --author mattstoller --token your-auth-token --private --url https://mattstoller.substack.com/p/private-post-slug
```

#### Using Cookies File

```bash
python substack_to_md.py --author mattstoller --cookies-file path/to/cookies.txt --private --url https://mattstoller.substack.com/p/private-post-slug
```

#### Saving Cookies for Future Use

```bash
python substack_to_md.py --author mattstoller --email your-email@example.com --password your-password --save-cookies path/to/cookies.txt --private --url https://mattstoller.substack.com/p/private-post-slug
```

### Command-line Arguments

| Argument | Description | Required | Default |
|----------|-------------|----------|---------|
| `--author` | Substack author identifier (username or subdomain) | Yes | - |
| `--output` | Output directory for Markdown files | No | Current directory |
| `--limit` | Maximum number of posts to fetch | No | All posts |
| `--verbose` | Enable verbose output | No | False |
| `--use-post-objects` | Use enhanced mode with direct Post object methods | No | False |
| `--url` | Process a single post by URL | No | - |
| `--slug` | Process a single post by slug | No | - |

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

- Support for fetching post comments
- Newsletter metadata extraction
- Improved authenticated access to private content
- Concurrent fetching for improved performance
- Support for exporting subscriber-only content
- Custom Markdown templates
- Batch processing for multiple authors
- Filtering posts by date range
- Export to other formats (e.g., PDF, HTML)
- Integration with Oxylabs for proxying requests to avoid rate limiting

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
