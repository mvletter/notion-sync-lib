# notion-sync-lib

Rate-limited Notion API client with smart diff-based sync.

## Features

- **Rate-limited client**: Automatic rate limiting (max 3 requests/second) with exponential backoff on 429 errors
- **Block operations**: Fetch, create, update, and delete Notion blocks
- **Recursive fetching**: Fetch entire page trees including nested children
- **Smart diff sync**: Content-based diffing using SequenceMatcher for minimal API calls
- **Leading insert handling**: Workaround for Notion API's lack of `before` parameter

## Installation

```bash
pip install notion-sync-lib
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
from notion_sync import get_notion_client, extract_page_id

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

### Diff Operations

The diff generates these operation types:

- `KEEP`: Block unchanged, no API call needed
- `UPDATE`: Same block type, different content - uses update API
- `REPLACE`: Different block type - deletes and re-creates
- `INSERT`: New block - uses append API with `after` positioning
- `DELETE`: Block removed - uses delete API

## API Reference

### Client

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

### Utils

- `get_notion_token()` - Get API token from environment
- `extract_page_id(url)` - Extract and format page ID from Notion URL
- `extract_page_title(page)` - Get plain text title from page object

### Blocks

- `fetch_page_blocks(client, page_id)` - Fetch top-level blocks
- `fetch_blocks_recursive(client, page_id)` - Fetch all blocks with children
- `extract_block_text(block)` - Get plain text from any block type
- `delete_all_blocks(client, page_id)` - Clear all blocks from page
- `append_blocks(client, page_id, blocks, after=None)` - Batch append with 100-block limit

### Diff

- `generate_diff(old_blocks, new_blocks)` - Content-based diff using SequenceMatcher
- `generate_diff_positional(notion_blocks, local_blocks)` - Simple position-based diff
- `generate_recursive_diff(old_blocks, new_blocks)` - Diff for trees with identical structure
- `execute_diff(client, ops, page_id, dry_run=False)` - Apply diff operations
- `execute_recursive_diff(client, ops, dry_run=False)` - Apply UPDATE-only operations
- `format_diff_preview(ops)` - Human-readable diff summary
- `create_content_hash(block)` - Stable hash for content matching
- `blocks_equal(notion_block, local_block)` - Compare two blocks
- `has_leading_inserts(ops)` - Check for inserts before existing blocks
- `handle_leading_inserts(ops, client, page_id)` - Workaround for leading inserts

## License

MIT License - see [LICENSE](LICENSE) for details.
