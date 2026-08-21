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

## api-append-cannot-prepend

**Trigger:** Adding an op type to `execute_diff`, or deciding whether an op needs `_execute_reorder`

`append_block_children` can only insert AFTER an existing block. `after=None`
appends to the END of the parent — Notion has no prepend. So any op that
**creates** a block cannot place it before a block that is staying put; only a
full delete-and-reinsert (`_execute_reorder`) can.

The trap is classifying ops by "does it touch an existing block" instead of
"does it create one". REPLACE touches an existing block (deletes it) *and*
creates a new one, so it looks like an anchor and behaves like an insert.

❌ Wrong:
```python
# REPLACE is treated as a position anchor because it has a notion_block_id
if op["op"] in ("KEEP", "UPDATE", "REPLACE"):
    seen_anchor = True
# ops = [REPLACE A->X, KEEP B]  → delete A, append X at END, keep B
# Result: [B, X] — the whole page rotates
```

✅ Right:
```python
# Only ops that LEAVE an existing block in place are anchors
if op["op"] in ("KEEP", "UPDATE"):
    seen_anchor = True
elif op["op"] in ("INSERT", "REPLACE"):   # both create a block
    if not seen_anchor and any(o["op"] in ("KEEP", "UPDATE") for o in ops[i + 1:]):
        return True                        # must use _execute_reorder
    seen_anchor = True
```

**Rule:** an op is a position anchor only if it leaves an existing block where it
already is (KEEP, UPDATE). Anything that creates a block (INSERT, REPLACE) is
subject to the no-prepend limitation.

**Why it bites silently:** nothing errors. The sync reports success, block counts
match, no content is lost — the page is just in the wrong order. Assert the
*order* (`tests/test_reorder_replace_anchor.py`), not just the ops or counts.
A live 33-block help-center page rotated twice before this was found
(SPEC-ORDER-001, 2026-08-21).

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

## api-update-sanitization-spread

**Trigger:** Adding UPDATE behavior for a new block type, editing sanitization in execute_diff or execute_recursive_diff

`_sanitize_for_update()` in `diff.py` is the **single source of truth** for all block UPDATE sanitization.
Both `execute_diff` and `execute_recursive_diff` call it.

If you add a special UPDATE case inline in one function instead, the other function won't get it — and you'll have diverged behavior that's hard to notice until a rare edge case fires.

❌ Wrong:
```python
# In execute_recursive_diff only:
if block_type == "my_new_block":
    clean.pop("some_field", None)
    update_data = {block_type: clean}

# execute_diff still uses old path → inconsistent behavior
```

✅ Right:
```python
# In _sanitize_for_update() in diff.py:
if block_type == "my_new_block":
    clean.pop("some_field", None)
    clean.pop("children", None)
    return {block_type: clean}

# Both execute_diff and execute_recursive_diff automatically pick it up
```

**AI-CONTEXT:** See `src/notion_sync/diff.py` → `_sanitize_for_update()`

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
