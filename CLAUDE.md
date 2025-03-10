# Claude Memory for Substack to Markdown CLI

## Common Commands

### Run Tests
```bash
python -m pytest
```

### Run Direct Downloader
```bash
python main.py direct --author <author_identifier> --output ./output
```

### Run Optimized CLI
```bash
python main.py optimized download --author <author_identifier>
```

### Run Classic Interface
```bash
python main.py classic --author <author_identifier>
```

## Project Structure
- `src/core/`: Core functionality modules
- `src/utils/`: Utility functions and helper classes
- `scripts/`: Standalone scripts and utilities
- `docs/`: Documentation files
- `logs/`: Log files
- `tests/`: Test suite

## Code Style Preferences
- Use type hints for function signatures
- Use descriptive variable names
- Include docstrings for all modules, classes, and functions
- Follow PEP 8 style guidelines