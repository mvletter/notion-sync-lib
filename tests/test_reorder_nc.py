"""Unit tests for non-creatable block handling in _execute_reorder().

Tests the marker block strategy that ensures content is inserted before
non-creatable blocks (child_page, child_database, meeting_notes) during
reorder operations.  Covers SPEC-FIX-002 acceptance criteria AC-1..AC-8.

NO live Notion API calls — these use mocks.
"""

import logging
from unittest.mock import MagicMock, call

import pytest

from notion_sync.diff import _NON_CREATABLE, _execute_reorder


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

def _make_mock_client(current_children=None, page_id="page-1"):
    """Create a mock RateLimitedNotionClient.

    Args:
        current_children: List of block dicts that get_blocks() returns
            for the page_id.  Each dict needs at least {"id": "...", "type": "..."}.
        page_id: The page ID that returns current_children.  All other
            block IDs return an empty list (prevents infinite recursion
            in _delete_block_recursive).
    """
    children = current_children or []

    def _get_blocks(block_id):
        # Only return children for the page itself; individual blocks
        # have no children in these unit tests.
        if block_id == page_id:
            return list(children)
        return []

    client = MagicMock()
    client.get_blocks = MagicMock(side_effect=_get_blocks)
    client.delete_block = MagicMock(return_value={"id": "deleted"})

    # Track append_blocks calls with incrementing IDs
    _append_call_count = {"n": 0}

    def _append_side_effect(**kwargs):
        _append_call_count["n"] += 1
        block_id = f"new-block-{_append_call_count['n']}"
        blocks = kwargs.get("blocks", [])
        # If inserting a divider marker, use a recognizable ID
        if blocks and blocks[0].get("type") == "divider":
            block_id = "marker-divider-id"
        return {"results": [{"id": block_id}]}

    client.append_blocks = MagicMock(side_effect=_append_side_effect)
    return client


def _make_op(op_type, block_type, notion_block_id=None, local_block=None, notion_block=None):
    """Create an op dict for _execute_reorder.

    Args:
        op_type: "INSERT", "KEEP", "UPDATE", "DELETE", "REPLACE"
        block_type: e.g. "paragraph", "child_page"
        notion_block_id: ID of existing Notion block (for KEEP/UPDATE/DELETE/REPLACE)
        local_block: Local block dict (defaults to {"type": block_type, block_type: {}})
        notion_block: Notion block dict (defaults based on block_type and notion_block_id)
    """
    op = {
        "op": op_type,
        "local_block": local_block or {"type": block_type, block_type: {}},
    }
    if notion_block_id:
        op["notion_block_id"] = notion_block_id
        op["notion_block"] = notion_block or {"id": notion_block_id, "type": block_type}
    return op


# ---------------------------------------------------------------------------
# AC-1: Content before NC blocks in standard reorder
# ---------------------------------------------------------------------------

class TestAC1_ContentBeforeNC:
    """Content is inserted before NC blocks after reorder."""

    def test_content_inserted_before_nc_blocks(self):
        """Given page [content_A, content_B, child_page_1, child_page_2],
        ops [INSERT X, INSERT Y, KEEP child_page_1, KEEP child_page_2]:
        content X, Y should end up before child_page blocks."""
        current_children = [
            {"id": "content-a", "type": "paragraph"},
            {"id": "content-b", "type": "paragraph"},
            {"id": "cp-1", "type": "child_page"},
            {"id": "cp-2", "type": "child_page"},
        ]
        client = _make_mock_client(current_children)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
            _make_op("KEEP", "child_page", notion_block_id="cp-2"),
        ]

        stats = _execute_reorder(client, ops, "page-1")

        # Marker should have been created after content-b (before cp-1)
        # Then content inserted after marker, then marker deleted
        assert stats["inserted"] == 2
        assert stats["reordered"] is True

        # Verify marker was inserted after content-b
        marker_call = client.append_blocks.call_args_list[0]
        assert marker_call == call(
            page_id="page-1",
            blocks=[{"type": "divider", "divider": {}}],
            after="content-b",
        )

        # Verify content blocks used marker as anchor
        content_call_1 = client.append_blocks.call_args_list[1]
        assert content_call_1[1]["after"] == "marker-divider-id"

        # Verify marker was deleted (positional arg)
        client.delete_block.assert_any_call("marker-divider-id")

    def test_no_marker_divider_left_on_page(self):
        """After reorder, the marker divider must be cleaned up."""
        current_children = [
            {"id": "content-a", "type": "paragraph"},
            {"id": "cp-1", "type": "child_page"},
        ]
        client = _make_mock_client(current_children)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
        ]

        _execute_reorder(client, ops, "page-1")

        # Marker cleanup: delete_block called with marker ID
        delete_calls = [c for c in client.delete_block.call_args_list
                        if c == call("marker-divider-id")]
        assert len(delete_calls) == 1


