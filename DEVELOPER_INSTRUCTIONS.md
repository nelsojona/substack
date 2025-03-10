# Developer Instructions for Substack to Markdown CLI

## Overview

This document provides instructions for implementing the next high-priority tasks for the Substack to Markdown CLI project, writing corresponding tests, updating task documentation, and planning next steps.

## Implementation Instructions

### 1. Review Project Documentation

Begin by reviewing the following project documentation to understand the current state and priorities:

- `TASKS.md`: Understand the prioritized tasks and current progress
- `README.md`: Review the detailed documentation of features and usage
- `substack_direct_downloader.py`: Understand the core functionality
- `tests/`: Familiarize yourself with the testing infrastructure

### 2. Implement High-Priority Tasks

Based on the prioritization in `TASKS.md`, implement the following critical in-progress tasks:

#### INT-2: Add support for fetching post comments

1. Extend the SubstackDirectDownloader class to extract comment data from posts
2. Implement comment threading to preserve parent-child relationships
3. Add CLI option to include/exclude comments in the output
4. Store comment metadata in the database
5. Include comments in the markdown output with proper formatting

#### INT-3: Implement newsletter metadata extraction

1. Create a function to extract newsletter metadata (title, description, author info)
2. Add storage for newsletter metadata in the database schema
3. Implement CLI option to generate a newsletter index file
4. Add metadata to the frontmatter of markdown files
5. Create a summary report of newsletter statistics

#### INT-5: Implement concurrent fetching for improved performance

1. Enhance the connection pool to better handle concurrent API requests
2. Implement dynamic concurrency limits based on server response times
3. Add batching for API requests to reduce overhead
4. Optimize the semaphore implementation for better throughput
5. Implement proper error handling for concurrent operations

#### INT-6: Add support for exporting subscriber-only content

1. Enhance authentication mechanisms to handle different subscription tiers
2. Implement token refresh functionality to maintain authenticated sessions
3. Add detection for paywalled content with appropriate handling
4. Create specialized extraction methods for subscriber-only content
5. Add documentation for accessing private content

### 3. Write Comprehensive Tests

For each implemented feature, write the following types of tests:

#### Unit Tests

- Test individual components in isolation
- Verify component behavior with different inputs
- Test edge cases and error handling
- Mock external dependencies

```python
# Example unit test for comment extraction
import pytest
from unittest.mock import patch, MagicMock
from substack_direct_downloader import SubstackDirectDownloader

class TestCommentExtraction:
    @pytest.fixture
    def downloader(self):
        return SubstackDirectDownloader(author="testauthor")
        
    @patch("substack_direct_downloader.SubstackDirectDownloader._fetch_url")
    async def test_extract_comments_structure(self, mock_fetch, downloader):
        # Arrange
        mock_fetch.return_value = """
        <div class="comments-section">
            <div class="comment" id="comment-1">
                <div class="comment-body">Test comment 1</div>
                <div class="comment-author">Author 1</div>
                <div class="comment-replies">
                    <div class="comment" id="comment-2">
                        <div class="comment-body">Reply to comment 1</div>
                        <div class="comment-author">Author 2</div>
                    </div>
                </div>
            </div>
        </div>
        """
        
        # Act
        comments = await downloader.extract_comments("https://testauthor.substack.com/p/test-post")
        
        # Assert
        assert len(comments) == 1
        assert comments[0]["body"] == "Test comment 1"
        assert comments[0]["author"] == "Author 1"
        assert len(comments[0]["replies"]) == 1
        assert comments[0]["replies"][0]["body"] == "Reply to comment 1"
```

#### Integration Tests

- Test interactions between components
- Verify data flow through multiple components
- Test API integration points
- Ensure proper state management

```python
# Example integration test for subscriber-only content
import pytest
import os
from substack_direct_downloader import SubstackDirectDownloader

class TestSubscriberContent:
    @pytest.mark.asyncio
    async def test_download_subscriber_only_post(self):
        # Arrange
        test_token = os.environ.get("TEST_SUBSTACK_TOKEN", "test_token")
        test_url = "https://testauthor.substack.com/p/subscriber-only-post"
        output_dir = "test_output"
        
        # Act
        async with SubstackDirectDownloader(
            author="testauthor",
            output_dir=output_dir
        ) as downloader:
            downloader.set_auth_token(test_token)
            result = await downloader.download_post(test_url)
            
            # Read the generated file
            files = os.listdir(os.path.join(output_dir, "testauthor"))
            markdown_file = [f for f in files if f.endswith("subscriber-only-post.md")][0]
            with open(os.path.join(output_dir, "testauthor", markdown_file), "r") as f:
                content = f.read()
        
        # Assert
        assert result is True
        assert "This post is for paying subscribers" not in content
        assert len(content) > 1000  # Ensure we got full content, not just preview
```

#### End-to-End Tests

- Test complete user flows
- Verify application behavior across multiple components
- Test critical user journeys

