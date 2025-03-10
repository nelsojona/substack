#!/usr/bin/env python3
"""
Substack to Markdown CLI - Main Entry Point

This script provides a simplified CLI interface for all Substack to Markdown functionality.
"""

import sys
import os
import argparse
from src.core.substack_direct_downloader import main as direct_downloader_main
from src.core.optimized_substack_cli import main as optimized_cli_main
from src.core.substack_to_md import main as substack_to_md_main
from src.utils.batch_processor import BatchProcessor, create_example_config

def show_version():
    """Display the version information."""
    print("Substack to Markdown CLI v1.0.0")
    sys.exit(0)

def batch_main():
    """Main function for batch processing."""
    parser = argparse.ArgumentParser(
        description="Batch process multiple Substack authors")
    parser.add_argument("--config", required=True, help="Path to batch configuration file")
    parser.add_argument("--output", default="output", help="Base output directory")
    parser.add_argument("--processes", type=int, default=2, help="Maximum number of concurrent processes")
    parser.add_argument("--create-example", action="store_true", help="Create an example configuration file")
    
    args = parser.parse_args(sys.argv[2:])  # Skip the first two arguments (script name and 'batch')
    
    if args.create_example:
        create_example_config(args.config)
        print(f"Example configuration created at: {args.config}")
    else:
        processor = BatchProcessor(
            config_path=args.config,
            output_dir=args.output,
            max_processes=args.processes
        )
        
        results = processor.process_all()
        
        # Print summary
        success_count = sum(1 for result in results.values() if result)
        print(f"\nBatch processing complete: {success_count}/{len(results)} authors processed successfully")
        
        # Print details for each author
        for author, success in results.items():
            status = "✅ Success" if success else "❌ Failed"
            print(f"  - {author}: {status}")

def main():
    """Main function to dispatch to appropriate subcommands."""
    parser = argparse.ArgumentParser(
        description="Download and convert Substack posts to Markdown format")
    parser.add_argument("--version", action="store_true", help="Display version information")
    
    subparsers = parser.add_subparsers(title="commands", dest="command")
    
    # Direct download command (recommended)
    direct_parser = subparsers.add_parser("direct", help="Download posts directly (recommended)")
    direct_parser.set_defaults(func=direct_downloader_main)
    
    # Batch processing command
    batch_parser = subparsers.add_parser("batch", help="Batch process multiple authors")
    batch_parser.set_defaults(func=batch_main)
    
    # Optimized CLI command
    optimized_parser = subparsers.add_parser("optimized", help="Use optimized CLI interface")
    optimized_parser.set_defaults(func=optimized_cli_main)
    
    # Classic command
    classic_parser = subparsers.add_parser("classic", help="Use classic interface")
    classic_parser.set_defaults(func=substack_to_md_main)
    
    # Parse arguments
    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        # Special handling for batch command to support its own argument parsing
        batch_main()
    else:
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
