# Pitfalls

> Mistakes we've made. Don't repeat them.

## How to use

**When writing code**: Check if your pattern matches any trigger below
**When stuck**: Read this file fully
**Before commit**: Verify no pitfall patterns in your code
**In code**: Add `// AI-CONTEXT: See docs/pitfalls.md#[category]-[name]`

## Anchor format

Use category-prefixed anchors from the start:
- `#async-unhandled-promise`
- `#security-sql-injection`
- `#database-missing-index`

This enables splitting later without changing code references.

## Categories

- **async** - Promises, timing, race conditions
- **security** - Auth, validation, injection
- **database** - Queries, transactions, migrations
- **api** - HTTP, responses, error handling
- **state** - Caching, consistency, side effects
- **error** - Exception handling, logging, fail-fast

---

## error-catch-all

**Trigger:** try/catch blocks, exception handling, error suppression

AI tends to generate catch-all handlers that swallow errors, making code "feel stable" while hiding problems.

❌ Wrong:
```csharp
try {
    await ProcessOrder(order);
} catch (Exception ex) {
    Logger.Log(ex);  // Swallows error, caller thinks success
}
```

✅ Right:
```csharp
try {
    await ProcessOrder(order);
} catch (Exception ex) {
    Logger.Log(ex);
    throw;  // Log AND re-throw
}
```

**Also:** Use guard clauses to validate inputs early. Return/throw immediately on invalid state.

---

## api-wrong-diff-function

**Trigger:** Using generate_diff or generate_recursive_diff, syncing pages

When syncing between pages, choosing the wrong diff function returns 0 operations even though pages differ.

❌ Wrong:
```python
# Pages have DIFFERENT structures (master has blocks, clone is empty)
master_blocks = fetch_blocks_recursive(client, master_id)
clone_blocks = fetch_blocks_recursive(client, clone_id)

# generate_recursive_diff assumes IDENTICAL structure - returns 0 ops!
ops = generate_recursive_diff(clone_blocks, master_blocks)
# Result: 0 operations, nothing syncs
```

✅ Right:
```python
# Pages have different structures → Use generate_diff
master_blocks = fetch_blocks_recursive(client, master_id)
clone_blocks = fetch_blocks_recursive(client, clone_id)

# generate_diff handles INSERT/DELETE/UPDATE/REPLACE
ops = generate_diff(clone_blocks, master_blocks)
execute_diff(client, ops, clone_id, dry_run=False)
```

**Rule:**
- Different structures (different blocks)? → `generate_diff` + `execute_diff`
- Identical structure (same IDs, only text changes)? → `generate_recursive_diff` + `execute_recursive_diff`

---

## api-nested-blocks-format

**Trigger:** Inserting blocks with children (toggles, column_list), _prepare_block_for_api, API validation errors

Blocks from `fetch_blocks_recursive` use `_children` at root level (internal format).
Notion API requires children inside the block type property (e.g., `toggle.children`).

If you just remove `_children` without converting, nested blocks fail with:
```
body.children[0].column_list.children should be defined, instead was `undefined`.
```

❌ Wrong:
```python
def _prepare_block_for_api(block):
    cleaned = copy.deepcopy(block)
    cleaned.pop("_children", None)  # Just removes, doesn't convert!
    return cleaned

# Result: toggle/column_list has no children in API format → 400 error
```

✅ Right:
```python
def _prepare_block_for_api(block):
    cleaned = copy.deepcopy(block)
    children = cleaned.pop("_children", None)

    if children:
        block_type = cleaned.get("type")
        if block_type and block_type in cleaned:
            # Recursively convert children
            prepared = [_prepare_block_for_api(child) for child in children]
            cleaned[block_type]["children"] = prepared  # Correct API format

    return cleaned
```

**Why this matters:**
- Toggle blocks: `_children` → `toggle.children`
- Column_list: `_children` → `column_list.children` (where each child is a column)
- Column blocks: `_children` → `column.children`

**Prevention:**
Always convert recursively when preparing blocks from `fetch_blocks_recursive` for API insertion.

---

---

## Templates (remove when adding real entries)

### async-[name]

**Trigger:** [Pattern that triggers this pitfall]

❌ Wrong:
```
[Code that causes problems]
```

✅ Right:
```
[Code that works correctly]
```

### security-[name]

...

---

## Adding new pitfalls

**Via /retro command (recommended):**
Use `/retro [description]` after a bug. This generates the correct format automatically.

**Manually:**
1. Add entry with category-prefixed anchor
2. Show wrong/right code, minimal explanation
3. Add trigger to CLAUDE.md
4. Add AI-CONTEXT comment in fixed code

## Entry format (from /retro)

Entries from `/retro` use plain language:

```markdown
---

## [category]-[short-name]

**Severity:** low | medium | high | critical
**Date:** YYYY-MM-DD

**What went wrong:**
[Description in plain language - what did the user see?]

**Why this could happen:**
[What check or test was missing?]

**Prevention:**
[One concrete, verifiable action]

**Trigger:** [When should AI think about this?]
```

**Severity levels:**
- **low** - Annoying but no damage
- **medium** - Feature doesn't work well
- **high** - Data lost or corrupted
- **critical** - Security or completely broken

---

## Scaling

**When to split:** >50 entries OR >15k tokens OR hard to scan

**How to split:**

1. Create `docs/pitfalls/` directory
2. Move entries to category files: `async.md`, `security.md`, etc.
3. Keep this file as index (see below)
4. **Code references don't change** - anchors stay the same

**This file becomes index:**

```markdown
# Pitfalls Index

Categories:
- [async](pitfalls/async.md) - Promises, timing, race conditions
- [security](pitfalls/security.md) - Auth, validation, injection
- [database](pitfalls/database.md) - Queries, transactions

Anchor format: `#[category]-[name]`
Files location: `docs/pitfalls/[category].md`
```

**After split, AI-CONTEXT still works:**
```
// AI-CONTEXT: See docs/pitfalls.md#security-sql-injection
→ AI reads index, finds security.md, locates #sql-injection
```
