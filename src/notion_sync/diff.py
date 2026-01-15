"""Notion Sync Diff - Smart diff generation and execution for Notion blocks.

Provides content-based diff generation using SequenceMatcher to produce
minimal operations when synchronizing local blocks with Notion pages.

Also includes leading insert handling for Notion API limitation (no `before` parameter).
"""

import hashlib
import logging
from difflib import SequenceMatcher
from typing import Any

from notion_sync.client import RateLimitedNotionClient

logger = logging.getLogger(__name__)


# =============================================================================
# BLOCK COMPARISON
# =============================================================================


def extract_block_text(block: dict[str, Any]) -> str:
    """Extract plain text content from a block for comparison.

    Works with both Notion API blocks and local blocks (from markdown_to_notion_blocks).
    Notion API blocks have plain_text field, local blocks have text.content.

    Args:
        block: A Notion block dictionary.

    Returns:
        Plain text content of the block, or empty string if no text content.
    """
    block_type = block.get("type")
    if not block_type:
        return ""

    content = block.get(block_type, {})

    # Handle divider first (no text content)
    if block_type == "divider":
        return "---"

    # Handle table blocks - compare structure AND content
    if block_type == "table":
        table_width = content.get("table_width", 0)
        # Check for children (local blocks have 'children', fetched blocks have '_children')
        children = block.get("_children") or content.get("children", [])
        if children:
            # Extract text from all table rows
            row_texts = []
            for child in children:
                if child.get("type") == "table_row":
                    cells = child.get("table_row", {}).get("cells", [])
                    cell_texts = []
                    for cell in cells:
                        # Extract text from each cell's rich_text
                        if isinstance(cell, list):
                            for segment in cell:
                                if "plain_text" in segment:
                                    cell_texts.append(segment["plain_text"])
                                elif "text" in segment and "content" in segment["text"]:
                                    cell_texts.append(segment["text"]["content"])
                    row_texts.append("|".join(cell_texts))
            return f"table:{table_width}:{';'.join(row_texts)}"
        return f"table:{table_width}"

    # Handle rich_text fields
    rich_text = content.get("rich_text", [])
    if rich_text:
        # Extract text from each segment
        texts = []
        for segment in rich_text:
            # Notion API format: has plain_text
            if "plain_text" in segment:
                texts.append(segment["plain_text"])
            # Local format: has text.content
            elif "text" in segment and "content" in segment["text"]:
                texts.append(segment["text"]["content"])
        return "".join(texts)

    return ""


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

    # Create normalized string and hash
    normalized = f"{block_type}:{text}{extras}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def blocks_equal(notion_block: dict[str, Any], local_block: dict[str, Any]) -> bool:
    """Check if two blocks are equivalent (same type and content).

    Used for position-based diff generation to determine if a block needs updating.

    Args:
        notion_block: Block from Notion API.
        local_block: Block from local markdown conversion.

    Returns:
        True if blocks have same type and content.
    """
    # Type must match
    if notion_block.get("type") != local_block.get("type"):
        return False

    block_type = notion_block.get("type")

    # For code blocks, also compare language
    if block_type == "code":
        notion_lang = notion_block.get("code", {}).get("language", "")
        local_lang = local_block.get("code", {}).get("language", "")
        if notion_lang != local_lang:
            return False

    # Compare text content
    notion_text = extract_block_text(notion_block)
    local_text = extract_block_text(local_block)

    return notion_text == local_text


# =============================================================================
# DIFF GENERATION
# =============================================================================


