# Substack Downloader Scripts

This directory contains scripts for downloading content from Substack newsletters and managing Substack authentication.

## Trade Companion Downloader

The `download_all_trade_companion.py` script downloads all posts from the Trade Companion Substack newsletter with robust error handling and self-healing capabilities.

### Features

- Downloads all posts from Trade Companion Substack
- Downloads and properly links all images
- Includes proper metadata in each post
- Implements robust exception handling
- Adds retry mechanisms with exponential backoff for network failures
- Resume capability to continue from where it left off if interrupted
- Validates downloaded content and retries if validation fails
- Comprehensive logging system to track progress and errors
- Progress tracking with percentage complete
- Summary report of downloaded posts
- Option to force refresh already downloaded posts
- Configurable parameters (retry count, delay, etc.)
- Checkpointing to save state between runs

### Usage

```bash
python scripts/download_all_trade_companion.py [OPTIONS]
```

### Options

- `--force`: Force refresh of already downloaded posts
- `--verbose`: Enable verbose output
- `--max-retries N`: Set maximum number of retry attempts (default: 5)
- `--retry-delay N`: Set initial retry delay in seconds (default: 2)
- `--skip-images`: Skip downloading images
- `--checkpoint-interval N`: Number of posts to process before saving checkpoint (default: 5)
- `--private`: Indicate that the posts are private and require authentication

### Authentication

For private posts, the script uses authentication credentials from the `.env` file. Make sure to set the following variables:

```
SUBSTACK_EMAIL=your_email@example.com
SUBSTACK_PASSWORD=your_password
# or
SUBSTACK_TOKEN=your_token
```

### Output

The script saves all downloaded posts to the `output/tradecompanion` directory. Each post is saved as a Markdown file with the following naming convention:

```
YYYY-MM-DD_Post_Title.md
```

The Markdown files include front matter with metadata (title, subtitle, author, date, original URL) and the post content converted to Markdown.

### Logs

The script logs its progress to both the console and a log file at `scripts/trade_companion_download.log`.

### Checkpoints

The script saves checkpoint data to `scripts/trade_companion_checkpoint.json` to allow resuming interrupted downloads.

### Examples

Download all posts with verbose output:
```bash
python scripts/download_all_trade_companion.py --verbose
```

Download all posts, including private ones:
```bash
python scripts/download_all_trade_companion.py --private
```

Force refresh all posts:
```bash
python scripts/download_all_trade_companion.py --force
```

Download all posts with custom retry settings:
```bash
python scripts/download_all_trade_companion.py --max-retries 10 --retry-delay 5
```

## Substack Token Extractor

The `get_substack_token.py` script automates the process of obtaining a Substack authentication token. It can use multiple methods to extract the token and updates the `.env` file with the new token.

### Features

- Multiple extraction methods:
  - Direct HTTP requests to Substack's API
  - Browser automation with Selenium
  - Browser automation with Pyppeteer
  - Manual cookie input
- Extracts authentication token from cookies or local storage
- Updates the `.env` file with the new token
- Provides detailed logging of the extraction process
- Graceful error handling with fallback to alternative methods

### Usage

```bash
python scripts/get_substack_token.py [OPTIONS]
```

### Options

- `--email EMAIL`: Substack account email (if not provided, will use SUBSTACK_EMAIL from .env)
- `--password PASSWORD`: Substack account password (if not provided, will use SUBSTACK_PASSWORD from .env)
- `--env-file ENV_FILE`: Path to the .env file (default: .env)
- `--headless`: Run browser in headless mode (no GUI)
- `--method METHOD`: Method to use for extraction: http, selenium, puppeteer, auto, or manual (default: auto)
- `--cookie COOKIE`: Manually provide a cookie string containing substack.sid (for manual method)

### Requirements

For browser automation methods, you'll need either Selenium or Pyppeteer:

```bash
pip install selenium pyppeteer
```

For Selenium, you also need a WebDriver for your browser. See: https://www.selenium.dev/documentation/webdriver/getting_started/install_drivers/

### Examples

Extract token using credentials from .env file (tries all methods):
```bash
python scripts/get_substack_token.py
```

Extract token with specific credentials:
```bash
python scripts/get_substack_token.py --email your_email@example.com --password your_password
```

Extract token in headless mode:
```bash
python scripts/get_substack_token.py --headless
```

Extract token using HTTP method only:
```bash
python scripts/get_substack_token.py --method http
```

Extract token using Selenium method only:
```bash
python scripts/get_substack_token.py --method selenium
```

Extract token using manual cookie input:
```bash
python scripts/get_substack_token.py --method manual --cookie "substack.sid=your_token_here"
```

### Manual Token Extraction

If automatic methods fail, you can manually extract the token from your browser:

1. Log in to Substack in your browser
2. Open the browser's developer tools (F12 or right-click > Inspect)
3. Go to the 'Application' or 'Storage' tab
4. Look for 'Cookies' > 'substack.com'
5. Find the 'substack.sid' cookie and copy its value
6. Run the script with the manual method:
   ```bash
   python scripts/get_substack_token.py --method manual --cookie "substack.sid=your_token_here"
   ```
