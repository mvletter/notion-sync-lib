# Inbox

> Unprocessed items. Review regularly and process to the right place.

## How to use

**Adding items:**
- Say `bug` or `idea` during any session
- Run `/wrap` at session end to catch missed items

**Processing items:**
- Bug fixed → `/wrap` auto-detects and marks as resolved
- Critical bug fixed → run `/retro [description]` → adds lesson to pitfalls.md
- Idea ready → run `/research [idea]` → creates full feature spec → mark as processed

**Idea types:**
- Simple idea → one-liner in Ideas table
- Discussed idea → one-liner + link to mini spec: `[idea] → [spec](features/name.md)`

---

## Bugs

| # | Date | Description | Severity | Status |
|---|------|-------------|----------|--------|
| 1 | 2026-01-18 | Auto-sync fixture niet werkend - clone blijft leeg terwijl master content krijgt, geen errors zichtbaar | high | open |

**Severity:** low, medium, high, critical

---

## Ideas

| # | Date | Idea | Priority |
|---|------|------|----------|
| | | | |

**Priority:** low, medium, high

---

## Processed

> Items resolved or converted to features. Kept for reference.

| # | Type | Priority | Original | Resolution | Date |
|---|------|----------|----------|------------|------|
| 1 | Bug | high | API timeout on large requests | Fixed, see pitfalls.md#api-timeout | 2025-01-10 |
| 2 | Idea | medium | Dark mode support | /research completed → docs/features/dark-mode.md | 2025-01-12 |
| 3 | Idea | medium | Drag-drop linking → [spec](features/drag-drop.md) | /research completed → expanded spec | 2025-01-15 |

*(Examples above - remove when adding real items)*