```python
# Example E2E test for the CLI
import pytest
import subprocess
import os
import shutil

class TestCliEndToEnd:
    def setup_method(self):
        # Create test directory
        os.makedirs("e2e_test_output", exist_ok=True)
        
    def teardown_method(self):
        # Clean up test directory
        shutil.rmtree("e2e_test_output", ignore_errors=True)
        
    def test_cli_with_comments_option(self):
        # Act
        result = subprocess.run([
            "python", "substack_direct_downloader.py",
            "--author", "testauthor",
            "--output", "e2e_test_output",
            "--include-comments",
            "--max-posts", "1",
            "--verbose"
        ], capture_output=True, text=True)
        
        # Assert
        assert result.returncode == 0
        assert "Extracting comments" in result.stdout
        
        # Verify output files
        files = os.listdir(os.path.join("e2e_test_output", "testauthor"))
        assert len(files) > 0
        
        # Check if comments are included in the markdown
        with open(os.path.join("e2e_test_output", "testauthor", files[0]), "r") as f:
            content = f.read()
            assert "## Comments" in content
```

#### Performance Tests

- Test loading times and resource usage
- Verify performance with large datasets
- Test concurrency handling

```python
# Example performance test
import pytest
import time
import asyncio
from substack_direct_downloader import SubstackDirectDownloader

class TestPerformance:
    @pytest.mark.asyncio
    async def test_concurrent_download_performance(self):
        # Arrange
        start_time = time.time()
        test_urls = [
            "https://testauthor.substack.com/p/test-post-1",
            "https://testauthor.substack.com/p/test-post-2",
            "https://testauthor.substack.com/p/test-post-3",
            "https://testauthor.substack.com/p/test-post-4",
            "https://testauthor.substack.com/p/test-post-5"
        ]
        
        # Act
        async with SubstackDirectDownloader(
            author="testauthor",
            output_dir="perf_test_output",
            max_concurrency=5
        ) as downloader:
            tasks = [downloader.download_post(url) for url in test_urls]
            results = await asyncio.gather(*tasks)
            
        end_time = time.time()
        duration = end_time - start_time
        
        # Assert
        assert all(results)
        assert duration < 10  # Should complete in under 10 seconds with concurrency
```

### 4. Update Task Documentation

After implementing each task and its corresponding tests, update the following documentation:

#### Update TASKS.md

Update the status of completed tasks:

```markdown
| Task ID | Description | Priority | Status | Effort | Dependencies | Responsible |
|---------|-------------|----------|--------|--------|--------------|-------------|
| INT-2   | Add support for fetching post comments | Medium | ✅ Completed | 1d | INT-1 | Dev |
| INT-3   | Implement newsletter metadata extraction | Medium | ✅ Completed | 0.5d | INT-1 | Dev |
```

#### Update README.md

Add documentation for the new features:

```markdown
## Comment Extraction

The tool now supports extracting and including comments in the Markdown output:

```bash
python substack_direct_downloader.py --author big --include-comments
```

This will add a "Comments" section at the end of each post with all comments and replies properly formatted.

## Newsletter Metadata

You can now extract and include newsletter metadata:

```bash
python substack_direct_downloader.py --author big --extract-metadata --generate-index
```

This will create an additional `index.md` file with newsletter statistics and metadata.
```

### 5. Provide Next Steps

After completing the implementation and documentation updates, provide clear next steps:

1. Identify the next set of tasks to be implemented based on the priority order in TASKS.md
2. Highlight any dependencies that need to be addressed
3. Suggest improvements to the testing strategy
4. Recommend any architectural changes based on implementation experience
5. Provide a timeline for the next sprint

## Example Implementation Plan

```markdown
# Implementation Plan for Next Sprint (March 16-30, 2025)

## Completed Tasks

- INT-2: Add support for fetching post comments
- INT-3: Implement newsletter metadata extraction
- INT-5: Implement concurrent fetching for improved performance
- INT-6: Add support for exporting subscriber-only content

## Current Focus

- INT-7: Create utility functions for working with Substack API objects (70% complete)
- INT-8: Implement caching mechanism for API responses (40% complete)

## Next Tasks

1. Complete INT-7 and INT-8 by March 20
2. Begin work on EXT-2: Implement batch processing for multiple authors
   - Create batch configuration file format
   - Implement parallel processing of multiple authors
3. Start EXT-3: Add support for filtering posts by date range
   - Add CLI arguments for date filtering
   - Implement filter logic in post discovery

## Technical Recommendations

1. Refactor the authentication module to better handle token refresh
2. Implement a more robust error handling strategy for network failures
3. Add more comprehensive logging for better debugging
4. Consider implementing a plugin system for custom post processors

## Timeline

- March 16-20: Complete INT-7 and INT-8
- March 21-25: Implement EXT-2 (Batch processing)
- March 26-30: Begin EXT-3 (Date filtering)

## Dependencies and Blockers

- Need to improve test coverage for authentication edge cases
- Consider upgrading aiohttp to latest version for better performance
```

## Conclusion

By following these instructions, you will successfully implement the next high-priority tasks for the Substack to Markdown CLI, write comprehensive tests, update documentation, and plan the next steps for the project. This structured approach ensures consistent progress and maintains high code quality throughout the development process.
