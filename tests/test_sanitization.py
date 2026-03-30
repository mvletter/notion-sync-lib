"""Characterization tests for block sanitization logic.

These tests capture the CURRENT behavior of all sanitization paths in diff.py.
They exist to prove behavior preservation after refactoring (SPEC-REFACTOR-002).

Tests are organized by block type, with each test verifying what data
reaches client.update_block() for each sanitization path.

NO live Notion API calls — these use mocks.
"""

import copy
import pytest
from unittest.mock import MagicMock, patch, call

from notion_sync.diff import (
    execute_recursive_diff,
    execute_diff,
    _sanitize_for_update,
    _RICH_TEXT_ONLY_BLOCKS,
    _FILE_BASED_BLOCKS,
    _STRUCTURE_ONLY_BLOCKS,
)


# Override autouse fixtures from conftest.py that require NOTION_API_TOKEN
@pytest.fixture(autouse=True)
def sync_to_clone():
    """No-op override — these are unit tests, no live sync needed."""
    yield

@pytest.fixture
def test_pages():
    """No-op override — these are unit tests."""
    return ("fake-master", "fake-clone")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_client():
    """Create a mock RateLimitedNotionClient."""
    client = MagicMock()
    client.update_block = MagicMock(return_value={"id": "block-1"})
    client.delete_block = MagicMock(return_value={"id": "block-1"})
    client.append_blocks = MagicMock(return_value={"results": []})
    return client


def _make_recursive_op(block_type, content, notion_content=None):
    """Create an UPDATE op for execute_recursive_diff.

    Args:
        block_type: e.g. "paragraph", "heading_1"
        content: dict of the block type content
        notion_content: optional different notion block content (defaults to content)
    """
    if notion_content is None:
        notion_content = content
    return {
        "op": "UPDATE",
        "notion_block_id": "block-1",
        "path": "[0]",
        "local_block": {
            "type": block_type,
            block_type: copy.deepcopy(content),
        },
        "notion_block": {
            "type": block_type,
            block_type: copy.deepcopy(notion_content),
            "archived": False,
        },
    }


def _make_diff_op(block_type, content, notion_content=None, index=0):
    """Create an UPDATE op for execute_diff.

    Args:
        block_type: e.g. "paragraph", "heading_1"
        content: dict of the block type content
        notion_content: optional different notion block content (defaults to content)
        index: operation index
    """
    if notion_content is None:
        notion_content = content
    return {
        "op": "UPDATE",
        "index": index,
        "notion_block_id": "block-1",
        "local_block": {
            "type": block_type,
            block_type: copy.deepcopy(content),
        },
        "notion_block": {
            "type": block_type,
            block_type: copy.deepcopy(notion_content),
            "archived": False,
        },
    }


def _get_update_data(client):
    """Extract the 'data' kwarg from the first update_block call."""
    assert client.update_block.called, "update_block was not called"
    return client.update_block.call_args[1]["data"]


# ---------------------------------------------------------------------------
# Paragraph (default path)
# ---------------------------------------------------------------------------

