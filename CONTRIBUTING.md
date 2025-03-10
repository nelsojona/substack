# Contributing to Substack to Markdown CLI

Thank you for considering contributing to the Substack to Markdown CLI! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the issue list to see if the problem has already been reported. If it has and the issue is still open, add a comment to the existing issue instead of opening a new one.

When you are creating a bug report, please use the provided bug report template. The template will guide you through providing the necessary information about the issue. Include as many details as possible:

- **Use a clear and descriptive title** for the issue to identify the problem.
- **Describe the exact steps which reproduce the problem** in as much detail as possible.
- **Provide specific examples to demonstrate the steps**. Include links to files or GitHub projects, or copy/pasteable snippets, which you use in those examples.
- **Describe the behavior you observed after following the steps** and point out what exactly is the problem with that behavior.
- **Explain which behavior you expected to see instead and why.**
- **Include screenshots and animated GIFs** which show you following the described steps and clearly demonstrate the problem.
- **If the problem wasn't triggered by a specific action**, describe what you were doing before the problem happened.

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When you are creating an enhancement suggestion, please use the provided feature request template. The template will guide you through providing the necessary information about your suggestion. Include as many details as possible:

- **Use a clear and descriptive title** for the issue to identify the suggestion.
- **Provide a step-by-step description of the suggested enhancement** in as much detail as possible.
- **Provide specific examples to demonstrate the steps**. Include copy/pasteable snippets which you use in those examples.
- **Describe the current behavior** and **explain which behavior you expected to see instead** and why.
- **Include screenshots and animated GIFs** which help you demonstrate the steps or point out the part of the project which the suggestion is related to.
- **Explain why this enhancement would be useful** to most users.
- **List some other applications where this enhancement exists.**
- **Specify which version of the project you're using.**

### Pull Requests

When submitting a pull request, please use the provided pull request template. The template will guide you through providing the necessary information about your changes.

- Fill in the required template
- Do not include issue numbers in the PR title
- Include screenshots and animated GIFs in your pull request whenever possible
- Follow the Python style guide
- Include tests for any new functionality
- Document new code based on the documentation style guide
- End all files with a newline

## Development Process

### Setting Up Development Environment

1. Fork the repository
2. Clone your fork: `git clone https://github.com/nelsojona/substack.git`
3. Create a virtual environment: `python -m venv venv`
4. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
5. Install dependencies: `pip install -r requirements.txt`
6. Install development dependencies: `pip install -r requirements-dev.txt` (if available)

### Running Tests

```bash
python run_tests.py
```

Or use pytest directly:

```bash
pytest
```

For specific test files:

```bash
pytest tests/test_specific_module.py
```

### Code Style

This project follows PEP 8 style guidelines. Please ensure your code adheres to these standards.

You can use tools like `flake8` and `black` to check and format your code:

```bash
# Check code style
flake8 src tests

# Format code
black src tests
```

### Documentation

- Document all functions, classes, and methods using docstrings
- Keep the README.md updated with any new features or changes
- Update the documentation in the docs/ directory as needed

## Git Workflow

1. Create a new branch for your feature or bugfix: `git checkout -b feature/your-feature-name` or `git checkout -b fix/your-bugfix-name`
2. Make your changes
3. Run tests to ensure your changes don't break existing functionality
4. Commit your changes with a descriptive commit message
5. Push your branch to your fork: `git push origin feature/your-feature-name`
6. Submit a pull request to the main repository

## Release Process

The maintainers will handle the release process, which typically involves:

1. Updating the version number
2. Creating a changelog entry
3. Creating a new release on GitHub
4. Publishing to PyPI (if applicable)

## Questions?

If you have any questions or need help with the contribution process, feel free to open an issue with your question or reach out to the maintainers.

Thank you for contributing to the Substack to Markdown CLI!
