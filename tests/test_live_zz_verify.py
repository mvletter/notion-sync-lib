"""Clone and sync verification tests."""

from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    extract_block_text,
)


def test_99_verify_sync(master_page, clone_page):
    """Verify that master and clone are identical after all tests.

    After each test, sync_to_clone fixture syncs master → clone via diff.
    This test verifies the final result: both pages should be identical.

    Runs last (test_99) to ensure all other tests have synced.
    Both pages remain for manual inspection.
    """
    client = get_notion_client()

    # Fetch both pages
    master_blocks = fetch_blocks_recursive(client, master_page)
    clone_blocks = fetch_blocks_recursive(client, clone_page)

    # Verify: same number of blocks
    assert len(master_blocks) == len(clone_blocks), \
        f"Master has {len(master_blocks)} blocks, clone has {len(clone_blocks)}"

    # Verify: all blocks have same type and content
    for i, (master_block, clone_block) in enumerate(zip(master_blocks, clone_blocks)):
        assert master_block["type"] == clone_block["type"], \
            f"Block {i}: type mismatch - master={master_block['type']}, clone={clone_block['type']}"

        master_text = extract_block_text(master_block)
        clone_text = extract_block_text(clone_block)
        assert master_text == clone_text, \
            f"Block {i}: content mismatch - master='{master_text}', clone='{clone_text}'"

        # For nested blocks, verify children
        if "_children" in master_block:
            assert "_children" in clone_block, f"Block {i}: master has children, clone doesn't"
            assert len(master_block["_children"]) == len(clone_block["_children"]), \
                f"Block {i}: children count mismatch"

    print(f"\n✓ Sync verification passed!")
    print(f"Master page ID: {master_page}")
    print(f"Clone page ID: {clone_page}")
    print(f"Both pages have {len(master_blocks)} blocks and are identical")
    print(f"Check both pages in Notion - they should match exactly")
