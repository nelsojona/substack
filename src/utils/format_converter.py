#!/usr/bin/env python3
"""
Format Converter for Substack to Markdown CLI.

This module provides functionality for converting Markdown content to other formats
such as HTML, PDF, and EPUB.
"""

import os
import logging
import tempfile
import subprocess
from typing import Optional, Dict, Any, List, Union
from pathlib import Path

logger = logging.getLogger("format_converter")

# Supported output formats
SUPPORTED_FORMATS = ["html", "pdf", "epub"]

class FormatConverter:
    """
    Converts Markdown content to various output formats.
    
    Attributes:
        output_dir (str): Directory to save converted files
        pandoc_path (str): Path to pandoc executable
        wkhtmltopdf_path (str): Path to wkhtmltopdf executable
    """
    
    def __init__(self, output_dir: str, pandoc_path: Optional[str] = None, wkhtmltopdf_path: Optional[str] = None):
        """
        Initialize the FormatConverter.
        
        Args:
            output_dir (str): Directory to save converted files
            pandoc_path (Optional[str], optional): Path to pandoc executable. If None, uses "pandoc" from PATH.
            wkhtmltopdf_path (Optional[str], optional): Path to wkhtmltopdf executable. If None, uses "wkhtmltopdf" from PATH.
        """
        self.output_dir = output_dir
        self.pandoc_path = pandoc_path or "pandoc"
        self.wkhtmltopdf_path = wkhtmltopdf_path or "wkhtmltopdf"
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
    
    def check_dependencies(self) -> Dict[str, bool]:
        """
        Check if required dependencies are installed.
        
        Returns:
            Dict[str, bool]: Dictionary of dependencies and their availability
        """
        dependencies = {
            "pandoc": False,
            "wkhtmltopdf": False
        }
        
        # Check pandoc
        try:
            result = subprocess.run(
                [self.pandoc_path, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            dependencies["pandoc"] = result.returncode == 0
        except FileNotFoundError:
            logger.warning(f"Pandoc not found at {self.pandoc_path}")
        
        # Check wkhtmltopdf
        try:
            result = subprocess.run(
                [self.wkhtmltopdf_path, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            dependencies["wkhtmltopdf"] = result.returncode == 0
        except FileNotFoundError:
            logger.warning(f"wkhtmltopdf not found at {self.wkhtmltopdf_path}")
        
        return dependencies
    
    def convert_to_html(self, markdown_file: str, output_file: Optional[str] = None, 
                        title: Optional[str] = None, css: Optional[str] = None) -> Optional[str]:
        """
        Convert Markdown to HTML.
        
        Args:
            markdown_file (str): Path to markdown file
            output_file (Optional[str], optional): Path to output file. If None, uses the same name with .html extension.
            title (Optional[str], optional): Title for the HTML document. If None, uses the filename.
            css (Optional[str], optional): Path to CSS file for styling.
        
        Returns:
            Optional[str]: Path to the output file if successful, None otherwise
        """
        if not os.path.exists(markdown_file):
            logger.error(f"Markdown file not found: {markdown_file}")
            return None
        
        # Determine output file path
        if output_file is None:
            output_file = os.path.join(
                self.output_dir,
                os.path.splitext(os.path.basename(markdown_file))[0] + ".html"
            )
        
        # Determine title
        if title is None:
            title = os.path.splitext(os.path.basename(markdown_file))[0]
        
        # Build pandoc command
        cmd = [self.pandoc_path, "-s", "-f", "markdown", "-t", "html", "--metadata", f"title={title}"]
        
        # Add CSS if provided
        if css and os.path.exists(css):
            cmd.extend(["--css", css])
        
        # Add input and output files
        cmd.extend(["-o", output_file, markdown_file])
        
        try:
            # Run pandoc
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully converted to HTML: {output_file}")
                return output_file
            else:
                logger.error(f"Error converting to HTML: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Error converting to HTML: {e}")
            return None
    
    def convert_to_pdf(self, markdown_file: str, output_file: Optional[str] = None,
                       title: Optional[str] = None, css: Optional[str] = None) -> Optional[str]:
        """
        Convert Markdown to PDF.
        
        Args:
            markdown_file (str): Path to markdown file
            output_file (Optional[str], optional): Path to output file. If None, uses the same name with .pdf extension.
            title (Optional[str], optional): Title for the PDF document. If None, uses the filename.
            css (Optional[str], optional): Path to CSS file for styling.
        
        Returns:
            Optional[str]: Path to the output file if successful, None otherwise
        """
        if not os.path.exists(markdown_file):
            logger.error(f"Markdown file not found: {markdown_file}")
            return None
        
        # Determine output file path
        if output_file is None:
            output_file = os.path.join(
                self.output_dir,
                os.path.splitext(os.path.basename(markdown_file))[0] + ".pdf"
            )
        
        # Determine title
        if title is None:
            title = os.path.splitext(os.path.basename(markdown_file))[0]
        
        # Build pandoc command
        cmd = [
            self.pandoc_path, "-s", "-f", "markdown", "-t", "pdf",
            "--pdf-engine=wkhtmltopdf", "--metadata", f"title={title}"
        ]
        
        # Add CSS if provided
        if css and os.path.exists(css):
            cmd.extend(["--css", css])
        
        # Add input and output files
        cmd.extend(["-o", output_file, markdown_file])
        
        try:
            # Run pandoc
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully converted to PDF: {output_file}")
                return output_file
            else:
                logger.error(f"Error converting to PDF: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Error converting to PDF: {e}")
            return None
    
    def convert_to_epub(self, markdown_file: str, output_file: Optional[str] = None,
                        title: Optional[str] = None, author: Optional[str] = None,
                        cover_image: Optional[str] = None) -> Optional[str]:
        """
        Convert Markdown to EPUB.
        
        Args:
            markdown_file (str): Path to markdown file
            output_file (Optional[str], optional): Path to output file. If None, uses the same name with .epub extension.
            title (Optional[str], optional): Title for the EPUB document. If None, uses the filename.
            author (Optional[str], optional): Author name for the EPUB metadata.
            cover_image (Optional[str], optional): Path to cover image file.
        
        Returns:
            Optional[str]: Path to the output file if successful, None otherwise
        """
        if not os.path.exists(markdown_file):
            logger.error(f"Markdown file not found: {markdown_file}")
            return None
        
        # Determine output file path
        if output_file is None:
            output_file = os.path.join(
                self.output_dir,
                os.path.splitext(os.path.basename(markdown_file))[0] + ".epub"
            )
        
        # Determine title
        if title is None:
            title = os.path.splitext(os.path.basename(markdown_file))[0]
        
        # Build pandoc command
        cmd = [self.pandoc_path, "-s", "-f", "markdown", "-t", "epub", "--metadata", f"title={title}"]
        
        # Add author if provided
        if author:
            cmd.extend(["--metadata", f"author={author}"])
        
        # Add cover image if provided
        if cover_image and os.path.exists(cover_image):
            cmd.extend(["--epub-cover-image", cover_image])
        
        # Add input and output files
        cmd.extend(["-o", output_file, markdown_file])
        
        try:
            # Run pandoc
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully converted to EPUB: {output_file}")
                return output_file
            else:
                logger.error(f"Error converting to EPUB: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Error converting to EPUB: {e}")
            return None
    
    def convert_file(self, markdown_file: str, output_format: str, output_file: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Convert a Markdown file to the specified format.
        
        Args:
            markdown_file (str): Path to markdown file
            output_format (str): Output format (html, pdf, epub)
            output_file (Optional[str], optional): Path to output file. If None, uses the same name with appropriate extension.
            metadata (Optional[Dict[str, Any]], optional): Additional metadata for the conversion.
        
        Returns:
            Optional[str]: Path to the output file if successful, None otherwise
        """
        if output_format not in SUPPORTED_FORMATS:
            logger.error(f"Unsupported output format: {output_format}")
            return None
        
        # Extract metadata
        metadata = metadata or {}
        title = metadata.get("title")
        author = metadata.get("author")
        css = metadata.get("css")
        cover_image = metadata.get("cover_image")
        
        # Call the appropriate conversion method
        if output_format == "html":
            return self.convert_to_html(markdown_file, output_file, title, css)
        elif output_format == "pdf":
            return self.convert_to_pdf(markdown_file, output_file, title, css)
        elif output_format == "epub":
            return self.convert_to_epub(markdown_file, output_file, title, author, cover_image)
        
        return None
    
    def convert_directory(self, markdown_dir: str, output_format: str, 
                          recursive: bool = False, metadata: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Convert all Markdown files in a directory to the specified format.
        
        Args:
            markdown_dir (str): Directory containing markdown files
            output_format (str): Output format (html, pdf, epub)
            recursive (bool, optional): Whether to process subdirectories recursively. Defaults to False.
            metadata (Optional[Dict[str, Any]], optional): Additional metadata for the conversion.
        
        Returns:
            List[str]: List of paths to the output files
        """
        if not os.path.isdir(markdown_dir):
            logger.error(f"Markdown directory not found: {markdown_dir}")
            return []
        
        output_files = []
        
        # Process files in the directory
        for item in os.listdir(markdown_dir):
            item_path = os.path.join(markdown_dir, item)
            
            # Process subdirectories if recursive is True
            if os.path.isdir(item_path) and recursive:
                # Create corresponding output subdirectory
                output_subdir = os.path.join(self.output_dir, item)
                os.makedirs(output_subdir, exist_ok=True)
                
                # Process subdirectory with a new converter instance
                subdir_converter = FormatConverter(
                    output_dir=output_subdir,
                    pandoc_path=self.pandoc_path,
                    wkhtmltopdf_path=self.wkhtmltopdf_path
                )
                
                # Convert files in subdirectory
                subdir_output_files = subdir_converter.convert_directory(
                    item_path, output_format, recursive, metadata
                )
                
                # Add to output files
                output_files.extend(subdir_output_files)
            
            # Process markdown files
            elif os.path.isfile(item_path) and item.endswith(('.md', '.markdown')):
                # Convert the file
                output_file = self.convert_file(item_path, output_format, metadata=metadata)
                
                # Add to output files if successful
                if output_file:
                    output_files.append(output_file)
        
        return output_files
    
    def convert_string(self, markdown_content: str, output_format: str, output_file: str,
                       metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Convert a Markdown string to the specified format.
        
        Args:
            markdown_content (str): Markdown content as a string
            output_format (str): Output format (html, pdf, epub)
            output_file (str): Path to output file
            metadata (Optional[Dict[str, Any]], optional): Additional metadata for the conversion.
        
        Returns:
            Optional[str]: Path to the output file if successful, None otherwise
        """
        if output_format not in SUPPORTED_FORMATS:
            logger.error(f"Unsupported output format: {output_format}")
            return None
        
        # Create a temporary file for the markdown content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
            temp_file.write(markdown_content)
            temp_file_path = temp_file.name
        
        try:
            # Convert the temporary file
            result = self.convert_file(temp_file_path, output_format, output_file, metadata)
            
            # Remove the temporary file
            os.unlink(temp_file_path)
            
            return result
        except Exception as e:
            # Remove the temporary file in case of error
            os.unlink(temp_file_path)
            logger.error(f"Error converting markdown string: {e}")
            return None


def create_default_css() -> str:
    """
    Create a default CSS file for styling HTML and PDF output.
    
    Returns:
        str: Path to the created CSS file
    """
    css_content = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        line-height: 1.6;
        max-width: 800px;
        margin: 0 auto;
        padding: 2em;
        color: #333;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-weight: 600;
        margin-top: 1.5em;
        margin-bottom: 0.5em;
    }
    
    h1 {
        font-size: 2.2em;
        border-bottom: 1px solid #eee;
        padding-bottom: 0.3em;
    }
    
    h2 {
        font-size: 1.8em;
        border-bottom: 1px solid #eee;
        padding-bottom: 0.3em;
    }
    
    h3 {
        font-size: 1.5em;
    }
    
    h4 {
        font-size: 1.3em;
    }
    
    p, ul, ol {
        margin-bottom: 1.5em;
    }
    
    a {
        color: #0366d6;
        text-decoration: none;
    }
    
    a:hover {
        text-decoration: underline;
    }
    
    code {
        font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
        background-color: #f6f8fa;
        padding: 0.2em 0.4em;
        border-radius: 3px;
        font-size: 0.9em;
    }
    
    pre {
        background-color: #f6f8fa;
        padding: 1em;
        border-radius: 3px;
        overflow: auto;
    }
    
    pre code {
        background-color: transparent;
        padding: 0;
    }
    
    blockquote {
        border-left: 4px solid #ddd;
        padding-left: 1em;
        color: #666;
        margin-left: 0;
        margin-right: 0;
    }
    
    img {
        max-width: 100%;
        height: auto;
    }
    
    table {
        border-collapse: collapse;
        width: 100%;
        margin-bottom: 1.5em;
    }
    
    table, th, td {
        border: 1px solid #ddd;
    }
    
    th, td {
        padding: 0.5em;
        text-align: left;
    }
    
    th {
        background-color: #f6f8fa;
    }
    
    tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    """
    
    # Create the CSS file in a temporary directory
    css_dir = tempfile.gettempdir()
    css_path = os.path.join(css_dir, "substack_default.css")
    
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(css_content)
    
    return css_path
