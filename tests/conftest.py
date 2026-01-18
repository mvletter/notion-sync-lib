"""Shared pytest fixtures and helpers for live tests."""

import os
import pytest
from dotenv import load_dotenv
from notion_sync import get_notion_client

# Load .env file
load_dotenv()


def pytest_collection_modifyitems(items):
    """Ensure test_99_verify_sync runs last."""
    verify_test = None
    other_tests = []

    for item in items:
        if item.name == "test_99_verify_sync":
            verify_test = item
        else:
            other_tests.append(item)

    if verify_test:
        items[:] = other_tests + [verify_test]


@pytest.fixture(scope="session")
def test_pages():
    """Create master and clone test pages for all tests.

    Uses scope="session" so all test files share the same pages.
    Content accumulates across tests - no cleanup between tests.
    Both pages remain after tests for manual inspection.

    Yields tuple: (master_page_id, clone_page_id)
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
    master_response = client.notion.pages.create(
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
    master_page_id = master_response["id"]

    # Create clone page
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

    # No cleanup - both pages remain for inspection
    yield (master_page_id, clone_page_id)


@pytest.fixture(scope="session")
def master_page(test_pages):
    """Get master page ID from test_pages fixture."""
    return test_pages[0]


@pytest.fixture(scope="session")
def clone_page(test_pages):
    """Get clone page ID from test_pages fixture."""
    return test_pages[1]


@pytest.fixture(autouse=True)
def sync_to_clone(request, test_pages):
    """After each test, sync master changes to clone.

    Uses autouse=True so it runs automatically after every test.
    Syncs via diff to test that all operations work correctly.
    """
    # Run the test first
    yield

    # After test: sync master to clone
    master_page_id, clone_page_id = test_pages

    # Skip sync for the final verification test (test_99)
    # to avoid double-syncing
    if request.node.name == "test_99_verify_sync":
        return

    from notion_sync import (
        fetch_blocks_recursive,
        generate_recursive_diff,
        execute_recursive_diff,
    )

    client = get_notion_client()

    # Fetch current state of both pages
    master_blocks = fetch_blocks_recursive(client, master_page_id)
    clone_blocks = fetch_blocks_recursive(client, clone_page_id)

    # Generate recursive diff to sync master → clone
    # Use recursive version to handle nested structures like column_lists
    ops = generate_recursive_diff(clone_blocks, master_blocks)

    # Execute sync
    if ops:
        execute_recursive_diff(client, ops, clone_page_id, dry_run=False)


# Helper functions for creating blocks


def make_paragraph(text: str) -> dict:
    """Create a paragraph block."""
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def make_heading(level: int, text: str) -> dict:
    """Create a heading block (level 1, 2, or 3)."""
    heading_type = f"heading_{level}"
    return {
        "type": heading_type,
        heading_type: {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def make_toggle(text: str, children: list = None) -> dict:
    """Create a toggle block with optional children."""
    block = {
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }
    if children:
        block["toggle"]["children"] = children
    return block


def find_block_by_text(blocks: list, text: str, block_type: str = None) -> dict:
    """Find a block by its text content.

    Args:
        blocks: List of blocks to search
        text: Text content to find
        block_type: Optional block type filter (e.g., "paragraph", "heading_1")

    Returns:
        First matching block or raises ValueError if not found
    """
    from notion_sync import extract_block_text

    for block in blocks:
        if block_type and block["type"] != block_type:
            continue
        if extract_block_text(block) == text:
            return block

    raise ValueError(f"Block with text '{text}' not found")


def find_blocks_by_type(blocks: list, block_type: str) -> list:
    """Find all blocks of a given type."""
    return [b for b in blocks if b["type"] == block_type]


def make_column_list(columns: list) -> dict:
    """Create a column_list structure for testing.

    Args:
        columns: List of dicts with 'children' and optional 'width_ratio'

    Example:
        make_column_list([
            {"children": [make_paragraph("Left")], "width_ratio": 0.5},
            {"children": [make_paragraph("Right")], "width_ratio": 0.5}
        ])
    """
    from notion_sync.columns import _build_column_list_block
    return _build_column_list_block(columns)
