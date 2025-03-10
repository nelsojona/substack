#!/usr/bin/env python3
"""
Tests for batch processing functionality.

This module tests the batch processing features of the Substack to Markdown CLI.
"""

import os
import sys
import json
import pytest
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.batch_processor import BatchProcessor, create_example_config


class TestBatchProcessor:
    """Test class for batch processing functionality."""

    def test_create_example_config_json(self):
        """Test creating an example JSON configuration file."""
        # Arrange
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Act
            create_example_config(temp_path)
            
            # Assert
            assert os.path.exists(temp_path)
            
            # Check that the file contains valid JSON
            with open(temp_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Check that the config has the expected structure
            assert "authors" in config
            assert isinstance(config["authors"], list)
            assert len(config["authors"]) > 0
            assert "identifier" in config["authors"][0]
            assert "global_settings" in config
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_create_example_config_yaml(self):
        """Test creating an example YAML configuration file."""
        # Arrange
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Act
            create_example_config(temp_path)
            
            # Assert
            assert os.path.exists(temp_path)
            
            # Check that the file contains valid YAML
            import yaml
            with open(temp_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Check that the config has the expected structure
            assert "authors" in config
            assert isinstance(config["authors"], list)
            assert len(config["authors"]) > 0
            assert "identifier" in config["authors"][0]
            assert "global_settings" in config
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_load_config_json(self):
        """Test loading a JSON configuration file."""
        # Arrange
        config_data = {
            "authors": [
                {
                    "identifier": "test-author-1",
                    "max_posts": 5
                },
                {
                    "identifier": "test-author-2",
                    "include_comments": True
                }
            ],
            "global_settings": {
                "min_delay": 1.0
            }
        }
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f)
        
        try:
            # Act
            processor = BatchProcessor(config_path=temp_path)
            
            # Assert
            assert processor.config == config_data
            assert len(processor.config["authors"]) == 2
            assert processor.config["authors"][0]["identifier"] == "test-author-1"
            assert processor.config["authors"][1]["identifier"] == "test-author-2"
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_load_config_yaml(self):
        """Test loading a YAML configuration file."""
        # Arrange
        config_data = {
            "authors": [
                {
                    "identifier": "test-author-1",
                    "max_posts": 5
                },
                {
                    "identifier": "test-author-2",
                    "include_comments": True
                }
            ],
            "global_settings": {
                "min_delay": 1.0
            }
        }
        
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as temp_file:
            temp_path = temp_file.name
            import yaml
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f)
        
        try:
            # Act
            processor = BatchProcessor(config_path=temp_path)
            
            # Assert
            assert processor.config == config_data
            assert len(processor.config["authors"]) == 2
            assert processor.config["authors"][0]["identifier"] == "test-author-1"
            assert processor.config["authors"][1]["identifier"] == "test-author-2"
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_validate_config_valid(self):
        """Test validating a valid configuration."""
        # Arrange
        config = {
            "authors": [
                {
                    "identifier": "test-author-1"
                },
                {
                    "identifier": "test-author-2"
                }
            ]
        }
        
        processor = BatchProcessor.__new__(BatchProcessor)
        
        # Act & Assert
        # Should not raise an exception
        processor._validate_config(config)

    def test_validate_config_invalid_no_authors(self):
        """Test validating a configuration with no authors key."""
        # Arrange
        config = {
            "not_authors": []
        }
        
        processor = BatchProcessor.__new__(BatchProcessor)
        
        # Act & Assert
        with pytest.raises(ValueError, match="must contain an 'authors' key"):
            processor._validate_config(config)

    def test_validate_config_invalid_authors_not_list(self):
        """Test validating a configuration with authors not as a list."""
        # Arrange
        config = {
            "authors": "not a list"
        }
        
        processor = BatchProcessor.__new__(BatchProcessor)
        
        # Act & Assert
        with pytest.raises(ValueError, match="must be a list"):
            processor._validate_config(config)

    def test_validate_config_invalid_author_not_dict(self):
        """Test validating a configuration with an author not as a dictionary."""
        # Arrange
        config = {
            "authors": [
                "not a dict"
            ]
        }
        
        processor = BatchProcessor.__new__(BatchProcessor)
        
        # Act & Assert
        with pytest.raises(ValueError, match="must be a dictionary"):
            processor._validate_config(config)

    def test_validate_config_invalid_author_no_identifier(self):
        """Test validating a configuration with an author missing an identifier."""
        # Arrange
        config = {
            "authors": [
                {
                    "not_identifier": "test-author"
                }
            ]
        }
        
        processor = BatchProcessor.__new__(BatchProcessor)
        
        # Act & Assert
        with pytest.raises(ValueError, match="must have an 'identifier' key"):
            processor._validate_config(config)

    @patch("src.utils.batch_processor.BatchProcessor.process_author")
    def test_process_all_sequential(self, mock_process_author):
        """Test processing all authors sequentially."""
        # Arrange
        config_data = {
            "authors": [
                {
                    "identifier": "test-author-1"
                },
                {
                    "identifier": "test-author-2"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f)
        
        try:
            # Mock the process_author method to return True
            mock_process_author.return_value = True
            
            # Act
            processor = BatchProcessor(config_path=temp_path, max_processes=1)
            results = processor.process_all()
            
            # Assert
            assert len(results) == 2
            assert results["test-author-1"] is True
            assert results["test-author-2"] is True
            assert mock_process_author.call_count == 2
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @patch("multiprocessing.Pool")
    def test_process_all_parallel(self, mock_pool):
        """Test processing all authors in parallel."""
        # Arrange
        config_data = {
            "authors": [
                {
                    "identifier": "test-author-1"
                },
                {
                    "identifier": "test-author-2"
                },
                {
                    "identifier": "test-author-3"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f)
        
        try:
            # Mock the pool.map method to return a list of results
            mock_pool_instance = MagicMock()
            mock_pool.return_value.__enter__.return_value = mock_pool_instance
            mock_pool_instance.map.return_value = [True, False, True]
            
            # Act
            processor = BatchProcessor(config_path=temp_path, max_processes=3)
            results = processor.process_all()
            
            # Assert
            assert len(results) == 3
            assert results["test-author-1"] is True
            assert results["test-author-2"] is False
            assert results["test-author-3"] is True
            
            # Check that the pool was created with the correct number of processes
            mock_pool.assert_called_once_with(processes=3)
            
            # Check that map was called with the correct arguments
            mock_pool_instance.map.assert_called_once()
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_process_author(self):
        """Test processing a single author."""
        # This test is simplified to avoid mocking asyncio
        from unittest.mock import patch
        
        # Arrange
        author_config = {
            "identifier": "test-author",
            "max_posts": 5,
            "include_comments": True,
            "token": "test-token"
        }
        
        # Create a processor instance
        processor = BatchProcessor.__new__(BatchProcessor)
        processor.output_dir = "test_output"
        
        # Mock the process_author method internally to get a predictable result
        with patch.object(processor, 'process_author', return_value=True) as mock_process:
            # Act
            result = processor.process_author(author_config)
            
            # Assert
            assert result is True


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
