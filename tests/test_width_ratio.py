"""Tests for width_ratio support in extract_block_text and create_content_hash."""

import pytest

from notion_sync.extract import extract_block_text
from notion_sync.diff import create_content_hash


class TestExtractBlockTextWidthRatio:
    """Tests for width_ratio in extract_block_text."""

    def test_column_without_width_ratio(self):
        """Column without width_ratio returns just 'column'."""
        block = {"type": "column", "column": {}}
        result = extract_block_text(block)
        assert result == "column"

    def test_column_with_width_ratio(self):
        """Column with width_ratio includes it in output."""
        block = {"type": "column", "column": {"width_ratio": 0.7}}
        result = extract_block_text(block)
        assert result == "column:0.7"

    def test_column_with_zero_width_ratio(self):
        """Column with width_ratio=0 is still included."""
        block = {"type": "column", "column": {"width_ratio": 0}}
        result = extract_block_text(block)
        # 0 is falsy but not None, so should be included
        assert result == "column:0"

    def test_column_with_none_width_ratio(self):
        """Column with width_ratio=None returns just 'column'."""
        block = {"type": "column", "column": {"width_ratio": None}}
        result = extract_block_text(block)
        assert result == "column"


class TestCreateContentHashWidthRatio:
    """Tests for width_ratio in create_content_hash."""

    def test_column_hash_differs_by_width_ratio(self):
        """Columns with different width_ratio have different hashes."""
        block1 = {"type": "column", "column": {"width_ratio": 0.7}}
        block2 = {"type": "column", "column": {"width_ratio": 0.3}}
        block3 = {"type": "column", "column": {}}

        hash1 = create_content_hash(block1)
        hash2 = create_content_hash(block2)
        hash3 = create_content_hash(block3)

        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3

    def test_same_width_ratio_same_hash(self):
        """Columns with same width_ratio have same hash."""
        block1 = {"type": "column", "column": {"width_ratio": 0.5}}
        block2 = {"type": "column", "column": {"width_ratio": 0.5}}

        assert create_content_hash(block1) == create_content_hash(block2)

    def test_columns_without_width_ratio_same_hash(self):
        """Columns without width_ratio have same hash."""
        block1 = {"type": "column", "column": {}}
        block2 = {"type": "column", "column": {}}

        assert create_content_hash(block1) == create_content_hash(block2)

    def test_column_list_hash_unchanged(self):
        """column_list blocks don't include width_ratio (it's on column)."""
        block1 = {"type": "column_list", "column_list": {}}
        block2 = {"type": "column_list", "column_list": {"children": []}}

        # Both should have the same hash based on type and empty content
        hash1 = create_content_hash(block1)
        hash2 = create_content_hash(block2)
        assert hash1 == hash2
