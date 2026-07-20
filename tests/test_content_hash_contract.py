"""The create_content_hash content contract, enumerated in one place.

`create_content_hash` gates BOTH diff paths (generate_diff / generate_recursive_diff)
and Herald's change detection. Any content dimension NOT folded into it is silently
un-syncable AND un-healable — this exact bug has been found three times (color,
callout icon, rich_text links). See herald docs/patterns/notion.md#notion-content-hash-contract.

This file is the canonical checklist: every content-bearing dimension gets a case that
asserts (a) changing only that dimension changes the hash, and where relevant (b) the
default/absent value folds to nothing (flood containment). When you add a new content
dimension to the hash, ADD A CASE HERE — that is the ritual that stops recurrence #4.

Pure unit tests, no live Notion calls.
"""

import pytest

from notion_sync.diff import create_content_hash

PAGE = "2ee40e6d8f9781f99ff5cd264f5f0492"
BLOCK_A = "2ee40e6d8f9781ff96fefb4416dae0cf"
BLOCK_B = "38e40e6d8f97819e9e32d51a1718d4c0"


# Override conftest autouse fixtures that require NOTION_API_TOKEN.
@pytest.fixture(autouse=True)
def sync_to_clone():
    yield


@pytest.fixture
def test_pages():
    return ("fake-master", "fake-clone")


def _text_run(content, url=None):
    run = {"type": "text", "text": {"content": content}, "plain_text": content}
    if url is not None:
        run["text"]["link"] = {"url": url}
    return run


def _para(text, color=None, url=None):
    data = {"rich_text": [_text_run(text, url)]}
    if color is not None:
        data["color"] = color
    return {"type": "paragraph", "paragraph": data}


# (name, block_a, block_b) — the two blocks differ ONLY in the named dimension,
# and the hash MUST differ. One row per content-bearing dimension.
DIMENSION_CASES = [
    ("type",          _para("same"),                       {"type": "quote", "quote": {"rich_text": [_text_run("same")]}}),
    ("text",          _para("alpha"),                       _para("beta")),
    ("color",         _para("x", color="default"),          _para("x", color="yellow_background")),
    ("link_presence", _para("x"),                            _para("x", url=f"/p/{PAGE}#{BLOCK_A}")),
    ("link_target",   _para("x", url=f"/p/{PAGE}#{BLOCK_A}"), _para("x", url=f"/p/{PAGE}#{BLOCK_B}")),
    ("todo_checked",
        {"type": "to_do", "to_do": {"rich_text": [_text_run("x")], "checked": False}},
        {"type": "to_do", "to_do": {"rich_text": [_text_run("x")], "checked": True}}),
    ("code_language",
        {"type": "code", "code": {"rich_text": [_text_run("x")], "language": "python"}},
        {"type": "code", "code": {"rich_text": [_text_run("x")], "language": "javascript"}}),
    ("column_width_ratio",
        {"type": "column", "column": {"width_ratio": 0.5}},
        {"type": "column", "column": {"width_ratio": 0.7}}),
    ("callout_icon",
        {"type": "callout", "callout": {"rich_text": [_text_run("x")], "icon": {"type": "emoji", "emoji": "⬆️"}}},
        {"type": "callout", "callout": {"rich_text": [_text_run("x")], "icon": {"type": "emoji", "emoji": "🔽"}}}),
    ("heading_toggleable",
        {"type": "heading_2", "heading_2": {"rich_text": [_text_run("x")], "is_toggleable": False}},
        {"type": "heading_2", "heading_2": {"rich_text": [_text_run("x")], "is_toggleable": True}}),
]


@pytest.mark.parametrize("name,block_a,block_b", DIMENSION_CASES, ids=[c[0] for c in DIMENSION_CASES])
def test_dimension_roundtrips_through_hash(name, block_a, block_b):
    """Changing only `name` must change the content hash (else it is un-syncable)."""
    assert create_content_hash(block_a) != create_content_hash(block_b), (
        f"dimension '{name}' is not folded into create_content_hash — "
        f"a {name}-only change would be silently un-syncable and un-healable"
    )


# Flood containment: default / absent values must fold to nothing so unchanged
# blocks keep their prior hash (no rebaseline flood).
FLOOD_INVARIANTS = [
    ("default_color_equals_none",  _para("x", color="default"), _para("x")),
    ("no_link_stable",             _para("x"),                  _para("x")),
    ("internal_link_form_canonical",
        _para("x", url=f"/p/{PAGE}#{BLOCK_A}"),
        _para("x", url=f"https://www.notion.so/{PAGE}#{BLOCK_A}")),
    ("heading_not_toggleable_equals_absent",
        {"type": "heading_2", "heading_2": {"rich_text": [_text_run("x")], "is_toggleable": False}},
        {"type": "heading_2", "heading_2": {"rich_text": [_text_run("x")]}}),
]


@pytest.mark.parametrize("name,block_a,block_b", FLOOD_INVARIANTS, ids=[c[0] for c in FLOOD_INVARIANTS])
def test_flood_containment_invariant(name, block_a, block_b):
    """Default/absent/canonically-equal values must hash IDENTICALLY."""
    assert create_content_hash(block_a) == create_content_hash(block_b), (
        f"invariant '{name}' broken — this would cause a rebaseline flood or phantom diffs"
    )
