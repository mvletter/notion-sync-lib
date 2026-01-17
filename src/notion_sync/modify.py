"""Block modification operations for Notion sync.

Provides functions to delete and append blocks in Notion pages.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from notion_sync.client import RateLimitedNotionClient

logger = logging.getLogger(__name__)


def delete_all_blocks(client: "RateLimitedNotionClient", page_id: str) -> int:
    """Delete all blocks from a Notion page.

    Fetches all top-level blocks and deletes them one by one.
    Skips archived blocks (which cannot be deleted).

    Args:
        client: RateLimitedNotionClient instance.
        page_id: Notion page ID to clear.

    Returns:
        Count of deleted blocks.
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
    """Append blocks to a Notion page.

    Batches blocks in groups of 100 to respect Notion API limits.
    Tracks last inserted block ID across batches to maintain correct order.

    Args:
        client: RateLimitedNotionClient instance.
        page_id: Notion page ID to append to.
        blocks: List of block objects to append.
        after: Optional block ID to insert after.

    Returns:
        Count of appended blocks.
    """
    if not blocks:
        logger.debug("No blocks to append")
        return 0

    logger.info(f"Appending {len(blocks)} blocks to page {page_id}")

    # Notion API limit is 100 blocks per request
    batch_size = 100
    appended_count = 0
    last_block_id = after

    for i in range(0, len(blocks), batch_size):
        batch = blocks[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(blocks) + batch_size - 1) // batch_size

        logger.debug(
            f"Appending batch {batch_num}/{total_batches} ({len(batch)} blocks)"
        )

        try:
            result = client.append_blocks(page_id, batch, after=last_block_id)
            appended_count += len(batch)

            # Track last inserted block for next batch positioning
            if result.get("results"):
                last_block_id = result["results"][-1]["id"]
        except Exception as e:
            logger.error(f"Failed to append batch {batch_num}: {e}")
            raise

    logger.info(f"Successfully appended {appended_count} blocks to page {page_id}")
    return appended_count
