"""
Block operations for Notion sync.

Functions for fetching, extracting text from, and manipulating Notion blocks.
Supports recursive fetching of nested block structures.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.lib.notion_sync.client import RateLimitedNotionClient

logger = logging.getLogger(__name__)


# =============================================================================
# FETCH OPERATIONS
# =============================================================================


def fetch_page_blocks(client: "RateLimitedNotionClient", page_id: str) -> list[dict]:
    """
    Fetch top-level blocks from a Notion page.

    Args:
        client: RateLimitedNotionClient instance
        page_id: Notion page ID

    Returns:
        List of block dicts (top-level only, no children fetched)
    """
    logger.debug(f"Fetching top-level blocks for page {page_id}")
    blocks = client.get_blocks(page_id)
    logger.debug(f"Fetched {len(blocks)} top-level blocks")
    return blocks


def fetch_blocks_recursive(client: "RateLimitedNotionClient", page_id: str) -> list[dict]:
    """
    Fetch ALL blocks from a Notion page, including nested children.

    Recursively traverses the block tree, fetching children for any block
    with has_children=True. Children are added to the block dict under
    the '_children' key.

    Handles special block types:
    - table: fetches table_row children
    - column_list: fetches column children
    - toggle: fetches nested content
    - callout: fetches nested content
    - bulleted_list_item, numbered_list_item: fetches nested items
    - quote: fetches nested content
    - synced_block: fetches synced content

    Args:
        client: RateLimitedNotionClient instance
        page_id: Notion page ID

    Returns:
        List of block dicts with nested children under '_children' key
    """
    logger.debug(f"Fetching blocks recursively for page {page_id}")

    top_level_blocks = client.get_blocks(page_id)

    def fetch_children_recursive(blocks: list[dict], depth: int = 0) -> list[dict]:
        """Recursively fetch children for blocks that have them."""
        result = []

        for block in blocks:
            block_id = block.get("id")
            block_type = block.get("type", "unknown")
            has_children = block.get("has_children", False)

            # Create a copy to avoid mutating the original
            enriched_block = dict(block)

            if has_children:
                logger.debug(
                    f"{'  ' * depth}Fetching children for {block_type} block {block_id}"
                )
                try:
                    children = client.get_blocks(block_id)
                    # Recursively fetch children of children
                    enriched_children = fetch_children_recursive(children, depth + 1)
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

    enriched_blocks = fetch_children_recursive(top_level_blocks)

    # Count total blocks for logging
    def count_blocks(blocks: list[dict]) -> int:
        total = len(blocks)
        for block in blocks:
            if "_children" in block:
                total += count_blocks(block["_children"])
        return total

    total_count = count_blocks(enriched_blocks)
    logger.info(f"Fetched {total_count} total blocks (including nested) for page {page_id}")

    return enriched_blocks


# =============================================================================
# TEXT EXTRACTION
# =============================================================================


def _extract_rich_text(rich_text: list[dict]) -> str:
    """
    Extract plain text from a Notion rich_text array.

    Args:
        rich_text: List of rich_text objects from Notion API

    Returns:
        Concatenated plain text from all segments
    """
    if not rich_text:
        return ""
    return "".join(item.get("plain_text", "") for item in rich_text)


def extract_block_text(block: dict) -> str:
    """
    Extract plain text content from a Notion block for hashing/comparison.

    Handles different block types appropriately:
    - Text blocks (paragraph, heading_*, list items, quote, callout, toggle):
      Returns the plain text from rich_text
    - Code blocks: Returns text with language annotation
    - Divider: Returns "---"
    - Table: Returns "table:{width}"
    - Image/video/file/pdf/bookmark: Returns URL or caption
    - Embed: Returns the embed URL
    - Equation: Returns the expression
    - Table of contents, breadcrumb: Returns type identifier
    - Unsupported/unknown: Returns empty string

    Args:
        block: Block dict from Notion API

    Returns:
        Plain text representation of the block content
    """
    block_type = block.get("type", "")
    block_data = block.get(block_type, {})

    # Text-based blocks with rich_text content
    text_block_types = {
        "paragraph",
        "heading_1",
        "heading_2",
        "heading_3",
        "bulleted_list_item",
        "numbered_list_item",
        "quote",
        "callout",
        "toggle",
        "to_do",
    }

    if block_type in text_block_types:
        rich_text = block_data.get("rich_text", [])
        text = _extract_rich_text(rich_text)

        # For callout, include icon if present
        if block_type == "callout":
            icon = block_data.get("icon", {})
            if icon.get("type") == "emoji":
                emoji = icon.get("emoji", "")
                text = f"{emoji} {text}" if text else emoji

        # For to_do, include checked status
        if block_type == "to_do":
            checked = block_data.get("checked", False)
            prefix = "[x]" if checked else "[ ]"
            text = f"{prefix} {text}"

        return text

    # Code blocks
    if block_type == "code":
        rich_text = block_data.get("rich_text", [])
        language = block_data.get("language", "plain text")
        code_text = _extract_rich_text(rich_text)
        return f"```{language}\n{code_text}\n```"

    # Divider
    if block_type == "divider":
        return "---"

    # Table - return identifying info AND content if children available
    if block_type == "table":
        width = block_data.get("table_width", 0)
        # Check for children (local blocks have 'children', fetched blocks have '_children')
        children = block.get("_children") or block_data.get("children", [])
        if children:
            # Extract text from all table rows
            row_texts = []
            for child in children:
                if child.get("type") == "table_row":
                    cells = child.get("table_row", {}).get("cells", [])
                    cell_texts = [_extract_rich_text(cell) for cell in cells]
                    row_texts.append("|".join(cell_texts))
            return f"table:{width}:{';'.join(row_texts)}"
        return f"table:{width}"

    # Table row - extract cell contents
    if block_type == "table_row":
        cells = block_data.get("cells", [])
        cell_texts = [_extract_rich_text(cell) for cell in cells]
        return " | ".join(cell_texts)

    # Media blocks - return URL or caption
    media_types = {"image", "video", "file", "pdf"}
    if block_type in media_types:
        # Try to get URL
        media_data = block_data
        url = ""
        if media_data.get("type") == "external":
            url = media_data.get("external", {}).get("url", "")
        elif media_data.get("type") == "file":
            url = media_data.get("file", {}).get("url", "")

        # Get caption if available
        caption = _extract_rich_text(media_data.get("caption", []))

        if caption:
            return f"{block_type}:{caption}"
        elif url:
            return f"{block_type}:{url}"
        return f"{block_type}"

    # Bookmark
    if block_type == "bookmark":
        url = block_data.get("url", "")
        caption = _extract_rich_text(block_data.get("caption", []))
        if caption:
            return f"bookmark:{caption}"
        return f"bookmark:{url}"

    # Embed
    if block_type == "embed":
        url = block_data.get("url", "")
        return f"embed:{url}"

    # Equation
    if block_type == "equation":
        expression = block_data.get("expression", "")
        return f"equation:{expression}"

    # Link preview
    if block_type == "link_preview":
        url = block_data.get("url", "")
        return f"link:{url}"

    # Structural blocks - return type identifier
    if block_type in {"table_of_contents", "breadcrumb", "column_list", "column"}:
        return block_type

    # Child page/database - return title if available
    if block_type == "child_page":
        title = block_data.get("title", "")
        return f"child_page:{title}"

    if block_type == "child_database":
        title = block_data.get("title", "")
        return f"child_database:{title}"

    # Synced block - extract from synced_from if available
    if block_type == "synced_block":
        synced_from = block_data.get("synced_from")
        if synced_from:
            return f"synced_block:{synced_from.get('block_id', '')}"
        return "synced_block:original"

    # Template blocks
    if block_type == "template":
        rich_text = block_data.get("rich_text", [])
        return f"template:{_extract_rich_text(rich_text)}"

    # Link to page
    if block_type == "link_to_page":
        page_id = block_data.get("page_id", block_data.get("database_id", ""))
        return f"link_to_page:{page_id}"

    # Unknown block type - log and return empty
    if block_type and block_type not in {"unsupported"}:
        logger.debug(f"Unknown block type for text extraction: {block_type}")

    return ""


# =============================================================================
# MODIFICATION OPERATIONS
# =============================================================================


def delete_all_blocks(client: "RateLimitedNotionClient", page_id: str) -> int:
    """
    Delete all blocks from a Notion page.

    Fetches all top-level blocks and deletes them one by one.
    Skips archived blocks (which cannot be deleted).

    Args:
        client: RateLimitedNotionClient instance
        page_id: Notion page ID to clear

    Returns:
        Count of deleted blocks
    """
    logger.info(f"Deleting all blocks from page {page_id}")

    blocks = client.get_blocks(page_id)
    deleted_count = 0

    for block in blocks:
        block_id = block.get("id")
        is_archived = block.get("archived", False)

        if is_archived:
            logger.debug(f"Skipping archived block {block_id}")
            continue

        try:
            client.delete_block(block_id)
            deleted_count += 1
            logger.debug(f"Deleted block {block_id}")
        except Exception as e:
            logger.warning(f"Failed to delete block {block_id}: {e}")

    logger.info(f"Deleted {deleted_count} blocks from page {page_id}")
    return deleted_count


def append_blocks(
    client: "RateLimitedNotionClient",
    page_id: str,
    blocks: list[dict],
    after: str | None = None,
) -> int:
    """
    Append blocks to a Notion page.

    Batches blocks in groups of 100 to respect Notion API limits.
    Optionally inserts after a specific block ID.

    Args:
        client: RateLimitedNotionClient instance
        page_id: Notion page ID to append to
        blocks: List of block objects to append
        after: Optional block ID to insert after

    Returns:
        Count of appended blocks
    """
    if not blocks:
        logger.debug("No blocks to append")
        return 0

    logger.info(f"Appending {len(blocks)} blocks to page {page_id}")

    # Notion API limit is 100 blocks per request
    batch_size = 100
    appended_count = 0

    for i in range(0, len(blocks), batch_size):
        batch = blocks[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(blocks) + batch_size - 1) // batch_size

        logger.debug(
            f"Appending batch {batch_num}/{total_batches} ({len(batch)} blocks)"
        )

        try:
            # Only use 'after' for the first batch
            after_id = after if i == 0 else None
            client.append_blocks(page_id, batch, after=after_id)
            appended_count += len(batch)
        except Exception as e:
            logger.error(f"Failed to append batch {batch_num}: {e}")
            raise

    logger.info(f"Successfully appended {appended_count} blocks to page {page_id}")
    return appended_count
