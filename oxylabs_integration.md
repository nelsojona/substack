# Oxylabs Integration Plan

This document outlines the plan for integrating Oxylabs proxy service with the Substack to Markdown CLI tool.

## Overview

Oxylabs is a proxy service that provides residential and datacenter proxies. Integrating with Oxylabs will allow the Substack to Markdown CLI tool to route requests through different IP addresses, which can help avoid rate limiting and access geo-restricted content.

## Implementation Steps

### 1. Add Oxylabs Configuration Options

Add the following command-line arguments to the CLI tool:

```python
# Proxy arguments
proxy_group = parser.add_argument_group('Proxy options (for using Oxylabs)')
proxy_group.add_argument('--use-proxy', action='store_true', help='Use Oxylabs proxy for requests')
proxy_group.add_argument('--proxy-username', help='Oxylabs username')
proxy_group.add_argument('--proxy-password', help='Oxylabs password')
proxy_group.add_argument('--proxy-country', help='Country code for proxy (e.g., US, GB, DE)')
proxy_group.add_argument('--proxy-city', help='City name for proxy (e.g., london, new_york)')
proxy_group.add_argument('--proxy-state', help='US state for proxy (e.g., us_california, us_new_york)')
proxy_group.add_argument('--proxy-session-id', help='Session ID to maintain the same IP across requests')
proxy_group.add_argument('--proxy-session-time', type=int, help='Session time in minutes (max 30)')
```

### 2. Create a Proxy Handler Module

Create a new module `proxy_handler.py` to handle proxy configuration and integration:

```python
import urllib.request
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class OxylabsProxyHandler:
    """
    Handler for Oxylabs proxy integration.
    """
    
    def __init__(
        self,
        username: str,
        password: str,
        country_code: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        session_id: Optional[str] = None,
        session_time: Optional[int] = None
    ):
        """
        Initialize the Oxylabs proxy handler.
        
        Args:
            username (str): Oxylabs username
            password (str): Oxylabs password
            country_code (Optional[str]): Country code in 2-letter format (e.g., US, GB)
            city (Optional[str]): City name in English (e.g., london, new_york)
            state (Optional[str]): US state name (e.g., us_california, us_new_york)
            session_id (Optional[str]): Session ID to maintain the same IP
            session_time (Optional[int]): Session time in minutes (max 30)
        """
        self.username = username
        self.password = password
        self.country_code = country_code
        self.city = city
        self.state = state
        self.session_id = session_id
        self.session_time = session_time
        
        # Build the proxy URL
        self.proxy_url = self._build_proxy_url()
        
        logger.info(f"Initialized Oxylabs proxy handler with URL: {self.proxy_url}")
    
    def _build_proxy_url(self) -> str:
        """
        Build the Oxylabs proxy URL with the provided parameters.
        
        Returns:
            str: The proxy URL
        """
        # Start with the base username
        username_parts = [f"customer-{self.username}"]
        
        # Add country code if provided
        if self.country_code:
            username_parts.append(f"cc-{self.country_code}")
        
        # Add city if provided (requires country code)
        if self.city and self.country_code:
            # Replace spaces with underscores
            city = self.city.replace(' ', '_')
            username_parts.append(f"city-{city}")
        
        # Add state if provided
        if self.state:
            username_parts.append(f"st-{self.state}")
        
        # Add session ID if provided
        if self.session_id:
            username_parts.append(f"sessid-{self.session_id}")
        
        # Add session time if provided
        if self.session_time:
            username_parts.append(f"sesstime-{self.session_time}")
        
        # Join the username parts with hyphens
        username = "-".join(username_parts)
        
        # Return the full proxy URL
        return f"http://{username}:{self.password}@pr.oxylabs.io:7777"
    
    def get_proxy_handler(self) -> urllib.request.ProxyHandler:
        """
        Get a ProxyHandler for use with urllib.
        
        Returns:
            urllib.request.ProxyHandler: The proxy handler
        """
        return urllib.request.ProxyHandler({
            'http': self.proxy_url,
            'https': self.proxy_url
        })
    
    def get_proxy_dict(self) -> Dict[str, str]:
        """
        Get a proxy dictionary for use with requests.
        
        Returns:
            Dict[str, str]: The proxy dictionary
        """
        return {
            'http': self.proxy_url,
            'https': self.proxy_url
        }
```

