"""Tests for notion_sync.columns module."""

import pytest

from notion_sync.columns import (
    extract_block_ids,
    build_column_list_block,
)


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


class TestBuildColumnListBlock:
    """Tests for build_column_list_block function."""

    def test_two_columns_simple(self):
        """Basic two-column structure."""
        columns = [
            {"children": [{"type": "paragraph", "paragraph": {"rich_text": []}}]},
            {"children": [{"type": "paragraph", "paragraph": {"rich_text": []}}]},
        ]
        result = build_column_list_block(columns)

        assert result["type"] == "column_list"
        assert len(result["column_list"]["children"]) == 2
        assert result["column_list"]["children"][0]["type"] == "column"
        assert result["column_list"]["children"][1]["type"] == "column"

    def test_columns_with_width_ratio(self):
        """Width ratio is preserved in column data."""
        columns = [
            {"children": [], "width_ratio": 0.7},
            {"children": [], "width_ratio": 0.3},
        ]
        result = build_column_list_block(columns)

        assert result["column_list"]["children"][0]["column"]["width_ratio"] == 0.7
        assert result["column_list"]["children"][1]["column"]["width_ratio"] == 0.3

    def test_columns_without_width_ratio(self):
        """Columns without width_ratio don't have the key."""
        columns = [
            {"children": []},
            {"children": []},
        ]
        result = build_column_list_block(columns)

        assert "width_ratio" not in result["column_list"]["children"][0]["column"]
        assert "width_ratio" not in result["column_list"]["children"][1]["column"]

    def test_mixed_width_ratio(self):
        """Mix of columns with and without width_ratio."""
        columns = [
            {"children": [], "width_ratio": 0.5},
            {"children": []},  # No width_ratio
        ]
        result = build_column_list_block(columns)

        assert result["column_list"]["children"][0]["column"]["width_ratio"] == 0.5
        assert "width_ratio" not in result["column_list"]["children"][1]["column"]

    def test_multiple_blocks_per_column(self):
        """Multiple content blocks per column."""
        columns = [
            {
                "children": [
                    {"type": "paragraph", "paragraph": {}},
                    {"type": "heading_1", "heading_1": {}},
                ]
            },
            {
                "children": [
                    {"type": "divider", "divider": {}},
                ]
            },
        ]
        result = build_column_list_block(columns)

        col1_children = result["column_list"]["children"][0]["column"]["children"]
        col2_children = result["column_list"]["children"][1]["column"]["children"]

        assert len(col1_children) == 2
        assert len(col2_children) == 1

    def test_empty_columns(self):
        """Empty columns list returns valid structure."""
        result = build_column_list_block([])
        assert result["type"] == "column_list"
        assert result["column_list"]["children"] == []

    def test_three_columns(self):
        """Three columns work correctly."""
        columns = [
            {"children": [], "width_ratio": 0.33},
            {"children": [], "width_ratio": 0.34},
            {"children": [], "width_ratio": 0.33},
        ]
        result = build_column_list_block(columns)

        assert len(result["column_list"]["children"]) == 3
