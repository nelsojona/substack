#!/usr/bin/env python3
"""
Tests for format converter functionality.

This module tests the format converter features of the Substack to Markdown CLI.
"""

import os
import sys
import pytest
import tempfile
import subprocess
from unittest.mock import patch, MagicMock

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.format_converter import FormatConverter, create_default_css, SUPPORTED_FORMATS


class TestFormatConverter:
    """Test class for format converter functionality."""

    @pytest.fixture
    def converter(self):
        """Create a FormatConverter instance for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield FormatConverter(output_dir=temp_dir)

    @pytest.fixture
    def sample_markdown(self):
        """Create a sample markdown file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
            temp_file.write("""# Test Markdown

This is a test markdown file.

## Section 1

- Item 1
- Item 2
- Item 3

## Section 2

Some text with **bold** and *italic* formatting.

[A link](https://example.com)
""")
            return temp_file.name

    def test_check_dependencies(self, converter):
        """Test checking for required dependencies."""
        # Mock subprocess.run to simulate dependencies being available
        with patch('subprocess.run') as mock_run:
            # Configure the mock to return success for both dependencies
            mock_run.return_value.returncode = 0
            
            # Call the method
            dependencies = converter.check_dependencies()
            
            # Assert
            assert dependencies["pandoc"] is True
            assert dependencies["wkhtmltopdf"] is True
            assert mock_run.call_count == 2

    def test_check_dependencies_not_found(self, converter):
        """Test checking for dependencies when they are not found."""
        # Mock subprocess.run to simulate dependencies not being available
        with patch('subprocess.run') as mock_run:
            # Configure the mock to raise FileNotFoundError
            mock_run.side_effect = FileNotFoundError()
            
            # Call the method
            dependencies = converter.check_dependencies()
            
            # Assert
            assert dependencies["pandoc"] is False
            assert dependencies["wkhtmltopdf"] is False
            assert mock_run.call_count == 2

    def test_convert_to_html(self, converter, sample_markdown):
        """Test converting markdown to HTML."""
        # Mock subprocess.run to simulate successful conversion
        with patch('subprocess.run') as mock_run:
            # Configure the mock to return success
            mock_run.return_value.returncode = 0
            
            # Call the method
            output_file = converter.convert_to_html(sample_markdown)
            
            # Assert
            assert output_file is not None
            assert output_file.endswith(".html")
            assert mock_run.call_count == 1
            
            # Check that the command was correct
            args, kwargs = mock_run.call_args
            cmd = args[0]
            assert cmd[0] == "pandoc"
            assert "-f" in cmd
            assert "markdown" in cmd
            assert "-t" in cmd
            assert "html" in cmd
            assert "-o" in cmd
            assert sample_markdown in cmd

    def test_convert_to_pdf(self, converter, sample_markdown):
        """Test converting markdown to PDF."""
        # Mock subprocess.run to simulate successful conversion
        with patch('subprocess.run') as mock_run:
            # Configure the mock to return success
            mock_run.return_value.returncode = 0
            
            # Call the method
            output_file = converter.convert_to_pdf(sample_markdown)
            
            # Assert
            assert output_file is not None
            assert output_file.endswith(".pdf")
            assert mock_run.call_count == 1
            
            # Check that the command was correct
            args, kwargs = mock_run.call_args
            cmd = args[0]
            assert cmd[0] == "pandoc"
            assert "-f" in cmd
            assert "markdown" in cmd
            assert "-t" in cmd
            assert "pdf" in cmd
            assert "--pdf-engine=wkhtmltopdf" in cmd
            assert "-o" in cmd
            assert sample_markdown in cmd

    def test_convert_to_epub(self, converter, sample_markdown):
        """Test converting markdown to EPUB."""
        # Mock subprocess.run to simulate successful conversion
        with patch('subprocess.run') as mock_run:
            # Configure the mock to return success
            mock_run.return_value.returncode = 0
            
            # Call the method
            output_file = converter.convert_to_epub(
                sample_markdown,
                title="Test Title",
                author="Test Author"
            )
            
            # Assert
            assert output_file is not None
            assert output_file.endswith(".epub")
            assert mock_run.call_count == 1
            
            # Check that the command was correct
            args, kwargs = mock_run.call_args
            cmd = args[0]
            assert cmd[0] == "pandoc"
            assert "-f" in cmd
            assert "markdown" in cmd
            assert "-t" in cmd
            assert "epub" in cmd
            assert "--metadata" in cmd
            assert "title=Test Title" in cmd
            assert "author=Test Author" in cmd
            assert "-o" in cmd
            assert sample_markdown in cmd

    def test_convert_file(self, converter, sample_markdown):
        """Test converting a file to different formats."""
        # Test for each supported format
        for output_format in SUPPORTED_FORMATS:
            # Mock the specific conversion method
            method_name = f"convert_to_{output_format}"
            with patch.object(converter, method_name) as mock_method:
                # Configure the mock to return a success
                mock_method.return_value = f"output.{output_format}"
                
                # Call the method
                output_file = converter.convert_file(
                    sample_markdown,
                    output_format,
                    metadata={"title": "Test Title", "author": "Test Author"}
                )
                
                # Assert
                assert output_file == f"output.{output_format}"
                mock_method.assert_called_once()

    def test_convert_file_unsupported_format(self, converter, sample_markdown):
        """Test converting a file to an unsupported format."""
        # Call the method with an unsupported format
        output_file = converter.convert_file(sample_markdown, "unsupported")
        
        # Assert
        assert output_file is None

    def test_convert_directory(self, converter):
        """Test converting all markdown files in a directory."""
        # Create a temporary directory with markdown files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create sample markdown files
            for i in range(3):
                with open(os.path.join(temp_dir, f"test{i}.md"), 'w') as f:
                    f.write(f"# Test {i}\n\nThis is test {i}.")
            
            # Mock the convert_file method
            with patch.object(converter, 'convert_file') as mock_convert:
                # Configure the mock to return success
                mock_convert.side_effect = lambda file, format, **kwargs: f"{file}.{format}"
                
                # Call the method
                output_files = converter.convert_directory(temp_dir, "html")
                
                # Assert
                assert len(output_files) == 3
                assert mock_convert.call_count == 3

    def test_convert_directory_recursive(self, converter):
        """Test converting markdown files in a directory recursively."""
        # Create a temporary directory structure with markdown files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create sample markdown files in the root directory
            for i in range(2):
                with open(os.path.join(temp_dir, f"test{i}.md"), 'w') as f:
                    f.write(f"# Test {i}\n\nThis is test {i}.")
            
            # Create a subdirectory with more markdown files
            subdir = os.path.join(temp_dir, "subdir")
            os.makedirs(subdir)
            for i in range(2):
                with open(os.path.join(subdir, f"subtest{i}.md"), 'w') as f:
                    f.write(f"# Subtest {i}\n\nThis is subtest {i}.")
            
            # Mock the convert_file method
            with patch.object(FormatConverter, 'convert_file') as mock_convert:
                # Configure the mock to return success
                mock_convert.side_effect = lambda file, format, **kwargs: f"{file}.{format}"
                
                # Call the method with recursive=True
                output_files = converter.convert_directory(temp_dir, "html", recursive=True)
                
                # Assert
                assert len(output_files) == 4
                assert mock_convert.call_count == 4

    def test_convert_string(self, converter):
        """Test converting a markdown string to different formats."""
        # Mock the convert_file method
        with patch.object(converter, 'convert_file') as mock_convert:
            # Configure the mock to return success
            mock_convert.return_value = "output.html"
            
            # Call the method
            output_file = converter.convert_string(
                "# Test\n\nThis is a test.",
                "html",
                "output.html"
            )
            
            # Assert
            assert output_file == "output.html"
            mock_convert.assert_called_once()
            
            # Check that a temporary file was created and passed to convert_file
            args, kwargs = mock_convert.call_args
            assert args[0].endswith(".md")  # Temp file path
            assert args[1] == "html"  # Format
            assert args[2] == "output.html"  # Output file

    def test_create_default_css(self):
        """Test creating a default CSS file."""
        # Call the function
        css_path = create_default_css()
        
        # Assert
        assert os.path.exists(css_path)
        assert css_path.endswith("substack_default.css")
        
        # Check the content
        with open(css_path, 'r') as f:
            content = f.read()
            assert "body" in content
            assert "font-family" in content
            assert "h1, h2, h3" in content
            assert "code" in content
            assert "table" in content


