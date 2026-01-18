"""Advanced tests: positioning, reordering, nested operations, rich text."""

from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    append_blocks,
    generate_diff,
    execute_diff,
    extract_block_text,
)
from .conftest import make_paragraph, make_heading, make_toggle, find_blocks_by_type


def test_18_insert_middle(master_page):
    """Test inserting a block in the middle.

    Scenario: INSERT operatie tussen bestaande blocks
    - Voeg 3 blocks toe (A, B, C)
    - Insert nieuwe block tussen A en B
    - Verify: volgorde is A, NEW, B, C
    """
    client = get_notion_client()

    # Add initial blocks
    initial_blocks = [
        make_paragraph("Test #18 INSERT MIDDLE - Block A"),
        make_paragraph("Test #18 INSERT MIDDLE - Block B"),
        make_paragraph("Test #18 INSERT MIDDLE - Block C"),
    ]
    append_blocks(client, master_page, initial_blocks)

    # Fetch current state
    current_blocks = fetch_blocks_recursive(client, master_page)

    # Create new list with inserted block
    # Find positions of A, B, C
    para_blocks = [b for b in current_blocks if b["type"] == "paragraph"]
    block_a = [b for b in para_blocks if "Test #18 INSERT MIDDLE - Block A" in extract_block_text(b)][0]
    block_b = [b for b in para_blocks if "Test #18 INSERT MIDDLE - Block B" in extract_block_text(b)][0]
    block_c = [b for b in para_blocks if "Test #18 INSERT MIDDLE - Block C" in extract_block_text(b)][0]

    # Get index of block_b in current_blocks
    idx_b = current_blocks.index(block_b)

    # Create new blocks list with insertion
    new_blocks = current_blocks.copy()
    new_blocks.insert(idx_b, make_paragraph("Test #18 INSERT MIDDLE - INSERTED HERE"))

    # Generate diff
    ops = generate_diff(current_blocks, new_blocks)

    # Execute
    execute_diff(client, ops, master_page, dry_run=False)

    # Verify order
    fetched = fetch_blocks_recursive(client, master_page)
    para_texts = [extract_block_text(b) for b in fetched if b["type"] == "paragraph"]

    # Find positions
    idx_a = next(i for i, t in enumerate(para_texts) if "Test #18 INSERT MIDDLE - Block A" in t)
    idx_new = next(i for i, t in enumerate(para_texts) if "Test #18 INSERT MIDDLE - INSERTED HERE" in t)
    idx_b_after = next(i for i, t in enumerate(para_texts) if "Test #18 INSERT MIDDLE - Block B" in t)
    idx_c = next(i for i, t in enumerate(para_texts) if "Test #18 INSERT MIDDLE - Block C" in t)

    # Verify order: A < NEW < B < C
    assert idx_a < idx_new < idx_b_after < idx_c, \
        f"Order wrong: A={idx_a}, NEW={idx_new}, B={idx_b_after}, C={idx_c}"


def test_19_delete_middle(master_page):
    """Test deleting a block from the middle.

    Scenario: DELETE operatie uit het midden
    - Voeg 3 blocks toe (A, B, C)
    - Delete B (middelste)
    - Verify: alleen A en C over, volgorde correct
    """
    client = get_notion_client()

    # Add blocks
    blocks = [
        make_paragraph("Test #19 DELETE MIDDLE - Block A"),
        make_paragraph("Test #19 DELETE MIDDLE - Block B DELETE ME"),
        make_paragraph("Test #19 DELETE MIDDLE - Block C"),
    ]
    append_blocks(client, master_page, blocks)

    # Fetch current
    current_blocks = fetch_blocks_recursive(client, master_page)

    # Find block B
    para_blocks = [b for b in current_blocks if b["type"] == "paragraph"]
    block_b = [b for b in para_blocks if "Test #19 DELETE MIDDLE - Block B DELETE ME" in extract_block_text(b)][0]

    # Create new list without B
    new_blocks = [b for b in current_blocks if b["id"] != block_b["id"]]

    # Generate diff
    ops = generate_diff(current_blocks, new_blocks)

    # Execute
    execute_diff(client, ops, master_page, dry_run=False)

    # Verify
    fetched = fetch_blocks_recursive(client, master_page)
    para_texts = [extract_block_text(b) for b in fetched if b["type"] == "paragraph"]

    # B should be gone
    assert not any("Test #19 DELETE MIDDLE - Block B DELETE ME" in t for t in para_texts)

    # A and C should remain in order
    idx_a = next(i for i, t in enumerate(para_texts) if "Test #19 DELETE MIDDLE - Block A" in t)
    idx_c = next(i for i, t in enumerate(para_texts) if "Test #19 DELETE MIDDLE - Block C" in t)
    assert idx_a < idx_c


