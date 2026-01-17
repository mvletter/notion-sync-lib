"""Block operations for Notion sync.

This module re-exports functions from specialized modules for backwards
compatibility. New code should import directly from the specific modules:

- notion_sync.fetch: fetch_page_blocks, fetch_blocks_recursive
- notion_sync.extract: extract_block_text, extract_rich_text
- notion_sync.modify: delete_all_blocks, append_blocks
"""

# Re-export for backwards compatibility
from notion_sync.fetch import fetch_page_blocks, fetch_blocks_recursive
from notion_sync.extract import extract_block_text, extract_rich_text
from notion_sync.modify import delete_all_blocks, append_blocks

__all__ = [
    # Fetch operations
    "fetch_page_blocks",
    "fetch_blocks_recursive",
    # Extract operations
    "extract_block_text",
    "extract_rich_text",
    # Modify operations
    "delete_all_blocks",
    "append_blocks",
]
