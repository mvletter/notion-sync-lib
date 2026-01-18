"""User action tests: reorder (manual) and delete all verification."""

import pytest
from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    append_blocks,
    generate_diff,
    execute_diff,
)
from .conftest import make_paragraph, make_heading


@pytest.mark.manual
def test_98_user_reorder(master_page, clone_page):
    """Test user reorder: user manually reorders, then we sync to clone.

    Scenario: User reorder test
    - Create instruction blocks + 3 blocks to reorder (A, B, C)
    - PAUSE: User reorders blocks in master to C, A, B
    - Sync the reordered master to clone
    - PAUSE: User verifies clone has same order
    - Test passes when user confirms

    Note: Reorder can only be done by user in Notion UI, not via API.
    """
    client = get_notion_client()

    # Create instruction block
    instruction = make_heading(
        1,
        "TEST #98 USER REORDER - MANUAL ACTION REQUIRED"
    )

    instructions_text = make_paragraph(
        "Test #98 REORDER - INSTRUCTIONS: "
        "1. Open the MASTER page in Notion. "
        "2. Find the 3 blocks below (A, B, C). "
        "3. Drag and drop to reorder them to: C, A, B. "
        "4. Come back here and type 'done' when finished."
    )

    # Create blocks to reorder
    blocks_to_reorder = [
        make_paragraph("Test #98 REORDER - Block A (move to middle)"),
        make_paragraph("Test #98 REORDER - Block B (move to end)"),
        make_paragraph("Test #98 REORDER - Block C (move to top)"),
    ]

    # Add all blocks
    all_blocks = [instruction, instructions_text] + blocks_to_reorder
    append_blocks(client, master_page, all_blocks)

    # Print master page URL
    print(f"\n" + "="*80)
    print(f"MANUAL ACTION REQUIRED - TEST #98 REORDER")
    print(f"="*80)
    print(f"Master Page ID: {master_page}")
    print(f"Clone Page ID: {clone_page}")
    print(f"\nSTEPS:")
    print(f"1. Open the MASTER page in Notion")
    print(f"2. Find blocks A, B, C (look for 'Test #98 REORDER')")
    print(f"3. Drag and drop to reorder: C → A → B (top to bottom)")
    print(f"4. Type 'done' and press Enter when finished")
    print(f"="*80)

    # Wait for user confirmation
    user_input = input("\nType 'done' when you've reordered the blocks: ").strip().lower()
    assert user_input == "done", "User must confirm reorder by typing 'done'"

    print("\n✓ User confirmed reorder in master")

    # Fetch master state after user reorder
    print("Fetching master blocks after reorder...")
    master_blocks = fetch_blocks_recursive(client, master_page)

    # Fetch clone state
    print("Fetching clone blocks...")
    clone_blocks = fetch_blocks_recursive(client, clone_page)

    # Generate diff to sync master → clone
    print("Generating diff to sync reordered master to clone...")
    ops = generate_diff(clone_blocks, master_blocks)
    print(f"Generated {len(ops)} operations")

    # Execute diff
    if ops:
        print("Syncing reordered blocks to clone...")
        execute_diff(client, ops, clone_page, dry_run=False)
        print(f"✓ Synced {len(ops)} operations to clone")
    else:
        print("No operations needed (already in sync)")

    # Ask user to verify clone
    print(f"\n" + "="*80)
    print(f"VERIFICATION REQUIRED")
    print(f"="*80)
    print(f"Clone Page ID: {clone_page}")
    print(f"\nSTEPS:")
    print(f"1. Open the CLONE page in Notion")
    print(f"2. Verify blocks are in order: C, A, B")
    print(f"3. Type 'ok' if the order matches")
    print(f"="*80)

    user_verify = input("\nType 'ok' if clone has correct order (C, A, B): ").strip().lower()
    assert user_verify == "ok", "User must verify clone order by typing 'ok'"

    print("\n✅ Test #98 PASSED - User confirmed clone has correct order")


