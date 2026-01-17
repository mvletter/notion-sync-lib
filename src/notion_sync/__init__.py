"""Notion Sync Library - Rate-limited Notion API client with utilities."""

from notion_sync.client import get_notion_client, RateLimitedNotionClient
from notion_sync.utils import get_notion_token, extract_page_id, extract_page_title
from notion_sync.blocks import (
    fetch_page_blocks,
    fetch_blocks_recursive,
    extract_block_text,
    delete_all_blocks,
    append_blocks,
)
from notion_sync.diff import (
    # Diff generation
    generate_diff,
    generate_recursive_diff,
    # Diff execution
    execute_diff,
    execute_recursive_diff,
    # Utilities
    format_diff_preview,
    create_content_hash,
    extract_block_text as extract_block_text_diff,
)

__all__ = [
    # Client
    "get_notion_client",
    "RateLimitedNotionClient",
    # Utils
    "get_notion_token",
    "extract_page_id",
    "extract_page_title",
    # Blocks
    "fetch_page_blocks",
    "fetch_blocks_recursive",
    "extract_block_text",
    "delete_all_blocks",
    "append_blocks",
    # Diff generation
    "generate_diff",
    "generate_recursive_diff",
    # Diff execution
    "execute_diff",
    "execute_recursive_diff",
    # Diff utilities
    "format_diff_preview",
    "create_content_hash",
    "extract_block_text_diff",
]
