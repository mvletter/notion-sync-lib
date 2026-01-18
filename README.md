# notion-sync-lib

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Sync Notion pages like Git commits.** Smart content-based diffing, automatic rate limiting, zero headaches.

Not another CRUD wrapper—this is a **sync engine** that understands your content and makes minimal changes automatically.

```python
from notion_sync import get_notion_client, generate_diff, execute_diff

client = get_notion_client()
ops = generate_diff(current_blocks, new_blocks)
execute_diff(client, ops, page_id)  # Magic happens ✨
```

---

## What Can You Build With This?

### 📝 Keep Your Docs in Sync
Sync your GitHub README to Notion automatically. No more copy-paste. Update once, sync everywhere.

```python
# Your CI pipeline
markdown = fetch_github_readme()
blocks = markdown_to_notion(markdown)
sync_to_notion(page_id, blocks)  # Only updates what changed
```

### 🌍 Translation Workflows
Maintain 20 language versions of your docs. Update master → slaves sync in seconds, not hours.

```python
# Example: sync NL master to EN/DE/FR translations
for lang in ["EN", "DE", "FR"]:
    ops = generate_recursive_diff(master, translate(master, lang))
    execute_recursive_diff(client, ops)  # 10x faster than full sync
```

### 🏢 Workspace Migration
Moving 500 pages to a new workspace? Clone everything with preserved structure—toggles, columns, nested content, all intact.

```python
# Clone entire workspace
for page_id in source_pages:
    content = fetch_blocks_recursive(client_A, page_id)
    clone_to_workspace_B(content)  # All nested content preserved
```

### 📋 Template System
Generate 100 project pages from one template. Replace placeholders, customize layouts, done.

```python
# Create project pages from template
template = fetch_blocks_recursive(client, template_page)
for project in projects:
    customized = replace_placeholders(template, project)
    create_page(project.name, customized)
```

### 📓 Obsidian/Markdown Sync
Daily sync from your markdown notes to Notion. Only changed files get updated.

```python
# Sync markdown vault
for note in obsidian_vault:
    if note.changed_today():
        sync_to_notion(note)  # Smart diff = minimal API calls
```

### 🤖 Automated Reports
Generate weekly reports with 3-column layouts, charts, and metrics—all programmatically.

```python
# Build complex layouts
columns = [
    {"children": [make_heading(2, "Summary"), *summary_blocks], "width_ratio": 0.5},
    {"children": [make_heading(2, "Metrics"), *metrics], "width_ratio": 0.25},
    {"children": [make_heading(2, "Charts"), chart], "width_ratio": 0.25}
]
create_column_list(client, report_page, columns)
```

---

## Why This Library?

### 🧠 Smart Diff Engine (Like Git for Notion)

Traditional approach: Match blocks by position → Everything breaks when you add/remove a block.

**Our approach:** Match blocks by content → Robust to any structural change.

```python
# You have: [A, B, C]
# You want: [A, X, B, C, D]

# Traditional: "Replace B→X, C→B, add C, add D" (4 operations)
# Smart diff: "Insert X after A, append D" (2 operations)
```

**Result:** Fewer API calls = faster syncs + lower rate limit risk.

### ⚡ Two Sync Modes for Different Needs

**Structural Sync** (`generate_diff`)
- Add, remove, reorder blocks freely
- Content-based matching with SequenceMatcher
- Use for: Documentation sync, markdown conversion, testing

**Content-Only Sync** (`generate_recursive_diff`)
- Update text in identical structures
- 10x faster (only UPDATE operations)
- Use for: Translation workflows, bulk text changes

### 🛡️ Production-Ready from Day One

- **Automatic rate limiting**: 3 req/sec with exponential backoff on 429 errors
- **Smart batching**: Handles 1000+ blocks automatically (100-block API limit)
- **Resilient execution**: Skips archived blocks, handles edge cases
- **Request tracking**: Monitor API usage with `client.request_count`

### 🏗️ Build Complex Layouts Easily

