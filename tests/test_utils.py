"""Tests for notion_sync.utils module."""

from notion_sync.utils import extract_page_icon


class TestExtractPageIcon:
    """Tests for extract_page_icon function."""

    def test_no_icon_returns_none(self):
        """Page without icon returns None."""
        assert extract_page_icon({}) is None

    def test_none_icon_returns_none(self):
        """Page with explicit null icon returns None."""
        assert extract_page_icon({"icon": None}) is None

    def test_emoji_icon(self):
        """Standard emoji icon is returned as-is."""
        page = {"icon": {"type": "emoji", "emoji": "🚀"}}
        assert extract_page_icon(page) == {"type": "emoji", "emoji": "🚀"}

    def test_external_icon(self):
        """External URL icon is returned as-is."""
        page = {"icon": {"type": "external", "external": {"url": "https://example.com/icon.png"}}}
        result = extract_page_icon(page)
        assert result == {"type": "external", "external": {"url": "https://example.com/icon.png"}}

    def test_file_icon(self):
        """Notion-hosted file icon is returned as-is."""
        page = {
            "icon": {
                "type": "file",
                "file": {"url": "https://s3.aws.../icon.png", "expiry_time": "2026-01-01T00:00:00Z"},
            }
        }
        result = extract_page_icon(page)
        assert result["type"] == "file"
        assert "url" in result["file"]

    def test_custom_emoji_icon(self):
        """Custom emoji icon is returned as-is."""
        page = {
            "icon": {
                "type": "custom_emoji",
                "custom_emoji": {
                    "id": "abc123",
                    "name": "livekit",
                    "url": "https://files.notion.com/livekit.png",
                },
            }
        }
        result = extract_page_icon(page)
        assert result["type"] == "custom_emoji"
        assert result["custom_emoji"]["id"] == "abc123"

    def test_ignores_other_page_fields(self):
        """Only extracts icon, ignores other page properties."""
        page = {
            "id": "some-page-id",
            "properties": {"title": []},
            "icon": {"type": "emoji", "emoji": "✅"},
        }
        assert extract_page_icon(page) == {"type": "emoji", "emoji": "✅"}
