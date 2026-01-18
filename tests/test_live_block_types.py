"""Block type tests: lists, to_do, code, quote, callout, divider."""

from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    append_blocks,
    extract_block_text,
)
from .conftest import make_paragraph, find_blocks_by_type


def test_11_bulleted_list(master_page):
    """Test creating bulleted list items.

    Scenario: Common block type
    - Create bulleted_list_item blocks
    - Fetch back → Assert: type correct, content correct
    """
    client = get_notion_client()

    # Create bulleted list items
    blocks = [
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": "Test #11 First item"}}]
            }
        },
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": "Test #11 Second item"}}]
            }
        },
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": "Test #11 Third item"}}]
            }
        }
    ]

    append_blocks(client, master_page, blocks)

    # Fetch and verify
    fetched = fetch_blocks_recursive(client, master_page)
    list_items = find_blocks_by_type(fetched, "bulleted_list_item")

    assert len(list_items) == 3
    assert extract_block_text(list_items[0]) == "Test #11 First item"
    assert extract_block_text(list_items[1]) == "Test #11 Second item"
    assert extract_block_text(list_items[2]) == "Test #11 Third item"


def test_12_numbered_list(master_page):
    """Test creating numbered list items.

    Scenario: Common block type
    - Create numbered_list_item blocks
    - Fetch back → Assert: type correct, content correct
    """
    client = get_notion_client()

    # Create numbered list items
    blocks = [
        {
            "type": "numbered_list_item",
            "numbered_list_item": {
                "rich_text": [{"type": "text", "text": {"content": "Test #12 Step one"}}]
            }
        },
        {
            "type": "numbered_list_item",
            "numbered_list_item": {
                "rich_text": [{"type": "text", "text": {"content": "Test #12 Step two"}}]
            }
        }
    ]

    append_blocks(client, master_page, blocks)

    # Fetch and verify
    fetched = fetch_blocks_recursive(client, master_page)
    list_items = find_blocks_by_type(fetched, "numbered_list_item")

    assert len(list_items) == 2
    assert extract_block_text(list_items[0]) == "Test #12 Step one"
    assert extract_block_text(list_items[1]) == "Test #12 Step two"


def test_13_to_do_unchecked(master_page):
    """Test creating to_do blocks with checked property.

    Scenario: Block type with special property
    - Create to_do blocks (checked and unchecked)
    - Fetch back → Assert: checked property preserved
    """
    client = get_notion_client()

    # Create to_do items
    blocks = [
        {
            "type": "to_do",
            "to_do": {
                "rich_text": [{"type": "text", "text": {"content": "Test #13 Not done yet"}}],
                "checked": False
            }
        },
        {
            "type": "to_do",
            "to_do": {
                "rich_text": [{"type": "text", "text": {"content": "Test #13 Already done"}}],
                "checked": True
            }
        }
    ]

    append_blocks(client, master_page, blocks)

    # Fetch and verify
    fetched = fetch_blocks_recursive(client, master_page)
    todo_blocks = find_blocks_by_type(fetched, "to_do")

    assert len(todo_blocks) == 2

    # Find each by content (text may include checkbox symbols)
    unchecked = [b for b in todo_blocks if "Test #13 Not done yet" in extract_block_text(b)][0]
    checked = [b for b in todo_blocks if "Test #13 Already done" in extract_block_text(b)][0]

    # Verify checked properties
    assert unchecked["to_do"]["checked"] is False
    assert checked["to_do"]["checked"] is True


def test_14_code_block(master_page):
    """Test creating code blocks with language property.

    Scenario: Block type with special property
    - Create code block with language set
    - Fetch back → Assert: language property preserved
    """
    client = get_notion_client()

    # Create code block
    blocks = [
        {
            "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": "# Test #14 Python\nprint('hello')"}}],
                "language": "python"
            }
        },
        {
            "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": "// Test #14 JavaScript\nconsole.log('hi')"}}],
                "language": "javascript"
            }
        }
    ]

    append_blocks(client, master_page, blocks)

    # Fetch and verify
    fetched = fetch_blocks_recursive(client, master_page)
    code_blocks = find_blocks_by_type(fetched, "code")

    assert len(code_blocks) == 2

    # Python code
    # Note: extract_block_text adds markdown formatting like ```python
    assert "Test #14 Python" in extract_block_text(code_blocks[0])
    assert code_blocks[0]["code"]["language"] == "python"

    # JavaScript code
    assert "Test #14 JavaScript" in extract_block_text(code_blocks[1])
    assert code_blocks[1]["code"]["language"] == "javascript"


def test_15_quote(master_page):
    """Test creating quote blocks.

    Scenario: Common block type
    - Create quote block
    - Fetch back → Assert: type and content correct
    """
    client = get_notion_client()

    blocks = [
        {
            "type": "quote",
            "quote": {
                "rich_text": [{"type": "text", "text": {"content": "Test #15 To be or not to be"}}]
            }
        }
    ]

    append_blocks(client, master_page, blocks)

    # Fetch and verify
    fetched = fetch_blocks_recursive(client, master_page)
    quote_blocks = find_blocks_by_type(fetched, "quote")

    assert len(quote_blocks) == 1
    assert extract_block_text(quote_blocks[0]) == "Test #15 To be or not to be"


def test_16_callout(master_page):
    """Test creating callout blocks.

    Scenario: Common block type
    - Create callout block (note: icon is complex, test basic case)
    - Fetch back → Assert: type and content correct
    """
    client = get_notion_client()

    blocks = [
        {
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": "Test #16 Important note"}}],
                "icon": {"type": "emoji", "emoji": "💡"}
            }
        }
    ]

    append_blocks(client, master_page, blocks)

    # Fetch and verify
    fetched = fetch_blocks_recursive(client, master_page)
    callout_blocks = find_blocks_by_type(fetched, "callout")

    assert len(callout_blocks) == 1
    # Note: extract_block_text includes emoji prefix for callouts
    assert "Test #16 Important note" in extract_block_text(callout_blocks[0])
    # Verify icon structure exists
    assert "icon" in callout_blocks[0]["callout"]
    assert callout_blocks[0]["callout"]["icon"]["type"] == "emoji"


def test_17_divider(master_page):
    """Test creating divider blocks.

    Scenario: Block type without content
    - Create divider block
    - Fetch back → Assert: type correct (no content to check)
    """
    client = get_notion_client()

    blocks = [
        make_paragraph("Test #17 Before divider"),
        {"type": "divider", "divider": {}},
        make_paragraph("Test #17 After divider")
    ]

    append_blocks(client, master_page, blocks)

    # Fetch and verify
    fetched = fetch_blocks_recursive(client, master_page)
    divider_blocks = find_blocks_by_type(fetched, "divider")

    assert len(divider_blocks) == 1
    # Divider has no content, just verify type exists
    assert divider_blocks[0]["type"] == "divider"