```python
from notion_sync import make_paragraph, make_heading, make_toggle, create_column_list

# Create nested structures
page_content = [
    make_heading(1, "Project Overview"),
    make_toggle("Details", children=[
        make_paragraph("Hidden content..."),
        make_bulleted_list_item("Nested item")
    ])
]

# Create column layouts with width ratios
columns = [
    {"children": [make_paragraph("Left")], "width_ratio": 0.7},
    {"children": [make_paragraph("Right")], "width_ratio": 0.3}
]
create_column_list(client, page_id, columns)
```

---

## Installation

```bash
pip install git+https://github.com/mvletter/notion-sync-lib.git
```

Set your Notion API token:
```bash
export NOTION_API_TOKEN=secret_xxx
```

Or create a `.env` file:
```
NOTION_API_TOKEN=secret_xxx
```

---

## Quick Examples

### Sync Markdown to Notion

```python
from notion_sync import get_notion_client, fetch_page_blocks, generate_diff, execute_diff

def sync_markdown_to_notion(markdown: str, page_id: str):
    """Convert markdown and sync to Notion in one go."""
    client = get_notion_client()

    # Convert markdown to Notion blocks (your converter)
    new_blocks = markdown_to_notion_blocks(markdown)

    # Fetch current state and generate diff
    current_blocks = fetch_page_blocks(client, page_id)
    ops = generate_diff(current_blocks, new_blocks)

    # Execute minimal changes
    stats = execute_diff(client, ops, page_id)
    print(f"✅ Synced: {stats['inserted']} added, {stats['updated']} updated, {stats['deleted']} removed")
```

### Translation Workflow (Content-Only Updates)

Perfect for maintaining translated pages:

```python
from notion_sync import get_notion_client, fetch_blocks_recursive, generate_recursive_diff, execute_recursive_diff

client = get_notion_client()

# Fetch master page structure
master = fetch_blocks_recursive(client, master_page_id)

# Apply translations (preserve structure!)
translated = apply_translations(master, translations)

# Update only changed text (10x faster)
ops = generate_recursive_diff(master, translated)
stats = execute_recursive_diff(client, ops)

print(f"✅ Updated {stats['updated']} blocks")
```

### Clone Page to Another Workspace

```python
from notion_sync import get_notion_client, fetch_blocks_recursive, append_blocks

# Fetch from source workspace
client_A = get_notion_client()  # Uses token from workspace A
content = fetch_blocks_recursive(client_A, source_page_id)

# Clone to target workspace
client_B = get_notion_client()  # Uses token from workspace B
new_page_id = create_page_in_workspace_B(title)
append_blocks(client_B, new_page_id, content)

print(f"✅ Cloned page with {len(content)} blocks")
```

### Preview Changes Before Applying

```python
from notion_sync import generate_diff, format_diff_preview, execute_diff

ops = generate_diff(current_blocks, new_blocks)

# Show human-readable preview
print(format_diff_preview(ops))
# Output:
# ============================================================
# Diff Preview
# ============================================================
# Summary: 2 new, 1 modified, 0 replaced, 1 deleted, 5 unchanged
# ------------------------------------------------------------
#
# Changes:
#
# + [NEW] paragraph
#   "This is new content"
#   -> Will be inserted at position 3
#
# ~ [MODIFIED] heading_1
#   "Old Title" -> "New Title"
#   -> Will update block abc123...

# Execute after confirmation
if confirm():
    stats = execute_diff(client, ops, page_id)
```

---

## When to Use Which Diff?

| Your Situation | Use This | Why |
|---------------|----------|-----|
| Syncing markdown/docs to Notion | `generate_diff` | Content may be added/removed/reordered |
| Translating existing pages | `generate_recursive_diff` | Structure identical, only text changes |
| Migrating workspaces | `generate_diff` | Flexible, handles any changes |
| Bulk text updates (find/replace) | `generate_recursive_diff` | 10x faster, updates only changed blocks |
| Building pages programmatically | Block builders + `append_blocks` | Direct construction |
| Testing/prototyping | `generate_diff` + `dry_run=True` | Preview mode |

