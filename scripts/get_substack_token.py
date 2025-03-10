#!/usr/bin/env python3
"""
Substack Token Extractor

This script automates the process of obtaining a Substack authentication token.
It can use multiple methods to extract the token:
1. Direct HTTP requests to Substack's API
2. Browser automation with Selenium
3. Browser automation with Pyppeteer

The token is then saved to the .env file for use by other scripts.

Usage:
    python scripts/get_substack_token.py [--email EMAIL] [--password PASSWORD] [--env-file ENV_FILE]

Options:
    --email EMAIL       Substack account email (if not provided, will use SUBSTACK_EMAIL from .env)
    --password PASSWORD Substack account password (if not provided, will use SUBSTACK_PASSWORD from .env)
    --env-file ENV_FILE Path to the .env file (default: .env)
    --headless          Run browser in headless mode (no GUI)
    --method METHOD     Method to use for extraction: http, selenium, puppeteer, or auto (default: auto)
"""

import os
import sys
import time
import argparse
import logging
import re
import json
import requests
from typing import Optional, Dict, Any, Tuple
from urllib.parse import unquote

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.env_loader import load_env_vars, get_substack_auth, get_env_var

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("substack_token_extractor")

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        argparse.Namespace: The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description='Extract Substack authentication token')
    parser.add_argument('--email', help='Substack account email')
    parser.add_argument('--password', help='Substack account password')
    parser.add_argument('--env-file', default='.env', help='Path to the .env file')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--method', choices=['http', 'selenium', 'puppeteer', 'auto', 'manual', 'headers'], default='auto',
                        help='Method to use for extraction: http, selenium, puppeteer, auto, manual, or headers (default: auto)')
    parser.add_argument('--cookie', help='Manually provide a cookie string containing substack.sid')
    parser.add_argument('--headers', help='Manually provide raw HTTP headers containing substack.sid')
    parser.add_argument('--headers-file', help='Path to a file containing raw HTTP headers')
    parser.add_argument('--test-token', action='store_true', help='Test the extracted token by making an authenticated request')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    return parser.parse_args()

def update_env_file(env_file: str, token: str) -> bool:
    """
    Update the .env file with the new Substack token.
    
    Args:
        env_file (str): Path to the .env file.
        token (str): The Substack authentication token.
    
    Returns:
        bool: True if the .env file was updated successfully, False otherwise.
    """
    try:
        # Read the current .env file
        with open(env_file, 'r', encoding='utf-8') as f:
            env_content = f.read()
        
        # Check if SUBSTACK_TOKEN already exists
        if 'SUBSTACK_TOKEN=' in env_content:
            # Replace the existing token
            env_content = re.sub(
                r'SUBSTACK_TOKEN=.*',
                f'SUBSTACK_TOKEN={token}',
                env_content
            )
        else:
            # Add the token to the file
            if env_content and not env_content.endswith('\n'):
                env_content += '\n'
            env_content += f'SUBSTACK_TOKEN={token}\n'
        
        # Write the updated content back to the .env file
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        logger.info(f"Updated {env_file} with new Substack token")
        return True
    
    except Exception as e:
        logger.error(f"Error updating {env_file}: {e}")
        return False

def extract_token_from_headers(headers_text: str) -> Optional[str]:
    """
    Extract Substack authentication token from HTTP headers.
    
    Args:
        headers_text (str): HTTP headers text.
    
    Returns:
        Optional[str]: The Substack authentication token, or None if extraction failed.
    """
    try:
        # Look for the set-cookie header with substack.sid
        for line in headers_text.splitlines():
            if 'set-cookie:' in line.lower() and 'substack.sid=' in line:
                # Extract the token value
                cookie_part = line.split('substack.sid=')[1].split(';')[0]
                token = unquote(cookie_part)
                logger.info("Successfully extracted Substack token from headers")
                return token
        
        logger.warning("Could not find substack.sid in headers")
        return None
    
    except Exception as e:
        logger.error(f"Error extracting token from headers: {e}")
        return None