def test_20_update_nested_content(master_page):
    """Test updating content inside a nested block via direct API.

    Scenario: UPDATE content binnen toggle child
    - Voeg toggle toe met child "Original"
    - Update child direct via API (niet via diff)
    - Verify: child content is gewijzigd

    Note: generate_diff vergelijkt alleen top-level blocks. Voor nested
    updates gebruik je direct de update API op het child block.
    """
    client = get_notion_client()

    # Add toggle with child
    toggle = make_toggle(
        "Test #20 UPDATE NESTED - Toggle",
        children=[make_paragraph("Test #20 UPDATE NESTED - Original child")]
    )
    append_blocks(client, master_page, [toggle])

    # Fetch current
    current_blocks = fetch_blocks_recursive(client, master_page)

    # Find toggle
    toggles = [b for b in current_blocks if b["type"] == "toggle"]
    toggle_block = [t for t in toggles if "Test #20 UPDATE NESTED - Toggle" in extract_block_text(t)][0]

    # Get child block ID
    assert "_children" in toggle_block
    child_block = toggle_block["_children"][0]
    child_id = child_block["id"]

    # Update child directly via API
    client.notion.blocks.update(
        block_id=child_id,
        paragraph={
            "rich_text": [{"type": "text", "text": {"content": "Test #20 UPDATE NESTED - Updated child"}}]
        }
    )

    # Verify
    fetched = fetch_blocks_recursive(client, master_page)
    toggles_after = [b for b in fetched if b["type"] == "toggle"]
    toggle_after = [t for t in toggles_after if "Test #20 UPDATE NESTED - Toggle" in extract_block_text(t)][0]

    # Check child content
    assert "_children" in toggle_after
    child_text = extract_block_text(toggle_after["_children"][0])
    assert "Test #20 UPDATE NESTED - Updated child" in child_text


def test_21_insert_child_in_toggle(master_page):
    """Test inserting a child into an existing toggle via direct API.

    Scenario: INSERT child in bestaande toggle
    - Voeg toggle toe met 1 child
    - Append 2e child direct via API
    - Verify: toggle heeft 2 children

    Note: Voor het toevoegen van children gebruik je append_blocks op het parent block.
    """
    client = get_notion_client()

    # Add toggle with 1 child
    toggle = make_toggle(
        "Test #21 INSERT CHILD - Toggle",
        children=[make_paragraph("Test #21 INSERT CHILD - First child")]
    )
    append_blocks(client, master_page, [toggle])

    # Fetch current
    current_blocks = fetch_blocks_recursive(client, master_page)

    # Find toggle
    toggles = [b for b in current_blocks if b["type"] == "toggle"]
    toggle_block = [t for t in toggles if "Test #21 INSERT CHILD - Toggle" in extract_block_text(t)][0]
    toggle_id = toggle_block["id"]

    # Append second child to toggle
    append_blocks(
        client,
        toggle_id,
        [make_paragraph("Test #21 INSERT CHILD - Second child")]
    )

    # Verify
    fetched = fetch_blocks_recursive(client, master_page)
    toggles_after = [b for b in fetched if b["type"] == "toggle"]
    toggle_after = [t for t in toggles_after if "Test #21 INSERT CHILD - Toggle" in extract_block_text(t)][0]

    # Check children count and content
    assert "_children" in toggle_after
    assert len(toggle_after["_children"]) == 2

    child_texts = [extract_block_text(c) for c in toggle_after["_children"]]
    assert any("Test #21 INSERT CHILD - First child" in t for t in child_texts)
    assert any("Test #21 INSERT CHILD - Second child" in t for t in child_texts)


