"""Tests for notion_sync.columns module.

Note: Tests for create_column_list are in test_live_columns.py as integration tests.
The _build_column_list_block helper is tested indirectly through those tests.
"""

import pytest

from notion_sync.columns import extract_block_ids


class TestExtractBlockIds:
    """Tests for extract_block_ids function."""

    def test_empty_blocks(self):
        """Empty list returns empty dict."""
        result = extract_block_ids([])
        assert result == {}

    def test_single_block(self):
        """Single block returns its ID at path '0'."""
        blocks = [{"id": "abc123", "type": "paragraph"}]
        result = extract_block_ids(blocks)
        assert result == {"0": "abc123"}

    def test_multiple_blocks(self):
        """Multiple blocks are numbered sequentially."""
        blocks = [
            {"id": "aaa", "type": "paragraph"},
            {"id": "bbb", "type": "heading_1"},
            {"id": "ccc", "type": "divider"},
        ]
        result = extract_block_ids(blocks)
        assert result == {"0": "aaa", "1": "bbb", "2": "ccc"}

    def test_nested_children(self):
        """Children are extracted with .children. path separator."""
        blocks = [
            {
                "id": "parent",
                "type": "column",
                "_children": [
                    {"id": "child1", "type": "paragraph"},
                    {"id": "child2", "type": "paragraph"},
                ],
            }
        ]
        result = extract_block_ids(blocks)
        assert result == {
            "0": "parent",
            "0.children.0": "child1",
            "0.children.1": "child2",
        }

    def test_column_list_structure(self):
        """Full column_list structure extracts all IDs correctly."""
        blocks = [
            {
                "id": "col1",
                "type": "column",
                "_children": [
                    {"id": "content1", "type": "paragraph"},
                ],
            },
            {
                "id": "col2",
                "type": "column",
                "_children": [
                    {"id": "content2a", "type": "paragraph"},
                    {"id": "content2b", "type": "heading_1"},
                ],
            },
        ]
        result = extract_block_ids(blocks)
        assert result == {
            "0": "col1",
            "0.children.0": "content1",
            "1": "col2",
            "1.children.0": "content2a",
            "1.children.1": "content2b",
        }

    def test_deeply_nested(self):
        """Deeply nested children are handled correctly."""
        blocks = [
            {
                "id": "toggle",
                "type": "toggle",
                "_children": [
                    {
                        "id": "nested",
                        "type": "bulleted_list_item",
                        "_children": [
                            {"id": "deep", "type": "paragraph"},
                        ],
                    }
                ],
            }
        ]
        result = extract_block_ids(blocks)
        assert result == {
            "0": "toggle",
            "0.children.0": "nested",
            "0.children.0.children.0": "deep",
        }

    def test_missing_id(self):
        """Blocks without ID are skipped."""
        blocks = [
            {"type": "paragraph"},  # No ID
            {"id": "has_id", "type": "heading_1"},
        ]
        result = extract_block_ids(blocks)
        # Block without ID is not in result, but path indices are preserved
        assert "1" in result
        assert result["1"] == "has_id"

    def test_with_prefix(self):
        """Prefix is applied to all paths."""
        blocks = [{"id": "aaa", "type": "paragraph"}]
        result = extract_block_ids(blocks, prefix="5.children.")
        assert result == {"5.children.0": "aaa"}
