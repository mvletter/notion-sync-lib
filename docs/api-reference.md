# API Reference

Complete API documentation for notion-sync-lib.

## Table of Contents

- [Client](#client)
- [Fetch Operations](#fetch-operations)
- [Extract Operations](#extract-operations)
- [Modify Operations](#modify-operations)
- [Diff Operations](#diff-operations)
- [Column Operations](#column-operations)
- [Block Builders](#block-builders)
- [Utilities](#utilities)
- [Type Definitions](#type-definitions)

## Client

### `get_notion_client()`

Factory function to create a configured rate-limited Notion client.

**Returns:** `RateLimitedNotionClient`

**Example:**
```python
from notion_sync import get_notion_client

client = get_notion_client()
```

**Environment:**
Reads `NOTION_API_TOKEN` from environment variables or `.env` file.

---

### `RateLimitedNotionClient`

Wrapper around `notion_client.Client` with automatic rate limiting and retry logic.

**Features:**
- Rate limiting: 0.35s minimum between requests (max 3 req/sec)
- Automatic retry with exponential backoff on 429 errors
- Request counting via `request_count` attribute

#### `get_page(page_id: str) -> dict`

Get page metadata including title and properties.

**Parameters:**
- `page_id` (str): Notion page ID

**Returns:** Page object dict

---

#### `get_blocks(block_id: str) -> list[dict]`

Get child blocks of a page or block. Handles pagination automatically.

**Parameters:**
- `block_id` (str): ID of page or block to fetch children from

**Returns:** List of block dicts (top-level only, no nested children)

---

#### `append_blocks(page_id: str, blocks: list[dict], after: str | None = None) -> dict`

Append blocks to a page or block. Handles batching (max 100 blocks per request).

**Parameters:**
- `page_id` (str): ID of page or block to append to
- `blocks` (list[dict]): List of block objects in Notion API format
- `after` (str, optional): Block ID to insert after. If None, appends to end.

**Returns:** API response dict with `results` key containing created blocks

**Example:**
```python
blocks = [
    {"type": "paragraph", "paragraph": {"rich_text": [...]}}
]
result = client.append_blocks(page_id, blocks)
created_ids = [b["id"] for b in result["results"]]
```

---

#### `delete_block(block_id: str) -> dict`

Delete a block (archives it in Notion).

**Parameters:**
- `block_id` (str): ID of block to delete

**Returns:** API response dict

**Note:** Does not delete children. Use `_delete_block_recursive` from `diff` module for recursive deletion.

---

#### `update_block(block_id: str, data: dict) -> dict`

Update block content.

**Parameters:**
- `block_id` (str): ID of block to update
- `data` (dict): Update data in format `{block_type: {properties}}`

**Returns:** Updated block dict

**Example:**
```python
data = {
    "paragraph": {
        "rich_text": [{"type": "text", "text": {"content": "New text"}}]
    }
}
client.update_block(block_id, data)
```

---

#### `update_page_title(page_id: str, title: str) -> dict`

Update page title.

**Parameters:**
- `page_id` (str): Page ID
- `title` (str): New title text

**Returns:** Updated page dict

---

## Fetch Operations

### `fetch_page_blocks(client: RateLimitedNotionClient, page_id: str) -> list[dict]`

Fetch top-level blocks only (no nested children).

**Parameters:**
- `client`: RateLimitedNotionClient instance
- `page_id` (str): Notion page ID

**Returns:** List of block dicts without `_children`

**Use when:** You only need top-level blocks

---

### `fetch_blocks_recursive(client: RateLimitedNotionClient, page_id: str) -> list[dict]`

Fetch all blocks recursively, including nested children.

**Parameters:**
- `client`: RateLimitedNotionClient instance
- `page_id` (str): Notion page or block ID

**Returns:** List of block dicts with `_children` key for nested blocks

**Use when:** You need the complete block tree (e.g., for diff operations)

**Example:**
```python
blocks = fetch_blocks_recursive(client, page_id)

# Access nested children
for block in blocks:
    if "_children" in block:
        print(f"Block {block['id']} has {len(block['_children'])} children")
```

---

## Extract Operations

### `extract_block_text(block: dict) -> str`

Extract plain text content from any block type.

**Parameters:**
- `block` (dict): Notion block object

**Returns:** Plain text string, or empty string if no text

**Supported block types:**
- paragraph, heading_1/2/3, callout, quote, toggle
- bulleted_list_item, numbered_list_item, to_do
- code, table_row, column (with width_ratio)
- And more...

**Example:**
```python
text = extract_block_text(block)
print(f"{block['type']}: {text}")
```

---

### `extract_rich_text(rich_text: list[dict]) -> str`

Extract plain text from a Notion rich_text array.

**Parameters:**
- `rich_text` (list[dict]): Notion rich_text array

**Returns:** Concatenated plain text string

**Example:**
```python
rich_text = block["paragraph"]["rich_text"]
text = extract_rich_text(rich_text)
```

---

## Modify Operations

### `delete_all_blocks(client: RateLimitedNotionClient, page_id: str) -> None`

Delete all blocks from a page.

**Parameters:**
- `client`: RateLimitedNotionClient instance
- `page_id` (str): Page ID to clear

**Warning:** This is destructive. Use with caution.

---

### `append_blocks(client: RateLimitedNotionClient, page_id: str, blocks: list[dict], after: str | None = None) -> dict`

Batch append blocks with automatic batching (100-block limit).

**Parameters:**
- `client`: RateLimitedNotionClient instance
- `page_id` (str): Page or block ID to append to
- `blocks` (list[dict]): Blocks to append
- `after` (str, optional): Block ID to insert after

**Returns:** Combined API response dict

**Note:** Automatically splits large lists into batches of 100.

---

## Diff Operations

### `generate_diff(old_blocks: list[dict], new_blocks: list[dict]) -> list[dict]`

Generate diff operations using content-based matching (SequenceMatcher).

**Use when:** Pages have different structures, or you're syncing new content

**Parameters:**
- `old_blocks`: Current blocks in Notion (from `fetch_page_blocks`)
- `new_blocks`: Desired blocks to sync to

**Returns:** List of operation dicts with keys:
- `op`: "KEEP" | "UPDATE" | "REPLACE" | "INSERT" | "DELETE"
- `notion_block_id`: ID of Notion block (None for INSERT)
- `notion_block`: Full Notion block
- `local_block`: Local block data (None for DELETE/KEEP)
- `index`: Position in final result

**Example:**
```python
ops = generate_diff(notion_blocks, local_blocks)
print(f"Generated {len(ops)} operations")
```

---

### `generate_recursive_diff(old_blocks: list[dict], new_blocks: list[dict]) -> list[dict]`

Generate UPDATE-only operations by recursively comparing block trees.

**Use when:** Both pages have identical structure (same block IDs at same positions)

**Parameters:**
- `old_blocks`: Current blocks with `_children` (from `fetch_blocks_recursive`)
- `new_blocks`: Modified copy with same structure

**Returns:** List of UPDATE operation dicts with keys:
- `op`: "UPDATE"
- `notion_block_id`: Block ID to update
- `notion_block`: Original block
- `local_block`: Modified block
- `path`: Human-readable path like "0.children.1"

**Warning:** Returns empty list if structures don't match.

**Example:**
```python
original = fetch_blocks_recursive(client, page_id)
modified = apply_changes(original)
ops = generate_recursive_diff(original, modified)
```

---

### `execute_diff(client: RateLimitedNotionClient, ops: list[dict], page_id: str, dry_run: bool = False) -> dict`

Execute all diff operation types (INSERT/DELETE/UPDATE/REPLACE/KEEP).

**Use with:** Output from `generate_diff`

**Parameters:**
- `client`: RateLimitedNotionClient instance
- `ops`: Operations from `generate_diff`
- `page_id` (str): Page ID to sync to
- `dry_run` (bool): If True, only count operations without executing

**Returns:** Stats dict:
```python
{
    'kept': 5,
    'updated': 2,
    'inserted': 1,
    'deleted': 0,
    'replaced': 0
}
```

---

### `execute_recursive_diff(client: RateLimitedNotionClient, ops: list[dict], dry_run: bool = False) -> dict`

Execute UPDATE operations only.

**Use with:** Output from `generate_recursive_diff`

**Parameters:**
- `client`: RateLimitedNotionClient instance
- `ops`: Operations from `generate_recursive_diff`
- `dry_run` (bool): If True, only count operations

**Returns:** Stats dict:
```python
{
    'updated': 12,
    'skipped': 0,
    'type_mismatch': 1  # Only present if mismatches occurred
}
```

---

### `format_diff_preview(ops: list[dict]) -> str`

Generate human-readable preview of diff operations.

**Parameters:**
- `ops`: Operations from `generate_diff`

**Returns:** Multi-line string showing all changes

**Example:**
```python
preview = format_diff_preview(ops)
print(preview)
# Output:
# ============================================================
# Diff Preview
# ============================================================
# Summary: 1 new, 2 modified, 0 replaced, 0 deleted, 5 unchanged
# ...
```

---

### `create_content_hash(block: dict) -> str`

Create stable hash for block content (used internally by diff).

**Parameters:**
- `block` (dict): Notion block

**Returns:** First 16 characters of SHA256 hash

**Note:** Hash includes type, text, and special properties (checked for to_do, language for code, width_ratio for column).

---

## Column Operations

### `extract_block_ids(blocks: list[dict], prefix: str = "") -> dict[str, str]`

Recursively extract path-to-ID mapping from block tree.

**Parameters:**
- `blocks`: List of blocks with optional `_children`
- `prefix` (str): Path prefix for recursion

**Returns:** Dict mapping paths to block IDs

**Example:**
```python
blocks = fetch_blocks_recursive(client, column_list_id)
id_map = extract_block_ids(blocks)
# {'0': 'col1_id', '0.children.0': 'content1_id', ...}
```

---

### `create_column_list(client: RateLimitedNotionClient, page_id: str, columns: list[dict], after: str | None = None) -> ColumnCreationResult`

Create column_list and return created structure with IDs.

**Parameters:**
- `client`: RateLimitedNotionClient instance
- `page_id` (str): Page ID to append to
- `columns`: List of column dicts, each with:
  - `children` (list, required): Block list for column content
  - `width_ratio` (float, optional): Column width (0-1)
- `after` (str, optional): Block ID to insert after

**Returns:** `ColumnCreationResult` TypedDict:
```python
{
    'column_list_id': str,
    'block_ids': dict[str, str],  # Path-to-ID mapping
    'results': list[dict]  # Raw API response
}
```

**Raises:**
- `ValueError`: If columns is empty or invalid
- `TypeError`: If columns parameter is not a list

**Example:**
```python
columns = [
    {"children": [make_paragraph("Left")], "width_ratio": 0.6},
    {"children": [make_paragraph("Right")], "width_ratio": 0.4}
]
result = create_column_list(client, page_id, columns)
```

---

### `read_column_content(client: RateLimitedNotionClient, column_list_id: str) -> list[ColumnContent]`

Read content from all columns in a column_list.

**Parameters:**
- `client`: RateLimitedNotionClient instance
- `column_list_id` (str): ID of column_list to read

**Returns:** List of `ColumnContent` TypedDicts:
```python
[
    {
        'column_id': str,
        'width_ratio': float | None,
        'blocks': list[dict]
    },
    ...
]
```

---

### `unwrap_column_list(client: RateLimitedNotionClient, page_id: str, column_list_id: str, after: str | None = None, delete_original: bool = True) -> UnwrapResult`

Unwrap column_list to flat blocks.

**Parameters:**
- `client`: RateLimitedNotionClient instance
- `page_id` (str): Page ID where blocks will be created
- `column_list_id` (str): ID of column_list to unwrap
- `after` (str, optional): Block ID to insert after
- `delete_original` (bool): Whether to delete column_list after unwrapping

**Returns:** `UnwrapResult` TypedDict:
```python
{
    'new_block_ids': list[str],
    'source_blocks': list[dict],
    'deleted': bool
}
```

---

## Block Builders

Convenience functions for creating Notion block structures.

### `make_paragraph(text: str) -> dict`

Create a paragraph block.

---

### `make_heading(level: int, text: str) -> dict`

Create a heading block.

**Parameters:**
- `level` (int): 1, 2, or 3

**Raises:** `ValueError` if level not 1, 2, or 3

---

### `make_toggle(text: str, children: list[dict] | None = None) -> dict`

Create a toggle block with optional children.

---

### `make_bulleted_list_item(text: str, children: list[dict] | None = None) -> dict`

Create a bulleted list item.

---

### `make_numbered_list_item(text: str, children: list[dict] | None = None) -> dict`

Create a numbered list item.

---

### `make_to_do(text: str, checked: bool = False) -> dict`

Create a to-do (checkbox) block.

---

### `make_code(code: str, language: str = "python") -> dict`

Create a code block.

**Parameters:**
- `code` (str): Code content
- `language` (str): Programming language (default: "python")

---

### `make_callout(text: str, icon: str = "💡") -> dict`

Create a callout block.

**Parameters:**
- `text` (str): Callout text
- `icon` (str): Emoji icon (default: "💡")

---

### `make_quote(text: str) -> dict`

Create a quote block.

---

### `make_divider() -> dict`

Create a divider block.

---

## Utilities

### `get_notion_token() -> str`

Get Notion API token from environment.

**Returns:** Token string from `NOTION_API_TOKEN` environment variable

**Raises:** `ValueError` if token not found

---

### `extract_page_id(url: str) -> str`

Extract and format page ID from Notion URL.

**Parameters:**
- `url` (str): Notion page URL

**Returns:** Formatted page ID with hyphens

**Example:**
```python
page_id = extract_page_id("https://notion.so/Page-abc123def456")
# Returns: "abc123de-f456-..."
```

---

### `extract_page_title(page: dict) -> str`

Extract plain text title from page object.

**Parameters:**
- `page` (dict): Page object from `client.get_page()`

**Returns:** Plain text title string

---

## Type Definitions

### `ColumnCreationResult`

TypedDict returned by `create_column_list`:

```python
class ColumnCreationResult(TypedDict):
    column_list_id: str
    block_ids: dict[str, str]
    results: list[dict]
```

---

### `ColumnContent`

TypedDict for column content from `read_column_content`:

```python
class ColumnContent(TypedDict):
    column_id: str
    width_ratio: float | None
    blocks: list[dict[str, Any]]
```

---

### `UnwrapResult`

TypedDict returned by `unwrap_column_list`:

```python
class UnwrapResult(TypedDict):
    new_block_ids: list[str]
    source_blocks: list[dict[str, Any]]
    deleted: bool
```

---

## See Also

- [Usage Guide](usage-guide.md) - Practical examples and patterns
- [docs/pitfalls.md](pitfalls.md) - Common mistakes to avoid
