"""create_content_hash folds inline-code identity (Herald, 2026-11-24).

Inline code is an annotation, so a block with `call_id` in code and the same
block with **call_id** in bold flatten to the same plain text. They hashed
equal and the diff KEEPs the slave forever. Live: Herald's "Call notifications"
NL slave kept every payload field name in bold over three force-retranslates
whenever the translated words did not change; lines whose words changed came
through as code. Occurrence #6 of the hash-contract pitfall.

Scope: the `code` annotation only. Blocks without inline code keep their exact
pre-fix hash (flood containment). Pure unit tests, no live Notion calls.
"""

import pytest

from notion_sync.diff import create_content_hash, generate_diff
from notion_sync.extract import extract_code_identity


# Override conftest autouse fixtures that require NOTION_API_TOKEN.
@pytest.fixture(autouse=True)
def sync_to_clone():
    yield


@pytest.fixture
def test_pages():
    return ("fake-master", "fake-clone")


def _run(text, **annotations):
    return {
        "type": "text",
        "text": {"content": text},
        "plain_text": text,
        "annotations": {"bold": False, "italic": False, "code": False, **annotations},
    }


def _item(runs):
    return {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": runs}}


CODE = _item([_run("call_id", code=True), _run(": Een unieke string.")])
BOLD = _item([_run("call_id:", bold=True), _run(" Een unieke string.")])


def test_code_and_bold_with_the_same_text_hash_differently():
    assert create_content_hash(CODE) != create_content_hash(BOLD)


def test_code_and_plain_text_hash_differently():
    plain = _item([_run("ringing"), _run(" - A belt B")])
    code = _item([_run("ringing", code=True), _run(" - A belt B")])
    assert create_content_hash(plain) != create_content_hash(code)


def test_block_without_code_keeps_its_pre_fix_hash():
    """Flood containment: no code run means nothing is folded."""
    assert extract_code_identity(BOLD) == ""
    plain = _item([_run("Gewone tekst")])
    assert extract_code_identity(plain) == ""


def test_bold_only_change_is_still_not_folded():
    """Only code is in scope; a bold-vs-plain difference keeps one hash."""
    bold = _item([_run("Let op", bold=True), _run(": tekst")])
    plain = _item([_run("Let op"), _run(": tekst")])
    assert create_content_hash(bold) == create_content_hash(plain)


def test_same_code_runs_hash_equal():
    other = _item([_run("call_id", code=True), _run(": Een unieke string.")])
    assert create_content_hash(CODE) == create_content_hash(other)


def test_code_identity_keeps_order_and_reads_table_cells():
    row = {
        "type": "table_row",
        "table_row": {"cells": [[_run("GET", code=True)], [_run("POST", code=True)]]},
    }
    assert extract_code_identity(row) == "GET|POST"
    assert extract_code_identity(_item([_run("a", code=True), _run(" en "), _run("b", code=True)])) == "a|b"


def test_diff_updates_a_slave_that_has_bold_where_the_new_block_has_code():
    """The live bug: the slave block must not be KEPT."""
    old = [{**BOLD, "id": "slave-1"}]
    new = [CODE]
    ops = generate_diff(old, new)
    assert [op["op"] for op in ops] != ["KEEP"]
