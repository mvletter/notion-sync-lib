"""Text extraction utilities for Notion blocks.

Provides functions to extract plain text content from Notion blocks
for comparison, hashing, and display purposes.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Matches a Notion UUID in compact (32 hex) or hyphenated (8-4-4-4-12) form.
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}",
    re.IGNORECASE,
)

# Rich-text-bearing block types whose plain text is folded into the content
# hash by extract_block_text — the same set whose links must be folded so the
# hash and the link identity stay symmetric (SPEC-LINK-002-M1).
_TEXT_BLOCK_TYPES = frozenset({
    "paragraph", "heading_1", "heading_2", "heading_3",
    "bulleted_list_item", "numbered_list_item", "quote",
    "callout", "toggle", "to_do", "code",
})
_CAPTIONED_TYPES = frozenset({"image", "video", "file", "pdf", "bookmark", "embed"})


def _normalize_link_identity(url: str) -> str:
    """Canonicalize a rich_text link URL into a stable identity string.

    Notion-internal links (``/p/{page}[?q]#{block}``, ``notion.so/…{page}#{block}``,
    ``notion://page/{page}``) normalize to ``notion:{page}[#{block}]`` with
    compacted lowercase UUIDs — so the same target in relative, absolute or
    query-string form yields ONE identity (otherwise every link-bearing block
    would phantom-UPDATE on every apply). External URLs are their own identity.
    """
    if not url:
        return ""
    is_notion = url.startswith("/p/") or "notion.so/" in url or url.startswith("notion://")
    if not is_notion:
        return url
    base, _, fragment = url.partition("#")
    base_ids = _UUID_PATTERN.findall(base)
    page = base_ids[-1].replace("-", "").lower() if base_ids else ""
    frag_ids = _UUID_PATTERN.findall(fragment)
    block = frag_ids[0].replace("-", "").lower() if frag_ids else ""
    return f"notion:{page}#{block}" if block else f"notion:{page}"


def _links_from_rich_text(rich_text: list[dict]) -> list[str]:
    """Normalized identities of every linked ``text`` run, in document order."""
    out = []
    for run in rich_text or []:
        if run.get("type") == "text":
            link = run.get("text", {}).get("link")
            url = link.get("url") if isinstance(link, dict) else None
            if url:
                out.append(_normalize_link_identity(url))
    return out


def extract_link_identity(block: dict) -> str:
    """Concatenate normalized link identities from a block's rich_text runs.

    Returns ``""`` when the block has no linked runs, so a linkless block folds
    nothing into its content hash and keeps its exact pre-fix hash (flood
    containment — SPEC-LINK-002-M1, R1.4). Walks the same rich_text-bearing
    fields ``extract_block_text`` covers: text-type ``rich_text``,
    ``table_row.cells``, and captions.
    """
    block_type = block.get("type", "")
    block_data = block.get(block_type, {})
    parts: list[str] = []

    if block_type in _TEXT_BLOCK_TYPES:
        parts.extend(_links_from_rich_text(block_data.get("rich_text", [])))
    elif block_type == "table_row":
        for cell in block_data.get("cells", []):
            parts.extend(_links_from_rich_text(cell))

    if block_type in _CAPTIONED_TYPES:
        parts.extend(_links_from_rich_text(block_data.get("caption", [])))

    return "|".join(parts)


def _custom_emoji_from_rich_text(rich_text: list[dict]) -> list[str]:
    """Identities of every custom-emoji mention run, in document order."""
    out = []
    for run in rich_text or []:
        if run.get("type") == "mention":
            mention = run.get("mention") or {}
            if mention.get("type") == "custom_emoji":
                emoji_id = (mention.get("custom_emoji") or {}).get("id")
                if emoji_id:
                    out.append(f"custom_emoji:{emoji_id}")
    return out


def extract_mention_identity(block: dict) -> str:
    """Concatenate custom-emoji mention identities from a block's rich_text runs.

    A custom-emoji mention's ``plain_text`` is its shortcode (":sa-flag:"), so a
    block carrying the mention and a block carrying the literal shortcode text
    flatten to the same plain text — without this fold they hash equal and a
    broken slave is KEEP'd forever (un-syncable AND un-healable; live-confirmed
    2026-07-20, Herald SPEC-EMOJI-001-M5, occurrence #4 of the hash-contract
    pitfall).

    Returns ``""`` when the block has no custom-emoji mentions, so unaffected
    blocks keep their exact pre-fix hash (flood containment — same rationale as
    SPEC-LINK-002-M1 R1.4). Scoped to ``custom_emoji`` mentions only: page/user/
    date mentions are deliberately NOT folded (their hash behavior must not
    shift). Walks the same rich_text-bearing fields ``extract_block_text``
    covers: text-type ``rich_text``, ``table_row.cells``, and captions.
    """
    block_type = block.get("type", "")
    block_data = block.get(block_type, {})
    parts: list[str] = []

    if block_type in _TEXT_BLOCK_TYPES:
        parts.extend(_custom_emoji_from_rich_text(block_data.get("rich_text", [])))
    elif block_type == "table_row":
        for cell in block_data.get("cells", []):
            parts.extend(_custom_emoji_from_rich_text(cell))

    if block_type in _CAPTIONED_TYPES:
        parts.extend(_custom_emoji_from_rich_text(block_data.get("caption", [])))

    return "|".join(parts)


def extract_rich_text(rich_text: list[dict]) -> str:
    """Extract plain text from a Notion rich_text array.

    Works with both Notion API blocks (plain_text) and local blocks (text.content).

    Args:
        rich_text: List of rich_text objects from Notion API or local blocks.

    Returns:
        Concatenated plain text from all segments.
    """
    if not rich_text:
        return ""
    texts = []
    for item in rich_text:
        # Notion API format: has plain_text
        if "plain_text" in item:
            texts.append(item["plain_text"])
        # Local format (markdown_to_notion_blocks): has text.content
        elif "text" in item and "content" in item["text"]:
            texts.append(item["text"]["content"])
    return "".join(texts)


def extract_block_text(block: dict) -> str:
    """Extract plain text content from a Notion block.

    Handles all block types appropriately:
    - Text blocks (paragraph, heading_*, list items, quote, callout, toggle):
      Returns the plain text from rich_text
    - Code blocks: Returns text with language annotation
    - Divider: Returns "---"
    - Table: Returns "table:{width}:{row_contents}" for content-based comparison
    - Image/video/file/pdf/bookmark: Returns URL or caption
    - Embed: Returns the embed URL
    - Equation: Returns the expression
    - Table of contents, breadcrumb: Returns type identifier
    - Unsupported/unknown: Returns empty string

    Args:
        block: Block dict from Notion API or local block.

    Returns:
        Plain text representation of the block content.
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
        text = extract_rich_text(rich_text)

        # For callout, include icon if present
        if block_type == "callout":
            icon = block_data.get("icon")
            if icon and icon.get("type") == "emoji":
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
        code_text = extract_rich_text(rich_text)
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
                    cell_texts = [extract_rich_text(cell) for cell in cells]
                    row_texts.append("|".join(cell_texts))
            return f"table:{width}:{';'.join(row_texts)}"
        return f"table:{width}"

    # Table row - extract cell contents
    if block_type == "table_row":
        cells = block_data.get("cells", [])
        cell_texts = [extract_rich_text(cell) for cell in cells]
        return " | ".join(cell_texts)

    # Media blocks - return URL or caption
    media_types = {"image", "video", "file", "pdf"}
    if block_type in media_types:
        media_data = block_data
        url = ""
        if media_data.get("type") == "external":
            url = media_data.get("external", {}).get("url", "")
        elif media_data.get("type") == "file":
            url = media_data.get("file", {}).get("url", "")

        caption = extract_rich_text(media_data.get("caption", []))

        if caption:
            return f"{block_type}:{caption}"
        elif url:
            return f"{block_type}:{url}"
        return f"{block_type}"

    # Bookmark
    if block_type == "bookmark":
        url = block_data.get("url", "")
        caption = extract_rich_text(block_data.get("caption", []))
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
    if block_type in {"table_of_contents", "breadcrumb", "column_list", "tab"}:
        return block_type

    # Column blocks - include width_ratio if present
    if block_type == "column":
        width_ratio = block_data.get("width_ratio")
        if width_ratio is not None:
            return f"column:{width_ratio}"
        return "column"

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
        return f"template:{extract_rich_text(rich_text)}"

    # Link to page
    if block_type == "link_to_page":
        page_id = block_data.get("page_id", block_data.get("database_id", ""))
        return f"link_to_page:{page_id}"

    # Meeting notes (read-only block, renamed from transcription in API 2026-03-11)
    if block_type == "meeting_notes":
        title = block_data.get("title", [])
        title_text = extract_rich_text(title)
        if title_text:
            return f"meeting_notes:{title_text}"
        return "meeting_notes"

    # Unknown block type - log and return empty
    if block_type and block_type not in {"unsupported"}:
        logger.debug(f"Unknown block type for text extraction: {block_type}")

    return ""
