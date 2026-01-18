# Usage Guide

Complete guide to using notion-sync-lib in your projects.

## Table of Contents

- [Setup](#setup)
- [Basic Operations](#basic-operations)
- [Fetching Blocks](#fetching-blocks)
- [Choosing the Right Diff Function](#choosing-the-right-diff-function)
- [Diff-Based Sync](#diff-based-sync)
- [Recursive Diff](#recursive-diff)
- [Column Operations](#column-operations)
- [Block Builders](#block-builders)
- [Common Patterns](#common-patterns)
- [Real-World Use Cases](#real-world-use-cases)

## Setup

Set your Notion API token as an environment variable or in a `.env` file:

```bash
export NOTION_API_TOKEN=secret_xxx
```

Or create a `.env` file in your project root:

```
NOTION_API_TOKEN=secret_xxx
```

## Basic Operations

### Creating a Client

```python
from notion_sync import get_notion_client

# Create a rate-limited client
client = get_notion_client()

# The client automatically:
# - Rate limits to 3 requests/second
# - Retries on 429 errors with exponential backoff
# - Tracks request count via client.request_count
```

### Working with Pages

```python
from notion_sync import get_notion_client, extract_page_id, extract_page_title

client = get_notion_client()

# Extract page ID from URL
page_id = extract_page_id("https://notion.so/My-Page-abc123def456...")

# Get page metadata
page = client.get_page(page_id)
print(f"Page title: {extract_page_title(page)}")

# Update page title
client.update_page_title(page_id, "New Title")
```

## Fetching Blocks

### Top-Level Blocks Only

```python
from notion_sync import get_notion_client, fetch_page_blocks

client = get_notion_client()
page_id = "your-page-id"

# Fetch only top-level blocks (no children)
blocks = fetch_page_blocks(client, page_id)
print(f"Found {len(blocks)} top-level blocks")
```

### Recursive Fetching (All Nested Blocks)

```python
from notion_sync import get_notion_client, fetch_blocks_recursive

client = get_notion_client()
page_id = "your-page-id"

# Fetch ALL blocks including nested children
# Children are stored under '_children' key
blocks = fetch_blocks_recursive(client, page_id)

def print_tree(blocks, indent=0):
    """Print block tree structure."""
    for block in blocks:
        block_type = block.get("type", "unknown")
        print(f"{'  ' * indent}{block_type}")
        if "_children" in block:
            print_tree(block["_children"], indent + 1)

print_tree(blocks)
```

### Extracting Text from Blocks

```python
from notion_sync import extract_block_text

for block in blocks:
    text = extract_block_text(block)
    if text:
        print(f"{block['type']}: {text}")
```

## Choosing the Right Diff Function

**Two diff modes available:**

| Mode | Use Case | Operations | When to Use |
|------|----------|-----------|-------------|
| **`generate_diff`** | Structure changes | INSERT, DELETE, UPDATE, REPLACE, KEEP | Pages with different structures, syncing new content, tests |
| **`generate_recursive_diff`** | Content-only updates | UPDATE only | Translation sync where structure is identical |

**Rule of thumb:**
- Pages might have different blocks? → Use `generate_diff`
- Pages have identical structure, only text changes? → Use `generate_recursive_diff`

**Why two modes?**

- `generate_diff`: Uses content-based matching to handle structural differences. Slower but handles any change.
- `generate_recursive_diff`: Assumes identical structure and IDs. Much faster but only works when structure matches.

## Diff-Based Sync

Use `generate_diff` when blocks may be added, removed, or reordered.

### Basic Example

```python
from notion_sync import (
    get_notion_client,
    fetch_page_blocks,
    generate_diff,
    execute_diff,
    format_diff_preview,
)

client = get_notion_client()
page_id = "your-page-id"

# Get current blocks from Notion
notion_blocks = fetch_page_blocks(client, page_id)

# Your desired blocks (e.g., from markdown conversion)
local_blocks = [
    {"type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": "Hello"}}]}},
    {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "World"}}]}},
]

# Generate diff operations (handles INSERT/DELETE/UPDATE/REPLACE)
ops = generate_diff(notion_blocks, local_blocks)

# Preview changes (dry run)
print(format_diff_preview(ops))

# Execute the diff
stats = execute_diff(client, ops, page_id, dry_run=False)
print(f"Stats: {stats}")
# Output: {'kept': 5, 'updated': 2, 'inserted': 1, 'deleted': 0, 'replaced': 0}
```

### Syncing from External Source

```python
from notion_sync import get_notion_client, fetch_page_blocks, generate_diff, execute_diff

def sync_markdown_to_notion(markdown_content: str, page_id: str):
    """Sync markdown content to Notion page."""
    client = get_notion_client()

    # Convert markdown to Notion blocks (your conversion logic)
    local_blocks = convert_markdown_to_blocks(markdown_content)

    # Get current Notion state
    notion_blocks = fetch_page_blocks(client, page_id)

    # Generate and execute diff
    ops = generate_diff(notion_blocks, local_blocks)
    stats = execute_diff(client, ops, page_id)

    print(f"Synced {stats['inserted']} new, {stats['updated']} updated, {stats['deleted']} deleted")
```

### Diff Operations Explained

The diff generates these operation types:

- **KEEP**: Block unchanged, no API call needed
- **UPDATE**: Same block type, different content - uses update API
- **REPLACE**: Different block type - deletes and re-creates
- **INSERT**: New block - uses append API with `after` positioning
- **DELETE**: Block removed - uses delete API

## Recursive Diff

Use `generate_recursive_diff` when structure is identical and only content changes (e.g., translations).

### Translation Sync Example

```python
from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    generate_recursive_diff,
    execute_recursive_diff,
)

client = get_notion_client()

# Fetch original page
original_blocks = fetch_blocks_recursive(client, original_page_id)

# Apply translations (preserve structure and IDs)
translated_blocks = apply_translations(original_blocks, translations)

# Generate UPDATE-only operations
# ⚠️ Assumes both block trees have same IDs at same positions
ops = generate_recursive_diff(original_blocks, translated_blocks)

# Execute updates
stats = execute_recursive_diff(client, ops, dry_run=False)
print(f"Updated {stats['updated']} blocks")
# Output: {'updated': 12, 'skipped': 0}
```

### How apply_translations Works

```python
import copy

def apply_translations(blocks, translation_map):
    """Apply translations to block tree while preserving structure.

    Args:
        blocks: Original block tree from fetch_blocks_recursive
        translation_map: Dict mapping block IDs to translated text

    Returns:
        Modified copy with same structure but translated content
    """
    translated = copy.deepcopy(blocks)

    def translate_recursive(block_list):
        for block in block_list:
            block_id = block.get("id")
            if block_id in translation_map:
                block_type = block["type"]
                if block_type in ("paragraph", "heading_1", "heading_2", "heading_3"):
                    block[block_type]["rich_text"] = [
                        {"type": "text", "text": {"content": translation_map[block_id]}}
                    ]

            # Recurse into children
            if "_children" in block:
                translate_recursive(block["_children"])

    translate_recursive(translated)
    return translated
```

## Column Operations

### Creating Columns

```python
from notion_sync import get_notion_client, create_column_list, make_paragraph

client = get_notion_client()
page_id = "your-page-id"

# Define columns with content and width ratios
columns = [
    {
        "children": [make_paragraph("Left column content")],
        "width_ratio": 0.6  # 60% width
    },
    {
        "children": [make_paragraph("Right column content")],
        "width_ratio": 0.4  # 40% width
    }
]

# Create column_list
result = create_column_list(client, page_id, columns)

print(f"Created column_list: {result['column_list_id']}")
print(f"Block IDs: {result['block_ids']}")
# Block IDs: {'0': 'col1_id', '0.children.0': 'content1_id', '1': 'col2_id', ...}
```

### Reading Column Content

```python
from notion_sync import get_notion_client, read_column_content

client = get_notion_client()
column_list_id = "your-column-list-id"

# Read all columns and their content
columns = read_column_content(client, column_list_id)

for i, col in enumerate(columns):
    print(f"Column {i}:")
    print(f"  Width ratio: {col['width_ratio']}")
    print(f"  Blocks: {len(col['blocks'])}")
    for block in col['blocks']:
        print(f"    - {block['type']}")
```

### Unwrapping Columns to Flat Blocks

```python
from notion_sync import get_notion_client, unwrap_column_list

client = get_notion_client()
page_id = "your-page-id"
column_list_id = "your-column-list-id"

# Flatten columns to sequential blocks
result = unwrap_column_list(
    client,
    page_id,
    column_list_id,
    after=None,  # Position to insert
    delete_original=True  # Delete column_list after unwrapping
)

print(f"Created {len(result['new_block_ids'])} flat blocks")
print(f"Original column_list deleted: {result['deleted']}")
```

## Block Builders

Use builder functions to create Notion block structures programmatically.

```python
from notion_sync import (
    make_paragraph,
    make_heading,
    make_toggle,
    make_bulleted_list_item,
    make_numbered_list_item,
    make_to_do,
    make_code,
    make_callout,
    make_quote,
    make_divider,
)

# Simple blocks
blocks = [
    make_heading(1, "Chapter 1"),
    make_paragraph("This is a paragraph."),
    make_divider(),
    make_quote("A famous quote"),
]

# Blocks with nested content
toggle_block = make_toggle("Click to expand", children=[
    make_paragraph("Hidden content"),
    make_paragraph("More hidden content"),
])

# Lists
list_blocks = [
    make_bulleted_list_item("First item"),
    make_bulleted_list_item("Second item", children=[
        make_bulleted_list_item("Nested item")
    ]),
]

# Code blocks
code_block = make_code(
    "def hello():\n    print('Hello')",
    language="python"
)

# To-do items
todo_block = make_to_do("Buy groceries", checked=False)

# Callouts
callout_block = make_callout("Important note", icon="⚠️")
```

## Common Patterns

### Clearing a Page

```python
from notion_sync import get_notion_client, delete_all_blocks

client = get_notion_client()
page_id = "your-page-id"

# Delete all blocks from page
delete_all_blocks(client, page_id)
```

### Appending Blocks

```python
from notion_sync import get_notion_client, make_paragraph

client = get_notion_client()
page_id = "your-page-id"

# Append blocks to end of page
blocks = [
    make_paragraph("First paragraph"),
    make_paragraph("Second paragraph"),
]

result = client.append_blocks(page_id, blocks)
print(f"Created {len(result['results'])} blocks")

# Append after specific block
result = client.append_blocks(page_id, blocks, after="block-id")
```

### Batch Operations

```python
from notion_sync import get_notion_client

client = get_notion_client()

# Notion API limit: 100 blocks per request
# append_blocks handles batching automatically
large_block_list = [make_paragraph(f"Para {i}") for i in range(250)]

result = client.append_blocks(page_id, large_block_list)
# Automatically split into 3 requests: 100, 100, 50
```

### Rate Limiting and Request Tracking

```python
from notion_sync import get_notion_client

client = get_notion_client()

# Make some requests
blocks = fetch_page_blocks(client, page_id)
# ...more operations...

# Check how many requests were made
print(f"Total requests: {client.request_count}")

# Rate limiting is automatic:
# - Max 3 requests per second
# - 0.35s minimum between requests
# - Exponential backoff on 429 errors
```

### Error Handling

```python
from notion_sync import get_notion_client
from notion_client.errors import APIResponseError

client = get_notion_client()

try:
    blocks = fetch_page_blocks(client, page_id)
except APIResponseError as e:
    if e.code == "object_not_found":
        print("Page not found")
    elif e.code == "unauthorized":
        print("Invalid API token or missing permissions")
    else:
        print(f"API error: {e}")
```

---

## Real-World Use Cases

Complete working examples for common scenarios.

### 1. Documentation Sync (GitHub → Notion)

**Scenario:** Automatically sync your GitHub README to a Notion wiki page whenever you push changes.

```python
import requests
from notion_sync import (
    get_notion_client,
    fetch_page_blocks,
    generate_diff,
    execute_diff,
    make_heading,
    make_paragraph,
    make_code,
)

def fetch_github_readme(repo_owner: str, repo_name: str) -> str:
    """Fetch README.md from GitHub repository."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/readme"
    headers = {"Accept": "application/vnd.github.raw"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def markdown_to_notion_blocks(markdown: str) -> list[dict]:
    """Convert markdown to Notion blocks (simplified example)."""
    blocks = []
    for line in markdown.split("\n"):
        if line.startswith("# "):
            blocks.append(make_heading(1, line[2:]))
        elif line.startswith("## "):
            blocks.append(make_heading(2, line[3:]))
        elif line.startswith("```"):
            # In real impl, collect code block content
            blocks.append(make_code("# code here", language="python"))
        elif line.strip():
            blocks.append(make_paragraph(line))
    return blocks

def sync_readme_to_notion(
    repo_owner: str,
    repo_name: str,
    notion_page_id: str
) -> dict:
    """Sync GitHub README to Notion page."""
    client = get_notion_client()

    # Fetch README from GitHub
    print(f"Fetching README from {repo_owner}/{repo_name}...")
    markdown = fetch_github_readme(repo_owner, repo_name)

    # Convert to Notion blocks
    print("Converting markdown to Notion blocks...")
    new_blocks = markdown_to_notion_blocks(markdown)

    # Fetch current Notion state
    print("Fetching current Notion page...")
    current_blocks = fetch_page_blocks(client, notion_page_id)

    # Generate diff
    print("Generating diff...")
    ops = generate_diff(current_blocks, new_blocks)

    # Execute sync
    print("Syncing changes...")
    stats = execute_diff(client, ops, notion_page_id)

    print(f"✅ Sync complete!")
    print(f"   {stats['inserted']} blocks added")
    print(f"   {stats['updated']} blocks updated")
    print(f"   {stats['deleted']} blocks deleted")
    print(f"   {stats['kept']} blocks unchanged")

    return stats

# Usage in CI/CD pipeline
if __name__ == "__main__":
    sync_readme_to_notion(
        repo_owner="mvletter",
        repo_name="notion-sync-lib",
        notion_page_id="your-wiki-page-id"
    )
```

**Use in GitHub Actions:**

```yaml
# .github/workflows/sync-docs.yml
name: Sync Docs to Notion

on:
  push:
    paths:
      - 'README.md'
    branches: [main]

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install git+https://github.com/mvletter/notion-sync-lib.git requests
      - name: Sync to Notion
        env:
          NOTION_API_TOKEN: ${{ secrets.NOTION_API_TOKEN }}
        run: python scripts/sync_docs.py
```

---

### 2. Multi-Language Translation Workflow

**Scenario:** Maintain 10 language versions of documentation. Update master (NL) → automatically sync to all slaves (EN, DE, FR, etc.).

```python
import copy
from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    generate_recursive_diff,
    execute_recursive_diff,
)

def apply_translations(blocks: list[dict], translations: dict[str, str]) -> list[dict]:
    """Apply translations to block tree.

    Args:
        blocks: Original block tree with _children
        translations: Dict mapping block IDs to translated text

    Returns:
        Modified copy with translated text
    """
    translated = copy.deepcopy(blocks)

    def translate_recursive(block_list):
        for block in block_list:
            block_id = block.get("id")

            # Apply translation if available
            if block_id in translations:
                block_type = block["type"]

                # Handle text blocks
                if block_type in ("paragraph", "heading_1", "heading_2", "heading_3", "quote"):
                    block[block_type]["rich_text"] = [{
                        "type": "text",
                        "text": {"content": translations[block_id]}
                    }]

                # Handle to_do blocks (preserve checked state)
                elif block_type == "to_do":
                    checked = block[block_type].get("checked", False)
                    block[block_type]["rich_text"] = [{
                        "type": "text",
                        "text": {"content": translations[block_id]}
                    }]
                    block[block_type]["checked"] = checked

                # Handle callout blocks (preserve icon)
                elif block_type == "callout":
                    icon = block[block_type].get("icon")
                    block[block_type]["rich_text"] = [{
                        "type": "text",
                        "text": {"content": translations[block_id]}
                    }]
                    if icon:
                        block[block_type]["icon"] = icon

            # Recurse into children
            if "_children" in block:
                translate_recursive(block["_children"])

    translate_recursive(translated)
    return translated

def sync_translations(
    master_page_id: str,
    slave_pages: dict[str, str],
    translations_per_lang: dict[str, dict[str, str]]
) -> dict[str, dict]:
    """Sync translations from master to slave pages.

    Args:
        master_page_id: Source page ID (e.g., NL version)
        slave_pages: Dict mapping language code to page ID
        translations_per_lang: Dict mapping language to translations dict

    Returns:
        Dict with stats per language
    """
    client = get_notion_client()
    results = {}

    # Fetch master structure once
    print(f"Fetching master page structure...")
    master = fetch_blocks_recursive(client, master_page_id)
    print(f"Master has {len(master)} top-level blocks")

    # Sync to each slave
    for lang, slave_page_id in slave_pages.items():
        print(f"\nSyncing to {lang}...")

        # Get translations for this language
        translations = translations_per_lang.get(lang, {})
        if not translations:
            print(f"  ⚠️  No translations found for {lang}, skipping")
            continue

        # Fetch current slave state
        slave = fetch_blocks_recursive(client, slave_page_id)

        # Apply translations to master structure
        translated = apply_translations(master, translations)

        # Generate diff (UPDATE operations only)
        ops = generate_recursive_diff(slave, translated)

        # Execute sync
        stats = execute_recursive_diff(client, ops, dry_run=False)

        print(f"  ✅ {lang}: Updated {stats['updated']} blocks")
        results[lang] = stats

    return results

# Usage example
if __name__ == "__main__":
    # Define pages
    master_page = "abc123-master-nl"
    slaves = {
        "EN": "def456-slave-en",
        "DE": "ghi789-slave-de",
        "FR": "jkl012-slave-fr",
    }

    # Load translations (from file, database, API, etc.)
    translations = {
        "EN": {
            "block-id-1": "Welcome to our documentation",
            "block-id-2": "Getting started is easy",
            # ... more translations
        },
        "DE": {
            "block-id-1": "Willkommen zu unserer Dokumentation",
            "block-id-2": "Der Einstieg ist einfach",
            # ... more translations
        },
        # ...
    }

    # Sync
    results = sync_translations(master_page, slaves, translations)

    # Summary
    print("\n" + "="*60)
    print("Translation Sync Summary")
    print("="*60)
    for lang, stats in results.items():
        print(f"{lang}: {stats['updated']} blocks updated, {stats.get('skipped', 0)} skipped")
```

**Tips:**
- Use `generate_recursive_diff` for 10x faster syncing
- Preserve block structure (don't add/remove blocks in translations)
- Store translations in database/file for easy updates
- Schedule sync with cron job or webhook

---

### 3. Workspace Migration

**Scenario:** Migrate 500 pages from one Notion workspace to another, preserving all structure (toggles, columns, nested content).

```python
from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    append_blocks,
    extract_page_title,
)

def get_all_pages_in_database(client, database_id: str) -> list[dict]:
    """Get all pages from a Notion database."""
    pages = []
    has_more = True
    start_cursor = None

    while has_more:
        params = {"database_id": database_id, "page_size": 100}
        if start_cursor:
            params["start_cursor"] = start_cursor

        response = client.client.databases.query(**params)
        pages.extend(response["results"])

        has_more = response["has_more"]
        start_cursor = response.get("next_cursor")

    return pages

def create_page_in_workspace(
    client,
    parent_id: str,
    title: str,
    is_database: bool = False
) -> str:
    """Create a new page in target workspace.

    Args:
        client: Notion client for target workspace
        parent_id: Parent page or database ID
        title: Page title
        is_database: Whether parent is a database

    Returns:
        New page ID
    """
    parent = (
        {"database_id": parent_id}
        if is_database
        else {"page_id": parent_id}
    )

    properties = {
        "title": {
            "title": [{"text": {"content": title}}]
        }
    }

    response = client.client.pages.create(parent=parent, properties=properties)
    return response["id"]

def migrate_page(
    source_client,
    target_client,
    source_page_id: str,
    target_parent_id: str,
    is_database: bool = False
) -> str:
    """Migrate a single page from source to target workspace.

    Args:
        source_client: Client for source workspace
        target_client: Client for target workspace
        source_page_id: Page ID to migrate
        target_parent_id: Parent in target workspace
        is_database: Whether target parent is a database

    Returns:
        New page ID in target workspace
    """
    # Fetch source page
    print(f"Fetching page {source_page_id[:12]}...")
    source_page = source_client.get_page(source_page_id)
    title = extract_page_title(source_page)

    # Fetch all content (recursive)
    content = fetch_blocks_recursive(source_client, source_page_id)
    print(f"  Fetched {len(content)} top-level blocks")

    # Create page in target workspace
    print(f"Creating '{title}' in target workspace...")
    new_page_id = create_page_in_workspace(
        target_client,
        target_parent_id,
        title,
        is_database
    )

    # Append all content
    if content:
        print(f"  Copying content...")
        append_blocks(target_client, new_page_id, content)

    print(f"  ✅ Migrated: {title}")
    return new_page_id

def migrate_workspace(
    source_token: str,
    target_token: str,
    source_database_id: str,
    target_parent_id: str
) -> dict:
    """Migrate all pages from source database to target workspace.

    Args:
        source_token: API token for source workspace
        target_token: API token for target workspace
        source_database_id: Database ID to migrate from
        target_parent_id: Parent page/database ID in target

    Returns:
        Dict with migration stats
    """
    # Create clients for both workspaces
    import os
    os.environ["NOTION_API_TOKEN"] = source_token
    source_client = get_notion_client()

    os.environ["NOTION_API_TOKEN"] = target_token
    target_client = get_notion_client()

    # Get all source pages
    print("Fetching all pages from source database...")
    source_pages = get_all_pages_in_database(source_client, source_database_id)
    print(f"Found {len(source_pages)} pages to migrate\n")

    # Migrate each page
    migrated = []
    failed = []

    for i, page in enumerate(source_pages, 1):
        page_id = page["id"]
        print(f"[{i}/{len(source_pages)}] ", end="")

        try:
            new_id = migrate_page(
                source_client,
                target_client,
                page_id,
                target_parent_id,
                is_database=True
            )
            migrated.append({"source_id": page_id, "target_id": new_id})
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            failed.append({"page_id": page_id, "error": str(e)})

        print()

    # Summary
    print("="*60)
    print("Migration Summary")
    print("="*60)
    print(f"✅ Migrated: {len(migrated)} pages")
    print(f"❌ Failed: {len(failed)} pages")

    return {"migrated": migrated, "failed": failed}

# Usage
if __name__ == "__main__":
    results = migrate_workspace(
        source_token="secret_source_workspace_token",
        target_token="secret_target_workspace_token",
        source_database_id="source-database-id",
        target_parent_id="target-page-or-database-id"
    )
```

**Important Notes:**
- Uses separate clients with different tokens
- Preserves all nested content (toggles, columns, etc.)
- Handles rate limiting automatically
- Can resume if interrupted (save `migrated` list)

---

### 4. Template System

**Scenario:** Create 100 project pages from one template, customizing content for each project.

```python
import copy
from notion_sync import (
    get_notion_client,
    fetch_blocks_recursive,
    append_blocks,
    extract_page_title,
)

def replace_placeholders(blocks: list[dict], replacements: dict[str, str]) -> list[dict]:
    """Replace placeholder text in all blocks.

    Args:
        blocks: Block tree with _children
        replacements: Dict mapping placeholder to replacement text
                     Example: {"[PROJECT_NAME]": "My Project"}

    Returns:
        Modified copy with replacements applied
    """
    result = copy.deepcopy(blocks)

    def replace_recursive(block_list):
        for block in block_list:
            block_type = block.get("type")

            # Replace in text blocks
            if block_type in ("paragraph", "heading_1", "heading_2", "heading_3", "quote", "callout", "toggle"):
                rich_text = block[block_type].get("rich_text", [])
                for item in rich_text:
                    if item.get("type") == "text":
                        content = item["text"]["content"]
                        for placeholder, replacement in replacements.items():
                            content = content.replace(placeholder, replacement)
                        item["text"]["content"] = content

            # Recurse into children
            if "_children" in block:
                replace_recursive(block["_children"])

    replace_recursive(result)
    return result

def create_page_from_template(
    client,
    template_page_id: str,
    parent_id: str,
    page_title: str,
    replacements: dict[str, str]
) -> str:
    """Create a new page from template with custom replacements.

    Args:
        client: Notion client
        template_page_id: Template page ID
        parent_id: Parent page/database ID for new page
        page_title: Title for new page
        replacements: Placeholder replacements

    Returns:
        New page ID
    """
    # Fetch template content
    template_content = fetch_blocks_recursive(client, template_page_id)

    # Apply replacements
    customized_content = replace_placeholders(template_content, replacements)

    # Create new page
    response = client.client.pages.create(
        parent={"page_id": parent_id},
        properties={
            "title": {
                "title": [{"text": {"content": page_title}}]
            }
        }
    )
    new_page_id = response["id"]

    # Add customized content
    if customized_content:
        append_blocks(client, new_page_id, customized_content)

    return new_page_id

def generate_projects_from_template(
    template_page_id: str,
    parent_id: str,
    projects: list[dict]
) -> list[str]:
    """Generate multiple project pages from template.

    Args:
        template_page_id: Template page ID
        parent_id: Parent page for new projects
        projects: List of project dicts with 'name' and custom fields

    Returns:
        List of created page IDs
    """
    client = get_notion_client()
    created_pages = []

    print(f"Creating {len(projects)} projects from template...")
    print()

    for i, project in enumerate(projects, 1):
        print(f"[{i}/{len(projects)}] Creating: {project['name']}")

        # Build replacements from project data
        replacements = {
            "[PROJECT_NAME]": project["name"],
            "[PROJECT_ID]": project.get("id", "TBD"),
            "[PROJECT_OWNER]": project.get("owner", "Unassigned"),
            "[PROJECT_STATUS]": project.get("status", "Not Started"),
            "[PROJECT_DEADLINE]": project.get("deadline", "TBD"),
        }

        try:
            new_id = create_page_from_template(
                client,
                template_page_id,
                parent_id,
                project["name"],
                replacements
            )
            created_pages.append(new_id)
            print(f"  ✅ Created: {new_id[:12]}")
        except Exception as e:
            print(f"  ❌ Failed: {e}")

        print()

    print(f"✅ Created {len(created_pages)}/{len(projects)} pages")
    return created_pages

# Usage
if __name__ == "__main__":
    # Define projects
    projects = [
        {
            "name": "Website Redesign",
            "id": "PROJ-001",
            "owner": "Alice",
            "status": "In Progress",
            "deadline": "2026-03-15"
        },
        {
            "name": "Mobile App Launch",
            "id": "PROJ-002",
            "owner": "Bob",
            "status": "Planning",
            "deadline": "2026-06-01"
        },
        # ... 98 more projects
    ]

    created = generate_projects_from_template(
        template_page_id="your-template-page-id",
        parent_id="your-projects-parent-id",
        projects=projects
    )

    print(f"\nCreated {len(created)} project pages")
```

**Template Design Tips:**
- Use clear placeholders: `[PROJECT_NAME]`, `[DEADLINE]`, etc.
- Include default structure (headings, sections, checklists)
- Add toggle blocks for optional sections
- Use columns for layout consistency

---

### 5. Obsidian/Markdown Sync

**Scenario:** Sync your Obsidian vault to Notion daily, only updating changed files.

```python
import os
import hashlib
from pathlib import Path
from datetime import datetime
from notion_sync import (
    get_notion_client,
    fetch_page_blocks,
    generate_diff,
    execute_diff,
    make_heading,
    make_paragraph,
    make_code,
    make_divider,
)

def get_file_hash(file_path: Path) -> str:
    """Get MD5 hash of file contents."""
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def markdown_to_notion_blocks(markdown: str) -> list[dict]:
    """Convert markdown to Notion blocks (enhanced version)."""
    blocks = []
    lines = markdown.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Headers
        if line.startswith("# "):
            blocks.append(make_heading(1, line[2:].strip()))
        elif line.startswith("## "):
            blocks.append(make_heading(2, line[3:].strip()))
        elif line.startswith("### "):
            blocks.append(make_heading(3, line[4:].strip()))

        # Code blocks
        elif line.startswith("```"):
            code_lines = []
            language = line[3:].strip() or "plain text"
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append(make_code("\n".join(code_lines), language=language))

        # Dividers
        elif line.strip() in ("---", "***", "___"):
            blocks.append(make_divider())

        # Paragraphs
        elif line.strip():
            blocks.append(make_paragraph(line.strip()))

        i += 1

    return blocks

def find_or_create_notion_page(
    client,
    parent_id: str,
    title: str,
    existing_pages: dict[str, str]
) -> str:
    """Find existing page by title or create new one.

    Args:
        client: Notion client
        parent_id: Parent page ID
        title: Page title
        existing_pages: Dict mapping titles to page IDs

    Returns:
        Page ID (existing or newly created)
    """
    if title in existing_pages:
        return existing_pages[title]

    # Create new page
    response = client.client.pages.create(
        parent={"page_id": parent_id},
        properties={
            "title": {
                "title": [{"text": {"content": title}}]
            }
        }
    )
    return response["id"]

def sync_vault_to_notion(
    vault_path: Path,
    notion_parent_id: str,
    sync_state_file: Path,
    file_patterns: list[str] = None
) -> dict:
    """Sync Obsidian vault to Notion.

    Args:
        vault_path: Path to Obsidian vault
        notion_parent_id: Parent page ID in Notion
        sync_state_file: File to store sync state (file hashes)
        file_patterns: List of glob patterns to include (default: ["*.md"])

    Returns:
        Dict with sync stats
    """
    client = get_notion_client()

    # Load previous sync state
    sync_state = {}
    if sync_state_file.exists():
        import json
        with open(sync_state_file) as f:
            sync_state = json.load(f)

    # Find markdown files
    if not file_patterns:
        file_patterns = ["*.md"]

    files_to_sync = []
    for pattern in file_patterns:
        files_to_sync.extend(vault_path.rglob(pattern))

    print(f"Found {len(files_to_sync)} markdown files")
    print()

    # Get existing Notion pages (to avoid duplicates)
    # In production, query database or maintain mapping file
    existing_pages = {}  # title -> page_id mapping

    # Sync each file
    stats = {"synced": 0, "skipped": 0, "created": 0, "updated": 0}

    for file_path in files_to_sync:
        file_name = file_path.stem  # filename without extension
        file_key = str(file_path.relative_to(vault_path))

        # Check if file changed
        current_hash = get_file_hash(file_path)
        previous_hash = sync_state.get(file_key)

        if current_hash == previous_hash:
            print(f"⏭️  Skipping (unchanged): {file_name}")
            stats["skipped"] += 1
            continue

        print(f"🔄 Syncing: {file_name}")

        # Read and convert
        markdown = file_path.read_text(encoding='utf-8')
        new_blocks = markdown_to_notion_blocks(markdown)

        # Find or create page
        page_id = find_or_create_notion_page(
            client,
            notion_parent_id,
            file_name,
            existing_pages
        )

        # Sync content
        current_blocks = fetch_page_blocks(client, page_id)
        ops = generate_diff(current_blocks, new_blocks)
        result = execute_diff(client, ops, page_id)

        # Update sync state
        sync_state[file_key] = current_hash

        if not existing_pages.get(file_name):
            stats["created"] += 1
            print(f"   ✅ Created new page")
        else:
            stats["updated"] += 1
            print(f"   ✅ Updated: {result['inserted']} added, {result['updated']} modified")

        stats["synced"] += 1
        existing_pages[file_name] = page_id
        print()

    # Save sync state
    import json
    with open(sync_state_file, 'w') as f:
        json.dump(sync_state, f, indent=2)

    print("="*60)
    print("Sync Summary")
    print("="*60)
    print(f"✅ Synced: {stats['synced']} files")
    print(f"   📝 Created: {stats['created']} pages")
    print(f"   🔄 Updated: {stats['updated']} pages")
    print(f"⏭️  Skipped: {stats['skipped']} files (unchanged)")

    return stats

# Usage
if __name__ == "__main__":
    sync_vault_to_notion(
        vault_path=Path("~/Documents/ObsidianVault").expanduser(),
        notion_parent_id="your-notion-parent-page-id",
        sync_state_file=Path(".sync_state.json"),
        file_patterns=["*.md", "!templates/*.md"]  # Exclude templates
    )
```

**Schedule with cron:**

```bash
# Sync daily at 2 AM
0 2 * * * /usr/bin/python3 /path/to/sync_obsidian.py
```

---

## Next Steps

- See [API Reference](api-reference.md) for complete function documentation
- See [docs/pitfalls.md](pitfalls.md) for common mistakes to avoid
- See [Development Guide](development.md) for contributing
