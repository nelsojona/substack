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
from src.utils.template_manager import create_example_templates
from src.utils.format_converter import FormatConverter, create_default_css, SUPPORTED_FORMATS

def show_version():
    """Display the version information."""
    print("Substack to Markdown CLI v1.0.0")
    sys.exit(0)

def template_main():
    """Main function for template management."""
    parser = argparse.ArgumentParser(
        description="Manage custom Markdown templates")
    parser.add_argument("--create-examples", action="store_true", help="Create example templates")
    parser.add_argument("--output-dir", default="templates", help="Directory to save templates")
    
    args = parser.parse_args(sys.argv[2:])  # Skip the first two arguments (script name and 'template')
    
    if args.create_examples:
        os.makedirs(args.output_dir, exist_ok=True)
        create_example_templates(args.output_dir)
        print(f"Example templates created in: {args.output_dir}")
        print("Available templates:")
        print("  - basic: A simple template with title, content, and comments")
        print("  - academic: A template formatted for academic citations")
        print("  - blog: A template with HTML formatting for blog posts")
    else:
        parser.print_help()

def convert_main():
    """Main function for format conversion."""
    parser = argparse.ArgumentParser(
        description="Convert Markdown files to other formats")
    parser.add_argument("--input", required=True, help="Input Markdown file or directory")
    parser.add_argument("--format", choices=SUPPORTED_FORMATS, required=True, help="Output format")
    parser.add_argument("--output-dir", default="converted", help="Output directory")
    parser.add_argument("--recursive", action="store_true", help="Process directories recursively")
    parser.add_argument("--title", help="Title for the output document")
    parser.add_argument("--author", help="Author name for the output document")
    parser.add_argument("--css", help="Path to CSS file for styling HTML and PDF output")
    parser.add_argument("--cover-image", help="Path to cover image for EPUB output")
    parser.add_argument("--check-deps", action="store_true", help="Check for required dependencies")
    
    args = parser.parse_args(sys.argv[2:])  # Skip the first two arguments (script name and 'convert')
    
    # Create converter
    converter = FormatConverter(
        output_dir=args.output_dir,
    )
    
    # Check dependencies if requested
    if args.check_deps:
        deps = converter.check_dependencies()
        print("Dependency check:")
        for dep, available in deps.items():
            status = "✅ Available" if available else "❌ Not found"
            print(f"  - {dep}: {status}")
        
        # Exit if any dependency is missing
        if not all(deps.values()):
            print("\nSome dependencies are missing. Please install them to use this feature.")
            print("  - pandoc: https://pandoc.org/installing.html")
            print("  - wkhtmltopdf: https://wkhtmltopdf.org/downloads.html")
            sys.exit(1)
    
    # Prepare metadata
    metadata = {
        "title": args.title,
        "author": args.author,
        "css": args.css or create_default_css(),
        "cover_image": args.cover_image
    }
    
    # Check if input is a file or directory
    if os.path.isfile(args.input):
        # Convert a single file
        output_file = converter.convert_file(
            args.input,
            args.format,
            metadata=metadata
        )
        
        if output_file:
            print(f"Successfully converted to {args.format.upper()}: {output_file}")
        else:
            print(f"Failed to convert {args.input} to {args.format.upper()}")
            sys.exit(1)
    elif os.path.isdir(args.input):
        # Convert all markdown files in the directory
        output_files = converter.convert_directory(
            args.input,
            args.format,
            recursive=args.recursive,
            metadata=metadata
        )
        
        if output_files:
            print(f"Successfully converted {len(output_files)} files to {args.format.upper()}")
            for output_file in output_files:
                print(f"  - {output_file}")
        else:
            print(f"No markdown files found in {args.input}")
            sys.exit(1)
    else:
        print(f"Input not found: {args.input}")
        sys.exit(1)

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
    direct_parser.add_argument("--template-dir", help="Directory containing custom Markdown templates")
    direct_parser.add_argument("--template", help="Name of the template to use")
    direct_parser.set_defaults(func=direct_downloader_main)
    
    # Batch processing command
    batch_parser = subparsers.add_parser("batch", help="Batch process multiple authors")
    batch_parser.set_defaults(func=batch_main)
    
    # Template management command
    template_parser = subparsers.add_parser("template", help="Manage custom Markdown templates")
    template_parser.set_defaults(func=template_main)
    
    # Format conversion command
    convert_parser = subparsers.add_parser("convert", help="Convert Markdown files to other formats")
    convert_parser.set_defaults(func=convert_main)
    
    # Optimized CLI command
    optimized_parser = subparsers.add_parser("optimized", help="Use optimized CLI interface")
    optimized_parser.set_defaults(func=optimized_cli_main)
    
    # Classic command
    classic_parser = subparsers.add_parser("classic", help="Use classic interface")
    classic_parser.set_defaults(func=substack_to_md_main)
    
    # Parse arguments
    if len(sys.argv) > 1 and sys.argv[1] in ["batch", "template", "convert"]:
        # Special handling for commands that need their own argument parsing
        if sys.argv[1] == "batch":
            batch_main()
        elif sys.argv[1] == "template":
            template_main()
        elif sys.argv[1] == "convert":
            convert_main()
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
