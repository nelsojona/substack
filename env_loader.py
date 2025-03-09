#!/usr/bin/env python3
"""
Environment Variable Loader

This module loads environment variables from a .env file using the python-dotenv library.
It provides functions to access environment variables for Substack authentication,
Oxylabs proxy configuration, and general configuration.
"""

import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def load_env_vars(env_file: str = '.env') -> bool:
    """
    Load environment variables from a .env file.
    
    Args:
        env_file (str, optional): Path to the .env file. Defaults to '.env'.
    
    Returns:
        bool: True if the .env file was loaded successfully, False otherwise.
    """
    # Check if the .env file exists
    if not os.path.exists(env_file):
        logger.warning(f".env file not found at {env_file}")
        return False
    
    # Load the .env file
    load_dotenv(env_file)
    logger.info(f"Loaded environment variables from {env_file}")
    return True

def get_substack_auth() -> Dict[str, str]:
    """
    Get Substack authentication credentials from environment variables.
    
    Returns:
        Dict[str, str]: Dictionary containing Substack authentication credentials.
    """
    return {
        'email': os.getenv('SUBSTACK_EMAIL', ''),
        'password': os.getenv('SUBSTACK_PASSWORD', ''),
        'token': os.getenv('SUBSTACK_TOKEN', '')
    }

def get_oxylabs_config() -> Dict[str, Any]:
    """
    Get Oxylabs proxy configuration from environment variables.
    
    Returns:
        Dict[str, Any]: Dictionary containing Oxylabs proxy configuration.
    """
    session_time = os.getenv('OXYLABS_SESSION_TIME', '')
    
    return {
        'username': os.getenv('OXYLABS_USERNAME', ''),
        'password': os.getenv('OXYLABS_PASSWORD', ''),
        'country_code': os.getenv('OXYLABS_COUNTRY', ''),
        'city': os.getenv('OXYLABS_CITY', ''),
        'state': os.getenv('OXYLABS_STATE', ''),
        'session_id': os.getenv('OXYLABS_SESSION_ID', ''),
        'session_time': int(session_time) if session_time and session_time.isdigit() else None
    }

def get_general_config() -> Dict[str, Any]:
    """
    Get general configuration from environment variables.
    
    Returns:
        Dict[str, Any]: Dictionary containing general configuration.
    """
    max_workers = os.getenv('DEFAULT_MAX_IMAGE_WORKERS', '')
    timeout = os.getenv('DEFAULT_IMAGE_TIMEOUT', '')
    
    return {
        'output_dir': os.getenv('DEFAULT_OUTPUT_DIR', './markdown_output'),
        'image_dir': os.getenv('DEFAULT_IMAGE_DIR', './images'),
        'max_image_workers': int(max_workers) if max_workers and max_workers.isdigit() else 4,
        'image_timeout': int(timeout) if timeout and timeout.isdigit() else 10
    }

def get_env_var(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a specific environment variable.
    
    Args:
        name (str): Name of the environment variable.
        default (Optional[str], optional): Default value if the environment variable is not set. Defaults to None.
    
    Returns:
        Optional[str]: Value of the environment variable, or the default value if not set.
    """
    return os.getenv(name, default)
