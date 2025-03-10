# Substack Content Compiler for LLMs

This tool compiles downloaded Substack content into a format optimized for Large Language Models (LLMs). It processes Markdown files, extracts metadata, and creates a structured JSON file that can be easily used as context for LLMs.

## Features

- Processes all downloaded Substack content from author directories
- Extracts title, date, URL, and content from each post
- Handles image references by replacing them with placeholders
- Truncates content to a configurable maximum length
- Organizes posts by author with metadata
- Outputs a structured JSON file for easy LLM ingestion

## Prerequisites

- Python 3.6 or higher
- Required packages:
  - pyyaml
  - tqdm

Install dependencies:
```bash
pip install pyyaml tqdm
```

## Usage

```bash
python compile_substack_for_llm.py [--output OUTPUT] [--authors AUTHORS [AUTHORS ...]] [--max-length MAX_LENGTH] [--clean-images CLEAN_IMAGES]
```

### Arguments

- `--output`: Path to the output JSON file (default: `substack_compiled.json`)
- `--authors`: List of author directories to include (default: all authors in the output directory)
- `--max-length`: Maximum character length for each post (default: 100000)
- `--clean-images`: Whether to replace image references with placeholders (default: True)

### Examples

Compile all author content with default settings:
```bash
python compile_substack_for_llm.py
```

Compile content from specific authors:
```bash
python compile_substack_for_llm.py --authors tradecompanion mattstoller
```

Specify output file and maximum content length:
```bash
python compile_substack_for_llm.py --output my_llm_data.json --max-length 50000
```

## Output Format

The script generates a JSON file with the following structure:

```json
{
  "metadata": {
    "compiled_date": "ISO datetime",
    "author_count": number,
    "total_posts": number
  },
  "authors": [
    {
      "author": "author_name",
      "post_count": number,
      "posts": [
        {
          "title": "Post Title",
          "date": "YYYY-MM-DD",
          "author": "author_name",
          "url": "original URL",
          "slug": "filename_slug",
          "content": "Full post content..."
        },
        // More posts...
      ]
    },
    // More authors...
  ]
}
```

## LLM Usage

The compiled JSON file can be used as context for LLMs in several ways:

1. **Direct Context Loading**: Load the entire JSON file as context for your LLM.

2. **Selective Loading**: Use the JSON structure to selectively load specific authors or posts based on your needs.

3. **Search and Retrieval**: Implement a search function to find relevant posts based on keywords, then provide those as context.

4. **Metadata Filtering**: Filter posts by date, author, or other metadata before providing them as context.

## Notes

- The script handles YAML frontmatter in Markdown files, but some parsing errors may occur with certain content like titles with nested quotes.
- Image references are replaced with `[IMAGE: alt_text]` placeholders by default to reduce token usage when using the content with LLMs.
- Posts are sorted by date (newest first) for each author.