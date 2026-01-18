"""Diff operation tests: UPDATE, DELETE, INSERT, REPLACE."""

from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    append_blocks,
    generate_diff,
    execute_diff,
    extract_block_text,
)
from .conftest import make_paragraph, make_heading, find_block_by_text


def test_3_diff_update(master_page):
    """Test updating content via diff.

    Scenario #2: Update via diff
    - Voeg paragraph "Version 1" toe
    - Wijzig naar "Version 2" via diff
    - Assert: UPDATE operatie (niet DELETE + INSERT)
    """
    client = get_notion_client()

    # Add a paragraph using helper
    append_blocks(client, master_page, [make_paragraph("Test #3 Version 1")])

    # Fetch current state
    current_blocks = fetch_blocks_recursive(client, master_page)

    # Find the "Version 1" paragraph using helper
    version_block = find_block_by_text(current_blocks, "Test #3 Version 1", "paragraph")

    # Generate diff for update
    updated_block = make_paragraph("Test #3 Version 2")
    ops = generate_diff([version_block], [updated_block])

    # Assert: should have UPDATE operation
    update_ops = [op for op in ops if op["op"] == "UPDATE"]
    assert len(update_ops) == 1, f"Expected 1 UPDATE, got {len(update_ops)}"

    # Execute diff
    stats = execute_diff(client, ops, master_page, dry_run=False)
    assert stats["updated"] == 1

    # Verify update
    fetched = fetch_blocks_recursive(client, master_page)
    version_blocks = [b for b in fetched if b["type"] == "paragraph"]
    version_texts = [extract_block_text(b) for b in version_blocks]
    assert "Test #3 Version 2" in version_texts


def test_5_diff_delete(master_page):
    """Test deleting content via diff.

    DELETE operatie - Block verwijderen
    - Voeg marker paragraph "DELETE ME" toe
    - Genereer diff zonder dit block
    - Assert: DELETE operatie
    - Verify: block is weg
    """
    client = get_notion_client()

    # Add a marker paragraph to delete
    append_blocks(client, master_page, [make_paragraph("Test #5 DELETE ME - will be removed")])

    # Fetch current state
    current_blocks = fetch_blocks_recursive(client, master_page)

    # Find the marker paragraph
    delete_block = find_block_by_text(current_blocks, "Test #5 DELETE ME - will be removed")

    # Generate diff to delete it (empty new blocks)
    ops = generate_diff([delete_block], [])

    # Assert: should have DELETE operation
    delete_ops = [op for op in ops if op["op"] == "DELETE"]
    assert len(delete_ops) == 1, f"Expected 1 DELETE, got {len(delete_ops)}"

    # Execute diff
    stats = execute_diff(client, ops, master_page, dry_run=False)
    assert stats["deleted"] == 1

    # Verify block is gone
    fetched = fetch_blocks_recursive(client, master_page)
    texts = [extract_block_text(b) for b in fetched if b["type"] == "paragraph"]
    assert "Test #5 DELETE ME - will be removed" not in texts


def test_6_diff_insert(master_page):
    """Test inserting content via diff.

    INSERT operatie - Nieuwe block tussen bestaande
    - Fetch current blocks
    - Genereer diff met extra block in het midden
    - Assert: INSERT operatie
    - Verify: nieuwe block staat er
    """
    client = get_notion_client()

    # Fetch current state
    current_blocks = fetch_blocks_recursive(client, master_page)

    # Create new blocks with an inserted one
    new_blocks = current_blocks.copy()
    new_blocks.append(make_paragraph("Test #6 INSERTED - new block"))

    # Generate diff
    ops = generate_diff(current_blocks, new_blocks)

    # Assert: should have INSERT operation
    insert_ops = [op for op in ops if op["op"] == "INSERT"]
    assert len(insert_ops) == 1, f"Expected 1 INSERT, got {len(insert_ops)}"

    # Execute diff
    stats = execute_diff(client, ops, master_page, dry_run=False)
    assert stats["inserted"] == 1

    # Verify new block exists
    fetched = fetch_blocks_recursive(client, master_page)
    texts = [extract_block_text(b) for b in fetched if b["type"] == "paragraph"]
    assert "Test #6 INSERTED - new block" in texts


def test_7_diff_replace(master_page):
    """Test replacing block type via diff.

    REPLACE operatie - Block type wijzigen
    - Voeg paragraph "CHANGE TYPE" toe
    - Genereer diff met zelfde text maar als heading_2
    - Assert: REPLACE operatie (delete + insert)
    - Verify: block is nu heading_2
    """
    client = get_notion_client()

    # Add a paragraph that we'll change to heading
    append_blocks(client, master_page, [make_paragraph("Test #7 REPLACE TYPE - will become heading")])

    # Fetch current state
    current_blocks = fetch_blocks_recursive(client, master_page)

    # Find the paragraph
    para_block = find_block_by_text(current_blocks, "Test #7 REPLACE TYPE - will become heading", "paragraph")

    # Create new version as heading_2
    heading_block = make_heading(2, "Test #7 REPLACE TYPE - will become heading")

    # Generate diff
    ops = generate_diff([para_block], [heading_block])

    # Assert: should have REPLACE operation
    replace_ops = [op for op in ops if op["op"] == "REPLACE"]
    assert len(replace_ops) == 1, f"Expected 1 REPLACE, got {len(replace_ops)}"

    # Execute diff
    stats = execute_diff(client, ops, master_page, dry_run=False)
    assert stats["replaced"] == 1

    # Verify block is now heading_2
    fetched = fetch_blocks_recursive(client, master_page)
    heading_blocks = [b for b in fetched if b["type"] == "heading_2"]
    heading_texts = [extract_block_text(b) for b in heading_blocks]
    assert "Test #7 REPLACE TYPE - will become heading" in heading_texts
