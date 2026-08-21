"""Ordering invariant for execute_diff: the page must end up in the desired order.

SPEC-ORDER-001. A REPLACE op deletes the old block and *creates a new one* with
``append_blocks(after=last_block_id)``. There is no prepend in the Notion API,
so when a REPLACE runs before any surviving block, its replacement lands at the
END of the page — the exact limitation that makes INSERT trigger the safe
delete-and-reinsert path. ``_needs_reorder`` counted REPLACE as a position
anchor anyway, so that path was skipped and every later KEEP anchored the
remaining inserts *ahead* of the misplaced replacement, rotating the page.

Live symptom (2026-08-21): the NL slave of "Bubble: Connect your phone system
with your CRM-ERP" was rotated twice in a row — all 33 blocks present exactly
once, but the page started at what should be block 18.

The invariant these tests assert — after execute_diff, the physical block order
equals new_blocks — had no test at all, which is how a two-block rotation
shipped.

NO live Notion API calls — everything runs against an in-memory page.
"""

import itertools
import random
from unittest.mock import MagicMock

import pytest

from notion_sync.diff import _needs_reorder, execute_diff, generate_diff


# Override autouse fixtures from conftest.py that require NOTION_API_TOKEN
@pytest.fixture(autouse=True)
def sync_to_clone():
    """No-op override — these are unit tests, no live sync needed."""
    yield


@pytest.fixture
def test_pages():
    """No-op override — these are unit tests."""
    return ("fake-master", "fake-clone")


PAGE_ID = "PAGE"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _block(block_type, text, block_id=None):
    """A block in fetch_blocks_recursive shape (rich_text + _children)."""
    block = {
        "type": block_type,
        block_type: {
            "rich_text": [{
                "type": "text",
                "text": {"content": text},
                "plain_text": text,
                "annotations": {},
            }]
        },
        "_children": [],
    }
    if block_id:
        block["id"] = block_id
    return block


def _label(block):
    """'type:text' — stable identity for order assertions."""
    block_type = block.get("type")
    rich_text = (block.get(block_type) or {}).get("rich_text") or [{}]
    return f"{block_type}:{rich_text[0].get('plain_text', '')}"


class _OrderedPageClient:
    """Mock client backed by an ordered list, mimicking the ordering contract.

    Only the two behaviours the diff relies on are modelled, both documented by
    Notion: ``append_blocks(after=X)`` inserts directly after X, and
    ``after=None`` appends to the END of the parent.
    """

    def __init__(self, blocks):
        self.page = [dict(b) for b in blocks]
        self._ids = itertools.count(1)
        self.deleted = []
        self.client = MagicMock()
        self.client.get_blocks = MagicMock(side_effect=self._get_blocks)
        self.client.append_blocks = MagicMock(side_effect=self._append_blocks)
        self.client.delete_block = MagicMock(side_effect=self._delete_block)
        self.client.update_block = MagicMock(side_effect=self._update_block)

    def _get_blocks(self, block_id):
        # Only the page has children here; individual blocks have none, which
        # also stops _delete_block_recursive from recursing forever.
        return list(self.page) if block_id == PAGE_ID else []

    def _append_blocks(self, page_id=None, blocks=None, after=None, **_):
        if after is None:
            index = len(self.page)
        else:
            index = next(
                i for i, b in enumerate(self.page) if b["id"] == after
            ) + 1
        results = []
        for block in blocks or []:
            new_block = dict(block)
            new_block["id"] = f"new-{next(self._ids)}"
            self.page.insert(index, new_block)
            index += 1
            results.append({"id": new_block["id"]})
        return {"results": results}

    def _delete_block(self, block_id=None, **_):
        for i, block in enumerate(self.page):
            if block["id"] == block_id:
                self.page.pop(i)
                self.deleted.append(block_id)
                break
        return {"id": block_id}

    def _update_block(self, block_id=None, data=None, **_):
        for block in self.page:
            if block["id"] == block_id:
                block.update(data or {})
        return {"id": block_id}

    @property
    def order(self):
        return [_label(b) for b in self.page]


def _sync(old_blocks, new_blocks):
    """Run the real diff + executor against an in-memory page.

    Returns (resulting_order, ops, harness).
    """
    harness = _OrderedPageClient(old_blocks)
    ops = generate_diff(old_blocks, new_blocks)
    execute_diff(harness.client, ops, PAGE_ID)
    return harness.order, ops, harness


# ---------------------------------------------------------------------------
# A1 — the minimal rotation
# ---------------------------------------------------------------------------

class TestMinimalRotation:
    """Two blocks are enough: retype the FIRST block of a master page while a
    later block stays untouched."""

    def test_replace_before_keep_keeps_page_order(self):
        old = [_block("heading_2", "X0", "old-0"), _block("paragraph", "T0", "old-1")]
        new = [_block("callout", "H0"), _block("paragraph", "T0")]

        order, ops, _ = _sync(old, new)

        assert [op["op"] for op in ops] == ["REPLACE", "KEEP"]
        assert order == ["callout:H0", "paragraph:T0"], (
            "the replacement must stay at the top; appending it after the "
            "surviving block rotates the page"
        )


