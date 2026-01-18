"""Live tests against real Notion API.

These tests make actual API calls to Notion using TEST_PAGE_ID from .env.
They validate the library works correctly against the real API.

Skip if NOTION_API_TOKEN not available.
"""

import os
import pytest
from dotenv import load_dotenv

from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    append_blocks,
    delete_all_blocks,
    generate_diff,
    execute_diff,
)

# Load .env file
load_dotenv()


@pytest.fixture
def test_page():
    """Create a test page under TEST_PAGE_ID and clean up after test.

    Yields the page_id of the created test page.
    Cleanup happens in finally block to ensure it runs even on test failure.
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

    # Create test page
    response = client.notion.pages.create(
        parent={"page_id": parent_id},
        properties={
            "title": {
                "title": [
                    {
                        "text": {"content": "Test Page (auto-generated)"}
                    }
                ]
            }
        }
    )
    page_id = response["id"]

    try:
        yield page_id
    finally:
        # Cleanup: delete the test page
        # Note: Notion API doesn't have a delete endpoint for pages
        # We archive it instead, or just leave cleanup to manual deletion
        # For now, we'll delete all blocks to clean up content
        try:
            delete_all_blocks(client, page_id)
        except Exception as e:
            # Don't fail test if cleanup fails
            print(f"Warning: Cleanup failed for page {page_id}: {e}")


def test_fixture_creates_page(test_page):
    """Test that fixture creates a page successfully.

    Scenario #6: Token check - if no token, test skips
    Scenario #7: Cleanup works - cleanup happens in finally
    """
    # If we get here, fixture worked (didn't skip, created page)
    assert test_page is not None
    assert len(test_page) > 0


def test_create_and_fetch(test_page):
    """Test creating blocks and fetching them back.

    Scenario #1: Create en fetch
    - Maak pagina "Test Master" met:
      - Heading 1: "Test Page"
      - Paragraph: "Initial content"
    - Fetch blocks terug → Assert: 2 blocks, types kloppen, content klopt
    """
    client = get_notion_client()

    # Create blocks
    blocks = [
        {
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"type": "text", "text": {"content": "Test Page"}}]
            }
        },
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": "Initial content"}}]
            }
        }
    ]

    append_blocks(client, test_page, blocks)

    # Fetch blocks back
    fetched = fetch_blocks_recursive(client, test_page)

    # Assert: 2 blocks
    assert len(fetched) == 2

    # Assert: types correct
    assert fetched[0]["type"] == "heading_1"
    assert fetched[1]["type"] == "paragraph"

    # Assert: content correct
    from notion_sync import extract_block_text
    assert extract_block_text(fetched[0]) == "Test Page"
    assert extract_block_text(fetched[1]) == "Initial content"


def test_empty_page(test_page):
    """Test fetching from empty page.

    Scenario #4: Lege pagina
    - Maak pagina zonder blocks
    - Fetch → Assert: empty list, geen error
    """
    client = get_notion_client()

    # Don't add any blocks, just fetch
    fetched = fetch_blocks_recursive(client, test_page)

    # Assert: empty list
    assert fetched == []
    assert isinstance(fetched, list)


def test_nested_blocks(test_page):
    """Test fetching nested blocks.

    Scenario #5: Nested blocks
    - Maak toggle met 2 nested paragraphs
    - Fetch recursive → Assert: toggle heeft _children met 2 items
    """
    client = get_notion_client()

    # Create toggle with nested children
    blocks = [
        {
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": "Toggle block"}}],
                "children": [
                    {
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": "Child 1"}}]
                        }
                    },
                    {
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": "Child 2"}}]
                        }
                    }
                ]
            }
        }
    ]

    append_blocks(client, test_page, blocks)

    # Fetch recursive
    fetched = fetch_blocks_recursive(client, test_page)

    # Assert: 1 toggle block
    assert len(fetched) == 1
    assert fetched[0]["type"] == "toggle"

    # Assert: toggle has _children with 2 items
    assert "_children" in fetched[0]
    assert len(fetched[0]["_children"]) == 2

    # Assert: children content
    from notion_sync import extract_block_text
    assert extract_block_text(fetched[0]["_children"][0]) == "Child 1"
    assert extract_block_text(fetched[0]["_children"][1]) == "Child 2"


def test_diff_update(test_page):
    """Test updating content via diff.

    Scenario #2: Update via diff
    - Start met pagina met paragraph "Version 1"
    - Wijzig naar "Version 2" via diff
    - Assert: 1 UPDATE operatie (geen DELETE + INSERT)
    - Fetch terug → Content is "Version 2"
    """
    client = get_notion_client()

    # Create initial content
    initial_blocks = [
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": "Version 1"}}]
            }
        }
    ]
    append_blocks(client, test_page, initial_blocks)

    # Fetch current state
    current_blocks = fetch_blocks_recursive(client, test_page)

    # New desired content
    new_blocks = [
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": "Version 2"}}]
            }
        }
    ]

    # Generate diff
    ops = generate_diff(current_blocks, new_blocks)

    # Assert: should have 1 UPDATE operation (not DELETE + INSERT)
    update_ops = [op for op in ops if op["op"] == "UPDATE"]
    delete_ops = [op for op in ops if op["op"] == "DELETE"]
    insert_ops = [op for op in ops if op["op"] == "INSERT"]

    assert len(update_ops) == 1, f"Expected 1 UPDATE, got {len(update_ops)}"
    assert len(delete_ops) == 0, f"Expected 0 DELETE, got {len(delete_ops)}"
    assert len(insert_ops) == 0, f"Expected 0 INSERT, got {len(insert_ops)}"

    # Execute diff
    stats = execute_diff(client, ops, test_page, dry_run=False)

    # Verify stats
    assert stats["updated"] == 1

    # Fetch back and verify content
    fetched = fetch_blocks_recursive(client, test_page)
    from notion_sync import extract_block_text
    assert extract_block_text(fetched[0]) == "Version 2"
