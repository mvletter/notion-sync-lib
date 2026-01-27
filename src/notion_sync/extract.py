"""Text extraction utilities for Notion blocks.

Provides functions to extract plain text content from Notion blocks
for comparison, hashing, and display purposes.
"""

import logging

logger = logging.getLogger(__name__)


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
    if block_type in {"table_of_contents", "breadcrumb", "column_list"}:
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

    # Unknown block type - log and return empty
    if block_type and block_type not in {"unsupported"}:
        logger.debug(f"Unknown block type for text extraction: {block_type}")

    return ""
