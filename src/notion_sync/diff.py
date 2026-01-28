"""Notion Sync Diff - Smart diff generation and execution for Notion blocks.

Provides content-based diff generation using SequenceMatcher to produce
minimal operations when synchronizing local blocks with Notion pages.
"""

import copy
import hashlib
import logging
from difflib import SequenceMatcher
from typing import Any

from notion_sync.client import RateLimitedNotionClient
from notion_sync.extract import extract_block_text

logger = logging.getLogger(__name__)

# Block types that can only have rich_text updated (not full content)
# These require special handling to avoid Notion API errors:
# - callout: icon property requires special handling
# - toggle: "Cannot remove toggle...children first" error
# - heading_1/2/3: is_toggleable triggers error even when false
_RICH_TEXT_ONLY_BLOCKS = frozenset([
    "callout", "toggle", "heading_1", "heading_2", "heading_3"
])

# Block types that contain files/external resources
# For these blocks, we can only update the caption during an UPDATE operation
# The type/file/external fields cannot be changed via update - only via replace
_FILE_BASED_BLOCKS = frozenset([
    "image", "video", "pdf", "file", "audio"
])

# Block types with immutable structure properties
# These blocks have structural properties that cannot be updated after creation
# Only their children can be modified (via recursive diff)
_STRUCTURE_ONLY_BLOCKS = frozenset([
    "table",  # table_width, has_column_header, has_row_header are immutable
              # Error: "body.table.table_width should be not present, instead was `3`"
    "numbered_list_item"  # list_start_index is immutable after creation
                          # Error: "body.numbered_list_item.list_start_index should be not present, instead was `3`"
])


def _is_synced_copy(block: dict[str, Any]) -> bool:
    """Check if a block is a synced copy (read-only reference to original).

    Synced blocks work as follows:
    - Original synced block: type="synced_block", synced_block.synced_from=None (can update)
    - Synced copy: type="synced_block", synced_block.synced_from={block_id} (read-only)

    Args:
        block: A Notion block dictionary.

    Returns:
        True if block is a synced copy (cannot be updated), False otherwise.
    """
    if block.get("type") != "synced_block":
        return False

    synced_from = block.get("synced_block", {}).get("synced_from")
    return synced_from is not None


