"""Live tests against real Notion API.

These tests make actual API calls to Notion using TEST_PAGE_ID from .env.
All tests use a single master page that accumulates content.
At the end, a clone is created - both pages remain for manual inspection.

Skip if NOTION_API_TOKEN not available.
"""

import os
import pytest
from dotenv import load_dotenv

from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    append_blocks,
    generate_diff,
    execute_diff,
)

# Load .env file
load_dotenv()


@pytest.fixture(scope="module")
def master_page():
    """Create master test page for all tests.

    Uses scope="module" so all tests share the same page.
    Content accumulates across tests - no cleanup between tests.
    Page remains after tests for manual inspection.
    """
    # Check if we have API token
    token = os.getenv("NOTION_API_TOKEN")
    if not token:
        pytest.skip("NOTION_API_TOKEN not set - skipping live tests")

    # Check if we have TEST_PAGE_ID
    parent_id = os.getenv("TEST_PAGE_ID")
    if not parent_id:
        pytest.skip("TEST_PAGE_ID not set - skipping live tests")

    # Create client
    client = get_notion_client()

    # Create master page
    response = client.notion.pages.create(
        parent={"page_id": parent_id},
        properties={
            "title": {
                "title": [
                    {
                        "text": {"content": "Test Master (auto-generated)"}
                    }
                ]
            }
        }
    )
    page_id = response["id"]

    # No cleanup - page remains for inspection
    yield page_id


def test_1_create_and_fetch(master_page):
    """Test creating initial blocks and fetching them back.

    Scenario #1: Create en fetch
    - Maak master met heading + paragraph
    - Fetch blocks terug → Assert: types en content kloppen
    """
    client = get_notion_client()

    # Create initial blocks
    blocks = [
        {
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"type": "text", "text": {"content": "Test Results"}}]
            }
        },
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": "Initial content"}}]
            }
        }
    ]

    append_blocks(client, master_page, blocks)

    # Fetch blocks back
    fetched = fetch_blocks_recursive(client, master_page)

    # Assert: 2 blocks with correct content
    assert len(fetched) >= 2
    from notion_sync import extract_block_text
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

    # Add toggle with nested children
    blocks = [
        {
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": "Nested Test"}}],
                "children": [
                    {
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": "Nested child 1"}}]
                        }
                    },
                    {
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": "Nested child 2"}}]
                        }
                    }
                ]
            }
        }
    ]

    append_blocks(client, master_page, blocks)

    # Fetch and find toggle block
    fetched = fetch_blocks_recursive(client, master_page)
    toggle_blocks = [b for b in fetched if b["type"] == "toggle"]

    assert len(toggle_blocks) >= 1
    toggle = toggle_blocks[0]
    assert "_children" in toggle
    assert len(toggle["_children"]) == 2

    from notion_sync import extract_block_text
    assert extract_block_text(toggle["_children"][0]) == "Nested child 1"
    assert extract_block_text(toggle["_children"][1]) == "Nested child 2"


def test_3_diff_update(master_page):
    """Test updating content via diff.

    Scenario #2: Update via diff
    - Voeg paragraph "Version 1" toe
    - Wijzig naar "Version 2" via diff
    - Assert: UPDATE operatie (niet DELETE + INSERT)
    """
    client = get_notion_client()

    # Add a paragraph
    blocks = [
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": "Version 1"}}]
            }
        }
    ]
    append_blocks(client, master_page, blocks)

    # Fetch current state
    current_blocks = fetch_blocks_recursive(client, master_page)

    # Find the "Version 1" paragraph
    version_blocks = [b for b in current_blocks if b["type"] == "paragraph"]
    from notion_sync import extract_block_text
    version_block = [b for b in version_blocks if extract_block_text(b) == "Version 1"][0]

    # Create updated version of just this block
    updated_block = {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": "Version 2"}}]
        }
    }

    # Generate diff for single block update
    ops = generate_diff([version_block], [updated_block])

    # Assert: should have UPDATE operation
    update_ops = [op for op in ops if op["op"] == "UPDATE"]
    assert len(update_ops) == 1, f"Expected 1 UPDATE, got {len(update_ops)}"

    # Execute diff
    stats = execute_diff(client, ops, master_page, dry_run=False)
    assert stats["updated"] == 1

    # Verify update
    fetched = fetch_blocks_recursive(client, master_page)
    version_blocks = [b for b in fetched if b["type"] == "paragraph"]
    version_texts = [extract_block_text(b) for b in version_blocks]
    assert "Version 2" in version_texts


def test_4_clone_and_sync(master_page):
    """Test cloning master and keeping both in sync.

    Scenario #3: Clone en sync
    - Clone master → "Test Clone"
    - Assert: Clone heeft alle content van master
    - Voeg "Final update" toe aan beide
    - Assert: master en clone blijven identiek

    Both pages remain for manual inspection.
    """
    client = get_notion_client()

    # Fetch all master content
    master_content = fetch_blocks_recursive(client, master_page)

    # Create clone page
    parent_id = os.getenv("TEST_PAGE_ID")
    clone_response = client.notion.pages.create(
        parent={"page_id": parent_id},
        properties={
            "title": {
                "title": [
                    {
                        "text": {"content": "Test Clone (auto-generated)"}
                    }
                ]
            }
        }
    )
    clone_page_id = clone_response["id"]

    # Clone all content to clone page
    clean_blocks = []
    for block in master_content:
        clean_block = {"type": block["type"]}
        clean_block[block["type"]] = block[block["type"]].copy()
        # Copy children recursively
        if "_children" in block:
            children = []
            for child in block["_children"]:
                child_clean = {"type": child["type"]}
                child_clean[child["type"]] = child[child["type"]].copy()
                children.append(child_clean)
            clean_block[block["type"]]["children"] = children
        clean_blocks.append(clean_block)

    append_blocks(client, clone_page_id, clean_blocks)

    # Verify clone has same content
    clone_content = fetch_blocks_recursive(client, clone_page_id)
    assert len(clone_content) == len(master_content)

    from notion_sync import extract_block_text
    for master_block, clone_block in zip(master_content, clone_content):
        assert master_block["type"] == clone_block["type"]
        assert extract_block_text(master_block) == extract_block_text(clone_block)

    # Add final update to both
    final_block = [
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": "Final sync test - both pages identical"}}]
            }
        }
    ]

    append_blocks(client, master_page, final_block)
    append_blocks(client, clone_page_id, final_block)

    # Verify both still identical
    final_master = fetch_blocks_recursive(client, master_page)
    final_clone = fetch_blocks_recursive(client, clone_page_id)

    assert len(final_master) == len(final_clone)

    # Both should have the final message
    master_texts = [extract_block_text(b) for b in final_master if b["type"] == "paragraph"]
    clone_texts = [extract_block_text(b) for b in final_clone if b["type"] == "paragraph"]

    assert "Final sync test - both pages identical" in master_texts
    assert "Final sync test - both pages identical" in clone_texts

    print(f"\nTest complete!")
    print(f"Master page ID: {master_page}")
    print(f"Clone page ID: {clone_page_id}")
    print(f"Check both pages in Notion - they should be identical")
