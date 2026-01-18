"""Clone and sync tests."""

import os
from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    append_blocks,
    extract_block_text,
)
from conftest import make_paragraph


def test_8_clone_and_sync(master_page):
    """Test cloning master and keeping both in sync.

    Scenario #3: Clone en sync
    - Clone master → "Test Clone"
    - Assert: Clone heeft alle content van master
    - Voeg "Final update" toe aan beide
    - Assert: master en clone blijven identiek

    Both pages remain for manual inspection.
    """
    client = get_notion_client()

    # Fetch all master content
    master_content = fetch_blocks_recursive(client, master_page)

    # Create clone page
    parent_id = os.getenv("TEST_PAGE_ID")
    clone_response = client.notion.pages.create(
        parent={"page_id": parent_id},
        properties={
            "title": {
                "title": [
                    {
                        "text": {"content": "Test Clone (auto-generated)"}
                    }
                ]
            }
        }
    )
    clone_page_id = clone_response["id"]

    # Clone all content to clone page
    clean_blocks = []
    for block in master_content:
        clean_block = {"type": block["type"]}
        clean_block[block["type"]] = block[block["type"]].copy()
        # Copy children recursively
        if "_children" in block:
            children = []
            for child in block["_children"]:
                child_clean = {"type": child["type"]}
                child_clean[child["type"]] = child[child["type"]].copy()
                children.append(child_clean)
            clean_block[block["type"]]["children"] = children
        clean_blocks.append(clean_block)

    append_blocks(client, clone_page_id, clean_blocks)

    # Verify clone has same content
    clone_content = fetch_blocks_recursive(client, clone_page_id)
    assert len(clone_content) == len(master_content)

    for master_block, clone_block in zip(master_content, clone_content):
        assert master_block["type"] == clone_block["type"]
        assert extract_block_text(master_block) == extract_block_text(clone_block)

    # Add final update to both using helper
    final_block = [make_paragraph("Final sync test - both pages identical")]

    append_blocks(client, master_page, final_block)
    append_blocks(client, clone_page_id, final_block)

    # Verify both still identical
    final_master = fetch_blocks_recursive(client, master_page)
    final_clone = fetch_blocks_recursive(client, clone_page_id)

    assert len(final_master) == len(final_clone)

    # Both should have the final message
    master_texts = [extract_block_text(b) for b in final_master if b["type"] == "paragraph"]
    clone_texts = [extract_block_text(b) for b in final_clone if b["type"] == "paragraph"]

    assert "Final sync test - both pages identical" in master_texts
    assert "Final sync test - both pages identical" in clone_texts

    print(f"\nTest complete!")
    print(f"Master page ID: {master_page}")
    print(f"Clone page ID: {clone_page_id}")
    print(f"Check both pages in Notion - they should be identical")
