"""rich_text chunking to satisfy Notion's write-time length limits.

Notion enforces two limits on WRITES (blocks.children.append + blocks.update)
that it does NOT enforce on reads:

- every rich_text element's ``text.content`` must be <= 2000 characters
- a rich_text array may contain at most 100 elements

A block read back from Notion can therefore contain a single 2105-char text
element that then fails to write verbatim (e.g. copying a master code block to a
translated slave). These helpers split over-long elements so any payload built
from fetched or generated content writes cleanly.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)

RICH_TEXT_CONTENT_LIMIT = 2000
RICH_TEXT_MAX_ELEMENTS = 100

# rich_text lives under these keys inside a block's type object.
_RICH_TEXT_KEYS = ("rich_text", "caption")


def chunk_rich_text(
    rich_text: list[dict] | None,
    limit: int = RICH_TEXT_CONTENT_LIMIT,
    max_elements: int = RICH_TEXT_MAX_ELEMENTS,
) -> list[dict] | None:
    """Split over-long text elements so every element's content is <= ``limit``.

    Lossless: Notion concatenates adjacent text elements sharing the same
    annotations (and link) when rendering, so splitting one long run into N pieces
    displays identically. Each piece keeps the original annotations, ``text.link``
    and ``href``; ``plain_text`` is sliced to match. Non-text elements (mention,
    equation) are atomic and pass through untouched.

    If the resulting array would exceed ``max_elements`` it is capped and a warning
    is logged — a >100-element array is rejected outright by Notion, so writing the
    first 100 elements is strictly better than failing the whole block.
    """
    if not rich_text:
        return rich_text

    chunked: list[dict] = []
    for el in rich_text:
        if not isinstance(el, dict) or el.get("type") != "text":
            chunked.append(el)
            continue

        content = (el.get("text") or {}).get("content", "")
        if not isinstance(content, str) or len(content) <= limit:
            chunked.append(el)
            continue

        for i in range(0, len(content), limit):
            piece = content[i:i + limit]
            new_el = copy.deepcopy(el)
            new_el["text"]["content"] = piece
            if "plain_text" in new_el:
                new_el["plain_text"] = piece
            chunked.append(new_el)

    if len(chunked) > max_elements:
        logger.warning(
            "chunk_rich_text: %d elements exceeds Notion's %d-element limit — "
            "capping (%d element(s) dropped)",
            len(chunked), max_elements, len(chunked) - max_elements,
        )
        chunked = chunked[:max_elements]

    return chunked


def chunk_block_payload(
    data: dict[str, Any],
    limit: int = RICH_TEXT_CONTENT_LIMIT,
    max_elements: int = RICH_TEXT_MAX_ELEMENTS,
) -> dict[str, Any]:
    """Chunk rich_text/caption arrays inside a ``{block_type: {...}}`` write payload.

    Used as the universal safety net in ``update_block`` so no update — including
    verbatim copies of fetched master blocks that bypass ``_sanitize_for_update`` —
    can exceed Notion's per-element limit. Returns a shallow-copied payload; the
    input is not mutated.
    """
    if not isinstance(data, dict):
        return data

    result: dict[str, Any] = {}
    for block_type, content in data.items():
        if isinstance(content, dict):
            new_content = dict(content)
            for key in _RICH_TEXT_KEYS:
                if isinstance(new_content.get(key), list):
                    new_content[key] = chunk_rich_text(new_content[key], limit, max_elements)
            # table_row payloads carry a list of rich_text arrays under "cells".
            # Cells read back from Notion can exceed the write limit too (e.g. a
            # partial-cell patch that re-sends untouched cells verbatim).
            if isinstance(new_content.get("cells"), list):
                new_content["cells"] = [
                    chunk_rich_text(cell, limit, max_elements)
                    if isinstance(cell, list) else cell
                    for cell in new_content["cells"]
                ]
            result[block_type] = new_content
        else:
            result[block_type] = content
    return result


def chunk_children_blocks(
    blocks: list[dict] | None,
    limit: int = RICH_TEXT_CONTENT_LIMIT,
    max_elements: int = RICH_TEXT_MAX_ELEMENTS,
) -> list[dict] | None:
    """Chunk over-long rich_text in a list of full block dicts (CREATE/append shape).

    ``blocks.children.append`` payloads are full block objects
    (``{"type": "code", "code": {...}, "children": [...]}``) rather than the
    ``{block_type: {...}}`` shape ``chunk_block_payload`` expects. This walks each
    block, chunks the rich_text/caption/cells inside its type object, and recurses
    into nested ``children`` arrays — both the top-level ``children`` key and any
    ``children`` nested inside a type object (columns, toggles, tables, etc.).

    Used as the universal safety net in ``append_blocks`` so verbatim copies of
    fetched master content (e.g. a >2000-char code block on new-page creation)
    write cleanly. Returns new lists/dicts; the input is not mutated.
    """
    if not isinstance(blocks, list):
        return blocks
    return [_chunk_block(block, limit, max_elements) for block in blocks]


def _chunk_block(block: Any, limit: int, max_elements: int) -> Any:
    """Chunk one full block dict, recursing into nested children."""
    if not isinstance(block, dict):
        return block

    # Reuse the update-path net to chunk rich_text/caption/cells in every type
    # object (dict-valued key). Returns a shallow copy; input is not mutated.
    result = chunk_block_payload(block, limit, max_elements)

    # Recurse into nested children wherever they live: the block's top-level
    # "children" key, and "children" nested inside a type object (column,
    # toggle, table, ...). chunk_block_payload copies the type-object dicts but
    # leaves their "children" list refs shared, so reassign rather than mutate.
    for key, value in result.items():
        if key == "children" and isinstance(value, list):
            result[key] = chunk_children_blocks(value, limit, max_elements)
        elif isinstance(value, dict) and isinstance(value.get("children"), list):
            value["children"] = chunk_children_blocks(value["children"], limit, max_elements)

    return result
