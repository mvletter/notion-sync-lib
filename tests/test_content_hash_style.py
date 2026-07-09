"""SPEC-BLOCK-STYLE-001-M3: create_content_hash covers color + callout icon.

A master-side style-only edit (color change, callout icon swap) must change the
content hash so change detection surfaces it — otherwise the slave silently
keeps its old style forever (live-confirmed 2026-07-09). These are pure unit
tests, no live Notion calls.
"""

import pytest

from notion_sync.diff import create_content_hash


# Override the autouse fixtures from conftest.py that require NOTION_API_TOKEN —
# these are pure unit tests with no live Notion calls.
@pytest.fixture(autouse=True)
def sync_to_clone():
    yield


@pytest.fixture
def test_pages():
    return ("fake-master", "fake-clone")


def _para(text, color=None):
    data = {"rich_text": [{"type": "text", "text": {"content": text},
                           "plain_text": text}]}
    if color is not None:
        data["color"] = color
    return {"type": "paragraph", "paragraph": data}


def _callout(text, color=None, icon=None):
    data = {"rich_text": [{"type": "text", "text": {"content": text},
                           "plain_text": text}]}
    if color is not None:
        data["color"] = color
    if icon is not None:
        data["icon"] = icon
    return {"type": "callout", "callout": data}


class TestColorAffectsHash:
    """R3.1: color-bearing types fold color into the hash."""

    def test_paragraph_color_change_detected(self):
        assert create_content_hash(_para("hi", "default")) != \
            create_content_hash(_para("hi", "yellow_background"))

    def test_default_color_equals_no_color(self):
        """A 'default' color must hash identically to no color at all — keeps
        the common unstyled case on its pre-M3 hash (no phantom-diff flood)."""
        assert create_content_hash(_para("hi")) == \
            create_content_hash(_para("hi", "default"))

    def test_same_color_same_text_stable(self):
        assert create_content_hash(_para("hi", "blue")) == \
            create_content_hash(_para("hi", "blue"))

    def test_text_change_still_detected_with_color(self):
        assert create_content_hash(_para("hi", "blue")) != \
            create_content_hash(_para("bye", "blue"))

    def test_toggle_color(self):
        base = {"type": "toggle", "toggle": {"rich_text": [], "color": "default"}}
        red = {"type": "toggle", "toggle": {"rich_text": [], "color": "red"}}
        assert create_content_hash(base) != create_content_hash(red)

    def test_to_do_color_independent_of_checked(self):
        """to_do folds BOTH checked (pre-existing) and color (M3)."""
        a = {"type": "to_do", "to_do": {"rich_text": [], "checked": True, "color": "default"}}
        b = {"type": "to_do", "to_do": {"rich_text": [], "checked": True, "color": "green"}}
        assert create_content_hash(a) != create_content_hash(b)


class TestCalloutIconAffectsHash:
    """R3.2: callout icon folds into the hash, stable representation only."""

    def test_emoji_icon_swap_detected(self):
        assert create_content_hash(_callout("n", icon={"type": "emoji", "emoji": "🔥"})) != \
            create_content_hash(_callout("n", icon={"type": "emoji", "emoji": "🚀"}))

    def test_callout_color_swap_detected(self):
        icon = {"type": "emoji", "emoji": "🔥"}
        assert create_content_hash(_callout("n", color="default", icon=icon)) != \
            create_content_hash(_callout("n", color="blue_background", icon=icon))

    def test_add_icon_detected(self):
        assert create_content_hash(_callout("n")) != \
            create_content_hash(_callout("n", icon={"type": "emoji", "emoji": "🔥"}))

    def test_same_icon_and_color_stable(self):
        icon = {"type": "emoji", "emoji": "🔥"}
        assert create_content_hash(_callout("n", "blue_background", icon)) == \
            create_content_hash(_callout("n", "blue_background", dict(icon)))

    def test_custom_emoji_id_hashed_not_url(self):
        """custom_emoji uses id; a changed url (re-fetch) does not change the hash."""
        a = _callout("n", icon={"type": "custom_emoji",
                                "custom_emoji": {"id": "ce-1", "url": "https://x/1"}})
        b = _callout("n", icon={"type": "custom_emoji",
                                "custom_emoji": {"id": "ce-1", "url": "https://x/2-DIFFERENT"}})
        assert create_content_hash(a) == create_content_hash(b)

    def test_file_icon_url_expiry_not_volatile(self):
        """R3.2: a 'file'-type icon's expiring S3 URL must NOT feed the hash —
        two re-fetches of the SAME icon (different signed URL) hash identically."""
        a = _callout("n", icon={"type": "file",
                                "file": {"url": "https://s3/x?sig=AAA", "expiry_time": "t1"}})
        b = _callout("n", icon={"type": "file",
                                "file": {"url": "https://s3/x?sig=BBB", "expiry_time": "t2"}})
        assert create_content_hash(a) == create_content_hash(b)

    def test_icon_type_change_detected(self):
        """A file->emoji swap IS detected (via icon_type), even though the
        file url itself is not hashed."""
        a = _callout("n", icon={"type": "file", "file": {"url": "https://s3/x?sig=AAA"}})
        b = _callout("n", icon={"type": "emoji", "emoji": "🔥"})
        assert create_content_hash(a) != create_content_hash(b)


class TestNoFalsePositives:
    """Scenario 5: no change → identical hash (no phantom diffs)."""

    def test_unstyled_paragraph_stable(self):
        assert create_content_hash(_para("hello")) == create_content_hash(_para("hello"))

    def test_plain_callout_stable(self):
        assert create_content_hash(_callout("note")) == create_content_hash(_callout("note"))