### 3. Modify the SubstackFetcher Class

Update the `SubstackFetcher` class to use the proxy handler:

```python
def __init__(self, use_proxy: bool = False, proxy_config: Optional[Dict[str, Any]] = None):
    """
    Initialize the SubstackFetcher.
    
    Args:
        use_proxy (bool, optional): Whether to use a proxy. Defaults to False.
        proxy_config (Optional[Dict[str, Any]], optional): Proxy configuration. Defaults to None.
    """
    self.session = requests.Session()
    self.is_authenticated = False
    
    # Set up proxy if enabled
    if use_proxy and proxy_config:
        self.proxy_handler = OxylabsProxyHandler(
            username=proxy_config.get('username'),
            password=proxy_config.get('password'),
            country_code=proxy_config.get('country_code'),
            city=proxy_config.get('city'),
            state=proxy_config.get('state'),
            session_id=proxy_config.get('session_id'),
            session_time=proxy_config.get('session_time')
        )
        
        # Apply proxy to the session
        self.session.proxies = self.proxy_handler.get_proxy_dict()
        
        logger.info("Using Oxylabs proxy for requests")
```

### 4. Update the Main Function

Modify the main function to pass proxy configuration to the SubstackFetcher:

```python
# Initialize the Substack fetcher with proxy if enabled
proxy_config = None
if args.use_proxy:
    if not args.proxy_username or not args.proxy_password:
        logger.error("Proxy username and password are required when using a proxy")
        return 1
    
    proxy_config = {
        'username': args.proxy_username,
        'password': args.proxy_password,
        'country_code': args.proxy_country,
        'city': args.proxy_city,
        'state': args.proxy_state,
        'session_id': args.proxy_session_id,
        'session_time': args.proxy_session_time
    }

fetcher = SubstackFetcher(use_proxy=args.use_proxy, proxy_config=proxy_config)
```

### 5. Update Documentation

Update the README.md file to include information about the proxy integration:

- Add a new section about using proxies
- Add examples of using the proxy options
- Update the command-line arguments table to include the proxy options

### 6. Add Tests

Create tests for the proxy integration:

- Unit tests for the OxylabsProxyHandler class
- Integration tests for the SubstackFetcher with proxy
- Mock tests to avoid actual proxy usage during testing

## Usage Examples

```bash
# Basic usage with proxy
python substack_to_md.py --author mattstoller --use-proxy --proxy-username your-username --proxy-password your-password

# Using a specific country
python substack_to_md.py --author mattstoller --use-proxy --proxy-username your-username --proxy-password your-password --proxy-country US

# Using a specific city
python substack_to_md.py --author mattstoller --use-proxy --proxy-username your-username --proxy-password your-password --proxy-country GB --proxy-city london

# Using a session ID to maintain the same IP
python substack_to_md.py --author mattstoller --use-proxy --proxy-username your-username --proxy-password your-password --proxy-session-id abc12345

# Setting a session time
python substack_to_md.py --author mattstoller --use-proxy --proxy-username your-username --proxy-password your-password --proxy-session-id abc12345 --proxy-session-time 10
```

## Dependencies

- requests: For making HTTP requests with proxy support
- urllib.request: For building the proxy handler

## Security Considerations

- Proxy credentials should be handled securely
- Use environment variables to store sensitive information like proxy credentials
- Add warnings about potential security risks of using proxies

## Environment Variables Integration

The Oxylabs proxy integration will use environment variables from the `.env` file for configuration. The following environment variables will be used:

```
# Oxylabs Proxy Configuration
OXYLABS_USERNAME=your-username
OXYLABS_PASSWORD=your-password
OXYLABS_COUNTRY=US
OXYLABS_CITY=new_york
OXYLABS_STATE=us_new_york
OXYLABS_SESSION_ID=random-session-id
OXYLABS_SESSION_TIME=10
```

The `env_loader.py` module provides functions to load these environment variables:

```python
from env_loader import load_env_vars, get_oxylabs_config

# Load environment variables from .env file
load_env_vars()

# Get Oxylabs proxy configuration
proxy_config = get_oxylabs_config()

# Initialize the SubstackFetcher with proxy configuration
fetcher = SubstackFetcher(use_proxy=True, proxy_config=proxy_config)
```

Command-line arguments will take precedence over environment variables, allowing users to override the configuration when needed.
