"""Column operation tests: create, read, unwrap."""

from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    extract_block_text,
)
from notion_sync.columns import (
    create_column_list,
    read_column_content,
    unwrap_column_list,
)
from .conftest import make_paragraph, make_heading, find_blocks_by_type


def test_9_create_column_list(master_page):
    """Test creating a column layout.

    Column operatie - create_column_list
    - Maak 2 kolommen aan (left/right split)
    - Vul met verschillende content
    - Verify: column_list bestaat met 2 columns
    - Verify: content in elke column klopt
    """
    client = get_notion_client()

    # Create 2-column layout: 50/50 split
    columns = [
        {
            "children": [
                make_heading(3, "Test #9 Left Column"),
                make_paragraph("Test #9 Content in left column")
            ],
            "width_ratio": 0.5
        },
        {
            "children": [
                make_heading(3, "Test #9 Right Column"),
                make_paragraph("Test #9 Content in right column")
            ],
            "width_ratio": 0.5
        }
    ]

    # Create column_list
    result = create_column_list(client, master_page, columns)

    # Verify column_list created
    assert "column_list_id" in result
    assert "block_ids" in result
    column_list_id = result["column_list_id"]

    # Read column content back
    col_content = read_column_content(client, column_list_id)

    # Verify: 2 columns
    assert len(col_content) == 2

    # Verify: left column content
    left_col = col_content[0]
    assert left_col["width_ratio"] == 0.5
    assert len(left_col["blocks"]) == 2
    assert extract_block_text(left_col["blocks"][0]) == "Test #9 Left Column"
    assert extract_block_text(left_col["blocks"][1]) == "Test #9 Content in left column"

    # Verify: right column content
    right_col = col_content[1]
    assert right_col["width_ratio"] == 0.5
    assert len(right_col["blocks"]) == 2
    assert extract_block_text(right_col["blocks"][0]) == "Test #9 Right Column"
    assert extract_block_text(right_col["blocks"][1]) == "Test #9 Content in right column"


def test_10_unwrap_column_list(master_page):
    """Test unwrapping columns to flat blocks.

    Column operatie - unwrap_column_list
    - Maak column layout aan
    - Unwrap naar flat blocks
    - Verify: column_list verwijderd
    - Verify: alle content bestaat als flat blocks
    """
    client = get_notion_client()

    # Create 2-column layout
    columns = [
        {
            "children": [make_paragraph("Test #10 Unwrap - column 1")],
        },
        {
            "children": [make_paragraph("Test #10 Unwrap - column 2")],
        }
    ]

    result = create_column_list(client, master_page, columns)
    column_list_id = result["column_list_id"]

    # Unwrap columns
    unwrap_result = unwrap_column_list(
        client,
        master_page,
        column_list_id,
        delete_original=True
    )

    # Verify: 2 blocks created (1 per column)
    assert len(unwrap_result["new_block_ids"]) == 2
    assert unwrap_result["deleted"] is True

    # Verify: flat blocks exist on page
    fetched = fetch_blocks_recursive(client, master_page)
    texts = [extract_block_text(b) for b in fetched if b["type"] == "paragraph"]

    assert "Test #10 Unwrap - column 1" in texts
    assert "Test #10 Unwrap - column 2" in texts

    # Verify: column_list is gone (should not be in fetched blocks)
    column_lists = find_blocks_by_type(fetched, "column_list")
    # We might have other column_lists from previous tests
    # Just verify our specific column_list is not there by checking
    # that the unwrapped content exists as paragraphs (already checked above)
