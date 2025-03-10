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

The tool now provides a unified interface through the main.py script:

```bash
python main.py [command] [options]
```

Available commands:

#### 1. Direct Downloader (Recommended)

The direct downloader offers better performance and uses sitemap.xml for more reliable post discovery:

```bash
python main.py direct --author <author_identifier>
```

#### 2. Batch Processing

Process multiple authors in parallel using a configuration file:

```bash
python main.py batch --config <config_file_path>
```

#### 3. Optimized CLI

```bash
python main.py optimized download --author <author_identifier>
```

#### 4. Classic Interface

```bash
python main.py classic --author <author_identifier>
```

Where `<author_identifier>` is the Substack author's username or subdomain (e.g., "big" for "big.substack.com" which is Matt Stoller's BIG newsletter).

### Command Structure

The general command structure for the direct downloader:

```bash
python main.py direct --author <author> [options]
```

For batch processing:

```bash
python main.py batch --config <config_file> [options]
```

### Common Usage Patterns

The examples below use the recommended direct downloader command.

#### 1. Basic Fetching

Fetch all posts from a specific author and save them to the default output directory:

```bash
python main.py direct --author big
```

#### 2. Specifying Output Location

Save posts to a specific directory:

```bash
python main.py direct --author big --output ./my_posts
```

#### 3. Limiting Post Count

Fetch only the 5 most recent posts:

```bash
python main.py direct --author big --max-posts 5
```

#### 4. Detailed Output

Enable verbose mode to see detailed progress information:

```bash
python main.py direct --author big --verbose
```

#### 5. Single Post Processing

Process a specific post by its URL:

```bash
python main.py direct --author big --url https://big.substack.com/p/how-to-get-rich-sabotaging-nuclear
```

#### 6. Using Sitemap for Efficient Post Discovery

By default, the direct downloader uses sitemap.xml for efficient post discovery. You can disable this feature if needed:

```bash
python main.py direct --author big --no-sitemap
```

#### 7. Controlling Concurrency

Adjust the number of concurrent downloads for better performance:

```bash
python main.py direct --author big --max-concurrency 10 --max-image-concurrency 20
```

#### 8. Force Refresh

Force refresh existing posts:

```bash
python main.py direct --author big --force
```

#### 9. Filtering Posts by Date Range

Filter posts by date range:

```bash
python main.py direct --author big --start-date 2023-01-01 --end-date 2023-12-31
```

This will only download posts published between January 1, 2023 and December 31, 2023.

### Handling Images

By default, the direct downloader saves images locally. You can disable this:

```bash
python main.py direct --author big --no-images
```

Control the number of concurrent image downloads:

```bash
python main.py direct --author big --max-image-concurrency 15
```

### Including Comments

To include post comments in the Markdown output:

```bash
python main.py direct --author big --include-comments
```

This will add a "Comments" section at the end of each post with all comments and replies properly formatted.

### Accessing Private Content

To access private/subscriber-only content with the direct downloader, you can use an authentication token:

