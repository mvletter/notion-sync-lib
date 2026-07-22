"""Unit tests for non-creatable block guards in execute_diff().

SPEC-NCBLOCK-002-M1: execute_diff must never delete a non-creatable Notion
block (child_database / child_page / meeting_notes / unsupported) via the
REPLACE branch, and must never attempt update_block on one via UPDATE.

Regression for the 2026-07-22 incident: a force-retranslate whose master was
restructured produced a REPLACE op whose *old* (notion) block was the slave's
real inline database. The old REPLACE branch only guarded the *new* (local)
block, so it recursively deleted the database — unrecoverable via the API.

NO live Notion API calls — these use mocks.
"""

from unittest.mock import MagicMock

import pytest

from notion_sync.diff import _NON_CREATABLE, execute_diff, generate_diff


# Override autouse fixtures from conftest.py that require NOTION_API_TOKEN
@pytest.fixture(autouse=True)
def sync_to_clone():
    """No-op override — these are unit tests, no live sync needed."""
    yield


@pytest.fixture
def test_pages():
    """No-op override — these are unit tests."""
    return ("fake-master", "fake-clone")


def _para(block_id: str, text: str) -> dict:
    return {
        "id": block_id,
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text},
                                     "plain_text": text}]},
    }


def _child_db(block_id: str, title: str) -> dict:
    return {
        "id": block_id,
        "type": "child_database",
        "child_database": {"title": title},
    }


def _mock_client():
    """Mock RateLimitedNotionClient recording delete/append/update calls."""
    client = MagicMock()
    counter = {"n": 0}

    def _append(page_id=None, blocks=None, after=None):
        counter["n"] += 1
        return {"results": [{"id": f"new-{counter['n']}"}]}

    client.append_blocks.side_effect = _append
    client.get_blocks.return_value = []  # no children when delete recurses
    return client


class TestReplaceGuard:
    """Scenario 1: REPLACE never deletes a non-creatable Notion block."""

    def test_replace_with_nc_old_block_is_not_deleted(self):
        # old: [paragraph A, child_database DB]
        # new: [paragraph A, paragraph B]
        # generate_diff yields KEEP(A) then REPLACE(DB -> B): old block is NC.
        old_blocks = [_para("A", "alpha"), _child_db("DB", "Help Pages NL")]
        new_blocks = [_para("A", "alpha"), _para("B", "beta")]

        ops = generate_diff(old_blocks, new_blocks)
        replace_ops = [o for o in ops if o["op"] == "REPLACE"]
        assert len(replace_ops) == 1, f"fixture must yield one REPLACE, got {[o['op'] for o in ops]}"
        assert replace_ops[0]["notion_block"]["type"] == "child_database"

        client = _mock_client()
        stats = execute_diff(client, ops, page_id="page-1")

        # The database block must never be deleted.
        deleted_ids = [c.kwargs.get("block_id") for c in client.delete_block.call_args_list]
        assert "DB" not in deleted_ids, f"database was deleted: {deleted_ids}"

        # The new paragraph content must still be inserted.
        appended_texts = [
            b["paragraph"]["rich_text"][0]["text"]["content"]
            for c in client.append_blocks.call_args_list
            for b in c.kwargs.get("blocks", [])
            if b.get("type") == "paragraph"
        ]
        assert "beta" in appended_texts

        # The preserved DB counts as kept, not replaced.
        assert stats.get("kept", 0) >= 2  # paragraph A + database


class TestUpdateGuard:
    """Scenario 2: UPDATE ops on non-creatable blocks are skipped."""

    def test_update_on_nc_block_does_not_call_update_block(self):
        # old: [child_database "X"], new: [child_database "Y"] -> UPDATE (same type)
        old_blocks = [_child_db("DB", "Old Title")]
        new_blocks = [_child_db("DB", "New Title")]

        ops = generate_diff(old_blocks, new_blocks)
        assert [o["op"] for o in ops] == ["UPDATE"]
        assert ops[0]["notion_block"]["type"] == "child_database"

        client = _mock_client()
        stats = execute_diff(client, ops, page_id="page-1")

        client.update_block.assert_not_called()
        assert client.delete_block.call_count == 0
        assert stats.get("kept", 0) == 1


class TestConstant:
    def test_nc_constant_includes_all_noncreatable_types(self):
        assert _NON_CREATABLE == frozenset(
            {"child_database", "child_page", "meeting_notes", "unsupported"}
        )