def extract_token_with_http(email: str, password: str) -> Optional[str]:
    """
    Extract Substack authentication token using direct HTTP requests.
    
    Args:
        email (str): Substack account email.
        password (str): Substack account password.
    
    Returns:
        Optional[str]: The Substack authentication token, or None if extraction failed.
    """
    logger.info("Attempting to extract token using direct HTTP requests...")
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    # Set headers to mimic a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://substack.com/',
        'Origin': 'https://substack.com',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
    }
    
    try:
        # Step 1: Get the sign-in page to get any initial cookies
        logger.info("Fetching sign-in page...")
        response = session.get('https://substack.com/sign-in', headers=headers)
        response.raise_for_status()
        
        # Step 2: Submit email
        logger.info(f"Submitting email: {email}")
        email_data = {
            'email': email,
            'redirect': '/home',
            'for_pub': '',
            'captcha_response': '',
            'captcha_token': ''
        }
        response = session.post(
            'https://substack.com/api/v1/login/email',
            headers={**headers, 'Content-Type': 'application/json'},
            json=email_data
        )
        response.raise_for_status()
        
        # Step 3: Submit password
        logger.info("Submitting password")
        password_data = {
            'email': email,
            'password': password,
            'captcha_response': '',
            'captcha_token': ''
        }
        response = session.post(
            'https://substack.com/api/v1/login',
            headers={**headers, 'Content-Type': 'application/json'},
            json=password_data,
            allow_redirects=False  # Don't follow redirects to capture the Set-Cookie header
        )
        
        # Check if login was successful (should get a 302 redirect)
        if response.status_code in (200, 302):
            logger.info("Login successful")
            
            # Extract the token from cookies
            for cookie in session.cookies:
                if cookie.name == 'substack.sid':
                    token = cookie.value
                    logger.info("Successfully extracted Substack token from cookies")
                    return token
            
            # If not found in cookies, check the Set-Cookie header
            if 'Set-Cookie' in response.headers:
                cookies = response.headers.get('Set-Cookie')
                match = re.search(r'substack\.sid=([^;]+)', cookies)
                if match:
                    token = match.group(1)
                    logger.info("Successfully extracted Substack token from Set-Cookie header")
                    return token
            
            logger.warning("Could not find substack.sid in cookies or headers")
        else:
            logger.error(f"Login failed with status code: {response.status_code}")
        
        return None
    
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request error: {e}")
        return None
    
    except Exception as e:
        logger.error(f"Error extracting token with HTTP: {e}")
        return None