@pytest.mark.manual
def test_99_delete_all_verification(master_page, clone_page):
    """Test delete all: user deletes all blocks, verify clone is also empty.

    Scenario: Delete all verification
    - PAUSE: User deletes all blocks from master page
    - Auto-sync will sync the deletion to clone
    - Verify both master and clone are empty
    - Test passes when both pages are empty

    Note: This is the final test. It cleans up all test data.
    """
    client = get_notion_client()

    # Create instruction block
    instruction = make_heading(
        1,
        "TEST #99 DELETE ALL - MANUAL ACTION REQUIRED"
    )

    instructions_text = make_paragraph(
        "Test #99 DELETE ALL - INSTRUCTIONS: "
        "1. Open the MASTER page in Notion. "
        "2. Select ALL blocks (Cmd+A or Ctrl+A). "
        "3. Delete all blocks. "
        "4. Come back here and type 'done' when the page is empty."
    )

    # Add instruction blocks
    append_blocks(client, master_page, [instruction, instructions_text])

    # Print instructions
    print(f"\n" + "="*80)
    print(f"MANUAL ACTION REQUIRED - TEST #99 DELETE ALL")
    print(f"="*80)
    print(f"Master Page ID: {master_page}")
    print(f"\nSTEPS:")
    print(f"1. Open the MASTER page in Notion")
    print(f"2. Select ALL blocks (Cmd+A or Ctrl+A)")
    print(f"3. Delete all blocks (backspace/delete)")
    print(f"4. Type 'done' when the page is completely empty")
    print(f"="*80)

    # Wait for user confirmation
    user_input = input("\nType 'done' when master page is empty: ").strip().lower()
    assert user_input == "done", "User must confirm deletion by typing 'done'"

    print("\n✓ User confirmed master is empty")

    # Fetch master - should be empty
    print("Verifying master is empty...")
    master_blocks = fetch_blocks_recursive(client, master_page)

    if len(master_blocks) > 0:
        print(f"⚠️  WARNING: Master still has {len(master_blocks)} blocks")
        print("Please make sure all blocks are deleted from master")
        raise AssertionError(f"Master page should be empty but has {len(master_blocks)} blocks")

    print("✓ Master page is empty")

    # The auto-sync fixture should have already synced the deletion to clone
    # But let's verify clone is also empty
    print("Verifying clone is empty (via auto-sync)...")
    clone_blocks = fetch_blocks_recursive(client, clone_page)

    if len(clone_blocks) > 0:
        print(f"⚠️  Clone still has {len(clone_blocks)} blocks")
        print("Auto-sync should have deleted these. Checking if sync is needed...")

        # Generate diff to ensure clone is also empty
        ops = generate_diff(clone_blocks, master_blocks)
        if ops:
            print(f"Executing {len(ops)} operations to empty clone...")
            execute_diff(client, ops, clone_page, dry_run=False)

            # Re-check
            clone_blocks = fetch_blocks_recursive(client, clone_page)

    assert len(clone_blocks) == 0, f"Clone should be empty but has {len(clone_blocks)} blocks"

    print("✓ Clone page is empty")

    # Final verification with user
    print(f"\n" + "="*80)
    print(f"FINAL VERIFICATION")
    print(f"="*80)
    print(f"Master Page ID: {master_page}")
    print(f"Clone Page ID: {clone_page}")
    print(f"\nSTEPS:")
    print(f"1. Open BOTH master and clone pages in Notion")
    print(f"2. Verify BOTH pages are completely empty")
    print(f"3. Type 'ok' if both pages are empty")
    print(f"="*80)

    user_verify = input("\nType 'ok' if BOTH pages are empty: ").strip().lower()
    assert user_verify == "ok", "User must verify both pages are empty by typing 'ok'"

    print("\n✅ TEST #99 PASSED - Both master and clone are empty")
    print("✅ ALL TESTS COMPLETED - Test pages are clean")
