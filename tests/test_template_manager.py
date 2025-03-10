#!/usr/bin/env python3
"""
Tests for template manager functionality.

This module tests the template manager features of the Substack to Markdown CLI.
"""

import os
import sys
import pytest
import tempfile
from string import Template

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.template_manager import TemplateManager, create_example_templates


class TestTemplateManager:
    """Test class for template manager functionality."""

    def test_default_template(self):
        """Test that the default template is available."""
        # Arrange
        manager = TemplateManager()
        
        # Act
        template = manager.get_template()
        
        # Assert
        assert template is not None
        assert isinstance(template, Template)
        assert "${title}" in template.template
        assert "${content}" in template.template

    def test_load_templates(self, tmp_path):
        """Test loading templates from a directory."""
        # Arrange
        template_dir = tmp_path / "templates"
        os.makedirs(template_dir)
        
        # Create a test template
        test_template_path = template_dir / "test.template"
        with open(test_template_path, 'w', encoding='utf-8') as f:
            f.write("# ${title}\n\n${content}")
        
        # Act
        manager = TemplateManager(str(template_dir))
        
        # Assert
        assert "test" in manager.templates
        assert isinstance(manager.templates["test"], Template)
        assert "# ${title}" in manager.templates["test"].template

    def test_get_template_by_name(self, tmp_path):
        """Test getting a template by name."""
        # Arrange
        template_dir = tmp_path / "templates"
        os.makedirs(template_dir)
        
        # Create multiple test templates
        with open(template_dir / "template1.template", 'w', encoding='utf-8') as f:
            f.write("Template 1: ${title}")
        
        with open(template_dir / "template2.template", 'w', encoding='utf-8') as f:
            f.write("Template 2: ${title}")
        
        manager = TemplateManager(str(template_dir))
        
        # Act
        template1 = manager.get_template("template1")
        template2 = manager.get_template("template2")
        default_template = manager.get_template()
        nonexistent_template = manager.get_template("nonexistent")
        
        # Assert
        assert "Template 1: ${title}" == template1.template
        assert "Template 2: ${title}" == template2.template
        assert default_template == manager.default_template
        assert nonexistent_template == manager.default_template

    def test_apply_template(self, tmp_path):
        """Test applying a template to post data."""
        # Arrange
        template_dir = tmp_path / "templates"
        os.makedirs(template_dir)
        
        # Create a test template
        test_template_path = template_dir / "test.template"
        with open(test_template_path, 'w', encoding='utf-8') as f:
            f.write("# ${title}\n\nBy ${author} on ${date}\n\n${content}\n\n${comments}")
        
        manager = TemplateManager(str(template_dir))
        
        post_data = {
            "title": "Test Post",
            "author": "Test Author",
            "date": "2023-01-01",
            "url": "https://example.com/p/test-post",
            "content": "This is the content.",
            "comments": "This is a comment."
        }
        
        # Act
        result = manager.apply_template("test", post_data)
        
        # Assert
        assert "# Test Post" in result
        assert "By Test Author on 2023-01-01" in result
        assert "This is the content." in result
        assert "This is a comment." in result

    def test_apply_template_with_additional_frontmatter(self, tmp_path):
        """Test applying a template with additional frontmatter fields."""
        # Arrange
        template_dir = tmp_path / "templates"
        os.makedirs(template_dir)
        
        # Create a test template
        test_template_path = template_dir / "test.template"
        with open(test_template_path, 'w', encoding='utf-8') as f:
            f.write("---\ntitle: \"${title}\"\n${additional_frontmatter}\n---\n\n${content}")
        
        manager = TemplateManager(str(template_dir))
        
        post_data = {
            "title": "Test Post",
            "content": "This is the content.",
            "is_paid": True,
            "word_count": 100,
            "tags": "test, example"
        }
        
        # Act
        result = manager.apply_template("test", post_data)
        
        # Assert
        assert 'title: "Test Post"' in result
        assert "is_paid: true" in result
        assert "word_count: 100" in result
        assert 'tags: "test, example"' in result
        assert "This is the content." in result

    def test_create_example_template(self, tmp_path):
        """Test creating an example template."""
        # Arrange
        manager = TemplateManager()
        output_path = tmp_path / "example.template"
        
        # Act
        result = manager.create_example_template(str(output_path))
        
        # Assert
        assert result is True
        assert os.path.exists(output_path)
        
        # Check content
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "${title}" in content
            assert "${content}" in content
            assert "${comments}" in content

    def test_create_example_templates(self, tmp_path):
        """Test creating multiple example templates."""
        # Arrange
        output_dir = tmp_path / "templates"
        
        # Act
        result = create_example_templates(str(output_dir))
        
        # Assert
        assert result is True
        assert os.path.exists(output_dir / "basic.template")
        assert os.path.exists(output_dir / "academic.template")
        assert os.path.exists(output_dir / "blog.template")
        
        # Check content of one template
        with open(output_dir / "academic.template", 'r', encoding='utf-8') as f:
            content = f.read()
            assert "## Abstract" in content
            assert "## Citation" in content


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