# ---------------------------------------------------------------------------
# AC-2: Mixed content and NC blocks
# ---------------------------------------------------------------------------

class TestAC2_MixedContentAndNC:
    """Content and NC blocks in mixed order."""

    def test_mixed_content_nc_blocks(self):
        """Given page [content_A, child_page_1, child_database_1],
        ops with content before NC: marker should be used."""
        current_children = [
            {"id": "content-a", "type": "paragraph"},
            {"id": "cp-1", "type": "child_page"},
            {"id": "cd-1", "type": "child_database"},
        ]
        client = _make_mock_client(current_children)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "paragraph", notion_block_id="content-a"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
            _make_op("KEEP", "child_database", notion_block_id="cd-1"),
        ]

        stats = _execute_reorder(client, ops, "page-1")

        # Marker should be placed after content-a (before cp-1)
        marker_call = client.append_blocks.call_args_list[0]
        assert marker_call == call(
            page_id="page-1",
            blocks=[{"type": "divider", "divider": {}}],
            after="content-a",
        )
        assert stats["inserted"] == 1
        assert stats["kept"] == 1  # content-a KEEP


# ---------------------------------------------------------------------------
# AC-3: Marker is a divider block
# ---------------------------------------------------------------------------

class TestAC3_MarkerIsDivider:
    """Marker block must be of type 'divider'."""

    def test_marker_block_is_divider(self):
        """The marker block payload must be {"type": "divider", "divider": {}}."""
        current_children = [
            {"id": "content-a", "type": "paragraph"},
            {"id": "cp-1", "type": "child_page"},
        ]
        client = _make_mock_client(current_children)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
        ]

        _execute_reorder(client, ops, "page-1")

        # First append_blocks call is the marker
        marker_call = client.append_blocks.call_args_list[0]
        blocks_arg = marker_call[1]["blocks"]
        assert blocks_arg == [{"type": "divider", "divider": {}}]

    def test_marker_inserted_before_first_nc_block(self):
        """Marker is inserted via after=prev_block_id (block before first NC)."""
        current_children = [
            {"id": "para-1", "type": "paragraph"},
            {"id": "para-2", "type": "heading_1"},
            {"id": "cp-1", "type": "child_page"},
        ]
        client = _make_mock_client(current_children)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
        ]

        _execute_reorder(client, ops, "page-1")

        marker_call = client.append_blocks.call_args_list[0]
        # Should be after para-2 (the block before cp-1)
        assert marker_call[1]["after"] == "para-2"


# ---------------------------------------------------------------------------
# AC-4: Marker cleanup on insertion error
# ---------------------------------------------------------------------------

class TestAC4_MarkerCleanupOnError:
    """Marker block must be cleaned up even when content insertion fails."""

    def test_marker_deleted_on_content_insertion_failure(self):
        """When append_blocks fails for content (after marker success),
        the marker must still be deleted."""
        current_children = [
            {"id": "content-a", "type": "paragraph"},
            {"id": "cp-1", "type": "child_page"},
        ]
        client = _make_mock_client(current_children)

        # Make append_blocks succeed for marker, then fail for content
        call_count = {"n": 0}

        def _failing_append(**kwargs):
            call_count["n"] += 1
            blocks = kwargs.get("blocks", [])
            if blocks and blocks[0].get("type") == "divider":
                return {"results": [{"id": "marker-divider-id"}]}
            raise RuntimeError("Simulated API error during content insertion")

        client.append_blocks = MagicMock(side_effect=_failing_append)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
        ]

        with pytest.raises(RuntimeError, match="Simulated API error"):
            _execute_reorder(client, ops, "page-1")

        # Marker must be cleaned up despite the error
        client.delete_block.assert_any_call("marker-divider-id")

    def test_original_error_reraised(self):
        """The original error must propagate to the caller after cleanup."""
        current_children = [
            {"id": "content-a", "type": "paragraph"},
            {"id": "cp-1", "type": "child_page"},
        ]
        client = _make_mock_client(current_children)

        def _failing_append(**kwargs):
            blocks = kwargs.get("blocks", [])
            if blocks and blocks[0].get("type") == "divider":
                return {"results": [{"id": "marker-divider-id"}]}
            raise ValueError("Content insertion failed")

        client.append_blocks = MagicMock(side_effect=_failing_append)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
        ]

        with pytest.raises(ValueError, match="Content insertion failed"):
            _execute_reorder(client, ops, "page-1")