def test_22_delete_child_from_toggle(master_page):
    """Test deleting a child from a toggle via direct API.

    Scenario: DELETE child uit toggle
    - Voeg toggle toe met 2 children
    - Delete 1 child direct via API
    - Verify: toggle heeft nog 1 child

    Note: Voor het verwijderen van een child gebruik je de delete API op het child block.
    """
    client = get_notion_client()

    # Add toggle with 2 children
    toggle = make_toggle(
        "Test #22 DELETE CHILD - Toggle",
        children=[
            make_paragraph("Test #22 DELETE CHILD - Keep this"),
            make_paragraph("Test #22 DELETE CHILD - Delete this")
        ]
    )
    append_blocks(client, master_page, [toggle])

    # Fetch current
    current_blocks = fetch_blocks_recursive(client, master_page)

    # Find toggle
    toggles = [b for b in current_blocks if b["type"] == "toggle"]
    toggle_block = [t for t in toggles if "Test #22 DELETE CHILD - Toggle" in extract_block_text(t)][0]

    # Find child to delete
    assert "_children" in toggle_block
    child_to_delete = [c for c in toggle_block["_children"] if "Test #22 DELETE CHILD - Delete this" in extract_block_text(c)][0]
    child_id = child_to_delete["id"]

    # Delete child via API
    client.notion.blocks.delete(block_id=child_id)

    # Verify
    fetched = fetch_blocks_recursive(client, master_page)
    toggles_after = [b for b in fetched if b["type"] == "toggle"]
    toggle_after = [t for t in toggles_after if "Test #22 DELETE CHILD - Toggle" in extract_block_text(t)][0]

    # Check children count and content
    assert "_children" in toggle_after
    assert len(toggle_after["_children"]) == 1

    child_text = extract_block_text(toggle_after["_children"][0])
    assert "Test #22 DELETE CHILD - Keep this" in child_text
    assert "DELETE CHILD - Delete this" not in child_text


def test_23_deep_nesting(master_page):
    """Test deep nesting (3 levels).

    Scenario: 3 levels diep nesten
    - Toggle → Toggle → Paragraph
    - Verify: alle levels zijn correct genest
    """
    client = get_notion_client()

    # Create 3-level nested structure
    deep_toggle = make_toggle(
        "Test #23 DEEP NESTING - Level 1 Toggle",
        children=[
            make_toggle(
                "Test #23 DEEP NESTING - Level 2 Toggle",
                children=[
                    make_paragraph("Test #23 DEEP NESTING - Level 3 Paragraph")
                ]
            )
        ]
    )
    append_blocks(client, master_page, [deep_toggle])

    # Fetch and verify structure
    fetched = fetch_blocks_recursive(client, master_page)

    # Find level 1 toggle
    toggles = [b for b in fetched if b["type"] == "toggle"]
    level_1 = [t for t in toggles if "Test #23 DEEP NESTING - Level 1 Toggle" in extract_block_text(t)][0]

    # Verify level 1 has children
    assert "_children" in level_1
    assert len(level_1["_children"]) == 1

    # Verify level 2 is a toggle
    level_2 = level_1["_children"][0]
    assert level_2["type"] == "toggle"
    assert "Test #23 DEEP NESTING - Level 2 Toggle" in extract_block_text(level_2)

    # Verify level 2 has children
    assert "_children" in level_2
    assert len(level_2["_children"]) == 1

    # Verify level 3 is a paragraph
    level_3 = level_2["_children"][0]
    assert level_3["type"] == "paragraph"
    assert "Test #23 DEEP NESTING - Level 3 Paragraph" in extract_block_text(level_3)


