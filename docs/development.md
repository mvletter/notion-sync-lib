# Development Guide

Guide for contributing to notion-sync-lib.

## Table of Contents

- [Setup](#setup)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)
- [Code Quality](#code-quality)
- [Common Pitfalls](#common-pitfalls)
- [Release Process](#release-process)

## Setup

### Clone and Install

```bash
# Clone repository
git clone https://github.com/mvletter/notion-sync-lib.git
cd notion-sync-lib

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Environment Setup

Create a `.env` file in the project root:

```bash
# Required for tests
NOTION_API_TOKEN=secret_xxx

# Test page ID (a page where test pages can be created)
TEST_PAGE_ID=your-test-page-id
```

### Editable Installation

When developing locally, install in editable mode:

```bash
pip install -e .
```

**Important:** After modifying source code, you may need to reinstall to pick up changes:

```bash
pip install -e . --force-reinstall --no-deps
```

## Project Structure

```
notion-sync-lib/
├── src/notion_sync/           # Library source code
│   ├── __init__.py           # Public API exports
│   ├── client.py             # Rate-limited API wrapper
│   ├── fetch.py              # Block fetching (top-level and recursive)
│   ├── extract.py            # Text extraction from blocks
│   ├── modify.py             # Block deletion and appending
│   ├── diff.py               # Smart diff generation and execution
│   ├── columns.py            # Column layout operations (with TypedDict)
│   ├── builders.py           # Block creation utilities
│   └── utils.py              # Token and URL utilities
│
├── tests/                     # Integration test suite
│   ├── conftest.py           # Pytest fixtures and helpers
│   ├── test_live_basic.py    # Basic operations tests
│   ├── test_live_diff.py     # Diff functionality tests
│   ├── test_live_columns.py  # Column operations tests
│   ├── test_live_advanced.py # Advanced features tests
│   ├── test_live_block_types.py  # Block type tests
│   ├── test_live_zz_user_actions.py  # Manual user action tests
│   ├── test_columns.py       # Unit tests for column utilities
│   └── test_width_ratio.py   # Width ratio handling tests
│
├── docs/                      # Documentation
│   ├── usage-guide.md        # Complete usage guide
│   ├── api-reference.md      # Full API documentation
│   ├── development.md        # This file
│   ├── architecture.md       # System architecture
│   ├── database.md           # Database structure (if applicable)
│   ├── patterns.md           # Code patterns
│   ├── pitfalls.md           # Common mistakes
│   └── features/             # Feature specifications
│
├── pyproject.toml            # Project configuration
├── README.md                 # Short, wervende intro
└── LICENSE                   # MIT License
```

## Running Tests

### Test Suite Overview

The integration test suite has **25 tests total**:
- 23 automated tests
- 2 manual tests (require user interaction)

### Running Automated Tests

```bash
# All automated tests with logging
pytest -v --log-cli-level=INFO -m "not manual"

# Specific test files
pytest tests/test_live_basic.py -v --log-cli-level=INFO
pytest tests/test_live_diff.py -v --log-cli-level=INFO
pytest tests/test_live_columns.py -v --log-cli-level=INFO

# Unit tests only
pytest tests/test_columns.py tests/test_width_ratio.py -v
```

### Running Manual Tests

Manual tests require user interaction (input prompts):

```bash
# Manual tests require -s flag for input() prompts
pytest -s -v --log-cli-level=INFO -m "manual"
```

### Running All Tests

```bash
# All tests (automated + manual)
pytest -s -v --log-cli-level=INFO
```

### Test Configuration

Tests are configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
log_cli = true
log_cli_level = "INFO"
markers = [
    "manual: marks tests as requiring manual user interaction (input prompts)",
]
```

### Prerequisites for Tests

1. Set `NOTION_API_TOKEN` in environment or `.env` file
2. Set `TEST_PAGE_ID` to a Notion page where test pages can be created
3. Ensure API token has appropriate permissions

### Test Fixtures

The test suite uses session-scoped fixtures that create two test pages:
- `master_page`: Primary test page
- `clone_page`: Secondary page for sync testing

After each test, an auto-sync runs from master to clone to verify changes.

## Code Quality

### Type Checking with MyPy

```bash
mypy src/notion_sync
```

Configuration in `pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true
```

### Linting with Ruff

```bash
# Check code
ruff check src/ tests/

# Auto-fix issues
ruff check --fix src/ tests/
```

Configuration in `pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]
```

### Code Style Guidelines

1. **Line length**: 100 characters max
2. **Type hints**: All public functions must have type hints
3. **Docstrings**: All public functions must have docstrings
4. **Naming**:
   - Private functions: `_function_name`
   - Constants: `UPPER_CASE`
   - Type hints: Use `list[dict]` not `List[Dict]` (Python 3.10+)

### TypedDict Usage

For complex return types, use TypedDict:

```python
from typing import TypedDict

class MyResult(TypedDict):
    """Result from my_function."""
    field1: str
    field2: list[dict]

def my_function() -> MyResult:
    return {"field1": "value", "field2": []}
```

## Common Pitfalls

See [docs/pitfalls.md](pitfalls.md) for detailed explanations. Key development pitfalls:

### 1. Using the Wrong Diff Function

**Problem:** Using `generate_diff` when you should use `generate_recursive_diff` or vice versa.

**Solution:**
- Different structures → `generate_diff` + `execute_diff`
- Identical structure, only text changes → `generate_recursive_diff` + `execute_recursive_diff`

See: `docs/pitfalls.md#api-wrong-diff-function`

### 2. Nested Blocks Format

**Problem:** Blocks from `fetch_blocks_recursive` have `_children` at root, but Notion API expects `block_type.children`.

**Solution:** Always use `_prepare_block_for_api` before inserting:

```python
from notion_sync.diff import _prepare_block_for_api

# Fetch blocks with _children
blocks = fetch_blocks_recursive(client, page_id)

# Prepare for API (converts _children → block_type.children)
api_blocks = [_prepare_block_for_api(b) for b in blocks]
client.append_blocks(page_id, api_blocks)
```

See: `docs/pitfalls.md#api-nested-blocks-format`

### 3. Error Handling

**Problem:** Catching all exceptions silently.

**Solution:** Always re-raise unless you have a specific reason not to:

```python
try:
    client.update_block(block_id, data)
except Exception as e:
    logger.error(f"Failed to update block: {e}")
    raise  # Don't swallow the error!
```

### 4. Input Validation

**Problem:** Not validating parameters in public functions.

**Solution:** Validate at function entry:

```python
def my_function(columns: list[dict]) -> None:
    if not isinstance(columns, list):
        raise TypeError(f"columns must be a list, got {type(columns).__name__}")

    if not columns:
        raise ValueError("columns must be a non-empty list")

    # ... rest of function
```

## Release Process

### Version Numbering

We use semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking API changes
- **MINOR**: New features, backwards compatible
- **PATCH**: Bug fixes, backwards compatible

### Creating a Release

1. **Update version** in `pyproject.toml`:
   ```toml
   version = "0.4.0"
   ```

2. **Update CHANGELOG** (if exists) with changes

3. **Run full test suite**:
   ```bash
   pytest -s -v --log-cli-level=INFO
   ```

4. **Tag release**:
   ```bash
   git tag -a v0.4.0 -m "Release v0.4.0"
   git push origin v0.4.0
   ```

5. **Create GitHub release** from tag with release notes

### Publishing to PyPI (Future)

When ready for PyPI:

```bash
# Build distribution
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

## Contributing

### Pull Request Process

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/your-feature`
3. **Make changes** with tests
4. **Run tests**: `pytest -v`
5. **Run linting**: `ruff check src/ tests/`
6. **Commit**: Follow conventional commits format
7. **Push** and create Pull Request

### Commit Message Format

Use conventional commits:

```
feat: add support for table blocks
fix: handle archived blocks in diff
docs: update API reference
test: add column unwrap tests
refactor: simplify diff matching logic
```

### Code Review Guidelines

- All PRs require review
- Tests must pass
- Code coverage should not decrease
- Documentation must be updated

## Documentation

### Updating Documentation

When adding features:

1. Update relevant docs in `docs/`
2. Add examples to `docs/usage-guide.md`
3. Add API docs to `docs/api-reference.md`
4. Update README if it affects quick start

### Documentation Structure

- **README.md**: Short intro, installation, quick start
- **docs/usage-guide.md**: Complete examples and patterns
- **docs/api-reference.md**: Full API documentation
- **docs/pitfalls.md**: Common mistakes and solutions
- **docs/architecture.md**: System design
- **docs/patterns.md**: Code patterns and best practices

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/mvletter/notion-sync-lib/issues)
- **Discussions**: [GitHub Discussions](https://github.com/mvletter/notion-sync-lib/discussions)
- **Documentation**: Check `docs/` directory first

## License

MIT License - see [LICENSE](../LICENSE) for details.