# ---------------------------------------------------------------------------
# AC-5: Graceful degradation — NC blocks already at top
# ---------------------------------------------------------------------------

class TestAC5_NCBlocksAtTop:
    """When NC blocks are already at the top, no marker is created."""

    def test_no_marker_when_nc_at_top(self):
        """Given page [child_page_1, child_page_2, content_A],
        with content ops that come before NC in desired order but NC is
        already at the top of the page: no marker, standard behavior."""
        current_children = [
            {"id": "cp-1", "type": "child_page"},
            {"id": "cp-2", "type": "child_page"},
            {"id": "content-a", "type": "paragraph"},
        ]
        client = _make_mock_client(current_children)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
            _make_op("KEEP", "child_page", notion_block_id="cp-2"),
        ]

        stats = _execute_reorder(client, ops, "page-1")

        # No marker created — no divider in append_blocks calls
        for c in client.append_blocks.call_args_list:
            blocks = c[1].get("blocks", c[0][0] if c[0] else [])
            if isinstance(blocks, list):
                for b in blocks:
                    assert b.get("type") != "divider", "No marker should be created"

        # Content still inserted (just at end, after NC)
        assert stats["inserted"] == 1

    def test_no_crash_when_nc_first_in_children(self):
        """NC block is the very first child — prev_block_id is None."""
        current_children = [
            {"id": "cp-1", "type": "child_page"},
        ]
        client = _make_mock_client(current_children)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
        ]

        # Should not raise
        stats = _execute_reorder(client, ops, "page-1")
        assert stats["inserted"] == 1


# ---------------------------------------------------------------------------
# AC-6: _NON_CREATABLE constant consistency
# ---------------------------------------------------------------------------

class TestAC6_NonCreatableConstant:
    """Module-level _NON_CREATABLE constant is correct and unified."""

    def test_non_creatable_is_frozenset(self):
        assert isinstance(_NON_CREATABLE, frozenset)

    def test_non_creatable_contains_all_types(self):
        assert _NON_CREATABLE == frozenset({"child_database", "child_page", "meeting_notes"})

    def test_no_inline_tuples_in_diff_py(self):
        """Grep-style check: no inline ("child_database", "child_page") tuples remain."""
        import re
        with open("src/notion_sync/diff.py") as f:
            content = f.read()

        # Find inline tuples like ("child_database", "child_page")
        # Exclude the _NON_CREATABLE definition itself and comments/docstrings
        pattern = r'\("child_database",\s*"child_page"\)'
        matches = re.findall(pattern, content)
        assert len(matches) == 0, (
            f"Found {len(matches)} inline ('child_database', 'child_page') tuple(s) "
            f"that should use _NON_CREATABLE instead"
        )


# ---------------------------------------------------------------------------
# AC-7: Dry-run mode
# ---------------------------------------------------------------------------

class TestAC7_DryRun:
    """Dry-run mode must not make any API calls."""

    def test_dry_run_no_api_calls(self):
        """When dry_run=True, no client methods should be called."""
        client = _make_mock_client()

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
            _make_op("UPDATE", "paragraph", notion_block_id="para-1"),
        ]

        _execute_reorder(client, ops, "page-1", dry_run=True)

        client.get_blocks.assert_not_called()
        client.append_blocks.assert_not_called()
        client.delete_block.assert_not_called()

    def test_dry_run_correct_stats(self):
        """Dry-run should still count all ops correctly."""
        client = _make_mock_client()

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("INSERT", "heading_1"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
            _make_op("UPDATE", "paragraph", notion_block_id="para-1"),
            _make_op("DELETE", "paragraph", notion_block_id="para-2"),
            _make_op("REPLACE", "paragraph", notion_block_id="para-3"),
        ]

        stats = _execute_reorder(client, ops, "page-1", dry_run=True)

        assert stats["inserted"] == 2
        assert stats["kept"] == 1
        assert stats["updated"] == 1
        assert stats["deleted"] == 1
        assert stats["replaced"] == 1
        assert stats["reordered"] is True

    def test_dry_run_with_nc_blocks(self):
        """Dry-run with NC blocks should not trigger marker strategy."""
        client = _make_mock_client()

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
            _make_op("KEEP", "child_database", notion_block_id="cd-1"),
        ]

        _execute_reorder(client, ops, "page-1", dry_run=True)

        client.get_blocks.assert_not_called()


# ---------------------------------------------------------------------------
# AC-8: Logging of marker operations
# ---------------------------------------------------------------------------

