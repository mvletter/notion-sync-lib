"""Shared pytest fixtures and helpers for live tests."""

import os
import logging
import pytest
from dotenv import load_dotenv
from notion_sync import get_notion_client

# Load .env file
load_dotenv()

# Configure logging for fixtures
logger = logging.getLogger(__name__)


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

    # Skip sync for user action tests (test_98 and test_99)
    # These tests handle syncing manually
    if request.node.name in ["test_98_user_reorder", "test_99_delete_all_verification"]:
        logger.info(f"[{request.node.name}] Skipping auto-sync for user action test")
        return

    logger.info(f"[{request.node.name}] Starting auto-sync: master → clone")

    from notion_sync import (
        fetch_blocks_recursive,
        generate_diff,
        execute_diff,
    )

    client = get_notion_client()

    try:
        # Fetch current state of both pages
        logger.debug(f"Fetching master blocks from {master_page_id}")
        master_blocks = fetch_blocks_recursive(client, master_page_id)
        logger.info(f"Master has {len(master_blocks)} top-level blocks")

        logger.debug(f"Fetching clone blocks from {clone_page_id}")
        clone_blocks = fetch_blocks_recursive(client, clone_page_id)
        logger.info(f"Clone has {len(clone_blocks)} top-level blocks")

        # Generate diff to sync master → clone
        # Use generate_diff (not recursive) which handles INSERT/DELETE/UPDATE operations
        # generate_recursive_diff is only for UPDATE-only scenarios (e.g., translations)
        # AI-CONTEXT: See docs/pitfalls.md#api-wrong-diff-function
        logger.debug("Generating diff")
        ops = generate_diff(clone_blocks, master_blocks)
        logger.info(f"Generated {len(ops)} operations")

        # Execute sync
        if ops:
            logger.debug(f"Executing {len(ops)} operations on clone")
            execute_diff(client, ops, clone_page_id, dry_run=False)
            logger.info(f"✅ Auto-sync completed: {len(ops)} operations executed")

            # Verify sync was successful by checking block count
            logger.debug("Verifying sync success")
            clone_blocks_after = fetch_blocks_recursive(client, clone_page_id)
            if len(clone_blocks_after) == len(master_blocks):
                logger.info(f"✅ Verification passed: clone has {len(clone_blocks_after)} blocks")
            else:
                logger.error(
                    f"❌ Verification failed: clone has {len(clone_blocks_after)} blocks, "
                    f"expected {len(master_blocks)}"
                )
                raise AssertionError(
                    f"Auto-sync verification failed: clone has {len(clone_blocks_after)} blocks, "
                    f"expected {len(master_blocks)}"
                )
        else:
            logger.info("ℹ️ No operations needed - pages already in sync")

    except Exception as e:
        logger.error(f"❌ Auto-sync failed: {type(e).__name__}: {e}", exc_info=True)
        raise


# Helper functions for creating blocks


# Import block builders from the library
from notion_sync.builders import make_paragraph, make_heading, make_toggle


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
