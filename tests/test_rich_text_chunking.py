"""Tests for rich_text chunking (Notion's 2000-char / 100-element write limits)."""

from notion_sync.rich_text import (
    RICH_TEXT_CONTENT_LIMIT,
    chunk_block_payload,
    chunk_rich_text,
)


def _text_el(content, **annotations):
    ann = {"bold": False, "italic": False, "code": False, "color": "default"}
    ann.update(annotations)
    return {
        "type": "text",
        "text": {"content": content, "link": None},
        "annotations": ann,
        "plain_text": content,
        "href": None,
    }


def test_short_element_untouched():
    rt = [_text_el("hello")]
    assert chunk_rich_text(rt) == rt


def test_exact_limit_untouched():
    rt = [_text_el("x" * RICH_TEXT_CONTENT_LIMIT)]
    out = chunk_rich_text(rt)
    assert len(out) == 1
    assert out[0]["text"]["content"] == "x" * RICH_TEXT_CONTENT_LIMIT


def test_2105_char_element_splits_into_two():
    rt = [_text_el("a" * 2105)]
    out = chunk_rich_text(rt)
    assert len(out) == 2
    assert len(out[0]["text"]["content"]) == 2000
    assert len(out[1]["text"]["content"]) == 105
    # Lossless: concatenation reproduces the original.
    assert "".join(el["text"]["content"] for el in out) == "a" * 2105


def test_annotations_link_href_preserved_on_each_chunk():
    el = _text_el("b" * 4001, bold=True)
    el["text"]["link"] = {"url": "https://example.com"}
    el["href"] = "https://example.com"
    out = chunk_rich_text([el])
    assert len(out) == 3  # 2000 + 2000 + 1
    for piece in out:
        assert piece["annotations"]["bold"] is True
        assert piece["text"]["link"] == {"url": "https://example.com"}
        assert piece["href"] == "https://example.com"
    # plain_text tracks the sliced content, not the original.
    assert out[0]["plain_text"] == "b" * 2000
    assert out[2]["plain_text"] == "b"


def test_multi_element_order_preserved():
    rt = [_text_el("start "), _text_el("m" * 2500), _text_el(" end")]
    out = chunk_rich_text(rt)
    assert [len(e["text"]["content"]) for e in out] == [6, 2000, 500, 4]
    assert "".join(e["text"]["content"] for e in out) == "start " + "m" * 2500 + " end"


def test_non_text_elements_pass_through():
    mention = {"type": "mention", "mention": {"type": "page", "page": {"id": "p1"}}}
    equation = {"type": "equation", "equation": {"expression": "x" * 3000}}
    out = chunk_rich_text([mention, equation])
    assert out == [mention, equation]  # atomic, never split


def test_100_element_cap():
    # 250 pieces of 2000 chars → 500k chars → must cap at 100.
    rt = [_text_el("z" * (2000 * 250))]
    out = chunk_rich_text(rt)
    assert len(out) == 100


def test_empty_and_none():
    assert chunk_rich_text([]) == []
    assert chunk_rich_text(None) is None


def test_chunk_block_payload_rich_text_and_caption():
    payload = {
        "code": {"rich_text": [_text_el("c" * 2500)], "language": "python"},
    }
    out = chunk_block_payload(payload)
    assert len(out["code"]["rich_text"]) == 2
    assert out["code"]["language"] == "python"

    cap = {"image": {"caption": [_text_el("d" * 2500)]}}
    out2 = chunk_block_payload(cap)
    assert len(out2["image"]["caption"]) == 2


def test_chunk_block_payload_does_not_mutate_input():
    original = {"paragraph": {"rich_text": [_text_el("e" * 3000)]}}
    chunk_block_payload(original)
    assert len(original["paragraph"]["rich_text"]) == 1  # untouched


def test_chunk_block_payload_ignores_non_rich_text():
    payload = {"table": {"table_width": 3}}
    assert chunk_block_payload(payload) == payload


def test_chunk_block_payload_table_row_cells():
    """table_row cells (list of rich_text arrays) must be chunked per cell.

    Regression: partial-cell patches re-send untouched cells read back from
    Notion verbatim — those can exceed the write limit just like rich_text.
    """
    payload = {
        "table_row": {
            "cells": [
                [_text_el("short")],
                [_text_el("f" * 2500)],
                [],  # empty cell passes through
            ]
        }
    }
    out = chunk_block_payload(payload)
    cells = out["table_row"]["cells"]
    assert len(cells) == 3  # cell COUNT unchanged (must match table width)
    assert len(cells[0]) == 1
    assert len(cells[1]) == 2  # long cell split into 2 elements
    assert all(len(el["text"]["content"]) <= 2000 for el in cells[1])
    assert cells[2] == []
