#!/usr/bin/env python3
"""
Template Manager for Substack to Markdown CLI.

This module provides functionality for loading, parsing, and applying custom
Markdown templates for post conversion.
"""

import os
import re
import logging
from typing import Dict, Any, Optional
from string import Template

logger = logging.getLogger("template_manager")

DEFAULT_TEMPLATE = """---
title: "${title}"
date: "${date}"
author: "${author}"
original_url: "${url}"
${additional_frontmatter}
---

# ${title}

${content}

${comments}
"""

class TemplateManager:
    """
    Manages custom Markdown templates for post conversion.
    
    Attributes:
        template_dir (str): Directory containing template files
        templates (Dict[str, Template]): Dictionary of loaded templates
    """
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize the TemplateManager.
        
        Args:
            template_dir (Optional[str], optional): Directory containing template files.
                                                 If None, no templates are loaded initially.
        """
        self.template_dir = template_dir
        self.templates = {}
        self.default_template = Template(DEFAULT_TEMPLATE)
        
        # Load templates if directory is provided
        if template_dir and os.path.isdir(template_dir):
            self.load_templates(template_dir)
    
    def load_templates(self, template_dir: str) -> None:
        """
        Load all template files from the specified directory.
        
        Args:
            template_dir (str): Directory containing template files
        """
        self.template_dir = template_dir
        self.templates = {}
        
        if not os.path.isdir(template_dir):
            logger.warning(f"Template directory does not exist: {template_dir}")
            return
        
        # Load all .md and .template files
        for filename in os.listdir(template_dir):
            if filename.endswith(('.md', '.template')):
                template_path = os.path.join(template_dir, filename)
                template_name = os.path.splitext(filename)[0]
                
                try:
                    with open(template_path, 'r', encoding='utf-8') as f:
                        template_content = f.read()
                    
                    # Create a Template object
                    self.templates[template_name] = Template(template_content)
                    logger.debug(f"Loaded template: {template_name}")
                except Exception as e:
                    logger.error(f"Error loading template {template_path}: {e}")
    
    def get_template(self, template_name: Optional[str] = None) -> Template:
        """
        Get a template by name.
        
        Args:
            template_name (Optional[str], optional): Name of the template to get.
                                                 If None, returns the default template.
        
        Returns:
            Template: The requested template or the default template if not found
        """
        if template_name and template_name in self.templates:
            return self.templates[template_name]
        
        # Return default template if not found
        if template_name:
            logger.warning(f"Template not found: {template_name}, using default template")
        
        return self.default_template
    
    def apply_template(self, template_name: Optional[str], post_data: Dict[str, Any]) -> str:
        """
        Apply a template to post data.
        
        Args:
            template_name (Optional[str]): Name of the template to apply.
                                       If None, uses the default template.
            post_data (Dict[str, Any]): Post data to apply to the template
        
        Returns:
            str: The rendered markdown content
        """
        # Get the template
        template = self.get_template(template_name)
        
        # Prepare template variables
        template_vars = {
            'title': post_data.get('title', ''),
            'date': post_data.get('date', ''),
            'author': post_data.get('author', ''),
            'url': post_data.get('url', ''),
            'content': post_data.get('content', ''),
            'comments': post_data.get('comments', '')
        }
        
        # Add any additional frontmatter fields
        additional_frontmatter = []
        for key, value in post_data.items():
            if key not in ['title', 'date', 'author', 'url', 'content', 'comments']:
                # Format value based on type
                if isinstance(value, bool):
                    formatted_value = str(value).lower()
                elif isinstance(value, (int, float)):
                    formatted_value = str(value)
                else:
                    formatted_value = f'"{value}"'
                
                additional_frontmatter.append(f"{key}: {formatted_value}")
        
        template_vars['additional_frontmatter'] = '\n'.join(additional_frontmatter)
        
        # Apply the template
        try:
            return template.safe_substitute(template_vars)
        except Exception as e:
            logger.error(f"Error applying template: {e}")
            # Fall back to default template
            return self.default_template.safe_substitute(template_vars)
    
    def create_example_template(self, output_path: str) -> bool:
        """
        Create an example template file.
        
        Args:
            output_path (str): Path to save the example template
        
        Returns:
            bool: True if successful, False otherwise
        """
        example_template = """---
title: "${title}"
date: "${date}"
author: "${author}"
original_url: "${url}"
${additional_frontmatter}
---

# ${title}

*Published on ${date} by ${author}*

---

${content}

---

## Comments

${comments}

---

*This post was downloaded from [${url}](${url})*
"""
        
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(example_template)
            logger.info(f"Created example template at {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error creating example template: {e}")
            return False


def create_example_templates(output_dir: str) -> bool:
    """
    Create example template files in the specified directory.
    
    Args:
        output_dir (str): Directory to save example templates
    
    Returns:
        bool: True if successful, False otherwise
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a basic template
    basic_template_path = os.path.join(output_dir, "basic.template")
    basic_template = """---
title: "${title}"
date: "${date}"
author: "${author}"
original_url: "${url}"
${additional_frontmatter}
---

# ${title}

*Published on ${date} by ${author}*

${content}

${comments}
"""
    
    # Create an academic template
    academic_template_path = os.path.join(output_dir, "academic.template")
    academic_template = """---
title: "${title}"
date: "${date}"
author: "${author}"
original_url: "${url}"
${additional_frontmatter}
---

# ${title}

**Author:** ${author}  
**Date:** ${date}  
**Source:** [Original Article](${url})

## Abstract

This is a Substack article titled "${title}" by ${author}.

## Content

${content}

## Notes

${comments}

## Citation

${author}. (${date}). ${title}. Retrieved from ${url}
"""
    
    # Create a blog template
    blog_template_path = os.path.join(output_dir, "blog.template")
    blog_template = """---
layout: post
title: "${title}"
date: "${date}"
author: "${author}"
original_url: "${url}"
${additional_frontmatter}
---

<h1>${title}</h1>
<p class="meta">Published on ${date} by ${author}</p>

<div class="post-content">
${content}
</div>

<div class="comments">
<h2>Comments</h2>
${comments}
</div>

<div class="footer">
<p>Originally published at <a href="${url}">${url}</a></p>
</div>
"""
    
    try:
        # Write the templates
        with open(basic_template_path, 'w', encoding='utf-8') as f:
            f.write(basic_template)
        
        with open(academic_template_path, 'w', encoding='utf-8') as f:
            f.write(academic_template)
        
        with open(blog_template_path, 'w', encoding='utf-8') as f:
            f.write(blog_template)
        
        logger.info(f"Created example templates in {output_dir}")
        return True
    except Exception as e:
        logger.error(f"Error creating example templates: {e}")
        return False