def extract_token_with_selenium(email: str, password: str, headless: bool = False) -> Optional[str]:
    """
    Extract Substack authentication token using Selenium.
    
    Args:
        email (str): Substack account email.
        password (str): Substack account password.
        headless (bool, optional): Run browser in headless mode. Defaults to False.
    
    Returns:
        Optional[str]: The Substack authentication token, or None if extraction failed.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
    except ImportError:
        logger.error("Selenium is not installed. Please install it with: pip install selenium")
        logger.error("You also need a WebDriver for your browser. See: https://www.selenium.dev/documentation/webdriver/getting_started/install_drivers/")
        return None
    
    logger.info("Launching browser with Selenium...")
    
    # Set up browser options
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless=new')  # Updated headless mode
        options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,800')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Initialize the browser
    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        logger.error(f"Error initializing Chrome WebDriver: {e}")
        logger.error("Make sure you have Chrome and ChromeDriver installed.")
        return None
    
    token = None
    
    try:
        # Navigate to Substack login page
        driver.get('https://substack.com/sign-in')
        logger.info("Navigated to Substack login page")
        
        # Wait for the page to load
        time.sleep(2)
        
        # Wait for the email input field to be visible
        wait = WebDriverWait(driver, 20)
        
        try:
            # Try different selectors for the email input
            try:
                email_input = wait.until(EC.visibility_of_element_located((By.ID, 'email')))
            except (TimeoutException, NoSuchElementException):
                email_input = wait.until(EC.visibility_of_element_located((By.NAME, 'email')))
            except (TimeoutException, NoSuchElementException):
                email_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[type="email"]')))
            
            # Enter email
            email_input.clear()
            email_input.send_keys(email)
            logger.info(f"Entered email: {email}")
            
            # Try different selectors for the continue button
            try:
                continue_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
            except NoSuchElementException:
                continue_button = driver.find_element(By.XPATH, "//button[contains(text(), 'continue')]")
            except NoSuchElementException:
                continue_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            
            # Click the Continue button
            continue_button.click()
            logger.info("Clicked Continue button")
            
            # Wait for the password input field to be visible
            time.sleep(2)
            try:
                password_input = wait.until(EC.visibility_of_element_located((By.ID, 'password')))
            except (TimeoutException, NoSuchElementException):
                password_input = wait.until(EC.visibility_of_element_located((By.NAME, 'password')))
            except (TimeoutException, NoSuchElementException):
                password_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[type="password"]')))
            
            # Enter password
            password_input.clear()
            password_input.send_keys(password)
            logger.info("Entered password")
            
            # Try different selectors for the sign in button
            try:
                sign_in_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Sign in')]")
            except NoSuchElementException:
                sign_in_button = driver.find_element(By.XPATH, "//button[contains(text(), 'sign in')]")
            except NoSuchElementException:
                sign_in_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            
            # Click the Sign In button
            sign_in_button.click()
            logger.info("Clicked Sign In button")
            
            # Wait for login to complete
            time.sleep(5)  # Give it some time to process the login
            
            # Check if login was successful
            current_url = driver.current_url
            if 'substack.com/home' in current_url or 'substack.com/inbox' in current_url or 'substack.com/account' in current_url:
                logger.info(f"Login successful, redirected to {current_url}")
            else:
                logger.warning(f"Login might have failed, current URL: {current_url}")
            
            # Extract the token from cookies
            cookies = driver.get_cookies()
            for cookie in cookies:
                if cookie['name'] == 'substack.sid':
                    token = cookie['value']
                    logger.info("Successfully extracted Substack token from cookies")
                    break
            
            if not token:
                # Try to extract token from local storage
                try:
                    token = driver.execute_script("return localStorage.getItem('substack.authToken');")
                    if token:
                        logger.info("Successfully extracted Substack token from local storage")
                except Exception as e:
                    logger.warning(f"Error accessing local storage: {e}")
            
            # If still no token, try to extract from document.cookie
            if not token:
                try:
                    cookie_string = driver.execute_script("return document.cookie;")
                    logger.debug(f"Cookie string: {cookie_string}")
                    
                    # Parse the cookie string
                    cookies_dict = {}
                    for cookie_part in cookie_string.split(';'):
                        if '=' in cookie_part:
                            name, value = cookie_part.strip().split('=', 1)
                            cookies_dict[name] = value
                    
                    if 'substack.sid' in cookies_dict:
                        token = cookies_dict['substack.sid']
                        logger.info("Successfully extracted Substack token from document.cookie")
                except Exception as e:
                    logger.warning(f"Error extracting token from document.cookie: {e}")
            
            return token
            
        except Exception as e:
            logger.error(f"Error during login process: {e}")
            return None
    
    except Exception as e:
        logger.error(f"Error extracting Substack token: {e}")
        return None
    
    finally:
        # Close the browser
        driver.quit()
        logger.info("Browser closed")

def extract_token_with_puppeteer(email: str, password: str, headless: bool = False) -> Optional[str]:
    """
    Extract Substack authentication token using Puppeteer via pyppeteer.
    
    Args:
        email (str): Substack account email.
        password (str): Substack account password.
        headless (bool, optional): Run browser in headless mode. Defaults to False.
    
    Returns:
        Optional[str]: The Substack authentication token, or None if extraction failed.
    """
    try:
        import asyncio
        from pyppeteer import launch
    except ImportError:
        logger.error("Pyppeteer is not installed. Please install it with: pip install pyppeteer")
        return None
    
    logger.info("Launching browser with Pyppeteer...")
    
    async def extract_token_async():
        # Launch the browser
        browser = await launch(
            headless=headless, 
            args=[
                '--window-size=1280,800',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        page = await browser.newPage()
        
        try:
            # Navigate to Substack login page
            await page.goto('https://substack.com/sign-in', {'waitUntil': 'networkidle0', 'timeout': 60000})
            logger.info("Navigated to Substack login page")
            
            # Wait a bit for the page to fully load
            await asyncio.sleep(2)
            
            # Try different selectors for the email input
            try:
                await page.waitForSelector('#email', {'visible': True, 'timeout': 5000})
                email_selector = '#email'
            except Exception:
                try:
                    await page.waitForSelector('input[type="email"]', {'visible': True, 'timeout': 5000})
                    email_selector = 'input[type="email"]'
                except Exception:
                    await page.waitForSelector('input[name="email"]', {'visible': True, 'timeout': 5000})
                    email_selector = 'input[name="email"]'
            
            # Enter email
            await page.type(email_selector, email)
            logger.info(f"Entered email: {email}")
            
            # Click the Continue button
            continue_buttons = await page.xpath("//button[contains(text(), 'Continue')]")
            if continue_buttons and len(continue_buttons) > 0:
                await continue_buttons[0].click()
                logger.info("Clicked Continue button")
            else:
                # Try to find the button by type
                submit_buttons = await page.xpath("//button[@type='submit']")
                if submit_buttons and len(submit_buttons) > 0:
                    await submit_buttons[0].click()
                    logger.info("Clicked submit button")
            
            # Wait for the password input field to be visible
            await asyncio.sleep(2)
            
            try:
                await page.waitForSelector('#password', {'visible': True, 'timeout': 5000})
                password_selector = '#password'
            except Exception:
                try:
                    await page.waitForSelector('input[type="password"]', {'visible': True, 'timeout': 5000})
                    password_selector = 'input[type="password"]'
                except Exception:
                    await page.waitForSelector('input[name="password"]', {'visible': True, 'timeout': 5000})
                    password_selector = 'input[name="password"]'
            
            # Enter password
            await page.type(password_selector, password)
            logger.info("Entered password")
            
            # Click the Sign In button
            sign_in_buttons = await page.xpath("//button[contains(text(), 'Sign in')]")
            if sign_in_buttons and len(sign_in_buttons) > 0:
                await sign_in_buttons[0].click()
                logger.info("Clicked Sign In button")
            else:
                # Try to find the button by type
                submit_buttons = await page.xpath("//button[@type='submit']")
                if submit_buttons and len(submit_buttons) > 0:
                    await submit_buttons[0].click()
                    logger.info("Clicked submit button")
            
            # Wait for login to complete
            await asyncio.sleep(5)
            
            # Check if login was successful
            current_url = page.url
            if 'substack.com/home' in current_url or 'substack.com/inbox' in current_url or 'substack.com/account' in current_url:
                logger.info(f"Login successful, redirected to {current_url}")
            else:
                logger.warning(f"Login might have failed, current URL: {current_url}")
            
            # Extract the token from cookies
            cookies = await page.cookies()
            token = None
            for cookie in cookies:
                if cookie.get('name') == 'substack.sid':
                    token = cookie.get('value')
                    logger.info("Successfully extracted Substack token from cookies")
                    break
            
            if not token:
                # Try to extract token from local storage
                try:
                    token = await page.evaluate("() => localStorage.getItem('substack.authToken')")
                    if token:
                        logger.info("Successfully extracted Substack token from local storage")
                except Exception as e:
                    logger.warning(f"Error accessing local storage: {e}")
            
            # If still no token, try to extract from document.cookie
            if not token:
                try:
                    cookie_string = await page.evaluate("() => document.cookie")
                    logger.debug(f"Cookie string: {cookie_string}")
                    
                    # Parse the cookie string
                    cookies_dict = {}
                    for cookie_part in cookie_string.split(';'):
                        if '=' in cookie_part:
                            name, value = cookie_part.strip().split('=', 1)
                            cookies_dict[name] = value
                    
                    if 'substack.sid' in cookies_dict:
                        token = cookies_dict['substack.sid']
                        logger.info("Successfully extracted Substack token from document.cookie")
                except Exception as e:
                    logger.warning(f"Error extracting token from document.cookie: {e}")
            
            return token
        
        except Exception as e:
            logger.error(f"Error extracting Substack token: {e}")
            return None
        
        finally:
            # Close the browser
            await browser.close()
            logger.info("Browser closed")
    
    # Create a new event loop for this function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(extract_token_async())
    finally:
        loop.close()

def extract_token_from_cookie_string(cookie_string: str) -> Optional[str]:
    """
    Extract Substack authentication token from a cookie string.
    
    Args:
        cookie_string (str): Cookie string.
    
    Returns:
        Optional[str]: The Substack authentication token, or None if extraction failed.
    """
    try:
        # Parse the cookie string
        for cookie_part in cookie_string.split(';'):
            cookie_part = cookie_part.strip()
            if cookie_part.startswith('substack.sid='):
                token = cookie_part.split('substack.sid=')[1].strip()
                return unquote(token)
        
        # If not found in the direct format, check for URL encoded format
        match = re.search(r'substack\.sid=([^;]+)', cookie_string)
        if match:
            token = match.group(1)
            return unquote(token)
        
        return None
    
    except Exception as e:
        logger.error(f"Error extracting token from cookie string: {e}")
        return None
        
def extract_token_from_headers_string(headers_string: str) -> Optional[str]:
    """
    Extract Substack authentication token from raw HTTP headers.
    
    Args:
        headers_string (str): Raw HTTP headers string.
    
    Returns:
        Optional[str]: The Substack authentication token, or None if extraction failed.
    """
    try:
        # Look for the set-cookie header with substack.sid
        for line in headers_string.splitlines():
            line = line.strip()
            if line.lower().startswith('set-cookie:') and 'substack.sid=' in line:
                match = re.search(r'substack\.sid=([^;]+)', line)
                if match:
                    token = match.group(1)
                    logger.info("Successfully extracted Substack token from headers")
                    return unquote(token)
        
        # Also try to match in format provided by browsers
        match = re.search(r'substack\.sid=([^;]+)', headers_string)
        if match:
            token = match.group(1)
            logger.info("Successfully extracted Substack token from headers")
            return unquote(token)
        
        logger.warning("Could not find substack.sid in headers")
        return None
    
    except Exception as e:
        logger.error(f"Error extracting token from headers: {e}")
        return None

def test_token(token: str) -> bool:
    """
    Test the extracted token by making an authenticated request to Substack.
    
    Args:
        token (str): The Substack authentication token to test.
    
    Returns:
        bool: True if the token is valid, False otherwise.
    """
    try:
        # Create a session with the token
        session = requests.Session()
        
        # Set the cookie with the token
        cookie = requests.cookies.create_cookie(
            domain='.substack.com',
            name='substack.sid',
            value=token
        )
        session.cookies.set_cookie(cookie)
        
        # Set headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://substack.com/home',
            'Origin': 'https://substack.com'
        }
        
        # Make a request to an authenticated endpoint
        response = session.get('https://substack.com/api/v1/reader/user', headers=headers)
        
        # Check if the request was successful
        if response.status_code == 200:
            try:
                data = response.json()
                # Check if we got user data
                if 'email' in data:
                    logger.info(f"Token verified: authenticated as {data.get('email')}")
                    return True
                else:
                    logger.warning("Token appears valid but user data is incomplete")
                    return True  # Still consider it valid since request succeeded
            except:
                # If we can't parse JSON, but got 200, assume it's valid
                logger.warning("Received 200 response but couldn't parse JSON")
                return True
        else:
            logger.error(f"Token validation failed with status code: {response.status_code}")
            return False
    
    except Exception as e:
        logger.error(f"Error testing token: {e}")
        return False

def main():
    """Main function to run the script."""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    
    # Load environment variables
    env_file = args.env_file
    load_env_vars(env_file)
    
    # Extract token using the specified method
    token = None
    
    # Headers method - extract token from provided HTTP headers
    if args.method == 'headers' or args.headers or args.headers_file:
        if args.headers:
            logger.info("Using manually provided headers string")
            token = extract_token_from_headers_string(args.headers)
            if not token:
                logger.error("Could not extract token from provided headers string")
                if args.method == 'headers':
                    return 1
        elif args.headers_file:
            logger.info(f"Reading headers from file: {args.headers_file}")
            try:
                with open(args.headers_file, 'r', encoding='utf-8') as f:
                    headers_text = f.read()
                token = extract_token_from_headers_string(headers_text)
                if not token:
                    logger.error("Could not extract token from headers file")
                    if args.method == 'headers':
                        return 1
            except Exception as e:
                logger.error(f"Error reading headers file: {e}")
                if args.method == 'headers':
                    return 1
        else:
            logger.error("Headers method requires --headers or --headers-file parameter")
            return 1
    
    # Manual method - directly use provided cookie
    if token is None and (args.method == 'manual' or args.cookie):
        if args.cookie:
            logger.info("Using manually provided cookie string")
            token = extract_token_from_cookie_string(args.cookie)
            if not token:
                logger.error("Could not extract token from provided cookie string")
                if args.method == 'manual':
                    return 1
        else:
            logger.error("Manual method requires --cookie parameter")
            return 1
    
    # If token not extracted yet and method is not manual/headers only, try automated methods
    if token is None and args.method not in ('manual', 'headers'):
        # Get credentials
        email = args.email
        password = args.password
        
        # If credentials are not provided, try to get them from .env
        if not email or not password:
            substack_auth = get_substack_auth()
            email = email or substack_auth['email']
            password = password or substack_auth['password']
        
        # Check if credentials are available
        if not email or not password:
            logger.error("Substack email and password are required")
            logger.error("Provide them as command-line arguments or in the .env file")
            return 1
        
        if args.method == 'auto' or args.method == 'http':
            try:
                token = extract_token_with_http(email, password)
            except Exception as e:
                logger.error(f"Error using HTTP method: {e}")
                if args.method == 'http':
                    return 1
        
        if (args.method == 'auto' or args.method == 'selenium') and token is None:
            try:
                token = extract_token_with_selenium(email, password, args.headless)
            except Exception as e:
                logger.error(f"Error using Selenium: {e}")
                if args.method == 'selenium':
                    return 1
        
        if (args.method == 'auto' or args.method == 'puppeteer') and token is None:
            try:
                token = extract_token_with_puppeteer(email, password, args.headless)
            except Exception as e:
                logger.error(f"Error using Puppeteer: {e}")
                if args.method == 'puppeteer':
                    return 1
    
    # Check if token was extracted
    if token is None:
        logger.error("Failed to extract Substack token using any method")
        print("To manually extract the token:")
        print("1. Log in to Substack in your browser")
        print("2. Open the browser's developer tools (F12 or right-click > Inspect)")
        print("3. Go to the 'Application' or 'Storage' tab")
        print("4. Look for 'Cookies' > 'substack.com'")
        print("5. Find the 'substack.sid' cookie and copy its value")
        print("6. Run this script with: python scripts/get_substack_token.py --method manual --cookie YOUR_COOKIE_VALUE")
        print("\nAlternatively, copy the full HTTP headers from a request to substack.com while logged in:")
        print("1. Open Developer Tools > Network tab")
        print("2. Visit https://substack.com/home")
        print("3. Find the request to 'home' in the Network tab")
        print("4. Right-click > Copy > Copy request headers")
        print("5. Run: python scripts/get_substack_token.py --method headers --headers \"PASTE_HEADERS_HERE\"")
        return 1
    
    # Test the token if requested
    if args.test_token:
        logger.info("Testing token validity...")
        if not test_token(token):
            logger.error("Token test failed - the token may not be valid or may have expired")
            print("Token validation failed. The token may not be valid or may have expired.")
            print("Consider trying a different method to extract a fresh token.")
            return 1
    
    # Update the .env file with the new token
    if update_env_file(env_file, token):
        logger.info("Substack token extraction completed successfully")
        print(f"Substack token: {token}")
        
        # Display additional usage instructions
        print("\nThe token has been saved to your .env file and can now be used with download_all_trade_companion.py")
        print("Example usage:")
        print("  python scripts/download_all_trade_companion.py --private --verbose")
        
        return 0
    else:
        logger.error("Failed to update .env file with Substack token")
        return 1

if __name__ == "__main__":
    sys.exit(main())