class TestFormatConverterIntegration:
    """Integration tests for format converter functionality."""

    @pytest.fixture
    def converter(self):
        """Create a FormatConverter instance for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield FormatConverter(output_dir=temp_dir)

    @pytest.fixture
    def sample_markdown_file(self):
        """Create a sample markdown file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
            temp_file.write("""# Integration Test

This is a test markdown file for integration testing.

## Section 1

- Item 1
- Item 2
- Item 3

## Section 2

Some text with **bold** and *italic* formatting.

[A link](https://example.com)
""")
            return temp_file.name

    def test_pandoc_availability(self):
        """Test if pandoc is available on the system."""
        try:
            result = subprocess.run(
                ["pandoc", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            pandoc_available = result.returncode == 0
        except FileNotFoundError:
            pandoc_available = False
        
        # Skip the test if pandoc is not available
        if not pandoc_available:
            pytest.skip("Pandoc is not available on the system")

    def test_html_conversion_integration(self, converter, sample_markdown_file):
        """Test HTML conversion with the actual pandoc command."""
        # Skip if pandoc is not available
        self.test_pandoc_availability()
        
        # Call the method
        output_file = converter.convert_to_html(sample_markdown_file)
        
        # Assert
        assert output_file is not None
        assert os.path.exists(output_file)
        assert output_file.endswith(".html")
        
        # Check the content
        with open(output_file, 'r') as f:
            content = f.read()
            assert "<h1" in content
            assert "Integration Test" in content
            assert "<strong>bold</strong>" in content
            assert "<em>italic</em>" in content
            assert '<a href="https://example.com">A link</a>' in content


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