def create_content_hash(block: dict[str, Any]) -> str:
    """Create a stable hash for a Notion block based on its content.

    Used for content-based matching in generate_diff.
    Includes: type, text content, block-specific properties (checked for to_do, language for code).
    Excludes: id, timestamps, user info (volatile).

    Args:
        block: A Notion block dictionary.

    Returns:
        First 16 characters of SHA256 hash of normalized content.
    """
    block_type = block.get("type", "unknown")

    # Extract text content
    text = extract_block_text(block)

    # Block-specific properties that affect identity
    extras = ""
    if block_type == "to_do":
        type_data = block.get(block_type, {})
        extras = f":checked={type_data.get('checked', False)}"
    elif block_type == "code":
        type_data = block.get(block_type, {})
        extras = f":lang={type_data.get('language', 'plain text')}"
    elif block_type == "column":
        type_data = block.get(block_type, {})
        width_ratio = type_data.get("width_ratio")
        if width_ratio is not None:
            extras = f":width={width_ratio}"

    # Create normalized string and hash
    normalized = f"{block_type}:{text}{extras}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def generate_diff(
    old_blocks: list[dict[str, Any]],
    new_blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Generate list of operations using content-based matching.

    Uses difflib.SequenceMatcher to match blocks by content hash instead of position.
    This produces minimal operations when blocks are inserted/deleted at any position.

    **USE THIS WHEN:**
    - Pages have different structures (different number of blocks)
    - You're adding, removing, or reordering blocks
    - Syncing content from external sources (markdown, tests, etc.)
    - Block structures may not match

    **DON'T USE THIS WHEN:**
    - Both pages have identical structure (same block IDs at same positions)
    - You only need to update text content (use generate_recursive_diff instead)

    Args:
        old_blocks: Current blocks in Notion (notion_blocks).
        new_blocks: Desired blocks to sync to (local_blocks).

    Returns:
        List of operation dicts with:
        - op: "KEEP" | "UPDATE" | "REPLACE" | "INSERT" | "DELETE"
        - notion_block_id: ID of Notion block (None for INSERT)
        - notion_block: Full Notion block (for archived check)
        - local_block: Local block data (None for DELETE/KEEP)
        - index: Position in the final result
    """
    # Create hashes for all blocks
    old_hashes = [create_content_hash(b) for b in old_blocks]
    new_hashes = [create_content_hash(b) for b in new_blocks]

    # Use SequenceMatcher to find optimal matching
    matcher = SequenceMatcher(None, old_hashes, new_hashes, autojunk=False)

    ops: list[dict[str, Any]] = []
    result_index = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            # Blocks match - keep them
            for ni, li in zip(range(i1, i2), range(j1, j2)):
                ops.append({
                    "op": "KEEP",
                    "notion_block_id": old_blocks[ni]["id"],
                    "notion_block": old_blocks[ni],
                    "local_block": None,
                    "index": result_index
                })
                result_index += 1

        elif tag == "replace":
            # Content changed at these positions
            # Check if types match (UPDATE) or differ (REPLACE)
            old_range = list(range(i1, i2))
            new_range = list(range(j1, j2))

            # Process pairs first
            for ni, li in zip(old_range, new_range):
                old_block = old_blocks[ni]
                new_block = new_blocks[li]

                if old_block.get("type") == new_block.get("type"):
                    # Same type, different content - update
                    ops.append({
                        "op": "UPDATE",
                        "notion_block_id": old_block["id"],
                        "notion_block": old_block,
                        "local_block": new_block,
                        "index": result_index
                    })
                else:
                    # Different type - replace
                    ops.append({
                        "op": "REPLACE",
                        "notion_block_id": old_block["id"],
                        "notion_block": old_block,
                        "local_block": new_block,
                        "index": result_index
                    })
                result_index += 1

            # Handle unmatched old blocks (delete)
            for ni in old_range[len(new_range):]:
                ops.append({
                    "op": "DELETE",
                    "notion_block_id": old_blocks[ni]["id"],
                    "notion_block": old_blocks[ni],
                    "local_block": None,
                    "index": result_index
                })
                # Don't increment result_index for DELETE

            # Handle unmatched new blocks (insert)
            for li in new_range[len(old_range):]:
                ops.append({
                    "op": "INSERT",
                    "notion_block_id": None,
                    "notion_block": None,
                    "local_block": new_blocks[li],
                    "index": result_index
                })
                result_index += 1

        elif tag == "delete":
            # Blocks only in old - delete them
            for ni in range(i1, i2):
                ops.append({
                    "op": "DELETE",
                    "notion_block_id": old_blocks[ni]["id"],
                    "notion_block": old_blocks[ni],
                    "local_block": None,
                    "index": result_index
                })
                # Don't increment result_index for DELETE

        elif tag == "insert":
            # Blocks only in new - insert them
            for li in range(j1, j2):
                ops.append({
                    "op": "INSERT",
                    "notion_block_id": None,
                    "notion_block": None,
                    "local_block": new_blocks[li],
                    "index": result_index
                })
                result_index += 1

    return ops


def generate_recursive_diff(
    old_blocks: list[dict[str, Any]],
    new_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate UPDATE operations by recursively comparing block trees.

    Unlike generate_diff which only compares top-level blocks, this function
    walks both trees in parallel and compares content at every level.

    **USE THIS WHEN:**
    - Both pages have identical structure (same block IDs at same positions)
    - You only need to update content (not add/remove/reorder blocks)
    - new_blocks is a modified copy of old_blocks (same structure, different content)

    **DON'T USE THIS WHEN:**
    - Pages have different structures → Use generate_diff instead
    - You need to add, remove, or reorder blocks → Use generate_diff instead
    - Syncing between different pages → Use generate_diff instead

    **WARNING:**
    If structures don't match, this function will return an empty list (0 operations)
    because it assumes identical block IDs at identical positions.

    **TYPICAL USE CASE:**
    When you fetch a page, modify only the content in a copy, and want to sync
    those content changes back. For example: translation workflows, bulk text updates,
    content replacement, property changes.

    Example workflow:
    ```python
    # 1. Fetch original blocks
    original = fetch_blocks_recursive(client, page_id)

    # 2. Create modified copy (same structure, different content)
    modified = copy.deepcopy(original)
    # ... modify text/properties in modified, keep IDs unchanged ...

    # 3. Generate UPDATE operations only
    ops = generate_recursive_diff(original, modified)

    # 4. Execute updates
    execute_recursive_diff(client, ops)
    ```

    Args:
        old_blocks: Current blocks in Notion (with _children from recursive fetch).
        new_blocks: Modified copy with same structure, different content.

    Returns:
        List of UPDATE operation dicts for all blocks with changed content.
        Each operation has:
        - op: "UPDATE"
        - notion_block_id: Block ID to update
        - notion_block: Original block (for reference)
        - local_block: New block with modified content
        - path: Human-readable path like "0", "0.children.1"
    """
    ops: list[dict[str, Any]] = []

    def compare_recursive(
        old_list: list[dict[str, Any]],
        new_list: list[dict[str, Any]],
        path_prefix: str = "",
    ) -> None:
        """Recursively compare blocks and collect UPDATE ops."""
        for i, (old_block, new_block) in enumerate(zip(old_list, new_list)):
            path = f"{path_prefix}{i}" if path_prefix else str(i)

            # Compare content hashes
            old_hash = create_content_hash(old_block)
            new_hash = create_content_hash(new_block)

            if old_hash != new_hash:
                # Content changed - add UPDATE op
                ops.append({
                    "op": "UPDATE",
                    "notion_block_id": old_block.get("id"),
                    "notion_block": old_block,
                    "local_block": new_block,
                    "path": path,
                })

            # Recurse into children
            old_children = old_block.get("_children", [])
            new_children = new_block.get("_children", [])

            if old_children and new_children:
                compare_recursive(
                    old_children,
                    new_children,
                    f"{path}.children.",
                )

    compare_recursive(old_blocks, new_blocks)

    logger.info(f"Recursive diff found {len(ops)} blocks to update")
    return ops


