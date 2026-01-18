"""Block builder utilities for creating Notion block structures.

Provides convenient functions for building Notion API block structures.
These are especially useful for testing and creating content programmatically.
"""

from typing import Any


def make_paragraph(text: str) -> dict[str, Any]:
    """Create a paragraph block.

    Args:
        text: Text content for the paragraph.

    Returns:
        Paragraph block dictionary ready for Notion API.

    Example:
        >>> make_paragraph("Hello, world!")
        {'type': 'paragraph', 'paragraph': {'rich_text': [...]}}
    """
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def make_heading(level: int, text: str) -> dict[str, Any]:
    """Create a heading block (level 1, 2, or 3).

    Args:
        level: Heading level (1, 2, or 3).
        text: Text content for the heading.

    Returns:
        Heading block dictionary ready for Notion API.

    Raises:
        ValueError: If level is not 1, 2, or 3.

    Example:
        >>> make_heading(1, "Chapter 1")
        {'type': 'heading_1', 'heading_1': {'rich_text': [...]}}
    """
    if level not in (1, 2, 3):
        raise ValueError(f"Heading level must be 1, 2, or 3, got {level}")

    heading_type = f"heading_{level}"
    return {
        "type": heading_type,
        heading_type: {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def make_toggle(text: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Create a toggle block with optional children.

    Args:
        text: Text content for the toggle.
        children: Optional list of child blocks.

    Returns:
        Toggle block dictionary ready for Notion API.

    Example:
        >>> make_toggle("Details", [make_paragraph("Hidden content")])
        {'type': 'toggle', 'toggle': {'rich_text': [...], 'children': [...]}}
    """
    block: dict[str, Any] = {
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }
    if children:
        block["toggle"]["children"] = children
    return block


def make_bulleted_list_item(text: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Create a bulleted list item block.

    Args:
        text: Text content for the list item.
        children: Optional list of child blocks (for nested lists).

    Returns:
        Bulleted list item block dictionary ready for Notion API.

    Example:
        >>> make_bulleted_list_item("First item")
        {'type': 'bulleted_list_item', 'bulleted_list_item': {'rich_text': [...]}}
    """
    block: dict[str, Any] = {
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }
    if children:
        block["bulleted_list_item"]["children"] = children
    return block


def make_numbered_list_item(text: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Create a numbered list item block.

    Args:
        text: Text content for the list item.
        children: Optional list of child blocks (for nested lists).

    Returns:
        Numbered list item block dictionary ready for Notion API.

    Example:
        >>> make_numbered_list_item("Step 1")
        {'type': 'numbered_list_item', 'numbered_list_item': {'rich_text': [...]}}
    """
    block: dict[str, Any] = {
        "type": "numbered_list_item",
        "numbered_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }
    if children:
        block["numbered_list_item"]["children"] = children
    return block


def make_to_do(text: str, checked: bool = False) -> dict[str, Any]:
    """Create a to-do (checkbox) block.

    Args:
        text: Text content for the to-do item.
        checked: Whether the checkbox is checked.

    Returns:
        To-do block dictionary ready for Notion API.

    Example:
        >>> make_to_do("Buy groceries", checked=False)
        {'type': 'to_do', 'to_do': {'rich_text': [...], 'checked': False}}
    """
    return {
        "type": "to_do",
        "to_do": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "checked": checked
        }
    }


def make_code(code: str, language: str = "python") -> dict[str, Any]:
    """Create a code block.

    Args:
        code: Code content.
        language: Programming language (default: "python").

    Returns:
        Code block dictionary ready for Notion API.

    Example:
        >>> make_code("print('Hello')", language="python")
        {'type': 'code', 'code': {'rich_text': [...], 'language': 'python'}}
    """
    return {
        "type": "code",
        "code": {
            "rich_text": [{"type": "text", "text": {"content": code}}],
            "language": language
        }
    }


def make_callout(text: str, icon: str = "💡") -> dict[str, Any]:
    """Create a callout block.

    Args:
        text: Text content for the callout.
        icon: Emoji icon for the callout (default: "💡").

    Returns:
        Callout block dictionary ready for Notion API.

    Example:
        >>> make_callout("Important note", icon="⚠️")
        {'type': 'callout', 'callout': {'rich_text': [...], 'icon': {...}}}
    """
    return {
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "icon": {"type": "emoji", "emoji": icon}
        }
    }


def make_quote(text: str) -> dict[str, Any]:
    """Create a quote block.

    Args:
        text: Text content for the quote.

    Returns:
        Quote block dictionary ready for Notion API.

    Example:
        >>> make_quote("To be or not to be")
        {'type': 'quote', 'quote': {'rich_text': [...]}}
    """
    return {
        "type": "quote",
        "quote": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def make_divider() -> dict[str, Any]:
    """Create a divider block.

    Returns:
        Divider block dictionary ready for Notion API.

    Example:
        >>> make_divider()
        {'type': 'divider', 'divider': {}}
    """
    return {
        "type": "divider",
        "divider": {}
    }


__all__ = [
    "make_paragraph",
    "make_heading",
    "make_toggle",
    "make_bulleted_list_item",
    "make_numbered_list_item",
    "make_to_do",
    "make_code",
    "make_callout",
    "make_quote",
    "make_divider",
]