class TestParagraphSanitization:
    """Paragraph uses the default path in both functions."""

    def test_recursive_diff_strips_children_and_icon(self):
        """execute_recursive_diff: default path strips children + icon."""
        client = _make_mock_client()
        ops = [_make_recursive_op("paragraph", {
            "rich_text": [{"type": "text", "text": {"content": "hello"}}],
            "children": [{"type": "paragraph"}],
            "icon": None,
            "color": "default",
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert "paragraph" in data
        assert "children" not in data["paragraph"]
        assert "icon" not in data["paragraph"]
        # color preserved in paragraph (default path)
        assert data["paragraph"]["color"] == "default"

    def test_diff_strips_children_and_icon(self):
        """execute_diff: default path strips children + icon."""
        client = _make_mock_client()
        ops = [_make_diff_op("paragraph", {
            "rich_text": [{"type": "text", "text": {"content": "hello"}}],
            "children": [{"type": "paragraph"}],
            "icon": None,
            "color": "default",
        })]
        execute_diff(client, ops, page_id="page-1")
        data = _get_update_data(client)
        assert "paragraph" in data
        assert "children" not in data["paragraph"]
        assert "icon" not in data["paragraph"]
        assert data["paragraph"]["color"] == "default"


# ---------------------------------------------------------------------------
# Heading (rich_text only + is_toggleable + color)
# ---------------------------------------------------------------------------

class TestHeadingSanitization:
    """Headings use _RICH_TEXT_ONLY_BLOCKS path with special heading props."""

    @pytest.mark.parametrize("heading_type", ["heading_1", "heading_2", "heading_3"])
    def test_recursive_diff_preserves_heading_props(self, heading_type):
        """execute_recursive_diff: preserves is_toggleable and color for headings."""
        client = _make_mock_client()
        ops = [_make_recursive_op(heading_type, {
            "rich_text": [{"type": "text", "text": {"content": "Title"}}],
            "is_toggleable": True,
            "color": "blue",
            "children": [{"type": "paragraph"}],
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert heading_type in data
        assert data[heading_type]["rich_text"] == [{"type": "text", "text": {"content": "Title"}}]
        assert data[heading_type]["is_toggleable"] is True
        assert data[heading_type]["color"] == "blue"
        # Should NOT have children
        assert "children" not in data[heading_type]

    @pytest.mark.parametrize("heading_type", ["heading_1", "heading_2", "heading_3"])
    def test_diff_preserves_heading_props(self, heading_type):
        """execute_diff: preserves is_toggleable and color for headings."""
        client = _make_mock_client()
        ops = [_make_diff_op(heading_type, {
            "rich_text": [{"type": "text", "text": {"content": "Title"}}],
            "is_toggleable": True,
            "color": "blue",
            "children": [{"type": "paragraph"}],
        })]
        execute_diff(client, ops, page_id="page-1")
        data = _get_update_data(client)
        assert heading_type in data
        assert data[heading_type]["is_toggleable"] is True
        assert data[heading_type]["color"] == "blue"
        assert "children" not in data[heading_type]

    def test_recursive_diff_heading_without_toggleable(self):
        """execute_recursive_diff: heading without is_toggleable omits it."""
        client = _make_mock_client()
        ops = [_make_recursive_op("heading_1", {
            "rich_text": [{"type": "text", "text": {"content": "Title"}}],
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert "is_toggleable" not in data["heading_1"]
        assert "color" not in data["heading_1"]


# ---------------------------------------------------------------------------
# Callout (rich_text only, icon NOT stripped)
# ---------------------------------------------------------------------------

class TestCalloutSanitization:
    """Callout is in _RICH_TEXT_ONLY_BLOCKS — only rich_text sent."""

    def test_recursive_diff_callout_rich_text_only(self):
        """execute_recursive_diff: callout restricted to rich_text only."""
        client = _make_mock_client()
        ops = [_make_recursive_op("callout", {
            "rich_text": [{"type": "text", "text": {"content": "note"}}],
            "icon": {"type": "emoji", "emoji": "💡"},
            "color": "yellow_background",
            "children": [{"type": "paragraph"}],
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert "callout" in data
        assert "rich_text" in data["callout"]
        # Callout is NOT a heading, so no is_toggleable/color added
        assert "icon" not in data["callout"]
        assert "color" not in data["callout"]
        assert "children" not in data["callout"]

    def test_diff_callout_rich_text_only(self):
        """execute_diff: callout restricted to rich_text only."""
        client = _make_mock_client()
        ops = [_make_diff_op("callout", {
            "rich_text": [{"type": "text", "text": {"content": "note"}}],
            "icon": {"type": "emoji", "emoji": "💡"},
            "color": "yellow_background",
        })]
        execute_diff(client, ops, page_id="page-1")
        data = _get_update_data(client)
        assert "callout" in data
        assert "rich_text" in data["callout"]
        assert "icon" not in data["callout"]
        assert "color" not in data["callout"]


# ---------------------------------------------------------------------------
# Toggle (rich_text only)
# ---------------------------------------------------------------------------

class TestToggleSanitization:
    """Toggle is in _RICH_TEXT_ONLY_BLOCKS — only rich_text sent."""

    def test_recursive_diff_toggle_rich_text_only(self):
        client = _make_mock_client()
        ops = [_make_recursive_op("toggle", {
            "rich_text": [{"type": "text", "text": {"content": "toggle"}}],
            "color": "default",
            "children": [{"type": "paragraph"}],
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert data == {"toggle": {"rich_text": [{"type": "text", "text": {"content": "toggle"}}]}}

    def test_diff_toggle_rich_text_only(self):
        client = _make_mock_client()
        ops = [_make_diff_op("toggle", {
            "rich_text": [{"type": "text", "text": {"content": "toggle"}}],
            "color": "default",
        })]
        execute_diff(client, ops, page_id="page-1")
        data = _get_update_data(client)
        assert data == {"toggle": {"rich_text": [{"type": "text", "text": {"content": "toggle"}}]}}


# ---------------------------------------------------------------------------
# File-based blocks (caption only)
# ---------------------------------------------------------------------------

class TestFileBasedSanitization:
    """image/video/pdf/file/audio — caption only."""

    @pytest.mark.parametrize("block_type", ["image", "video", "pdf", "file", "audio"])
    def test_recursive_diff_caption_only(self, block_type):
        client = _make_mock_client()
        ops = [_make_recursive_op(block_type, {
            "type": "external",
            "external": {"url": "https://example.com/test.png"},
            "caption": [{"type": "text", "text": {"content": "caption"}}],
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert data == {block_type: {"caption": [{"type": "text", "text": {"content": "caption"}}]}}

    @pytest.mark.parametrize("block_type", ["image", "video", "pdf", "file", "audio"])
    def test_diff_caption_only(self, block_type):
        client = _make_mock_client()
        ops = [_make_diff_op(block_type, {
            "type": "external",
            "external": {"url": "https://example.com/test.png"},
            "caption": [{"type": "text", "text": {"content": "caption"}}],
        })]
        execute_diff(client, ops, page_id="page-1")
        data = _get_update_data(client)
        assert data == {block_type: {"caption": [{"type": "text", "text": {"content": "caption"}}]}}

    @pytest.mark.parametrize("block_type", ["image", "video", "pdf", "file", "audio"])
    def test_empty_caption(self, block_type):
        """When no caption present, should still send empty caption."""
        client = _make_mock_client()
        ops = [_make_recursive_op(block_type, {
            "type": "external",
            "external": {"url": "https://example.com/test.png"},
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert data == {block_type: {"caption": []}}


# ---------------------------------------------------------------------------
# Numbered list item (strip list_start_index)
# ---------------------------------------------------------------------------

class TestNumberedListSanitization:
    """numbered_list_item: execute_diff strips list_start_index.

    KNOWN BUG: execute_recursive_diff does NOT strip list_start_index
    (falls through to default path). This test captures the current
    (buggy) behavior — the refactor will fix this.
    """

    def test_diff_strips_list_start_index(self):
        """execute_diff: strips list_start_index and children."""
        client = _make_mock_client()
        ops = [_make_diff_op("numbered_list_item", {
            "rich_text": [{"type": "text", "text": {"content": "item 1"}}],
            "list_start_index": 1,
            "children": [{"type": "paragraph"}],
            "color": "default",
        })]
        execute_diff(client, ops, page_id="page-1")
        data = _get_update_data(client)
        assert "numbered_list_item" in data
        assert "list_start_index" not in data["numbered_list_item"]
        assert "children" not in data["numbered_list_item"]
        # Other props preserved
        assert "rich_text" in data["numbered_list_item"]
        assert data["numbered_list_item"]["color"] == "default"

    def test_recursive_diff_strips_list_start_index(self):
        """execute_recursive_diff: now strips list_start_index via _sanitize_for_update.

        Previously this was a bug — list_start_index passed through the default
        path. Fixed by SPEC-REFACTOR-002.
        """
        client = _make_mock_client()
        ops = [_make_recursive_op("numbered_list_item", {
            "rich_text": [{"type": "text", "text": {"content": "item 1"}}],
            "list_start_index": 1,
            "children": [{"type": "paragraph"}],
            "color": "default",
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert "numbered_list_item" in data
        assert "list_start_index" not in data["numbered_list_item"]
        assert "children" not in data["numbered_list_item"]
        assert data["numbered_list_item"]["color"] == "default"


# ---------------------------------------------------------------------------
# Table (strip table_width)
# ---------------------------------------------------------------------------

class TestTableSanitization:
    """table: execute_diff strips table_width. But table is in _STRUCTURE_ONLY_BLOCKS
    so it gets SKIPPED entirely in both paths (never reaches sanitization).

    Wait — re-reading the code: _STRUCTURE_ONLY_BLOCKS check happens BEFORE
    the sanitization in execute_recursive_diff (line 406). In execute_diff
    it also skips (line 943). So table blocks are ALWAYS skipped for UPDATE.

    BUT execute_diff has explicit table sanitization code at line 973-977.
    This code is unreachable because the _STRUCTURE_ONLY_BLOCKS check at
    line 943 skips before reaching it.

    Let's verify this behavior.
    """

    def test_recursive_diff_skips_table(self):
        """execute_recursive_diff: table in _STRUCTURE_ONLY_BLOCKS → skipped."""
        client = _make_mock_client()
        ops = [_make_recursive_op("table", {
            "table_width": 3,
            "has_column_header": True,
            "has_row_header": False,
            "children": [],
        })]
        stats = execute_recursive_diff(client, ops)
        assert not client.update_block.called
        assert stats["skipped"] == 1

    def test_diff_skips_table(self):
        """execute_diff: table in _STRUCTURE_ONLY_BLOCKS → skipped (kept count)."""
        client = _make_mock_client()
        ops = [_make_diff_op("table", {
            "table_width": 3,
            "has_column_header": True,
            "has_row_header": False,
            "children": [],
        })]
        stats = execute_diff(client, ops, page_id="page-1")
        assert not client.update_block.called
        # execute_diff counts skipped structure blocks as "kept"
        assert stats["kept"] == 1


# ---------------------------------------------------------------------------
# Column (strip width_ratio >= 1)
# ---------------------------------------------------------------------------

class TestColumnSanitization:
    """column: execute_diff strips width_ratio >= 1.

    KNOWN BUG: execute_recursive_diff does NOT strip width_ratio
    (falls through to default path). The refactor will fix this.
    """

    def test_diff_strips_width_ratio_gte_1(self):
        """execute_diff: strips width_ratio when >= 1."""
        client = _make_mock_client()
        ops = [_make_diff_op("column", {
            "width_ratio": 1,
            "children": [{"type": "paragraph"}],
        })]
        execute_diff(client, ops, page_id="page-1")
        data = _get_update_data(client)
        assert "column" in data
        assert "width_ratio" not in data["column"]
        assert "children" not in data["column"]

    def test_diff_preserves_width_ratio_lt_1(self):
        """execute_diff: preserves width_ratio when < 1."""
        client = _make_mock_client()
        ops = [_make_diff_op("column", {
            "width_ratio": 0.5,
            "children": [{"type": "paragraph"}],
        })]
        execute_diff(client, ops, page_id="page-1")
        data = _get_update_data(client)
        assert "column" in data
        assert data["column"]["width_ratio"] == 0.5
        assert "children" not in data["column"]

    def test_recursive_diff_strips_width_ratio_gte_1(self):
        """execute_recursive_diff: now strips width_ratio >= 1 via _sanitize_for_update.

        Previously this was a bug — width_ratio passed through the default path.
        Fixed by SPEC-REFACTOR-002.
        """
        client = _make_mock_client()
        ops = [_make_recursive_op("column", {
            "width_ratio": 1,
            "children": [{"type": "paragraph"}],
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert "column" in data
        assert "width_ratio" not in data["column"]
        assert "children" not in data["column"]


# ---------------------------------------------------------------------------
# Synced block (null synced_from, strip children)
# ---------------------------------------------------------------------------

class TestSyncedBlockSanitization:
    """synced_block: both paths null synced_from."""

    def test_recursive_diff_nulls_synced_from(self):
        """execute_recursive_diff: synced_from set to None."""
        client = _make_mock_client()
        ops = [_make_recursive_op("synced_block", {
            "synced_from": {"block_id": "orig-123"},
            "children": [{"type": "paragraph"}],
        })]
        # synced copies are filtered out by _is_synced_copy check,
        # but original synced blocks (synced_from=None already or set to None)
        # go through the synced_block branch
        ops[0]["local_block"]["synced_block"]["synced_from"] = {"block_id": "abc"}
        # The notion_block should NOT be a synced copy (synced_from=None)
        ops[0]["notion_block"]["synced_block"] = {"synced_from": None, "children": []}
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert "synced_block" in data
        assert data["synced_block"]["synced_from"] is None

    def test_diff_nulls_synced_from_and_strips_children(self):
        """execute_diff: synced_from set to None, children stripped."""
        client = _make_mock_client()
        ops = [_make_diff_op("synced_block", {
            "synced_from": {"block_id": "abc"},
            "children": [{"type": "paragraph"}],
        })]
        ops[0]["notion_block"]["synced_block"] = {"synced_from": None, "children": []}
        execute_diff(client, ops, page_id="page-1")
        data = _get_update_data(client)
        assert "synced_block" in data
        assert data["synced_block"]["synced_from"] is None
        assert "children" not in data["synced_block"]


# ---------------------------------------------------------------------------
# Archived + synced copy blocks (skipped)
# ---------------------------------------------------------------------------

class TestSkippedBlocks:
    """Blocks that should be skipped entirely."""

    def test_recursive_diff_skips_archived(self):
        client = _make_mock_client()
        op = _make_recursive_op("paragraph", {
            "rich_text": [{"type": "text", "text": {"content": "archived"}}],
        })
        op["notion_block"]["archived"] = True
        stats = execute_recursive_diff(client, [op])
        assert not client.update_block.called
        assert stats["skipped"] == 1

    def test_diff_unarchives_and_updates_archived(self):
        """Archived blocks should be unarchived+updated in one PATCH call."""
        client = _make_mock_client()
        op = _make_diff_op("paragraph", {
            "rich_text": [{"type": "text", "text": {"content": "archived"}}],
        })
        op["notion_block"]["archived"] = True
        stats = execute_diff(client, [op], page_id="page-1")
        assert client.update_block.called
        data = _get_update_data(client)
        assert data.get("archived") is False
        assert "paragraph" in data
        assert stats["updated"] == 1

    def test_diff_archived_fallback_insert(self):
        """If unarchive+update fails, insert a fresh block instead."""
        client = _make_mock_client()
        client.update_block.side_effect = Exception("Can't edit archived block")
        client.append_blocks.return_value = {"results": [{"id": "new-block-1"}]}
        op = _make_diff_op("paragraph", {
            "rich_text": [{"type": "text", "text": {"content": "archived"}}],
        })
        op["notion_block"]["archived"] = True
        stats = execute_diff(client, [op], page_id="page-1")
        assert client.update_block.called
        assert client.append_blocks.called
        assert stats["inserted"] == 1

    def test_recursive_diff_skips_synced_copy(self):
        client = _make_mock_client()
        op = _make_recursive_op("synced_block", {
            "synced_from": {"block_id": "orig-123"},
        })
        op["notion_block"]["synced_block"] = {
            "synced_from": {"block_id": "orig-123"},
        }
        stats = execute_recursive_diff(client, [op])
        assert not client.update_block.called
        assert stats["skipped"] == 1

    def test_diff_skips_synced_copy(self):
        client = _make_mock_client()
        op = _make_diff_op("synced_block", {
            "synced_from": {"block_id": "orig-123"},
        })
        op["notion_block"]["synced_block"] = {
            "synced_from": {"block_id": "orig-123"},
        }
        stats = execute_diff(client, [op], page_id="page-1")
        assert not client.update_block.called
        assert stats["kept"] == 1


# ---------------------------------------------------------------------------
# Type mismatch (skipped in recursive_diff)
# ---------------------------------------------------------------------------

class TestTypeMismatch:
    """Block type mismatch between local and notion — skipped."""

    def test_recursive_diff_skips_type_mismatch(self):
        client = _make_mock_client()
        op = _make_recursive_op("paragraph", {
            "rich_text": [{"type": "text", "text": {"content": "hello"}}],
        })
        # Make notion_block a different type
        op["notion_block"]["type"] = "heading_1"
        op["notion_block"]["heading_1"] = {
            "rich_text": [{"type": "text", "text": {"content": "hello"}}],
        }
        stats = execute_recursive_diff(client, [op])
        assert not client.update_block.called
        assert stats.get("type_mismatch") == 1


# ---------------------------------------------------------------------------
# Bulleted list item (default path - simple)
# ---------------------------------------------------------------------------

class TestBulletedListSanitization:
    """bulleted_list_item: uses default path."""

    def test_recursive_diff_strips_children(self):
        client = _make_mock_client()
        ops = [_make_recursive_op("bulleted_list_item", {
            "rich_text": [{"type": "text", "text": {"content": "bullet"}}],
            "color": "default",
            "children": [{"type": "paragraph"}],
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert "children" not in data["bulleted_list_item"]
        assert data["bulleted_list_item"]["rich_text"] == [{"type": "text", "text": {"content": "bullet"}}]

    def test_diff_strips_children(self):
        client = _make_mock_client()
        ops = [_make_diff_op("bulleted_list_item", {
            "rich_text": [{"type": "text", "text": {"content": "bullet"}}],
            "color": "default",
            "children": [{"type": "paragraph"}],
        })]
        execute_diff(client, ops, page_id="page-1")
        data = _get_update_data(client)
        assert "children" not in data["bulleted_list_item"]


# ---------------------------------------------------------------------------
# Quote (default path)
# ---------------------------------------------------------------------------

class TestQuoteSanitization:
    """quote: uses default path."""

    def test_recursive_diff_default_path(self):
        client = _make_mock_client()
        ops = [_make_recursive_op("quote", {
            "rich_text": [{"type": "text", "text": {"content": "quoted"}}],
            "color": "default",
            "children": [{"type": "paragraph"}],
            "icon": None,
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert "children" not in data["quote"]
        assert "icon" not in data["quote"]
        assert data["quote"]["color"] == "default"


# ---------------------------------------------------------------------------
# To-do (default path)
# ---------------------------------------------------------------------------

class TestTodoSanitization:
    """to_do: uses default path."""

    def test_recursive_diff_preserves_checked(self):
        client = _make_mock_client()
        ops = [_make_recursive_op("to_do", {
            "rich_text": [{"type": "text", "text": {"content": "task"}}],
            "checked": True,
            "color": "default",
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert data["to_do"]["checked"] is True
        assert data["to_do"]["rich_text"] == [{"type": "text", "text": {"content": "task"}}]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases in sanitization."""

    def test_empty_rich_text(self):
        """Heading with empty rich_text."""
        client = _make_mock_client()
        ops = [_make_recursive_op("heading_1", {
            "rich_text": [],
            "is_toggleable": False,
            "color": "default",
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert data["heading_1"]["rich_text"] == []
        assert data["heading_1"]["is_toggleable"] is False
        assert data["heading_1"]["color"] == "default"

    def test_no_caption_in_file_block(self):
        """File block without caption key."""
        client = _make_mock_client()
        ops = [_make_recursive_op("image", {
            "type": "external",
            "external": {"url": "https://example.com/img.png"},
        })]
        execute_recursive_diff(client, ops)
        data = _get_update_data(client)
        assert data == {"image": {"caption": []}}

    def test_multiple_ops_stats(self):
        """Multiple operations return correct stats."""
        client = _make_mock_client()
        ops = [
            _make_recursive_op("paragraph", {
                "rich_text": [{"type": "text", "text": {"content": "p1"}}],
            }),
            _make_recursive_op("paragraph", {
                "rich_text": [{"type": "text", "text": {"content": "p2"}}],
            }),
        ]
        # Give different block_ids
        ops[1]["notion_block_id"] = "block-2"
        stats = execute_recursive_diff(client, ops)
        assert stats["updated"] == 2
        assert client.update_block.call_count == 2

    def test_dry_run_no_api_calls(self):
        """Dry run should not call update_block."""
        client = _make_mock_client()
        ops = [_make_recursive_op("paragraph", {
            "rich_text": [{"type": "text", "text": {"content": "hello"}}],
        })]
        stats = execute_recursive_diff(client, ops, dry_run=True)
        assert not client.update_block.called
        assert stats["updated"] == 1


# ---------------------------------------------------------------------------
# Direct _sanitize_for_update tests (post-refactor validation)
# ---------------------------------------------------------------------------

class TestSanitizeForUpdate:
    """Direct tests for the extracted _sanitize_for_update function."""

    def test_paragraph_strips_children_and_icon(self):
        result = _sanitize_for_update("paragraph", {
            "rich_text": [{"type": "text", "text": {"content": "hello"}}],
            "children": [{"type": "paragraph"}],
            "icon": None,
            "color": "default",
        })
        assert result == {"paragraph": {
            "rich_text": [{"type": "text", "text": {"content": "hello"}}],
            "color": "default",
        }}

    def test_heading_preserves_toggleable_and_color(self):
        result = _sanitize_for_update("heading_1", {
            "rich_text": [{"type": "text", "text": {"content": "Title"}}],
            "is_toggleable": True,
            "color": "blue",
            "children": [{"type": "paragraph"}],
        })
        assert result == {"heading_1": {
            "rich_text": [{"type": "text", "text": {"content": "Title"}}],
            "is_toggleable": True,
            "color": "blue",
        }}

    def test_heading_omits_missing_toggleable(self):
        result = _sanitize_for_update("heading_2", {
            "rich_text": [],
        })
        assert result == {"heading_2": {"rich_text": []}}
        assert "is_toggleable" not in result["heading_2"]

    def test_callout_rich_text_only(self):
        result = _sanitize_for_update("callout", {
            "rich_text": [{"type": "text", "text": {"content": "note"}}],
            "icon": {"type": "emoji", "emoji": "💡"},
            "color": "yellow_background",
        })
        assert result == {"callout": {
            "rich_text": [{"type": "text", "text": {"content": "note"}}],
        }}

    def test_toggle_rich_text_only(self):
        result = _sanitize_for_update("toggle", {
            "rich_text": [{"type": "text", "text": {"content": "toggle"}}],
            "color": "default",
            "children": [{"type": "paragraph"}],
        })
        assert result == {"toggle": {
            "rich_text": [{"type": "text", "text": {"content": "toggle"}}],
        }}

    @pytest.mark.parametrize("block_type", ["image", "video", "pdf", "file", "audio"])
    def test_file_blocks_caption_only(self, block_type):
        result = _sanitize_for_update(block_type, {
            "type": "external",
            "external": {"url": "https://example.com/test.png"},
            "caption": [{"type": "text", "text": {"content": "cap"}}],
        })
        assert result == {block_type: {"caption": [{"type": "text", "text": {"content": "cap"}}]}}

    def test_file_block_no_caption(self):
        result = _sanitize_for_update("image", {
            "type": "external",
            "external": {"url": "https://example.com/img.png"},
        })
        assert result == {"image": {"caption": []}}

    def test_numbered_list_strips_list_start_index(self):
        result = _sanitize_for_update("numbered_list_item", {
            "rich_text": [{"type": "text", "text": {"content": "item 1"}}],
            "list_start_index": 1,
            "children": [{"type": "paragraph"}],
            "color": "default",
        })
        assert "list_start_index" not in result["numbered_list_item"]
        assert "children" not in result["numbered_list_item"]
        assert result["numbered_list_item"]["color"] == "default"

    def test_synced_block_nulls_synced_from(self):
        result = _sanitize_for_update("synced_block", {
            "synced_from": {"block_id": "abc"},
            "children": [{"type": "paragraph"}],
        })
        assert result["synced_block"]["synced_from"] is None
        assert "children" not in result["synced_block"]

    def test_column_strips_width_ratio_gte_1(self):
        result = _sanitize_for_update("column", {
            "width_ratio": 1,
            "children": [{"type": "paragraph"}],
        })
        assert "width_ratio" not in result["column"]
        assert "children" not in result["column"]

    def test_column_preserves_width_ratio_lt_1(self):
        result = _sanitize_for_update("column", {
            "width_ratio": 0.5,
            "children": [{"type": "paragraph"}],
        })
        assert result["column"]["width_ratio"] == 0.5
        assert "children" not in result["column"]

    def test_does_not_mutate_input(self):
        """Input dict must not be modified."""
        original = {
            "rich_text": [{"type": "text", "text": {"content": "hello"}}],
            "children": [{"type": "paragraph"}],
            "icon": None,
        }
        original_copy = copy.deepcopy(original)
        _sanitize_for_update("paragraph", original)
        assert original == original_copy

    def test_bulleted_list_default_path(self):
        result = _sanitize_for_update("bulleted_list_item", {
            "rich_text": [{"type": "text", "text": {"content": "bullet"}}],
            "color": "default",
            "children": [{"type": "paragraph"}],
        })
        assert "children" not in result["bulleted_list_item"]
        assert "icon" not in result["bulleted_list_item"]

    def test_to_do_preserves_checked(self):
        result = _sanitize_for_update("to_do", {
            "rich_text": [],
            "checked": True,
            "color": "default",
        })
        assert result["to_do"]["checked"] is True


# ---------------------------------------------------------------------------
# Tab (structure-only — skipped for UPDATE)
# ---------------------------------------------------------------------------

class TestTabSanitization:
    """tab: in _STRUCTURE_ONLY_BLOCKS — skipped entirely for UPDATE.

    tab: {} is an empty object. Content lives in paragraph children.
    """

    def test_tab_in_structure_only_blocks(self):
        assert "tab" in _STRUCTURE_ONLY_BLOCKS

    def test_recursive_diff_skips_tab(self):
        """execute_recursive_diff: tab in _STRUCTURE_ONLY_BLOCKS → skipped."""
        client = _make_mock_client()
        ops = [_make_recursive_op("tab", {})]
        stats = execute_recursive_diff(client, ops)
        assert not client.update_block.called
        assert stats["skipped"] == 1

    def test_diff_skips_tab(self):
        """execute_diff: tab in _STRUCTURE_ONLY_BLOCKS → skipped (kept count)."""
        client = _make_mock_client()
        ops = [_make_diff_op("tab", {})]
        stats = execute_diff(client, ops, page_id="page-1")
        assert not client.update_block.called
        assert stats["kept"] == 1


# ---------------------------------------------------------------------------
# Meeting notes (structure-only + non-creatable — fully read-only)
# ---------------------------------------------------------------------------

class TestMeetingNotesSanitization:
    """meeting_notes: read-only block. Cannot create, update, or delete via API."""

    def test_meeting_notes_in_structure_only_blocks(self):
        assert "meeting_notes" in _STRUCTURE_ONLY_BLOCKS

    def test_recursive_diff_skips_meeting_notes(self):
        """execute_recursive_diff: meeting_notes → skipped."""
        client = _make_mock_client()
        ops = [_make_recursive_op("meeting_notes", {
            "title": [{"type": "text", "text": {"content": "Team Sync"}}],
            "status": "notes_ready",
        })]
        stats = execute_recursive_diff(client, ops)
        assert not client.update_block.called
        assert stats["skipped"] == 1

    def test_diff_skips_meeting_notes(self):
        """execute_diff: meeting_notes → skipped (kept count)."""
        client = _make_mock_client()
        ops = [_make_diff_op("meeting_notes", {
            "title": [{"type": "text", "text": {"content": "Team Sync"}}],
            "status": "notes_ready",
        })]
        stats = execute_diff(client, ops, page_id="page-1")
        assert not client.update_block.called
        assert stats["kept"] == 1


# ---------------------------------------------------------------------------
# Text extraction for new block types
# ---------------------------------------------------------------------------

class TestExtractNewBlockTypes:
    """Text extraction for tab and meeting_notes blocks."""

    def test_tab_returns_type_identifier(self):
        from notion_sync.extract import extract_block_text
        block = {"type": "tab", "tab": {}}
        assert extract_block_text(block) == "tab"

    def test_meeting_notes_with_title(self):
        from notion_sync.extract import extract_block_text
        block = {
            "type": "meeting_notes",
            "meeting_notes": {
                "title": [{"type": "text", "text": {"content": "Team Sync"}, "plain_text": "Team Sync"}],
                "status": "notes_ready",
            }
        }
        assert extract_block_text(block) == "meeting_notes:Team Sync"

    def test_meeting_notes_without_title(self):
        from notion_sync.extract import extract_block_text
        block = {
            "type": "meeting_notes",
            "meeting_notes": {
                "status": "transcription_in_progress",
            }
        }
        assert extract_block_text(block) == "meeting_notes"

    def test_meeting_notes_empty(self):
        from notion_sync.extract import extract_block_text
        block = {"type": "meeting_notes", "meeting_notes": {}}
        assert extract_block_text(block) == "meeting_notes"