```bash
python main.py direct --author big --token your-auth-token --url https://big.substack.com/p/private-post-slug
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
| `--start-date` | Start date for filtering posts (YYYY-MM-DD) | No | - |
| `--end-date` | End date for filtering posts (YYYY-MM-DD) | No | - |

### Authentication Arguments

| Argument | Description | Required | Default |
|----------|-------------|----------|---------|
| `--email` | Substack account email | No | - |
| `--password` | Substack account password | No | - |
| `--token` | Substack authentication token | No | - |
| `--cookies-file` | Path to a file containing cookies | No | - |
| `--save-cookies` | Save cookies to a file after authentication | No | - |
| `--private` | Indicate that the post is private and requires authentication | No | False |

### Proxy Arguments

| Argument | Description | Required | Default |
|----------|-------------|----------|---------|
| `--use-proxy` | Use Oxylabs proxy for requests | No | False |
| `--proxy-username` | Oxylabs username | No | - |
| `--proxy-password` | Oxylabs password | No | - |
| `--proxy-country` | Country code for proxy (e.g., US, GB, DE) | No | - |
| `--proxy-city` | City name for proxy (e.g., london, new_york) | No | - |
| `--proxy-state` | US state for proxy (e.g., us_california, us_new_york) | No | - |
| `--proxy-session-id` | Session ID to maintain the same IP across requests | No | - |
| `--proxy-session-time` | Session time in minutes (max 30) | No | - |

### Image Downloading Arguments

| Argument | Description | Required | Default |
|----------|-------------|----------|---------|
| `--download-images` | Download and embed images in the Markdown | No | False |
| `--image-dir` | Directory to save downloaded images | No | `images` |
| `--image-base-url` | Base URL for image references in Markdown | No | Relative paths |
| `--max-image-workers` | Maximum number of concurrent image downloads | No | 4 |
| `--image-timeout` | Timeout for image download requests in seconds | No | 10 |

### Batch Processing

The batch processing feature allows you to download posts from multiple Substack authors in parallel. This is especially useful for backing up or migrating content from multiple newsletters.

#### Creating a Batch Configuration File

You can create an example configuration file with:

```bash
python main.py batch --config authors.json --create-example
```

This will generate a JSON file with the following structure:

```json
{
  "authors": [
    {
      "identifier": "mattstoller",
      "output_dir": "output/mattstoller",
      "max_posts": 10,
      "include_comments": true,
      "no_images": false,
      "incremental": true,
      "verbose": true
    },
    {
      "identifier": "tradecompanion",
      "max_posts": 5,
      "include_comments": false,
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
```

You can also use YAML format by specifying a `.yaml` or `.yml` extension:

```bash
python main.py batch --config authors.yaml --create-example
```

#### Running Batch Processing

To process all authors in the configuration file:

```bash
python main.py batch --config authors.json
```

You can specify the output directory and the number of parallel processes:

```bash
python main.py batch --config authors.json --output custom_output --processes 4
```

#### Configuration Options

Each author in the configuration can have the following options:

- `identifier` (required): The Substack author identifier
- `output_dir`: Custom output directory for this author
- `max_posts`: Maximum number of posts to download
- `include_comments`: Whether to include comments in the output
- `no_images`: Skip downloading images
- `token`: Authentication token for private content
- `incremental`: Only download new or updated content
- `force`: Force refresh of already downloaded posts
- `verbose`: Enable verbose output
- `min_delay`: Minimum delay between requests
- `max_delay`: Maximum delay between requests
- `max_concurrency`: Maximum concurrent requests
- `max_image_concurrency`: Maximum concurrent image downloads
- `no_sitemap`: Skip using sitemap.xml for post discovery

## Features

- Fetches all posts for a specified Substack author
- Filters posts by date range
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
- Supports batch processing of multiple authors in parallel
- Provides proxy support for avoiding rate limits and accessing geo-restricted content

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

## Custom Markdown Templates

The tool now supports custom Markdown templates for post conversion. This allows you to customize the format and structure of the generated Markdown files.

### Creating Templates

You can create custom templates using the `template` command:

```bash
python main.py template --create-examples --output-dir templates
```

This will create example templates in the specified directory:

- `basic.template`: A simple template with title, content, and comments
- `academic.template`: A template formatted for academic citations
- `blog.template`: A template with HTML formatting for blog posts

### Using Templates

To use a custom template when downloading posts:

```bash
python main.py direct --author big --template-dir templates --template basic
```

This will use the `basic` template from the `templates` directory for all downloaded posts.

### Template Format

Templates use the Python string.Template format with the following variables:

- `${title}`: Post title
- `${date}`: Publication date
- `${author}`: Author name
- `${url}`: Original post URL
- `${content}`: Post content in Markdown format
- `${comments}`: Post comments in Markdown format (if included)
- `${additional_frontmatter}`: Additional metadata fields

## Export to Other Formats

The tool now supports exporting Markdown files to other formats using the `convert` command:

```bash
python main.py convert --input output/big --format html --output-dir converted
```

### Supported Formats

- `html`: Export to HTML format
- `pdf`: Export to PDF format
- `epub`: Export to EPUB format

### Conversion Options

```bash
python main.py convert --input output/big/2023-01-01_post-slug.md --format pdf --title "Custom Title" --author "Custom Author" --css custom.css
```

Available options:

- `--input`: Input Markdown file or directory
- `--format`: Output format (html, pdf, epub)
- `--output-dir`: Output directory
- `--recursive`: Process directories recursively
- `--title`: Title for the output document
- `--author`: Author name for the output document
- `--css`: Path to CSS file for styling HTML and PDF output
- `--cover-image`: Path to cover image for EPUB output
- `--check-deps`: Check for required dependencies

### Dependencies

The format conversion feature requires the following external dependencies:

- [Pandoc](https://pandoc.org/installing.html): For converting Markdown to other formats
- [wkhtmltopdf](https://wkhtmltopdf.org/downloads.html): For PDF generation

You can check if these dependencies are installed:

```bash
python main.py convert --check-deps --input dummy --format html
```

## Using Proxies

The tool supports using Oxylabs proxy service to route requests through different IP addresses. This can help avoid rate limiting and access geo-restricted content.

### Basic Proxy Usage

To use a proxy with the direct downloader:

```bash
python main.py direct --author big --use-proxy --proxy-username your-username --proxy-password your-password
```

### Proxy Configuration Options

You can configure various aspects of the proxy:

```bash
# Using a specific country
python main.py direct --author big --use-proxy --proxy-username your-username --proxy-password your-password --proxy-country US

# Using a specific city
python main.py direct --author big --use-proxy --proxy-username your-username --proxy-password your-password --proxy-country GB --proxy-city london

# Using a session ID to maintain the same IP
python main.py direct --author big --use-proxy --proxy-username your-username --proxy-password your-password --proxy-session-id abc12345

# Setting a session time
python main.py direct --author big --use-proxy --proxy-username your-username --proxy-password your-password --proxy-session-id abc12345 --proxy-session-time 10
```

### Environment Variables for Proxy

You can also configure the proxy using environment variables in your `.env` file:

```
OXYLABS_USERNAME=your-username
OXYLABS_PASSWORD=your-password
OXYLABS_COUNTRY=US
OXYLABS_CITY=new_york
OXYLABS_STATE=us_new_york
OXYLABS_SESSION_ID=random-session-id
OXYLABS_SESSION_TIME=10
```

Then use the proxy without specifying credentials on the command line:

```bash
python main.py direct --author big --use-proxy
```

### Batch Processing with Proxies

You can also configure proxies in your batch configuration file:

```json
{
  "authors": [
    {
      "identifier": "mattstoller",
      "use_proxy": true,
      "proxy_country": "US"
    }
  ],
  "global_settings": {
    "use_proxy": true,
    "proxy_username": "your-username",
    "proxy_password": "your-password"
  }
}
```

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

We welcome contributions to the Substack to Markdown CLI! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute.

## Security

If you discover a security vulnerability, please follow our [security policy](SECURITY.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See the [CHANGELOG.md](CHANGELOG.md) file for details on changes between versions.
