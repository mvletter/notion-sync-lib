"""SPEC-LINK-002-M1: create_content_hash folds a normalized link identity.

A link-only change (add / remove / retarget) on otherwise-identical text must
change the content hash so the diff writes it — otherwise a stripped or
retargeted in-page anchor ("Naar boven." / "Go Up") is silently KEEP'd forever
(live-confirmed 2026-07-15). Semantically-equal Notion links in different string
forms (relative / absolute / query string) must hash EQUAL, or every link-bearing
block phantom-UPDATEs on every apply. Pure unit tests, no live Notion calls.
"""

import pytest

from notion_sync.diff import create_content_hash
from notion_sync.extract import extract_link_identity

# Real IDs from the incident (Webphone Issues & Questions NL slave).
PAGE = "2ee40e6d8f9781f99ff5cd264f5f0492"
BLOCK = "2ee40e6d8f9781ff96fefb4416dae0cf"
PAGE_HYPHEN = "2ee40e6d-8f97-81f9-9ff5-cd264f5f0492"
BLOCK_HYPHEN = "2ee40e6d-8f97-81ff-96fe-fb4416dae0cf"


# Override conftest autouse fixtures that require NOTION_API_TOKEN.
@pytest.fixture(autouse=True)
def sync_to_clone():
    yield


@pytest.fixture
def test_pages():
    return ("fake-master", "fake-clone")


def _para(text, url=None):
    run = {"type": "text", "text": {"content": text}, "plain_text": text}
    if url is not None:
        run["text"]["link"] = {"url": url}
    return {"type": "paragraph", "paragraph": {"rich_text": [run]}}


def _row(text, url=None):
    run = {"type": "text", "text": {"content": text}, "plain_text": text}
    if url is not None:
        run["text"]["link"] = {"url": url}
    return {"type": "table_row", "table_row": {"cells": [[run]]}}


class TestLinkAffectsHash:

    def test_adding_link_changes_hash(self):
        """A1.1 — reproduction: linkless vs linked same-text must differ."""
        assert create_content_hash(_para("Naar boven.")) != \
            create_content_hash(_para("Naar boven.", f"/p/{PAGE}#{BLOCK}"))

    def test_retarget_changes_hash(self):
        """A1.2 — different fragment target → different hash."""
        other = "38e40e6d8f97819e9e32d51a1718d4c0"
        assert create_content_hash(_para("x", f"/p/{PAGE}#{BLOCK}")) != \
            create_content_hash(_para("x", f"/p/{PAGE}#{other}"))

    def test_relative_absolute_query_forms_hash_equal(self):
        """A1.3 — same target, different string forms → SAME hash (no phantom UPDATE)."""
        h_rel = create_content_hash(_para("x", f"/p/{PAGE}#{BLOCK}"))
        h_query = create_content_hash(_para("x", f"/p/{PAGE}?pvs=25#{BLOCK}"))
        h_abs = create_content_hash(_para("x", f"https://www.notion.so/{PAGE}#{BLOCK}"))
        h_hyphen = create_content_hash(_para("x", f"/p/{PAGE_HYPHEN}#{BLOCK_HYPHEN}"))
        assert h_rel == h_query == h_abs == h_hyphen

    def test_external_url_change_detected(self):
        """A1.4 — external URL is its own identity."""
        assert create_content_hash(_para("x", "https://a.example")) != \
            create_content_hash(_para("x", "https://b.example"))

    def test_same_external_url_hash_equal(self):
        assert create_content_hash(_para("x", "https://a.example")) == \
            create_content_hash(_para("x", "https://a.example"))

    def test_linkless_hash_unchanged_by_feature(self):
        """A1.5 — flood containment: a linkless block must hash exactly as the
        pre-fix formula did. The pre-fix normalized string was
        f"{type}:{text}" with no extras, so the hash equals sha256 of that."""
        import hashlib
        expected = hashlib.sha256("paragraph:hi".encode()).hexdigest()[:16]
        assert create_content_hash(_para("hi")) == expected

    def test_link_in_table_row_cell_detected(self):
        assert create_content_hash(_row("Up")) != \
            create_content_hash(_row("Up", f"/p/{PAGE}#{BLOCK}"))


class TestExtractLinkIdentity:

    def test_empty_when_no_links(self):
        assert extract_link_identity(_para("hi")) == ""

    def test_notion_internal_normalizes_to_compact_page_block(self):
        ident = extract_link_identity(_para("x", f"/p/{PAGE_HYPHEN}?pvs=25#{BLOCK_HYPHEN}"))
        assert PAGE in ident and BLOCK in ident
        assert "-" not in ident  # compacted
        assert "pvs" not in ident  # query dropped

    def test_notion_scheme_page_sentinel(self):
        ident = extract_link_identity(_para("x", f"notion://page/{PAGE_HYPHEN}"))
        assert PAGE in ident

    def test_external_is_raw(self):
        assert extract_link_identity(_para("x", "https://a.example/path")) == "https://a.example/path"
