"""SPEC-EMOJI-001-M5 (Herald): create_content_hash folds custom-emoji mention
identity.

A workspace custom-emoji mention's plain_text is its shortcode (":sa-flag:"),
so a healed block (mention + text) and a broken block (literal shortcode text)
flatten to the SAME plain text — hash-equal → the diff KEEPs the broken slave
forever: un-syncable AND un-healable (live-confirmed 2026-07-20 on "Freedom:
Het Dashboard"). Occurrence #4 of the hash-contract pitfall (color, callout
icon, links, now mention identity).

Scope: custom_emoji mentions ONLY. `_links_from_rich_text` reads only `text`
runs, so there is no overlap with the SPEC-LINK-002 link fold; blocks without
custom-emoji mentions keep their exact pre-fix hash (flood containment, same
rationale as R1.4 there). Pure unit tests, no live Notion calls.
"""

import pytest

from notion_sync.diff import create_content_hash
from notion_sync.extract import extract_mention_identity

# Real ids from the incident (Freedom: The Dashboard, :sa-flag:).
EMOJI_ID = "1af40e6d-8f97-8001-a6f4-007a017ea0f1"
OTHER_EMOJI_ID = "2bf40e6d-8f97-8001-a6f4-007a017ea0f2"


# Override conftest autouse fixtures that require NOTION_API_TOKEN.
@pytest.fixture(autouse=True)
def sync_to_clone():
    yield


@pytest.fixture
def test_pages():
    return ("fake-master", "fake-clone")


def _text_run(text):
    return {"type": "text", "text": {"content": text}, "plain_text": text}


def _emoji_run(emoji_id=EMOJI_ID, name="sa-flag"):
    return {
        "type": "mention",
        "mention": {"type": "custom_emoji",
                    "custom_emoji": {"id": emoji_id, "name": name}},
        "plain_text": f":{name}:",
    }


def _page_mention_run(page_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", title="Page"):
    return {
        "type": "mention",
        "mention": {"type": "page", "page": {"id": page_id}},
        "plain_text": title,
    }


def _quote(runs):
    return {"type": "quote", "quote": {"rich_text": runs}}


def _row(runs):
    return {"type": "table_row", "table_row": {"cells": [runs]}}


def _caption_image(runs):
    return {"type": "image",
            "image": {"type": "external", "external": {"url": "https://x/y.png"},
                      "caption": runs}}


class TestMentionAffectsHash:

    def test_mention_vs_literal_shortcode_differ(self):
        """Reproduction: healed (mention) vs broken (literal text) same plain
        text MUST hash differently, or the broken slave is KEEP'd forever."""
        healed = _quote([_emoji_run(), _text_run(" Dit is niet beschikbaar")])
        broken = _quote([_text_run(":sa-flag: Dit is niet beschikbaar")])
        assert create_content_hash(healed) != create_content_hash(broken)

    def test_different_emoji_ids_differ(self):
        a = _quote([_emoji_run(EMOJI_ID)])
        b = _quote([_emoji_run(OTHER_EMOJI_ID)])
        assert create_content_hash(a) != create_content_hash(b)

    def test_same_emoji_hashes_equal(self):
        """Convergence: master and healed slave carry the same mention → KEEP."""
        a = _quote([_emoji_run(), _text_run(" x")])
        b = _quote([_emoji_run(), _text_run(" x")])
        assert create_content_hash(a) == create_content_hash(b)

    def test_table_row_cells_covered(self):
        with_mention = _row([_emoji_run(), _text_run(" x")])
        without = _row([_text_run(":sa-flag: x")])
        assert create_content_hash(with_mention) != create_content_hash(without)

    def test_caption_covered(self):
        with_mention = _caption_image([_emoji_run()])
        without = _caption_image([_text_run(":sa-flag:")])
        assert create_content_hash(with_mention) != create_content_hash(without)


class TestFloodContainment:

    def test_plain_block_hash_unchanged(self):
        """A block without custom-emoji mentions folds nothing → its hash is
        byte-identical to the pre-fix formula (no rebaseline flood)."""
        block = _quote([_text_run("gewone tekst")])
        assert extract_mention_identity(block) == ""
        # pre-fix formula: sha256("quote:gewone tekst")[:16]
        import hashlib
        expected = hashlib.sha256(b"quote:gewone tekst").hexdigest()[:16]
        assert create_content_hash(block) == expected

    def test_page_mention_not_folded(self):
        """Page mentions are out of scope (their hash behavior must not shift)."""
        block = _quote([_page_mention_run(), _text_run(" tail")])
        assert extract_mention_identity(block) == ""

    def test_identity_string_format(self):
        block = _quote([_emoji_run(), _emoji_run(OTHER_EMOJI_ID, "other")])
        assert extract_mention_identity(block) == (
            f"custom_emoji:{EMOJI_ID}|custom_emoji:{OTHER_EMOJI_ID}"
        )
