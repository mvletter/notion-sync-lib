"""Block fetching operations for Notion sync.

Provides functions to retrieve blocks from Notion pages, either top-level
only or recursively including all nested children.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from notion_sync.client import RateLimitedNotionClient

logger = logging.getLogger(__name__)


def _strip_null_icon(block: dict) -> None:
    """Remove icon=null from a block's type-specific content dict (in-place).

    Notion's read API returns icon:null for some block types as an internal
    artefact. The write API rejects it with:
      "body.children[0].{type}.icon should be an object or `undefined`, instead was `null`"

    Blocks without an icon key, or with a valid icon value, pass through unmodified.
    """
    block_type = block.get("type")
    if not block_type:
        return
    content = block.get(block_type)
    if isinstance(content, dict) and "icon" in content and content["icon"] is None:
        content.pop("icon")


def fetch_page_blocks(client: "RateLimitedNotionClient", page_id: str) -> list[dict]:
    """Fetch top-level blocks from a Notion page.

    Use this when you only need the immediate children of a page,
    not nested content inside toggles, columns, etc.

    Args:
        client: RateLimitedNotionClient instance.
        page_id: Notion page ID.

    Returns:
        List of block dicts (top-level only, no children fetched).
    """
    logger.debug(f"Fetching top-level blocks for page {page_id}")
    blocks = client.get_blocks(page_id)
    for block in blocks:
        _strip_null_icon(block)
    logger.debug(f"Fetched {len(blocks)} top-level blocks")
    return blocks


def fetch_blocks_recursive(client: "RateLimitedNotionClient", page_id: str) -> list[dict]:
    """Fetch all blocks from a Notion page, including nested children.

    Recursively traverses the block tree, fetching children for any block
    with has_children=True. Children are stored under the '_children' key.

    Handles all block types with children:
    - table: fetches table_row children
    - column_list: fetches column children
    - toggle, callout, quote: fetches nested content
    - bulleted_list_item, numbered_list_item: fetches nested items
    - synced_block: fetches synced content

    Args:
        client: RateLimitedNotionClient instance.
        page_id: Notion page ID.

    Returns:
        List of block dicts with nested children under '_children' key.
    """
    logger.debug(f"Fetching blocks recursively for page {page_id}")

    top_level_blocks = client.get_blocks(page_id)

    def _fetch_children_recursive(blocks: list[dict], depth: int = 0) -> list[dict]:
        """Recursively fetch children for blocks that have them."""
        result = []

        for block in blocks:
            block_id = block.get("id")
            block_type = block.get("type", "unknown")
            has_children = block.get("has_children", False)

            # Create a copy to avoid mutating the original
            enriched_block = dict(block)

            # Strip icon:null before processing — Notion read API returns this as an
            # internal artefact that the write API rejects.
            _strip_null_icon(enriched_block)

            if has_children:
                logger.debug(
                    f"{'  ' * depth}Fetching children for {block_type} block {block_id}"
                )
                try:
                    children = client.get_blocks(block_id)
                    enriched_children = _fetch_children_recursive(children, depth + 1)
                    enriched_block["_children"] = enriched_children
                    logger.debug(
                        f"{'  ' * depth}Found {len(enriched_children)} children"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch children for block {block_id}: {e}"
                    )
                    enriched_block["_children"] = []

            result.append(enriched_block)

        return result

    enriched_blocks = _fetch_children_recursive(top_level_blocks)

    # Count total blocks for logging
    def _count_blocks(blocks: list[dict]) -> int:
        total = len(blocks)
        for block in blocks:
            if "_children" in block:
                total += _count_blocks(block["_children"])
        return total

    total_count = _count_blocks(enriched_blocks)
    logger.info(f"Fetched {total_count} total blocks (including nested) for page {page_id}")

    return enriched_blocks