def execute_recursive_diff(
    client: RateLimitedNotionClient,
    ops: list[dict[str, Any]],
    dry_run: bool = False,
) -> dict[str, int]:
    """Execute recursive diff operations (UPDATE only).

    **USE WITH:** generate_recursive_diff output only
    **NOT FOR:** generate_diff output (use execute_diff instead)

    This function only handles UPDATE operations. If you pass operations
    from generate_diff (which includes INSERT/DELETE), they will be skipped
    with a warning.

    Args:
        client: RateLimitedNotionClient instance for API calls.
        ops: List of UPDATE operations from generate_recursive_diff.
        dry_run: If True, only count operations without executing.

    Returns:
        Stats dict with counts: {updated, skipped}
    """
    stats = {"updated": 0, "skipped": 0}
    total_ops = len(ops)

    # Log progress every 20 blocks
    progress_interval = 20

    for i, op in enumerate(ops):
        if op["op"] != "UPDATE":
            logger.warning(f"Unexpected operation type: {op['op']}")
            continue

        block_id = op["notion_block_id"]
        local_block = op["local_block"]
        path = op.get("path", "unknown")

        if dry_run:
            old_text = _truncate(extract_block_text(op["notion_block"]), 30)
            new_text = _truncate(extract_block_text(local_block), 30)
            logger.info(f"[DRY-RUN] Would update {path}: '{old_text}' -> '{new_text}'")
            stats["updated"] += 1
            continue

        # Get block type early for checks
        local_type = local_block["type"]
        notion_type = op["notion_block"].get("type")

        # Check for archived blocks
        if op["notion_block"].get("archived", False):
            logger.debug(f"Skipping archived block at {path}")
            stats["skipped"] += 1
            continue

        # Check for synced copies (read-only blocks)
        if op["notion_block"] and _is_synced_copy(op["notion_block"]):
            logger.debug(f"Skipping synced copy block at {path} - read-only reference to original")
            stats["skipped"] += 1
            continue

        # Check for structure-only blocks (immutable structural properties)
        if local_type in _STRUCTURE_ONLY_BLOCKS:
            logger.debug(f"Skipping {local_type} block at {path} - structural properties are immutable, only children can be updated")
            stats["skipped"] += 1
            continue

        # Execute update
        try:

            # Check for block type mismatch (master vs slave structure difference)
            if local_type != notion_type:
                logger.warning(
                    f"Block type mismatch at {path}: local={local_type}, notion={notion_type}. "
                    "Skipping - slave page structure differs from master."
                )
                if "type_mismatch" not in stats:
                    stats["type_mismatch"] = 0
                stats["type_mismatch"] += 1
                continue

            block_content = local_block[local_type]

            # Use restricted update for certain block types
            if local_type in _RICH_TEXT_ONLY_BLOCKS:
                update_data = {local_type: {"rich_text": block_content.get("rich_text", [])}}
            elif local_type in _FILE_BASED_BLOCKS:
                # For file-based blocks, only update caption (not type/file/external)
                update_data = {local_type: {"caption": block_content.get("caption", [])}}
            elif local_type == "synced_block":
                # For original synced blocks (not copies), synced_from must be null
                # Notion API requires the field to be present, but cannot be updated
                clean_content = block_content.copy()
                # Ensure synced_from is null (not undefined/missing)
                if "synced_from" in clean_content:
                    clean_content["synced_from"] = None
                update_data = {local_type: clean_content}
            else:
                # Remove children from block content - UPDATE operations cannot contain children
                # Children are managed separately via the blocks API
                clean_content = block_content.copy()
                clean_content.pop("children", None)
                update_data = {local_type: clean_content}

            client.update_block(block_id=block_id, data=update_data)
            stats["updated"] += 1
            logger.debug(f"Updated block at {path}")

            # Log progress every N blocks
            if (i + 1) % progress_interval == 0 or (i + 1) == total_ops:
                logger.info(f"Diff progress: {i + 1}/{total_ops} blocks processed")
        except Exception as e:
            logger.error(f"Failed to update block at {path}: {e}")
            raise

    return stats


