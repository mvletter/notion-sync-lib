"""Column operations for Notion sync.

Functions for creating, reading, and manipulating column_list/column structures.
Handles column layout operations including width_ratio preservation.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from notion_sync.client import RateLimitedNotionClient

logger = logging.getLogger(__name__)


# =============================================================================
# EXTRACTION UTILITIES
# =============================================================================


def extract_block_ids(blocks: list[dict], prefix: str = "") -> dict[str, str]:
    """Recursively extract path-to-ID mapping from a block tree.

    Traverses a block tree (with _children keys) and builds a map from
    relative paths to block IDs. Useful after creating column structures
    to update mappings with new block IDs.

    Args:
        blocks: List of blocks with optional _children.
        prefix: Path prefix for recursion (e.g., "0.children.").

    Returns:
        Dict mapping paths to block IDs.
        Example: {"0": "abc123", "0.children.0": "def456", "1": "ghi789"}
    """
    result: dict[str, str] = {}
    for i, block in enumerate(blocks):
        path = f"{prefix}{i}" if prefix else str(i)
        block_id = block.get("id")
        if block_id:
            result[path] = block_id

        children = block.get("_children", [])
        if children:
            child_results = extract_block_ids(children, f"{path}.children.")
            result.update(child_results)

    return result


# =============================================================================
# COLUMN BUILDING
# =============================================================================


def _build_column_list_block(
    columns: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a column_list block structure for Notion API.

    Internal helper - use create_column_list() for the public API.

    Args:
        columns: List of column dicts, each with:
            - children: List of block dicts for column content
            - width_ratio: Optional float for column width (e.g., 0.7 for 70%)

    Returns:
        Complete column_list block dict ready for Notion API.
    """
    column_children = []

    for col in columns:
        children = col.get("children", [])
        width_ratio = col.get("width_ratio")

        column_data: dict[str, Any] = {"children": children}
        if width_ratio is not None:
            column_data["width_ratio"] = width_ratio

        column_children.append({
            "type": "column",
            "column": column_data
        })

    return {
        "type": "column_list",
        "column_list": {
            "children": column_children
        }
    }


def create_column_list(
    client: "RateLimitedNotionClient",
    page_id: str,
    columns: list[dict[str, Any]],
    after: str | None = None,
) -> dict[str, Any]:
    """Create a column_list in Notion and return the created structure.

    Builds and appends a column_list block to the specified page, then
    fetches the created structure to get all child block IDs.

    Args:
        client: RateLimitedNotionClient instance.
        page_id: Notion page ID to append to.
        columns: List of column dicts (see build_column_list_block).
        after: Optional block ID to insert after.

    Returns:
        Dict with:
            - column_list_id: ID of created column_list
            - block_ids: Dict mapping paths to IDs (from extract_block_ids)
            - results: Raw API response results
    """
    from notion_sync.fetch import fetch_blocks_recursive

    # Build and create the column_list
    column_list_block = _build_column_list_block(columns)

    # Use rate-limited append_blocks (supports after parameter)
    result = client.append_blocks(page_id, [column_list_block], after=after)

    column_list_id = result["results"][0]["id"]
    logger.info(f"Created column_list {column_list_id[:12]}...")

    # Fetch created structure to get all child IDs
    children = fetch_blocks_recursive(client, column_list_id)
    block_ids = extract_block_ids(children)

    return {
        "column_list_id": column_list_id,
        "block_ids": block_ids,
        "results": result["results"],
    }


# =============================================================================
# COLUMN READING
# =============================================================================


def read_column_content(
    client: "RateLimitedNotionClient",
    column_list_id: str,
) -> list[dict[str, Any]]:
    """Read content from all columns in a column_list.

    Fetches all columns and their content blocks, returning a structured
    list that preserves the column organization.

    Args:
        client: RateLimitedNotionClient instance.
        column_list_id: ID of the column_list to read.

    Returns:
        List of dicts, one per column, each with:
            - column_id: ID of the column block
            - width_ratio: Column width ratio (if set)
            - blocks: List of content blocks in the column
    """
    from notion_sync.fetch import fetch_blocks_recursive

    # Fetch column_list children (columns)
    columns = client.get_blocks(column_list_id)
    result = []

    for column in columns:
        if column.get("type") != "column":
            continue

        column_id = column.get("id")
        column_data = column.get("column", {})
        width_ratio = column_data.get("width_ratio")

        # Fetch column content
        content_blocks = fetch_blocks_recursive(client, column_id)

        result.append({
            "column_id": column_id,
            "width_ratio": width_ratio,
            "blocks": content_blocks,
        })

    return result


# =============================================================================
# COLUMN UNWRAPPING
# =============================================================================


def unwrap_column_list(
    client: "RateLimitedNotionClient",
    page_id: str,
    column_list_id: str,
    after: str | None = None,
    delete_original: bool = True,
) -> dict[str, Any]:
    """Unwrap a column_list to flat blocks.

    Extracts all content blocks from columns and creates them as flat
    blocks on the page. Optionally deletes the original column_list.

    Args:
        client: RateLimitedNotionClient instance.
        page_id: Notion page ID where blocks will be created.
        column_list_id: ID of the column_list to unwrap.
        after: Optional block ID to insert after.
        delete_original: Whether to delete the column_list after unwrapping.

    Returns:
        Dict with:
            - new_block_ids: List of IDs of created flat blocks
            - source_blocks: List of original block data (with column context)
            - deleted: Whether the column_list was deleted
    """
    # Read all content from columns
    columns = read_column_content(client, column_list_id)

    # Flatten blocks from all columns (in order: col0, col1, ...)
    flat_blocks = []
    source_info = []

    for col_idx, col in enumerate(columns):
        for block_idx, block in enumerate(col["blocks"]):
            block_type = block.get("type")
            block_content = block.get(block_type, {})

            # Remove children key if present (we're flattening)
            if isinstance(block_content, dict):
                block_content = {k: v for k, v in block_content.items() if k != "children"}

            flat_blocks.append({
                "type": block_type,
                block_type: block_content,
            })

            source_info.append({
                "original_id": block.get("id"),
                "column_index": col_idx,
                "block_index": block_idx,
                "block_type": block_type,
            })

    if not flat_blocks:
        logger.warning(f"No blocks to unwrap from column_list {column_list_id}")
        return {
            "new_block_ids": [],
            "source_blocks": [],
            "deleted": False,
        }

    # Create flat blocks using rate-limited append_blocks
    result = client.append_blocks(page_id, flat_blocks, after=after)

    new_block_ids = [b["id"] for b in result.get("results", [])]
    logger.info(f"Created {len(new_block_ids)} flat blocks from column_list")

    # Delete original column_list if requested
    deleted = False
    if delete_original:
        try:
            client.delete_block(column_list_id)
            logger.info(f"Deleted column_list {column_list_id}")
            deleted = True
        except Exception as e:
            logger.error(f"Failed to delete column_list: {e}")

    return {
        "new_block_ids": new_block_ids,
        "source_blocks": source_info,
        "deleted": deleted,
    }
