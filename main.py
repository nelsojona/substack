#!/usr/bin/env python3
"""
Substack to Markdown CLI - Main Entry Point

This script provides a simplified CLI interface for all Substack to Markdown functionality.
"""

import sys
import argparse
from src.core.substack_direct_downloader import main as direct_downloader_main
from src.core.optimized_substack_cli import main as optimized_cli_main
from src.core.substack_to_md import main as substack_to_md_main

def show_version():
    """Display the version information."""
    print("Substack to Markdown CLI v1.0.0")
    sys.exit(0)

def main():
    """Main function to dispatch to appropriate subcommands."""
    parser = argparse.ArgumentParser(
        description="Download and convert Substack posts to Markdown format")
    parser.add_argument("--version", action="store_true", help="Display version information")
    
    subparsers = parser.add_subparsers(title="commands", dest="command")
    
    # Direct download command (recommended)
    direct_parser = subparsers.add_parser("direct", help="Download posts directly (recommended)")
    direct_parser.set_defaults(func=direct_downloader_main)
    
    # Optimized CLI command
    optimized_parser = subparsers.add_parser("optimized", help="Use optimized CLI interface")
    optimized_parser.set_defaults(func=optimized_cli_main)
    
    # Classic command
    classic_parser = subparsers.add_parser("classic", help="Use classic interface")
    classic_parser.set_defaults(func=substack_to_md_main)
    
    args = parser.parse_args()
    
    if args.version:
        show_version()
        
    if hasattr(args, "func"):
        args.func()
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()