class TestAC8_Logging:
    """Marker operations must be logged."""

    def test_marker_creation_logged(self, caplog):
        """INFO log for marker creation."""
        current_children = [
            {"id": "content-a", "type": "paragraph"},
            {"id": "cp-1", "type": "child_page"},
        ]
        client = _make_mock_client(current_children)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
        ]

        with caplog.at_level(logging.INFO, logger="notion_sync.diff"):
            _execute_reorder(client, ops, "page-1")

        assert any("Inserted reorder marker block" in m for m in caplog.messages)

    def test_marker_removal_logged(self, caplog):
        """INFO log for marker removal."""
        current_children = [
            {"id": "content-a", "type": "paragraph"},
            {"id": "cp-1", "type": "child_page"},
        ]
        client = _make_mock_client(current_children)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
        ]

        with caplog.at_level(logging.INFO, logger="notion_sync.diff"):
            _execute_reorder(client, ops, "page-1")

        assert any("Removed reorder marker block" in m for m in caplog.messages)

    def test_marker_removal_failure_logged(self, caplog):
        """WARNING log when marker removal fails."""
        current_children = [
            {"id": "content-a", "type": "paragraph"},
            {"id": "cp-1", "type": "child_page"},
        ]
        client = _make_mock_client(current_children)

        # Make delete_block fail for marker
        def _failing_delete(block_id):
            if block_id == "marker-divider-id":
                raise RuntimeError("Simulated deletion failure")
            return {"id": block_id}

        client.delete_block = MagicMock(side_effect=_failing_delete)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
        ]

        with caplog.at_level(logging.WARNING, logger="notion_sync.diff"):
            # Should not raise — marker cleanup failure is logged, not raised
            _execute_reorder(client, ops, "page-1")

        assert any("Failed to remove reorder marker" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases beyond the core acceptance criteria."""

    def test_no_nc_blocks_no_marker(self):
        """Reorder without any NC blocks should not create a marker."""
        client = _make_mock_client()

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "paragraph", notion_block_id="para-1"),
            _make_op("KEEP", "heading_1", notion_block_id="h1-1"),
        ]

        stats = _execute_reorder(client, ops, "page-1")

        # No marker created — no divider in append_blocks calls
        for c in client.append_blocks.call_args_list:
            blocks = c[1].get("blocks", [])
            for b in blocks:
                assert b.get("type") != "divider", "No marker should be created"

        assert stats["inserted"] == 1
        assert stats["kept"] == 2

    def test_multiple_nc_blocks_at_end(self):
        """Multiple NC blocks at end — marker before the first one."""
        current_children = [
            {"id": "content-a", "type": "paragraph"},
            {"id": "cp-1", "type": "child_page"},
            {"id": "cp-2", "type": "child_page"},
            {"id": "cd-1", "type": "child_database"},
        ]
        client = _make_mock_client(current_children)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
            _make_op("KEEP", "child_page", notion_block_id="cp-2"),
            _make_op("KEEP", "child_database", notion_block_id="cd-1"),
        ]

        stats = _execute_reorder(client, ops, "page-1")

        # Marker before cp-1, after content-a
        marker_call = client.append_blocks.call_args_list[0]
        assert marker_call[1]["after"] == "content-a"
        assert stats["inserted"] == 1

    def test_meeting_notes_treated_as_nc(self):
        """meeting_notes blocks should be treated as non-creatable."""
        current_children = [
            {"id": "content-a", "type": "paragraph"},
            {"id": "mn-1", "type": "meeting_notes"},
        ]
        client = _make_mock_client(current_children)

        ops = [
            _make_op("INSERT", "paragraph"),
            _make_op("KEEP", "meeting_notes", notion_block_id="mn-1"),
        ]

        _execute_reorder(client, ops, "page-1")

        # Marker should be created (meeting_notes is NC)
        marker_call = client.append_blocks.call_args_list[0]
        assert marker_call[1]["blocks"] == [{"type": "divider", "divider": {}}]

    def test_all_nc_ops_no_content_no_marker(self):
        """If all ops are NC (no content ops), no marker is needed."""
        client = _make_mock_client()

        ops = [
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
            _make_op("KEEP", "child_database", notion_block_id="cd-1"),
        ]

        _execute_reorder(client, ops, "page-1")

        client.get_blocks.assert_not_called()

    def test_content_only_after_nc_no_marker(self):
        """If content ops only appear after NC ops, no marker needed."""
        client = _make_mock_client()

        ops = [
            _make_op("KEEP", "child_page", notion_block_id="cp-1"),
            _make_op("INSERT", "paragraph"),
        ]

        stats = _execute_reorder(client, ops, "page-1")

        # No marker — content is after NC in desired order
        client.get_blocks.assert_not_called()
        assert stats["inserted"] == 1