# ---------------------------------------------------------------------------
# A2 — the guard itself
# ---------------------------------------------------------------------------

class TestNeedsReorderGuard:
    def test_leading_replace_with_survivor_after_needs_reorder(self):
        """REPLACE creates a new block, so it cannot be positioned before an
        existing one — the reorder path is the only correct execution."""
        ops = [
            {"op": "REPLACE", "index": 0},
            {"op": "KEEP", "index": 1},
        ]
        assert _needs_reorder(ops) is True

    def test_leading_replace_without_survivor_stays_cheap(self):
        """Nothing anchored afterwards: appending at the end IS the desired
        position, so a full rebuild would be pure waste."""
        ops = [
            {"op": "REPLACE", "index": 0},
            {"op": "INSERT", "index": 1},
        ]
        assert _needs_reorder(ops) is False

    def test_keep_first_then_insert_stays_cheap(self):
        ops = [
            {"op": "KEEP", "index": 0},
            {"op": "INSERT", "index": 1},
        ]
        assert _needs_reorder(ops) is False


# ---------------------------------------------------------------------------
# A3 — the invariant across page shapes
# ---------------------------------------------------------------------------

TYPES = ["paragraph", "heading_2", "callout", "toggle", "bulleted_list_item"]


def _section(prefix, count, rng):
    return [_block(rng.choice(TYPES), f"{prefix}{i}") for i in range(count)]


def _scenarios(trials, seed=1234):
    """Reordered / shuffled / partially-deleted page shapes with edited content.

    Deterministic: a fixed seed keeps CI reproducible.
    """
    rng = random.Random(seed)
    for _ in range(trials):
        head = _section("H", rng.randint(1, 8), rng)
        mid = _section("M", rng.randint(0, 3), rng)
        tail = _section("T", rng.randint(1, 8), rng)
        new_blocks = head + mid + tail

        # The slave still holds the pre-restructure arrangement.
        pool = tail + mid + head
        arrangement = rng.choice(["rotated", "shuffled", "subset"])
        if arrangement == "rotated":
            old_logical = pool
        elif arrangement == "shuffled":
            old_logical = pool[:]
            rng.shuffle(old_logical)
        else:
            old_logical = [b for b in pool if rng.random() < 0.75]

        old_blocks = []
        for i, block in enumerate(old_logical):
            stored = dict(block)
            stored["id"] = f"old-{i}"
            if rng.random() < 0.35:
                # Content edited on the master since: hashes no longer match.
                block_type = stored["type"]
                stored[block_type] = {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"OLD{i}"},
                        "plain_text": f"OLD{i}",
                        "annotations": {},
                    }]
                }
            old_blocks.append(stored)

        yield arrangement, old_blocks, new_blocks


class TestOrderingInvariant:
    def test_execute_diff_preserves_desired_order(self):
        misordered = []
        for arrangement, old_blocks, new_blocks in _scenarios(trials=400):
            order, ops, _ = _sync(old_blocks, new_blocks)
            desired = [_label(b) for b in new_blocks]
            if order != desired:
                misordered.append({
                    "arrangement": arrangement,
                    "ops": [op["op"] for op in ops],
                    "desired": desired,
                    "actual": order,
                })

        assert not misordered, (
            f"{len(misordered)}/400 scenarios ended in the wrong order; "
            f"first: {misordered[0]}"
        )


# ---------------------------------------------------------------------------
# A4 — the cheap path is still used when it is safe
# ---------------------------------------------------------------------------

class TestCheapPathPreserved:
    def test_trailing_insert_does_not_rebuild_the_page(self):
        """Blocks appended at the end must not delete-and-reinsert the page:
        that would be correct but waste an API call per block and burn the
        block IDs block_translation_map tracks."""
        old = [_block("paragraph", "A", "old-0"), _block("paragraph", "B", "old-1")]
        new = [
            _block("paragraph", "A"),
            _block("paragraph", "B"),
            _block("paragraph", "C"),
        ]

        order, ops, harness = _sync(old, new)

        assert order == ["paragraph:A", "paragraph:B", "paragraph:C"]
        assert harness.deleted == [], "no block should be deleted for a pure append"
        assert [op["op"] for op in ops] == ["KEEP", "KEEP", "INSERT"]

    def test_content_only_update_keeps_block_ids(self):
        """An in-place text edit must not recreate the block."""
        old = [_block("paragraph", "old text", "old-0")]
        new = [_block("paragraph", "new text")]

        order, ops, harness = _sync(old, new)

        assert [op["op"] for op in ops] == ["UPDATE"]
        assert harness.deleted == []
        assert harness.page[0]["id"] == "old-0"
        assert order == ["paragraph:new text"]
