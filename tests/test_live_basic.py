"""Basic live tests: create, fetch, nested blocks."""

from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    append_blocks,
    extract_block_text,
)
from .conftest import make_paragraph, make_heading, make_toggle


def test_1_create_and_fetch(master_page):
    """Test creating initial blocks and fetching them back.

    Scenario #1: Create en fetch
    - Maak master met heading + paragraph
    - Fetch blocks terug → Assert: types en content kloppen

    Note: Session-scoped fixture means content accumulates.
    We search for our specific test blocks by text instead of position.
    """
    client = get_notion_client()

    # Create initial blocks using helpers
    blocks = [
        make_heading(1, "Test #1 Results"),
        make_paragraph("Test #1 Initial content")
    ]

    append_blocks(client, master_page, blocks)

    # Fetch blocks back
    fetched = fetch_blocks_recursive(client, master_page)

    # Find our test blocks by text (not position, since content accumulates)
    from .conftest import find_block_by_text

    heading = find_block_by_text(fetched, "Test #1 Results", "heading_1")
    paragraph = find_block_by_text(fetched, "Test #1 Initial content", "paragraph")

    # Assert: blocks exist with correct types and content
    assert heading["type"] == "heading_1"
    assert "Test #1 Results" in extract_block_text(heading)
    assert paragraph["type"] == "paragraph"
    assert "Test #1 Initial content" in extract_block_text(paragraph)


def test_2_nested_blocks(master_page):
    """Test adding nested blocks.

    Scenario #5: Nested blocks
    - Voeg toggle met nested children toe
    - Fetch recursive → Assert: toggle heeft _children
    """
    client = get_notion_client()

    # Add toggle with nested children using helper
    blocks = [
        make_toggle(
            "Test #2 Nested Toggle",
            children=[
                make_paragraph("Test #2 Nested child 1"),
                make_paragraph("Test #2 Nested child 2")
            ]
        )
    ]

    append_blocks(client, master_page, blocks)

    # Fetch and find toggle block
    fetched = fetch_blocks_recursive(client, master_page)
    toggle_blocks = [b for b in fetched if b["type"] == "toggle"]

    assert len(toggle_blocks) >= 1
    toggle = toggle_blocks[-1]  # Get last toggle (our test)
    assert "_children" in toggle
    assert len(toggle["_children"]) == 2

    assert "Test #2" in extract_block_text(toggle["_children"][0])
    assert "Test #2" in extract_block_text(toggle["_children"][1])
