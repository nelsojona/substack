# Substack to Markdown CLI - Task List

This TASKS.md file outlines the implementation tasks for the Substack to Markdown CLI tool.

## Features

| Task ID | Description | Priority | Status | Effort | Dependencies | Responsible |
|---------|-------------|----------|--------|--------|--------------|-------------|
| FEAT-1  | Set up project structure and dependencies | High | ✅ Completed | 0.5d | | Dev |
| FEAT-2  | Implement command-line argument parsing | High | ✅ Completed | 0.5d | FEAT-1 | Dev |
| FEAT-3  | Create Substack API client module | High | ✅ Completed | 1d | FEAT-1 | Dev |
| FEAT-4  | Implement post fetching functionality | High | ✅ Completed | 1d | FEAT-3 | Dev |
| FEAT-5  | Create HTML to Markdown conversion module | High | ✅ Completed | 1d | FEAT-1 | Dev |
| FEAT-6  | Implement file saving functionality | Medium | ✅ Completed | 0.5d | FEAT-2 | Dev |
| FEAT-7  | Add progress reporting and verbose output | Low | ✅ Completed | 0.5d | FEAT-4, FEAT-5, FEAT-6 | Dev |
| FEAT-8  | Implement error handling and retries | Medium | ✅ Completed | 1d | FEAT-3, FEAT-4, FEAT-5 | Dev |

## Documentation

| Task ID | Description | Priority | Status | Effort | Dependencies | Responsible |
|---------|-------------|----------|--------|--------|--------------|-------------|
| DOC-1   | Create comprehensive README.md | Medium | ✅ Completed | 0.5d | | Dev |
| DOC-2   | Add inline code documentation and comments | Medium | ✅ Completed | 0.5d | FEAT-1, FEAT-2, FEAT-3, FEAT-4, FEAT-5, FEAT-6 | Dev |
| DOC-3   | Create usage examples | Medium | ✅ Completed | 0.5d | FEAT-2, FEAT-4, FEAT-5, FEAT-6 | Dev |
| DOC-4   | Document installation process | Medium | ✅ Completed | 0.5d | FEAT-1 | Dev |

## Testing

| Task ID | Description | Priority | Status | Effort | Dependencies | Responsible |
|---------|-------------|----------|--------|--------|--------------|-------------|
| TEST-1  | Write unit tests for Substack API client | Medium | ✅ Completed | 1d | FEAT-3, FEAT-4 | Dev |
| TEST-2  | Write unit tests for Markdown conversion | Medium | ✅ Completed | 1d | FEAT-5 | Dev |
| TEST-3  | Create integration tests for end-to-end workflow | Medium | ✅ Completed | 1d | FEAT-1, FEAT-2, FEAT-3, FEAT-4, FEAT-5, FEAT-6 | Dev |
| TEST-4  | Test error handling scenarios | Medium | ✅ Completed | 0.5d | FEAT-8 | Dev |
| TEST-5  | Fix all pytest errors | High | ✅ Completed | 0.5d | TEST-1, TEST-2, TEST-3, TEST-4 | Dev |
| TEST-6  | Create CLI test suite | Medium | ⏳ In Progress | 1d | FEAT-2, TEST-3 | Dev |

## Integration with Substack API Wrapper

| Task ID | Description | Priority | Status | Effort | Dependencies | Responsible |
|---------|-------------|----------|--------|--------|--------------|-------------|
| INT-1   | Enhance SubstackFetcher to use direct Post object methods | High | ✅ Completed | 1d | FEAT-3, FEAT-4 | Dev |
| INT-2   | Add support for fetching post comments | Medium | ⏳ Not Started | 1d | INT-1 | Dev |
| INT-3   | Implement newsletter metadata extraction | Medium | ⏳ Not Started | 0.5d | INT-1 | Dev |
| INT-4   | Add support for authenticated access to private content | Low | ✅ Completed | 2d | INT-1 | Dev |
| INT-5   | Implement concurrent fetching for improved performance | Medium | ⏳ Not Started | 1.5d | INT-1 | Dev |
| INT-6   | Add support for exporting subscriber-only content | Low | ⏳ Not Started | 1d | INT-4 | Dev |
| INT-7   | Create utility functions for working with Substack API objects | Medium | ⏳ Not Started | 1d | INT-1 | Dev |
| INT-8   | Implement caching mechanism for API responses | Low | ⏳ Not Started | 1d | INT-1, INT-7 | Dev |

## Extended Features

| Task ID | Description | Priority | Status | Effort | Dependencies | Responsible |
|---------|-------------|----------|--------|--------|--------------|-------------|
| EXT-1   | Add support for custom Markdown templates | Low | ⏳ Not Started | 1d | FEAT-5 | Dev |
| EXT-2   | Implement batch processing for multiple authors | Medium | ⏳ Not Started | 1d | FEAT-4, INT-1 | Dev |
| EXT-3   | Add support for filtering posts by date range | Medium | ⏳ Not Started | 0.5d | FEAT-4, INT-1 | Dev |
| EXT-4   | Implement export to other formats (e.g., PDF, HTML) | Low | ⏳ Not Started | 2d | FEAT-5 | Dev |
| EXT-5   | Add support for downloading and embedding images | Medium | ✅ Completed | 1.5d | FEAT-5, INT-1 | Dev |
| EXT-6   | Integrate with Oxylabs for proxying requests | Medium | ⏳ Not Started | 1d | FEAT-3, FEAT-4 | Dev |
| EXT-7   | Add support for environment variables via .env file | Medium | ✅ Completed | 0.5d | FEAT-1 | Dev |
