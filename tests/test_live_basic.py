"""Basic live tests: create, fetch, nested blocks."""

from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    append_blocks,
    extract_block_text,
)
from conftest import make_paragraph, make_heading, make_toggle


def test_1_create_and_fetch(master_page):
    """Test creating initial blocks and fetching them back.

    Scenario #1: Create en fetch
    - Maak master met heading + paragraph
    - Fetch blocks terug → Assert: types en content kloppen
    """
    client = get_notion_client()

    # Create initial blocks using helpers
    blocks = [
        make_heading(1, "Test Results"),
        make_paragraph("Initial content")
    ]

    append_blocks(client, master_page, blocks)

    # Fetch blocks back
    fetched = fetch_blocks_recursive(client, master_page)

    # Assert: 2 blocks with correct content
    assert len(fetched) >= 2
    assert fetched[0]["type"] == "heading_1"
    assert extract_block_text(fetched[0]) == "Test Results"
    assert fetched[1]["type"] == "paragraph"
    assert extract_block_text(fetched[1]) == "Initial content"


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
            "Nested Test",
            children=[
                make_paragraph("Nested child 1"),
                make_paragraph("Nested child 2")
            ]
        )
    ]

    append_blocks(client, master_page, blocks)

    # Fetch and find toggle block
    fetched = fetch_blocks_recursive(client, master_page)
    toggle_blocks = [b for b in fetched if b["type"] == "toggle"]

    assert len(toggle_blocks) >= 1
    toggle = toggle_blocks[0]
    assert "_children" in toggle
    assert len(toggle["_children"]) == 2

    assert extract_block_text(toggle["_children"][0]) == "Nested child 1"
    assert extract_block_text(toggle["_children"][1]) == "Nested child 2"
