# notion-sync-lib

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Rate-limited Notion API client with smart diff-based sync.

## Features

- **Rate-limited client**: Automatic rate limiting (max 3 requests/second) with exponential backoff on 429 errors
- **Block operations**: Fetch, create, update, and delete Notion blocks
- **Recursive fetching**: Fetch entire page trees including nested children
- **Smart diff sync**: Content-based diffing using SequenceMatcher for minimal API calls
- **Column support**: Create and manipulate column layouts

## Installation

```bash
pip install git+https://github.com/mvletter/notion-sync-lib.git
```

Or install from source:

```bash
pip install -e .
```

## Quick Start

### Setup

Set your Notion API token as an environment variable or in a `.env` file:

```bash
export NOTION_API_TOKEN=secret_xxx
```

Or create a `.env` file:

```
NOTION_API_TOKEN=secret_xxx
```

### Basic Usage

```python
from notion_sync import get_notion_client, extract_page_id, extract_page_title

# Create a rate-limited client
client = get_notion_client()

# Extract page ID from URL
page_id = extract_page_id("https://notion.so/My-Page-abc123def456...")

# Get page metadata
page = client.get_page(page_id)
print(f"Page title: {extract_page_title(page)}")

# Get page blocks (top-level only)
blocks = client.get_blocks(page_id)
print(f"Found {len(blocks)} blocks")
```

### Fetching Blocks Recursively

```python
from notion_sync import get_notion_client, fetch_blocks_recursive

client = get_notion_client()
page_id = "your-page-id"

# Fetch ALL blocks including nested children
# Children are stored under '_children' key
blocks = fetch_blocks_recursive(client, page_id)

def print_tree(blocks, indent=0):
    for block in blocks:
        block_type = block.get("type", "unknown")
        print(f"{'  ' * indent}{block_type}")
        if "_children" in block:
            print_tree(block["_children"], indent + 1)

print_tree(blocks)
```

### Diff-Based Sync

The library provides smart diffing to minimize API calls when syncing content:

```python
from notion_sync import (
    get_notion_client,
    fetch_page_blocks,
    generate_diff,
    execute_diff,
    format_diff_preview,
)

client = get_notion_client()
page_id = "your-page-id"

# Get current blocks from Notion
notion_blocks = fetch_page_blocks(client, page_id)

# Your desired blocks (e.g., from markdown conversion)
local_blocks = [
    {"type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": "Hello"}}]}},
    {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "World"}}]}},
]

# Generate diff operations
ops = generate_diff(notion_blocks, local_blocks)

# Preview changes (dry run)
print(format_diff_preview(ops))

# Execute the diff
stats = execute_diff(client, ops, page_id, dry_run=False)
print(f"Stats: {stats}")
# Output: {'kept': 5, 'updated': 2, 'inserted': 1, 'deleted': 0, 'replaced': 0}
```

### Recursive Diff (for translation sync)

When syncing translations where the block structure is identical:

```python
from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    generate_recursive_diff,
    execute_recursive_diff,
)

client = get_notion_client()

# Fetch original and translated blocks (same structure)
original_blocks = fetch_blocks_recursive(client, original_page_id)
translated_blocks = inject_translations(original_blocks, translations)

# Generate UPDATE-only operations
ops = generate_recursive_diff(original_blocks, translated_blocks)

# Execute updates
stats = execute_recursive_diff(client, ops, dry_run=False)
```

### Diff Operations

The diff generates these operation types:

- `KEEP`: Block unchanged, no API call needed
- `UPDATE`: Same block type, different content - uses update API
- `REPLACE`: Different block type - deletes and re-creates
- `INSERT`: New block - uses append API with `after` positioning
- `DELETE`: Block removed - uses delete API

## Module Structure

```
notion_sync/
├── client.py    # Rate-limited API wrapper
├── fetch.py     # Block fetching (top-level and recursive)
├── extract.py   # Text extraction from blocks
├── modify.py    # Block deletion and appending
├── diff.py      # Smart diff generation and execution
├── columns.py   # Column layout operations
├── utils.py     # Token and URL utilities
└── blocks.py    # Re-exports for backwards compatibility
```

## API Reference

### Client (`notion_sync.client`)

#### `get_notion_client() -> RateLimitedNotionClient`
Factory function to create a configured client. Reads `NOTION_API_TOKEN` from environment.

#### `RateLimitedNotionClient`
Wrapper around `notion_client.Client` with:
- Rate limiting (0.35s between requests)
- Automatic retry with exponential backoff on 429 errors
- Request counting via `request_count` attribute

Methods:
- `get_page(page_id)` - Get page metadata
- `get_blocks(block_id)` - Get child blocks (paginated)
- `append_blocks(page_id, blocks, after=None)` - Append blocks
- `delete_block(block_id)` - Delete a block
- `update_block(block_id, data)` - Update block content
- `update_page_title(page_id, title)` - Update page title

### Fetch (`notion_sync.fetch`)

- `fetch_page_blocks(client, page_id)` - Fetch top-level blocks only
- `fetch_blocks_recursive(client, page_id)` - Fetch all blocks with nested children under `_children` key

### Extract (`notion_sync.extract`)

- `extract_block_text(block)` - Get plain text from any block type
- `extract_rich_text(rich_text)` - Get plain text from a rich_text array

### Modify (`notion_sync.modify`)

- `delete_all_blocks(client, page_id)` - Clear all blocks from a page
- `append_blocks(client, page_id, blocks, after=None)` - Batch append with 100-block limit

### Diff (`notion_sync.diff`)

- `generate_diff(old_blocks, new_blocks)` - Content-based diff (use when structure may change)
- `generate_recursive_diff(old_blocks, new_blocks)` - Diff for identical structure, UPDATE-only
- `execute_diff(client, ops, page_id, dry_run=False)` - Apply full diff operations
- `execute_recursive_diff(client, ops, dry_run=False)` - Apply UPDATE-only operations
- `format_diff_preview(ops)` - Human-readable diff summary
- `create_content_hash(block)` - Stable hash for content matching

### Columns (`notion_sync.columns`)

- `extract_block_ids(blocks, prefix="")` - Extract path-to-ID mapping from block tree
- `create_column_list(client, page_id, columns, after=None)` - Create column_list and return IDs
- `read_column_content(client, column_list_id)` - Read all column content
- `unwrap_column_list(client, page_id, column_list_id, ...)` - Flatten columns to blocks

### Utils (`notion_sync.utils`)

- `get_notion_token()` - Get API token from environment
- `extract_page_id(url)` - Extract and format page ID from Notion URL
- `extract_page_title(page)` - Get plain text title from page object

## License

MIT License - see [LICENSE](LICENSE) for details.