def test_24_rich_text_formatting(master_page):
    """Test rich text formatting (bold, italic, link).

    Scenario: Rich text met formatting
    - Voeg paragraph toe met bold, italic, link
    - Verify: formatting is behouden
    """
    client = get_notion_client()

    # Create paragraph with rich text formatting
    block = {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": "Test #24 RICH TEXT - "},
                },
                {
                    "type": "text",
                    "text": {"content": "bold text"},
                    "annotations": {
                        "bold": True,
                        "italic": False,
                        "strikethrough": False,
                        "underline": False,
                        "code": False,
                        "color": "default"
                    }
                },
                {
                    "type": "text",
                    "text": {"content": " and "},
                },
                {
                    "type": "text",
                    "text": {"content": "italic text"},
                    "annotations": {
                        "bold": False,
                        "italic": True,
                        "strikethrough": False,
                        "underline": False,
                        "code": False,
                        "color": "default"
                    }
                },
                {
                    "type": "text",
                    "text": {"content": " and "},
                },
                {
                    "type": "text",
                    "text": {
                        "content": "a link",
                        "link": {"url": "https://example.com"}
                    },
                }
            ]
        }
    }

    append_blocks(client, master_page, [block])

    # Fetch and verify
    fetched = fetch_blocks_recursive(client, master_page)
    para_blocks = [b for b in fetched if b["type"] == "paragraph"]

    # Find our test block
    test_block = None
    for p in para_blocks:
        rich_text = p.get("paragraph", {}).get("rich_text", [])
        for rt in rich_text:
            if "Test #24 RICH TEXT" in rt.get("text", {}).get("content", ""):
                test_block = p
                break
        if test_block:
            break

    assert test_block is not None, "Test #24 RICH TEXT block not found"

    # Verify rich_text array has multiple parts
    rich_text = test_block["paragraph"]["rich_text"]
    assert len(rich_text) > 1, "Expected multiple rich_text segments"

    # Find bold text
    bold_parts = [rt for rt in rich_text if rt.get("annotations", {}).get("bold", False)]
    assert len(bold_parts) >= 1, "No bold text found"
    assert any("bold text" == rt.get("text", {}).get("content", "") for rt in bold_parts), "Bold text content mismatch"

    # Find italic text
    italic_parts = [rt for rt in rich_text if rt.get("annotations", {}).get("italic", False)]
    assert len(italic_parts) >= 1, "No italic text found"
    assert any("italic text" == rt.get("text", {}).get("content", "") for rt in italic_parts), "Italic text content mismatch"

    # Find link
    link_parts = [rt for rt in rich_text if rt.get("text", {}).get("link") is not None]
    assert len(link_parts) >= 1, "No link found"
    assert any("a link" == rt.get("text", {}).get("content", "") for rt in link_parts), "Link content mismatch"

    # Check link URL (Notion may modify the URL slightly)
    link_urls = [rt.get("text", {}).get("link", {}).get("url", "") for rt in link_parts]
    assert any("example.com" in url for url in link_urls), f"Link URL mismatch, got: {link_urls}"


def test_25_bulk_insert(master_page):
    """Test bulk insert (15 blocks).

    Scenario: Bulk operatie met veel blocks
    - Insert 15 blocks in 1 operatie
    - Verify: alle blocks zijn toegevoegd
    """
    client = get_notion_client()

    # Create 15 blocks
    blocks = [
        make_paragraph(f"Test #25 BULK INSERT - Block {i+1}")
        for i in range(15)
    ]

    append_blocks(client, master_page, blocks)

    # Verify
    fetched = fetch_blocks_recursive(client, master_page)
    para_texts = [extract_block_text(b) for b in fetched if b["type"] == "paragraph"]

    # Check all 15 blocks exist
    bulk_blocks = [t for t in para_texts if "Test #25 BULK INSERT" in t]
    assert len(bulk_blocks) == 15

    # Verify numbering
    for i in range(15):
        assert any(f"Test #25 BULK INSERT - Block {i+1}" in t for t in bulk_blocks)