def _delete_block_recursive(client: RateLimitedNotionClient, block_id: str) -> int:
    """Delete a block and all its children (bottom-up) using iterative approach.

    Notion API requires children to be deleted before their parent.
    This function uses a stack-based iterative approach to handle deep trees
    without risk of stack overflow.

    Args:
        client: RateLimitedNotionClient instance for API calls.
        block_id: ID of the block to delete.

    Returns:
        Number of blocks deleted (including children).
    """
    # Build a complete tree of block IDs to delete (depth-first)
    to_process = [block_id]
    all_blocks = []  # List of (block_id, depth) tuples

    while to_process:
        current_id = to_process.pop(0)

        # Fetch children
        try:
            children = client.get_blocks(current_id)
            child_ids = [c["id"] for c in children if not c.get("archived", False)]

            # Add children to front of processing queue (depth-first)
            to_process = child_ids + to_process

            # Record this block and its depth (children come before parents)
            all_blocks.extend((child_id, 0) for child_id in child_ids)
            all_blocks.append((current_id, 0))
        except Exception as e:
            # Block might not support children, that's ok
            logger.debug(f"Could not fetch children for {current_id}: {e}")
            all_blocks.append((current_id, 0))

    # Delete in reverse order (children before parents)
    # Use a set to deduplicate block IDs
    seen = set()
    to_delete = []
    for block_id, _ in reversed(all_blocks):
        if block_id not in seen:
            seen.add(block_id)
            to_delete.append(block_id)

    # Execute deletes
    deleted_count = 0
    for block_id in to_delete:
        try:
            client.delete_block(block_id=block_id)
            deleted_count += 1
        except Exception as e:
            logger.warning(f"Failed to delete block {block_id}: {e}")

    return deleted_count