**Pro tip:** When in doubt, use `generate_diff`. It handles everything.

---

## Features

### Core Capabilities
- ✅ **Smart content-based diffing** - Minimal API calls, like Git for Notion
- ✅ **Two sync modes** - Structural (flexible) + Content-only (fast)
- ✅ **Automatic rate limiting** - 3 req/sec with exponential backoff
- ✅ **Recursive fetching** - Get entire page trees with nested content
- ✅ **Smart batching** - Handles 1000+ blocks automatically

### Advanced Features
- ✅ **Column layout support** - Create/read/unwrap with width ratios
- ✅ **Block builders** - 10+ block types (paragraphs, headings, toggles, code, etc.)
- ✅ **Text extraction** - 30+ block types → plain text
- ✅ **TypedDict returns** - Full IDE autocomplete
- ✅ **Dry-run mode** - Preview changes before applying
- ✅ **Request tracking** - Monitor API usage

### Production-Ready
- ✅ **Error resilience** - Handles archived blocks, API errors gracefully
- ✅ **Type safety** - Full type hints (passes mypy strict mode)
- ✅ **Comprehensive tests** - 25 integration tests
- ✅ **Well documented** - Usage guide + API reference + pitfalls doc

---

## Real-World Use Cases

| Use Case | Complexity | Demand | Key Feature |
|----------|-----------|--------|-------------|
| 📝 Documentation sync (GitHub → Notion) | Medium | 🔥🔥🔥 Very High | Smart diff |
| 🌍 Multi-language content management | High | 🔥🔥🔥 Very High | Recursive diff |
| 🏢 Workspace migration | Medium | 🔥🔥 High | Recursive fetch |
| 📋 Template system | Low | 🔥🔥 High | Block builders |
| 📓 Markdown sync (Obsidian/Roam) | Medium | 🔥🔥 High | Smart diff |
| 🔄 Bulk content transformation | High | 🔥 Medium | Recursive diff |
| 🤖 Automated page layouts | Low | 🔥 Medium | Column builders |
| 💾 Backup system | Low | 🔥 Medium | Text extraction |
| 📅 Meeting notes automation | Low | 🔥🔥 High | Block builders |

---

## What Makes This Different?

**Other Notion libraries:**
```python
# Manual position tracking, full page replacement
for i, block in enumerate(new_blocks):
    client.update_block(old_blocks[i].id, block)  # Breaks if count differs
```

**This library:**
```python
# Content-based matching, minimal operations
ops = generate_diff(old_blocks, new_blocks)
execute_diff(client, ops, page_id)  # Handles add/remove/reorder automatically
```

**Result:** Your code works when blocks are added/removed/reordered. No manual tracking.

---

## Documentation

📖 **[Usage Guide](docs/usage-guide.md)** - Complete examples and patterns
📚 **[API Reference](docs/api-reference.md)** - Full API documentation
⚠️ **[Common Pitfalls](docs/pitfalls.md)** - Mistakes to avoid
🛠️ **[Development Guide](docs/development.md)** - Contributing and testing

---

## Requirements

- Python 3.10+
- Notion API token ([get one here](https://developers.notion.com/))

---

## Contributing

We welcome contributions! See [Development Guide](docs/development.md) for setup and testing.

Quick start:
```bash
git clone https://github.com/mvletter/notion-sync-lib.git
cd notion-sync-lib
pip install -e ".[dev]"
pytest -v
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Credits

Built by [Mark Vletter](https://github.com/mvletter) for handling large-scale Notion translation workflows at [Voys](https://www.voys.nl/).

Inspired by Git's diff algorithm and the need for a production-ready Notion sync tool.

---

**⭐ Star this repo if it saved you time!**

**🐛 Found a bug?** [Open an issue](https://github.com/mvletter/notion-sync-lib/issues)

**💡 Have a use case?** [Share it in discussions](https://github.com/mvletter/notion-sync-lib/discussions)
