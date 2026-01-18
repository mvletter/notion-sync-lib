"""Notion Sync Library - Rate-limited Notion API client with smart diff-based sync.

Module structure:
- client: Rate-limited API wrapper
- fetch: Block fetching (top-level and recursive)
- extract: Text extraction from blocks
- modify: Block deletion and appending
- diff: Smart diff generation and execution
- columns: Column layout operations (with TypedDict return types)
- builders: Block creation utilities for testing and content generation
- utils: Token and URL utilities
"""

# Client
from notion_sync.client import get_notion_client, RateLimitedNotionClient

# Fetch operations
from notion_sync.fetch import fetch_page_blocks, fetch_blocks_recursive

# Extract operations
from notion_sync.extract import extract_block_text, extract_rich_text

# Modify operations
from notion_sync.modify import delete_all_blocks, append_blocks

# Diff operations
from notion_sync.diff import (
    generate_diff,
    generate_recursive_diff,
    execute_diff,
    execute_recursive_diff,
    format_diff_preview,
    create_content_hash,
)

# Column operations
from notion_sync.columns import (
    extract_block_ids,
    create_column_list,
    read_column_content,
    unwrap_column_list,
    # TypedDict types for column operations
    ColumnCreationResult,
    ColumnContent,
    UnwrapResult,
)

# Block builders
from notion_sync.builders import (
    make_paragraph,
    make_heading,
    make_toggle,
    make_bulleted_list_item,
    make_numbered_list_item,
    make_to_do,
    make_code,
    make_callout,
    make_quote,
    make_divider,
)

# Utils
from notion_sync.utils import get_notion_token, extract_page_id, extract_page_title

__all__ = [
    # Client
    "get_notion_client",
    "RateLimitedNotionClient",
    # Fetch
    "fetch_page_blocks",
    "fetch_blocks_recursive",
    # Extract
    "extract_block_text",
    "extract_rich_text",
    # Modify
    "delete_all_blocks",
    "append_blocks",
    # Diff
    "generate_diff",
    "generate_recursive_diff",
    "execute_diff",
    "execute_recursive_diff",
    "format_diff_preview",
    "create_content_hash",
    # Columns
    "extract_block_ids",
    "create_column_list",
    "read_column_content",
    "unwrap_column_list",
    "ColumnCreationResult",
    "ColumnContent",
    "UnwrapResult",
    # Builders
    "make_paragraph",
    "make_heading",
    "make_toggle",
    "make_bulleted_list_item",
    "make_numbered_list_item",
    "make_to_do",
    "make_code",
    "make_callout",
    "make_quote",
    "make_divider",
    # Utils
    "get_notion_token",
    "extract_page_id",
    "extract_page_title",
]