def execute_diff(
    client: RateLimitedNotionClient,
    ops: list[dict[str, Any]],
    page_id: str,
    dry_run: bool = False
) -> dict[str, int]:
    """Execute diff operations using Notion API.

    **USE WITH:** generate_diff output
    **NOT FOR:** generate_recursive_diff output (use execute_recursive_diff instead)

    Handles all operation types: KEEP, UPDATE, INSERT, DELETE, REPLACE.
    Processes operations in order, tracking last_block_id for correct
    insertion positioning using the `after` parameter.

    Args:
        client: RateLimitedNotionClient instance for API calls.
        ops: List of operations from generate_diff.
        page_id: Notion page ID to sync to.
        dry_run: If True, only count operations without executing.

    Returns:
        Stats dict with counts: {kept, updated, inserted, deleted, replaced}

    Raises:
        Exception: On API errors during execution.
    """
    stats = {"kept": 0, "updated": 0, "inserted": 0, "deleted": 0, "replaced": 0}

    if dry_run:
        for op in ops:
            op_type = op["op"]
            if op_type == "KEEP":
                stats["kept"] += 1
            elif op_type == "UPDATE":
                stats["updated"] += 1
            elif op_type == "REPLACE":
                stats["replaced"] += 1
            elif op_type == "INSERT":
                stats["inserted"] += 1
            elif op_type == "DELETE":
                stats["deleted"] += 1
        return stats

    last_block_id: str | None = None

    for op in ops:
        try:
            # Check if this operation involves an archived block
            notion_block = op.get("notion_block")
            is_archived = notion_block.get("archived", False) if notion_block else False

            if op["op"] == "KEEP":
                last_block_id = op["notion_block_id"]
                stats["kept"] += 1

            elif op["op"] == "UPDATE":
                if is_archived:
                    logger.debug(
                        "Skipping UPDATE of archived block at index %d",
                        op["index"]
                    )
                    last_block_id = op["notion_block_id"]
                    stats["kept"] += 1
                elif notion_block and _is_synced_copy(notion_block):
                    logger.debug(
                        "Skipping UPDATE of synced copy block at index %d - read-only reference",
                        op["index"]
                    )
                    last_block_id = op["notion_block_id"]
                    stats["kept"] += 1
                elif op["local_block"]["type"] in _STRUCTURE_ONLY_BLOCKS:
                    logger.debug(
                        "Skipping UPDATE of %s block at index %d - structural properties are immutable",
                        op["local_block"]["type"],
                        op["index"]
                    )
                    last_block_id = op["notion_block_id"]
                    stats["kept"] += 1
                else:
                    block_type = op["local_block"]["type"]
                    block_content = op["local_block"][block_type].copy()
                    # Use restricted update for certain block types
                    if block_type in _RICH_TEXT_ONLY_BLOCKS:
                        update_data = {block_type: {"rich_text": block_content.get("rich_text", [])}}
                    elif block_type in _FILE_BASED_BLOCKS:
                        # For file-based blocks, only update caption (not type/file/external)
                        update_data = {block_type: {"caption": block_content.get("caption", [])}}
                    elif block_type == "table":
                        # Remove table_width - can't be updated, only used at creation
                        block_content.pop("table_width", None)
                        block_content.pop("children", None)
                        update_data = {block_type: block_content}
                    elif block_type == "synced_block":
                        # For original synced blocks (not copies), synced_from must be null
                        # Notion API requires the field to be present, but cannot be updated
                        if "synced_from" in block_content:
                            block_content["synced_from"] = None
                        block_content.pop("children", None)
                        update_data = {block_type: block_content}
                    else:
                        # Remove children - can't update children via block update API
                        block_content.pop("children", None)
                        update_data = {block_type: block_content}
                    client.update_block(block_id=op["notion_block_id"], data=update_data)
                    last_block_id = op["notion_block_id"]
                    stats["updated"] += 1

            elif op["op"] == "DELETE":
                if is_archived:
                    logger.debug(
                        "Skipping DELETE of archived block at index %d",
                        op["index"]
                    )
                else:
                    # Use recursive delete to handle blocks with children (e.g., toggles)
                    _delete_block_recursive(client, op["notion_block_id"])
                    stats["deleted"] += 1

            elif op["op"] == "INSERT":
                prepared = _prepare_block_for_api(op["local_block"])
                if prepared is None:
                    logger.warning(f"Skipping INSERT at index {op['index']}: invalid block")
                    continue
                blocks_to_insert = [prepared]
                # Use rate-limited append_blocks method (not direct API call)
                result = client.append_blocks(page_id=page_id, blocks=blocks_to_insert, after=last_block_id)
                last_block_id = result["results"][0]["id"]
                stats["inserted"] += 1

            elif op["op"] == "REPLACE":
                prepared = _prepare_block_for_api(op["local_block"])
                if prepared is None:
                    logger.warning(f"Skipping REPLACE at index {op['index']}: invalid block")
                    last_block_id = op["notion_block_id"]
                    stats["kept"] += 1
                    continue
                blocks_to_insert = [prepared]

                if is_archived:
                    logger.debug(
                        "Skipping delete of archived block at index %d, inserting after",
                        op["index"]
                    )
                    last_block_id = op["notion_block_id"]
                    # Use rate-limited append_blocks method (not direct API call)
                    result = client.append_blocks(page_id=page_id, blocks=blocks_to_insert, after=last_block_id)
                    last_block_id = result["results"][0]["id"]
                    stats["inserted"] += 1
                else:
                    # Use recursive delete to handle blocks with children (e.g., toggles)
                    _delete_block_recursive(client, op["notion_block_id"])
                    # Use rate-limited append_blocks method (not direct API call)
                    result = client.append_blocks(page_id=page_id, blocks=blocks_to_insert, after=last_block_id)
                    last_block_id = result["results"][0]["id"]
                    stats["replaced"] += 1

        except Exception as e:
            logger.warning(
                "Failed to execute %s at index %d: %s",
                op["op"], op["index"], e
            )
            raise

    return stats