def generate_diff_positional(
    notion_blocks: list[dict[str, Any]],
    local_blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Generate list of operations using position-based matching.

    Simple position-based comparison. Use generate_diff for content-based
    matching which produces better results when blocks are reordered.

    Args:
        notion_blocks: Current blocks in Notion.
        local_blocks: Desired blocks from local markdown.

    Returns:
        List of operation dicts with op, notion_block_id, notion_block, local_block, index.
    """
    ops: list[dict[str, Any]] = []
    notion_idx = 0
    local_idx = 0

    while notion_idx < len(notion_blocks) or local_idx < len(local_blocks):
        notion_block = notion_blocks[notion_idx] if notion_idx < len(notion_blocks) else None
        local_block = local_blocks[local_idx] if local_idx < len(local_blocks) else None

        # Both exist at this position
        if notion_block and local_block:
            if blocks_equal(notion_block, local_block):
                # Same - keep
                ops.append({
                    "op": "KEEP",
                    "notion_block_id": notion_block["id"],
                    "notion_block": notion_block,
                    "local_block": None,
                    "index": local_idx
                })
            elif notion_block.get("type") == local_block.get("type"):
                block_type = notion_block.get("type")
                # Tables need REPLACE because table_row cells can't be updated via PATCH
                # See: https://developers.notion.com/reference/update-a-block
                if block_type == "table":
                    ops.append({
                        "op": "REPLACE",
                        "notion_block_id": notion_block["id"],
                        "notion_block": notion_block,
                        "local_block": local_block,
                        "index": local_idx
                    })
                else:
                    # Same type, different content - update
                    ops.append({
                        "op": "UPDATE",
                        "notion_block_id": notion_block["id"],
                        "notion_block": notion_block,
                        "local_block": local_block,
                        "index": local_idx
                    })
            else:
                # Different type - replace (delete + insert)
                ops.append({
                    "op": "REPLACE",
                    "notion_block_id": notion_block["id"],
                    "notion_block": notion_block,
                    "local_block": local_block,
                    "index": local_idx
                })
            notion_idx += 1
            local_idx += 1

        # Only local block exists - insert
        elif local_block:
            ops.append({
                "op": "INSERT",
                "notion_block_id": None,
                "notion_block": None,
                "local_block": local_block,
                "index": local_idx
            })
            local_idx += 1

        # Only Notion block exists - delete
        elif notion_block:
            ops.append({
                "op": "DELETE",
                "notion_block_id": notion_block["id"],
                "notion_block": notion_block,
                "local_block": None,
                "index": notion_idx
            })
            notion_idx += 1

    return ops


def generate_diff(
    old_blocks: list[dict[str, Any]],
    new_blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Generate list of operations using content-based matching.

    Uses difflib.SequenceMatcher to match blocks by content hash instead of position.
    This produces minimal operations when blocks are inserted/deleted at any position.

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
                    block_type = old_block.get("type")
                    # Tables need REPLACE because children can't be updated via PATCH
                    # The Notion API only allows updating table metadata, not row content
                    if block_type == "table":
                        ops.append({
                            "op": "REPLACE",
                            "notion_block_id": old_block["id"],
                            "notion_block": old_block,
                            "local_block": new_block,
                            "index": result_index
                        })
                    else:
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

    Assumes both trees have identical structure (same block IDs in same positions).
    This is the case when new_blocks comes from inject_translations, which
    deep-copies the original blocks and only modifies text content.

    Args:
        old_blocks: Current blocks in Notion (with _children from recursive fetch).
        new_blocks: Translated blocks (with _children from inject_translations).

    Returns:
        List of UPDATE operation dicts for all blocks with changed content.
        Each operation has:
        - op: "UPDATE"
        - notion_block_id: Block ID to update
        - notion_block: Original block (for reference)
        - local_block: New block with translated content
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


# =============================================================================
# LEADING INSERT HANDLING
# =============================================================================


def has_leading_inserts(ops: list[dict[str, Any]]) -> bool:
    """Check if there are INSERTs before any KEEP/UPDATE operation.

    Leading inserts are problematic because Notion's API doesn't have a `before`
    parameter - inserts without `after` go to the END of the page.

    Args:
        ops: List of operations from generate_diff.

    Returns:
        True if there are INSERT operations before any KEEP/UPDATE.
    """
    for op in ops:
        if op["op"] in ("KEEP", "UPDATE"):
            return False
        if op["op"] == "INSERT":
            return True
    return False


def _recreate_block_content(notion_block: dict[str, Any]) -> dict[str, Any]:
    """Recreate a block's content for re-insertion.

    Extracts only the content fields needed to create a new block,
    excluding metadata like id, created_time, etc.

    Args:
        notion_block: Original Notion block.

    Returns:
        Block dict suitable for inserting via API.
    """
    block_type = notion_block.get("type")
    if not block_type:
        return {}

    content = notion_block.get(block_type, {})

    # Build new block with just the content
    new_block: dict[str, Any] = {"type": block_type, block_type: {}}

    # Copy relevant fields based on block type
    if block_type == "divider":
        pass  # Divider has no content
    elif block_type == "table":
        new_block[block_type] = {
            "table_width": content.get("table_width", 1),
            "has_column_header": content.get("has_column_header", False),
            "has_row_header": content.get("has_row_header", False)
        }
    else:
        # Copy rich_text if present
        if "rich_text" in content:
            new_block[block_type]["rich_text"] = content["rich_text"]

        # Block-specific fields
        if block_type == "code":
            new_block[block_type]["language"] = content.get("language", "plain text")
        elif block_type == "to_do":
            new_block[block_type]["checked"] = content.get("checked", False)

    return new_block


def handle_leading_inserts(
    ops: list[dict[str, Any]],
    client: RateLimitedNotionClient,
    page_id: str
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Handle INSERTs that need to go before existing blocks.

    Strategy: When we need to insert BEFORE the first existing block:
    1. Find the first KEEP block
    2. Delete that block (temporarily)
    3. Insert our new blocks (now at start because no `after`)
    4. Re-insert the deleted block
    5. Continue normally

    Args:
        ops: List of operations from generate_diff.
        client: RateLimitedNotionClient for API calls.
        page_id: Notion page ID.

    Returns:
        Tuple of (modified_ops, block_id_mapping):
        - modified_ops: ops with leading inserts adjusted
        - block_id_mapping: {old_id: new_id} for re-inserted blocks
    """
    if not has_leading_inserts(ops):
        return ops, {}

    # Find the first KEEP block (this is what we'll delete/re-insert)
    first_keep_idx = None
    first_keep_op = None
    for i, op in enumerate(ops):
        if op["op"] in ("KEEP", "UPDATE"):
            first_keep_idx = i
            first_keep_op = op
            break

    # If no KEEP found, all blocks are new - no workaround needed
    if first_keep_op is None:
        return ops, {}

    # Strategy: Delete the first KEEP block, let inserts go first, then re-insert
    logger.debug(f"Handling leading inserts: will delete and re-insert block {first_keep_op['notion_block_id'][:8]}")

    # Save the block content for re-creation
    first_block = first_keep_op["notion_block"]
    first_block_id = first_keep_op["notion_block_id"]

    # Check if block is archived
    if first_block.get("archived", False):
        logger.warning("First KEEP block is archived - cannot use leading insert workaround")
        return ops, {}

    # Delete the first KEEP block
    try:
        client.delete_block(first_block_id)
    except Exception as e:
        logger.warning(f"Failed to delete first block for leading insert workaround: {e}")
        return ops, {}

    # Create the re-insert operation
    reinsert_block = _recreate_block_content(first_block)

    # Modify ops:
    # 1. Remove the original KEEP
    # 2. Add a special INSERT at the end of leading inserts
    modified_ops: list[dict[str, Any]] = []

    for i, op in enumerate(ops):
        if i == first_keep_idx:
            # Skip the original KEEP - we'll add it back as INSERT
            # Insert it after all the leading INSERTs
            modified_ops.append({
                "op": "INSERT",
                "notion_block_id": None,
                "notion_block": first_block,  # Keep reference for mapping
                "local_block": reinsert_block,
                "index": op["index"],
                "_was_keep": True,  # Mark for later mapping
                "_original_id": first_block_id
            })
        else:
            modified_ops.append(op)

    return modified_ops, {"deleted_for_leading": first_block_id}


# =============================================================================
# DIFF EXECUTION
# =============================================================================


def execute_recursive_diff(
    client: RateLimitedNotionClient,
    ops: list[dict[str, Any]],
    dry_run: bool = False,
) -> dict[str, int]:
    """Execute recursive diff operations (UPDATE only).

    Args:
        client: RateLimitedNotionClient instance for API calls.
        ops: List of UPDATE operations from generate_recursive_diff.
        dry_run: If True, only count operations without executing.

    Returns:
        Stats dict with counts: {updated, skipped}
    """
    stats = {"updated": 0, "skipped": 0}

    for op in ops:
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

        # Check for archived blocks
        if op["notion_block"].get("archived", False):
            logger.debug(f"Skipping archived block at {path}")
            stats["skipped"] += 1
            continue

        # Execute update
        try:
            block_type = local_block["type"]
            block_content = local_block[block_type]

            # For callout blocks, only update rich_text (icon requires special handling)
            if block_type == "callout":
                update_data = {block_type: {"rich_text": block_content.get("rich_text", [])}}
            else:
                update_data = {block_type: block_content}

            client.update_block(block_id=block_id, data=update_data)
            stats["updated"] += 1
            logger.debug(f"Updated block at {path}")
        except Exception as e:
            logger.error(f"Failed to update block at {path}: {e}")
            raise

    return stats


def execute_diff(
    client: RateLimitedNotionClient,
    ops: list[dict[str, Any]],
    page_id: str,
    dry_run: bool = False,
    handle_leading: bool = True
) -> dict[str, int]:
    """Execute diff operations using Notion API.

    Processes operations in order, tracking last_block_id for correct
    insertion positioning using the `after` parameter.

    Handles leading inserts (INSERTs before existing blocks) by temporarily
    deleting and re-inserting the first KEEP block.

    Args:
        client: RateLimitedNotionClient instance for API calls.
        ops: List of operations from generate_diff.
        page_id: Notion page ID to sync to.
        dry_run: If True, only count operations without executing.
        handle_leading: If True, handle leading inserts automatically.

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

    # Handle leading inserts if needed (modifies ops)
    if handle_leading:
        ops, _mapping = handle_leading_inserts(ops, client, page_id)

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
                else:
                    block_type = op["local_block"]["type"]
                    block_content = op["local_block"][block_type].copy()
                    # For callout blocks, only update rich_text (icon requires special handling)
                    if block_type == "callout":
                        update_data = {block_type: {"rich_text": block_content.get("rich_text", [])}}
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
                    client.delete_block(block_id=op["notion_block_id"])
                    stats["deleted"] += 1

            elif op["op"] == "INSERT":
                blocks_to_insert = [op["local_block"]]
                if last_block_id:
                    # Use the underlying notion client for after parameter
                    result = client.notion.blocks.children.append(
                        block_id=page_id,
                        children=blocks_to_insert,
                        after=last_block_id
                    )
                else:
                    result = client.append_blocks(page_id=page_id, blocks=blocks_to_insert)
                last_block_id = result["results"][0]["id"]

                # Special handling for re-inserted KEEP blocks (from leading insert workaround)
                if op.get("_was_keep"):
                    stats["kept"] += 1
                else:
                    stats["inserted"] += 1

            elif op["op"] == "REPLACE":
                if is_archived:
                    logger.debug(
                        "Skipping delete of archived block at index %d, inserting after",
                        op["index"]
                    )
                    last_block_id = op["notion_block_id"]
                    blocks_to_insert = [op["local_block"]]
                    if last_block_id:
                        result = client.notion.blocks.children.append(
                            block_id=page_id,
                            children=blocks_to_insert,
                            after=last_block_id
                        )
                    else:
                        result = client.append_blocks(page_id=page_id, blocks=blocks_to_insert)
                    last_block_id = result["results"][0]["id"]
                    stats["inserted"] += 1
                else:
                    client.delete_block(block_id=op["notion_block_id"])
                    blocks_to_insert = [op["local_block"]]
                    if last_block_id:
                        result = client.notion.blocks.children.append(
                            block_id=page_id,
                            children=blocks_to_insert,
                            after=last_block_id
                        )
                    else:
                        result = client.append_blocks(page_id=page_id, blocks=blocks_to_insert)
                    last_block_id = result["results"][0]["id"]
                    stats["replaced"] += 1

        except Exception as e:
            logger.warning(
                "Failed to execute %s at index %d: %s",
                op["op"], op["index"], e
            )
            raise

    return stats


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
