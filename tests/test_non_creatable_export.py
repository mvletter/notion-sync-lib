"""NON_CREATABLE_TYPES is the public name for the set of block types the diff
engine never writes to a slave (skipped on INSERT, never REPLACEd/UPDATEd).

Herald builds positional master<->slave block maps and must skip exactly this
set — a private copy drifted once (Herald lacked ``meeting_notes``) and an
``unsupported`` master block shifted every later BTM row by one (2026-10-12).
"""

import pytest

import notion_sync
from notion_sync.diff import _NON_CREATABLE


@pytest.fixture(autouse=True)
def sync_to_clone():
    """No-op override — unit test, no live sync needed."""
    yield


def test_public_alias_is_the_engine_set():
    assert notion_sync.NON_CREATABLE_TYPES is _NON_CREATABLE
    assert "NON_CREATABLE_TYPES" in notion_sync.__all__


def test_contains_every_type_the_engine_refuses_to_write():
    assert notion_sync.NON_CREATABLE_TYPES == frozenset(
        {"child_database", "child_page", "meeting_notes", "unsupported"}
    )