def _is_valid_notion_block(block: dict[str, Any]) -> bool:
    """Check if a block has a valid structure for Notion API.

    A valid block must have:
    - type: string field
    - <type>: dict property (e.g., paragraph.rich_text, column.children)
    - NOT be a child_database or child_page (unsupported via blocks API)

    Args:
        block: Block dictionary to validate.

    Returns:
        True if block is valid for Notion API, False otherwise.
    """
    if not isinstance(block, dict):
        return False

    block_type = block.get("type")
    if not block_type or not isinstance(block_type, str):
        return False

    # Filter out child_database and child_page blocks
    # These CANNOT be added via blocks.children.append API
    # They must be created via dedicated database/page creation endpoints
    if block_type in ("child_database", "child_page"):
        logger.warning(
            f"Skipping {block_type} block: cannot be added via blocks API (use dedicated creation endpoint)"
        )
        return False

    # Check if the type property exists and is a dict (required by Notion API)
    type_data = block.get(block_type)
    if not isinstance(type_data, dict):
        logger.warning(
            f"Invalid block: {block_type} property must be a dict, got {type(type_data).__name__}"
        )
        return False

    return True


def _prepare_block_for_api(block: dict[str, Any]) -> dict[str, Any] | None:
    """Deep copy a block and convert from internal format to Notion API format.

    Converts blocks from fetch_blocks_recursive format (with _children at root)
    to Notion API format (children inside block type property).

    Strips metadata fields (id, created_time, etc.) that Notion API doesn't accept
    in children arrays.

    # AI-CONTEXT: See docs/pitfalls.md#api-nested-blocks-format

    Args:
        block: A block dictionary that may contain _children.

    Returns:
        A deep copy of the block in Notion API format, or None if block is invalid.
    """
    # CRITICAL: Validate block BEFORE processing
    if not _is_valid_notion_block(block):
        logger.warning(f"Skipping invalid block in _prepare_block_for_api: {block.get('type', 'NO_TYPE')}")
        return None

    cleaned = copy.deepcopy(block)

    # Strip metadata fields that API doesn't accept in children
    # Keep only: type, <type>, and children (after conversion)
    metadata_fields = [
        "id", "created_time", "created_by", "last_edited_time", "last_edited_by",
        "archived", "in_trash", "has_children", "parent", "object"
    ]
    for field in metadata_fields:
        cleaned.pop(field, None)

    # CRITICAL: Strip 'children' from block type property BEFORE processing _children
    # Blocks from Notion API may have <type>.children (e.g., column.children with block IDs)
    # These must be removed - the API only accepts children in _children format
    block_type = cleaned.get("type")
    if block_type and block_type in cleaned and isinstance(cleaned[block_type], dict):
        cleaned[block_type].pop("children", None)

    # Convert _children to proper API format
    # AI-CONTEXT: See docs/pitfalls.md#api-nested-blocks-format
    children = cleaned.pop("_children", None)
    if children:
        if block_type and block_type in cleaned:
            # Recursively prepare each child block
            # For toggles: _children → toggle.children
            # For column_list: _children → column_list.children (each child is a column)
            # For columns: _children → column.children
            prepared_children = []
            for child in children:
                # Validate child block before preparing
                if not _is_valid_notion_block(child):
                    logger.warning(
                        f"Skipping invalid child block in {block_type}: missing or invalid type property"
                    )
                    continue
                prepared_child = _prepare_block_for_api(child)
                if prepared_child is not None:
                    prepared_children.append(prepared_child)

            # Only add children if we have valid ones
            if prepared_children:
                cleaned[block_type]["children"] = prepared_children

    return cleaned

