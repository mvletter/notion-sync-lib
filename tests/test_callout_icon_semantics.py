"""SPEC-ICON-001: callout icons — safe write semantics + hash equivalence class.

M0 probe (2026-07-16, live): Notion rejects `file_upload` icons on callout
blocks with HTTP 400 on BOTH blocks.children.append AND blocks.update
("File upload icons are not supported for this block type"). Therefore:

- No write path may ever emit a `file_upload` callout icon, nor an `external`
  icon pointing at a signed/expiring Notion file URL (written-but-invisible).
- A master's uploaded (`file`-type) icon, a slave's legacy uploaded icon, and
  the deterministic fallback emoji form one equivalence class for hashing, so
  tree-sync KEEPs converged callouts instead of phantom-updating forever.
- On UPDATE, the old (slave) icon decides: renderable → omit (preserve);
  missing/broken → write the fallback emoji (heals).

Pure unit tests, no live Notion calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from notion_sync.diff import (
    CALLOUT_ICON_FALLBACK_EMOJI,
    _prepare_block_for_api,
    _prepare_callout_icon_for_update,
    create_content_hash,
    execute_diff,
    resolve_callout_icon_for_write,
)
from notion_sync.utils import is_signed_file_url


# Override the autouse fixtures from conftest.py that require NOTION_API_TOKEN —
# these are pure unit tests with no live Notion calls.
@pytest.fixture(autouse=True)
def sync_to_clone():
    yield


@pytest.fixture
def test_pages():
    return ("fake-master", "fake-clone")


SIGNED_URL = (
    "https://prod-files-secure.s3.us-west-2.amazonaws.com/a/b/exclamation.svg"
    "?X-Amz-Signature=abc"
)
PUBLIC_URL = "https://www.notion.so/icons/exclamation-mark_gray.svg"

FILE_ICON = {"type": "file", "file": {"url": SIGNED_URL, "expiry_time": "2026-07-16T10:00:00Z"}}
FILE_UPLOAD_ICON = {"type": "file_upload", "file_upload": {"id": "up-123"}}
SIGNED_EXTERNAL_ICON = {"type": "external", "external": {"url": SIGNED_URL}}
PUBLIC_EXTERNAL_ICON = {"type": "external", "external": {"url": PUBLIC_URL}}
EMOJI_ICON = {"type": "emoji", "emoji": "🔥"}
FALLBACK_ICON = {"type": "emoji", "emoji": CALLOUT_ICON_FALLBACK_EMOJI}
CUSTOM_EMOJI_ICON = {"type": "custom_emoji", "custom_emoji": {"id": "ce-1"}}


def _callout(text="Belangrijk!", icon=None):
    data = {
        "rich_text": [
            {"type": "text", "text": {"content": text}, "plain_text": text}
        ]
    }
    if icon is not None:
        data["icon"] = icon
    return {"type": "callout", "callout": data}


def _assert_no_forbidden_icon(payload):
    """No dict anywhere in the payload may be a file_upload callout icon or a
    signed-URL external icon."""
    import json

    text = json.dumps(payload)
    assert "amazonaws" not in text, f"signed S3 URL leaked into payload: {text[:200]}"

    def walk(obj):
        if isinstance(obj, dict):
            icon = obj.get("icon")
            if isinstance(icon, dict):
                assert icon.get("type") != "file_upload", f"file_upload icon leaked: {icon}"
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(payload)


# ---------------------------------------------------------------------------
# is_signed_file_url
# ---------------------------------------------------------------------------


class TestIsSignedFileUrl:
    def test_signed_s3_url(self):
        assert is_signed_file_url(SIGNED_URL)

    def test_notion_static(self):
        assert is_signed_file_url("https://s3.us-west-2.amazonaws.com/secure.notion-static.com/x.png")

    def test_public_notion_builtin(self):
        assert not is_signed_file_url(PUBLIC_URL)

    def test_arbitrary_public_url(self):
        assert not is_signed_file_url("https://example.com/icon.png")

    def test_empty_and_none(self):
        assert not is_signed_file_url("")
        assert not is_signed_file_url(None)


# ---------------------------------------------------------------------------
# Hash equivalence class (R3.2 convergence + R3.3 stability)
# ---------------------------------------------------------------------------


class TestHashEquivalenceClass:
    """file / file_upload / fallback-emoji hash as one class: `file:None`."""

    def test_raw_master_file_icon_hash_unchanged(self):
        """R3.3 regression pin: the hash of a raw master block with a
        file-type icon must be byte-identical to the pre-SPEC-ICON-001 value
        (computed on lib main 200fc27 / v1.2.13) — no rebaseline flood."""
        assert create_content_hash(_callout(icon=FILE_ICON)) == "bded2c352168b286"

    def test_fallback_emoji_equals_file(self):
        """Slave ⚠️ (fixed create path) KEEPs against master file icon."""
        assert create_content_hash(_callout(icon=FALLBACK_ICON)) == \
            create_content_hash(_callout(icon=FILE_ICON))

    def test_file_upload_equals_file(self):
        """Slave file_upload (BLOCK-STYLE-era writes) KEEPs against master file."""
        assert create_content_hash(_callout(icon=FILE_UPLOAD_ICON)) == \
            create_content_hash(_callout(icon=FILE_ICON))

    def test_legacy_slave_file_equals_master_file(self):
        assert create_content_hash(_callout(icon=FILE_ICON)) == \
            create_content_hash(_callout(icon=dict(FILE_ICON)))

    def test_broken_signed_external_differs(self):
        """The broken written-but-invisible state must NOT converge — it has
        to keep triggering an UPDATE until healed."""
        assert create_content_hash(_callout(icon=SIGNED_EXTERNAL_ICON)) != \
            create_content_hash(_callout(icon=FILE_ICON))

    def test_public_external_differs_from_file(self):
        assert create_content_hash(_callout(icon=PUBLIC_EXTERNAL_ICON)) != \
            create_content_hash(_callout(icon=FILE_ICON))

    def test_regular_emoji_differs_from_file(self):
        """Only the designated fallback emoji joins the class — a genuine 🔥
        icon still hashes as itself (icon swaps stay detectable)."""
        assert create_content_hash(_callout(icon=EMOJI_ICON)) != \
            create_content_hash(_callout(icon=FILE_ICON))

    def test_regular_emoji_hash_unchanged(self):
        """Non-fallback emoji hashing is untouched by the canonicalization."""
        assert create_content_hash(_callout(icon=EMOJI_ICON)) == \
            create_content_hash(_callout(icon={"type": "emoji", "emoji": "🔥"}))

    def test_no_icon_differs_from_file(self):
        """Master has an icon, slave has none → must stay detectable."""
        assert create_content_hash(_callout()) != \
            create_content_hash(_callout(icon=FILE_ICON))


# ---------------------------------------------------------------------------
# resolve_callout_icon_for_write (the one decision function)
# ---------------------------------------------------------------------------


class TestResolveCalloutIconForWrite:
    @pytest.mark.parametrize(
        "icon",
        [EMOJI_ICON, FALLBACK_ICON, PUBLIC_EXTERNAL_ICON, CUSTOM_EMOJI_ICON],
        ids=["emoji", "fallback-emoji", "public-external", "custom-emoji"],
    )
    def test_write_safe_icons_pass_through_unchanged(self, icon):
        result = resolve_callout_icon_for_write(dict(icon))
        assert result == icon

    @pytest.mark.parametrize(
        "new_icon",
        [FILE_ICON, FILE_UPLOAD_ICON, SIGNED_EXTERNAL_ICON],
        ids=["file", "file_upload", "signed-external"],
    )
    @pytest.mark.parametrize(
        "old_icon",
        [EMOJI_ICON, CUSTOM_EMOJI_ICON, FILE_ICON, FILE_UPLOAD_ICON, PUBLIC_EXTERNAL_ICON],
        ids=["old-emoji", "old-custom-emoji", "old-file", "old-file-upload", "old-public-external"],
    )
    def test_unrepresentable_with_renderable_old_omits(self, new_icon, old_icon):
        """Renderable slave icon → omit from payload (preserve; protects
        legacy uploaded icons and manual fixes even when text changed)."""
        assert resolve_callout_icon_for_write(dict(new_icon), old_icon=dict(old_icon)) is None

    @pytest.mark.parametrize(
        "new_icon",
        [FILE_ICON, FILE_UPLOAD_ICON, SIGNED_EXTERNAL_ICON],
        ids=["file", "file_upload", "signed-external"],
    )
    @pytest.mark.parametrize(
        "old_icon",
        [None, SIGNED_EXTERNAL_ICON, {}, {"type": "external", "external": {}}],
        ids=["old-none", "old-signed-external", "old-empty", "old-external-no-url"],
    )
    def test_unrepresentable_with_broken_old_falls_back(self, new_icon, old_icon):
        """Missing/broken slave icon → deterministic fallback emoji (heals)."""
        result = resolve_callout_icon_for_write(
            dict(new_icon), old_icon=dict(old_icon) if old_icon else old_icon
        )
        assert result == FALLBACK_ICON

    def test_create_default_is_fallback(self):
        """No old_icon argument (create/INSERT context) → fallback emoji."""
        assert resolve_callout_icon_for_write(dict(FILE_ICON)) == FALLBACK_ICON

    def test_never_calls_upload(self):
        with patch("notion_sync.utils.prepare_icon_for_api") as mock_prep:
            resolve_callout_icon_for_write(dict(FILE_ICON))
            resolve_callout_icon_for_write(dict(FILE_ICON), old_icon=dict(EMOJI_ICON))
        mock_prep.assert_not_called()

    @pytest.mark.parametrize(
        "icon",
        [
            FILE_ICON, FILE_UPLOAD_ICON, SIGNED_EXTERNAL_ICON, PUBLIC_EXTERNAL_ICON,
            EMOJI_ICON, CUSTOM_EMOJI_ICON, None, {}, {"type": "file", "file": {}},
        ],
        ids=[
            "file", "file_upload", "signed-external", "public-external",
            "emoji", "custom-emoji", "none", "empty", "file-no-url",
        ],
    )
    @pytest.mark.parametrize("old_icon", [None, EMOJI_ICON, SIGNED_EXTERNAL_ICON],
                             ids=["old-none", "old-emoji", "old-signed"])
    def test_output_never_forbidden(self, icon, old_icon):
        """A2.2 structural ban: no input class ever yields a file_upload icon
        or a signed-URL external icon."""
        result = resolve_callout_icon_for_write(
            dict(icon) if icon else icon,
            old_icon=dict(old_icon) if old_icon else old_icon,
        )
        if result is not None:
            _assert_no_forbidden_icon({"icon": result})


# ---------------------------------------------------------------------------
# _prepare_callout_icon_for_update (old-aware payload)
# ---------------------------------------------------------------------------


class TestPrepareCalloutIconForUpdateOldAware:
    def test_write_safe_icon_passthrough_same_object(self):
        content = {"rich_text": [], "icon": dict(EMOJI_ICON)}
        result = _prepare_callout_icon_for_update(content, old_icon=dict(EMOJI_ICON))
        assert result is content

    def test_file_icon_old_renderable_omitted(self):
        content = {"rich_text": [], "icon": dict(FILE_ICON)}
        result = _prepare_callout_icon_for_update(content, old_icon=dict(FILE_ICON))
        assert "icon" not in result
        assert content["icon"] == FILE_ICON  # input not mutated

    def test_file_icon_old_broken_gets_fallback(self):
        content = {"rich_text": [], "icon": dict(FILE_ICON)}
        result = _prepare_callout_icon_for_update(
            content, old_icon=dict(SIGNED_EXTERNAL_ICON)
        )
        assert result["icon"] == FALLBACK_ICON

    def test_file_icon_old_missing_gets_fallback(self):
        content = {"rich_text": [], "icon": dict(FILE_ICON)}
        result = _prepare_callout_icon_for_update(content, old_icon=None)
        assert result["icon"] == FALLBACK_ICON

    def test_no_upload_ever(self):
        content = {"rich_text": [], "icon": dict(FILE_ICON)}
        with patch("notion_sync.utils.prepare_icon_for_api") as mock_prep:
            _prepare_callout_icon_for_update(content, old_icon=None)
            _prepare_callout_icon_for_update(content, old_icon=dict(EMOJI_ICON))
        mock_prep.assert_not_called()


# ---------------------------------------------------------------------------
# Native built-in icon type ("icon") — SPEC-ICON-001 addendum (2026-07-16)
# ---------------------------------------------------------------------------

NATIVE_ICON = {"type": "icon", "icon": {"name": "exclamation-mark", "color": "blue"}}


class TestNativeIconType:
    """Notion serves Icons-tab picks as {"type": "icon", "icon": {name, color}}
    and accepts them on callout writes (API docs + the M0 400 message). Live
    incident 2026-07-16 09:15: a master callout switched to a built-in blue
    exclamation mark was omitted by the sync (unknown type) — the slave kept
    the ⚠️ fallback instead of gaining the native icon."""

    def test_resolve_passes_native_icon_through(self):
        assert resolve_callout_icon_for_write(dict(NATIVE_ICON)) == NATIVE_ICON

    def test_resolve_strips_extra_read_fields(self):
        decorated = {
            "type": "icon",
            "icon": {"name": "exclamation-mark", "color": "blue", "url": "https://x/y.svg"},
        }
        assert resolve_callout_icon_for_write(decorated) == NATIVE_ICON

    def test_resolve_native_icon_without_name_omitted(self):
        assert resolve_callout_icon_for_write({"type": "icon", "icon": {}}) is None

    def test_native_icon_color_defaults_hash_gray(self):
        no_color = {"type": "icon", "icon": {"name": "exclamation-mark"}}
        gray = {"type": "icon", "icon": {"name": "exclamation-mark", "color": "gray"}}
        assert create_content_hash(_callout(icon=no_color)) == \
            create_content_hash(_callout(icon=gray))

    def test_native_icon_hash_detects_name_and_color_changes(self):
        blue = _callout(icon={"type": "icon", "icon": {"name": "exclamation-mark", "color": "blue"}})
        red = _callout(icon={"type": "icon", "icon": {"name": "exclamation-mark", "color": "red"}})
        pizza = _callout(icon={"type": "icon", "icon": {"name": "pizza", "color": "blue"}})
        assert create_content_hash(blue) != create_content_hash(red)
        assert create_content_hash(blue) != create_content_hash(pizza)

    def test_native_icon_differs_from_file_class(self):
        """Master switches uploaded icon → native icon: must be detected as a
        change against a slave still carrying file/⚠️ (UPDATE, not KEEP)."""
        assert create_content_hash(_callout(icon=dict(NATIVE_ICON))) != \
            create_content_hash(_callout(icon=FILE_ICON))
        assert create_content_hash(_callout(icon=dict(NATIVE_ICON))) != \
            create_content_hash(_callout(icon=FALLBACK_ICON))

    def test_native_icon_converges_with_itself(self):
        """After the write propagates, the slave reads back the same native
        icon → hashes equal → KEEP (no phantom updates)."""
        assert create_content_hash(_callout(icon=dict(NATIVE_ICON))) == \
            create_content_hash(_callout(icon=dict(NATIVE_ICON)))

    def test_update_payload_carries_native_icon(self):
        """UPDATE against a slave with the ⚠️ fallback: the native icon must
        be WRITTEN (upgrade), not omitted."""
        client = _make_client()
        execute_diff(client, [_update_op(dict(NATIVE_ICON), dict(FALLBACK_ICON))], page_id="p1")
        data = client.update_block.call_args.kwargs["data"]
        assert data["callout"]["icon"] == NATIVE_ICON

    def test_native_icon_renderable_as_old_icon(self):
        """A slave already carrying a native icon counts as renderable: a
        master file-type icon must omit (preserve), not stomp it with ⚠️."""
        content = {"rich_text": [], "icon": dict(FILE_ICON)}
        result = _prepare_callout_icon_for_update(content, old_icon=dict(NATIVE_ICON))
        assert "icon" not in result

    def test_prepare_icon_for_api_supports_native_icon(self):
        from notion_sync.utils import prepare_icon_for_api

        decorated = {
            "type": "icon",
            "icon": {"name": "exclamation-mark", "color": "blue", "url": "https://x/y.svg"},
        }
        assert prepare_icon_for_api(decorated) == NATIVE_ICON

    def test_insert_path_carries_native_icon(self):
        block = _callout(icon=dict(NATIVE_ICON))
        prepared = _prepare_block_for_api(block, notion_token="tok")
        assert prepared["callout"]["icon"] == NATIVE_ICON


# ---------------------------------------------------------------------------
# execute_diff UPDATE ops end-to-end payload checks
# ---------------------------------------------------------------------------


def _make_client():
    client = MagicMock()
    client.append_blocks.return_value = {"results": [{"id": "new-block-1"}]}
    return client


def _update_op(new_icon, old_icon):
    old_callout = {"rich_text": []}
    if old_icon is not None:
        old_callout["icon"] = old_icon
    new_callout = {
        "rich_text": [{"type": "text", "text": {"content": "hi"}, "plain_text": "hi"}]
    }
    if new_icon is not None:
        new_callout["icon"] = new_icon
    return {
        "op": "UPDATE",
        "index": 0,
        "notion_block_id": "slave-block-1",
        "notion_block": {"type": "callout", "id": "slave-block-1", "callout": old_callout},
        "local_block": {"type": "callout", "callout": new_callout},
    }


class TestExecuteDiffCalloutIconPayloads:
    def test_update_preserves_renderable_slave_icon(self):
        client = _make_client()
        execute_diff(client, [_update_op(dict(FILE_ICON), dict(EMOJI_ICON))], page_id="p1")
        data = client.update_block.call_args.kwargs["data"]
        assert "icon" not in data["callout"]
        _assert_no_forbidden_icon(data)

    def test_update_heals_broken_slave_icon(self):
        client = _make_client()
        execute_diff(
            client, [_update_op(dict(FILE_ICON), dict(SIGNED_EXTERNAL_ICON))], page_id="p1"
        )
        data = client.update_block.call_args.kwargs["data"]
        assert data["callout"]["icon"] == FALLBACK_ICON

    def test_update_heals_missing_slave_icon(self):
        client = _make_client()
        execute_diff(client, [_update_op(dict(FILE_ICON), None)], page_id="p1")
        data = client.update_block.call_args.kwargs["data"]
        assert data["callout"]["icon"] == FALLBACK_ICON

    def test_update_passes_emoji_through(self):
        client = _make_client()
        execute_diff(client, [_update_op(dict(EMOJI_ICON), dict(FILE_ICON))], page_id="p1")
        data = client.update_block.call_args.kwargs["data"]
        assert data["callout"]["icon"] == EMOJI_ICON


# ---------------------------------------------------------------------------
# INSERT path (_prepare_block_for_api)
# ---------------------------------------------------------------------------


class TestPrepareBlockForApiCalloutIcon:
    @pytest.mark.parametrize(
        "icon",
        [FILE_ICON, FILE_UPLOAD_ICON, SIGNED_EXTERNAL_ICON],
        ids=["file", "file_upload", "signed-external"],
    )
    def test_unrepresentable_icon_becomes_fallback(self, icon):
        block = _callout(icon=dict(icon))
        with patch("notion_sync.utils.prepare_icon_for_api") as mock_prep:
            prepared = _prepare_block_for_api(block, notion_token="tok")
        mock_prep.assert_not_called()
        assert prepared["callout"]["icon"] == FALLBACK_ICON
        _assert_no_forbidden_icon(prepared)

    @pytest.mark.parametrize(
        "icon",
        [EMOJI_ICON, PUBLIC_EXTERNAL_ICON, CUSTOM_EMOJI_ICON],
        ids=["emoji", "public-external", "custom-emoji"],
    )
    def test_write_safe_icon_untouched(self, icon):
        block = _callout(icon=dict(icon))
        prepared = _prepare_block_for_api(block, notion_token="tok")
        assert prepared["callout"]["icon"] == icon
