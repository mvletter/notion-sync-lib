"""Shared pytest fixtures and helpers for live tests."""

import os
import pytest
from dotenv import load_dotenv
from notion_sync import get_notion_client

# Load .env file
load_dotenv()


@pytest.fixture(scope="session")
def master_page():
    """Create master test page for all tests.

    Uses scope="session" so all test files share the same page.
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