def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis.

    Args:
        text: Text to truncate.
        max_len: Maximum length including ellipsis.

    Returns:
        Truncated text with '...' if needed.
    """
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def format_diff_preview(ops: list[dict[str, Any]]) -> str:
    """Generate human-readable preview of diff operations.

    Shows what changes will be made without executing them.
    Uses symbols: + [NEW], ~ [MODIFIED], - [DELETED], <-> [REPLACED]

    Args:
        ops: List of operations from generate_diff.

    Returns:
        Multi-line string showing all changes.
    """
    # Count operations
    counts = {
        "new": sum(1 for op in ops if op["op"] == "INSERT"),
        "modified": sum(1 for op in ops if op["op"] == "UPDATE"),
        "replaced": sum(1 for op in ops if op["op"] == "REPLACE"),
        "deleted": sum(1 for op in ops if op["op"] == "DELETE"),
        "unchanged": sum(1 for op in ops if op["op"] == "KEEP"),
    }

    lines = [
        "=" * 60,
        "Diff Preview",
        "=" * 60,
        f"Summary: {counts['new']} new, {counts['modified']} modified, "
        f"{counts['replaced']} replaced, {counts['deleted']} deleted, "
        f"{counts['unchanged']} unchanged",
        "-" * 60,
        "",
        "Changes:",
        "",
    ]

    unchanged_count = 0
    for op in ops:
        if op["op"] == "INSERT":
            local_block = op.get("local_block", {})
            block_type = local_block.get("type", "unknown")
            text = _truncate(extract_block_text(local_block), 50)
            lines.append(f"+ [NEW] {block_type}")
            if text:
                lines.append(f'  "{text}"')
            lines.append(f"  -> Will be inserted at position {op['index']}")
            lines.append("")

        elif op["op"] == "UPDATE":
            notion_block = op.get("notion_block", {})
            local_block = op.get("local_block", {})
            old_text = _truncate(extract_block_text(notion_block), 25)
            new_text = _truncate(extract_block_text(local_block), 25)
            block_id = op.get("notion_block_id", "unknown")[:12]
            lines.append(f"~ [MODIFIED] {local_block.get('type', 'unknown')}")
            lines.append(f'  "{old_text}" -> "{new_text}"')
            lines.append(f"  -> Will update block {block_id}...")
            lines.append("")

        elif op["op"] == "REPLACE":
            notion_block = op.get("notion_block", {})
            local_block = op.get("local_block", {})
            old_type = notion_block.get("type", "unknown")
            new_type = local_block.get("type", "unknown")
            block_id = op.get("notion_block_id", "unknown")[:12]
            lines.append(f"<-> [REPLACED] {old_type} -> {new_type}")
            lines.append(f"  -> Will delete and recreate block {block_id}...")
            lines.append("")

        elif op["op"] == "DELETE":
            notion_block = op.get("notion_block", {})
            block_type = notion_block.get("type", "unknown")
            text = _truncate(extract_block_text(notion_block), 50)
            block_id = op.get("notion_block_id", "unknown")[:12]
            lines.append(f"- [DELETED] {block_type}")
            if text:
                lines.append(f'  "{text}"')
            lines.append(f"  -> Will delete block {block_id}...")
            lines.append("")

        elif op["op"] == "KEEP":
            unchanged_count += 1

    # Summary for unchanged blocks
    if unchanged_count > 0:
        lines.append(f"  ... ({unchanged_count} unchanged blocks)")
        lines.append("")

    lines.append("-" * 60)
    lines.append("Run without dry_run=True to apply these changes.")

    return "\n".join(lines)
