# Feature: Test Scripts

> Status: In Progress
> Created: 2026-01-18
> Branch: `feature/test-scripts`

---
## Human-Readable Context (for non-coders)
---

## What we're solving

Scripts die checken of de library werkt tegen echte Notion pagina's. Maakt een test pagina, vult die, wijzigt content, kloot het, en checkt of alles klopt.

---
## Filled by /research
---

## Problem

**What**: Nu alleen unit tests voor pure functions. Handmatig testen tegen Notion kost tijd.

**Who**: Mark die releases valideert, developers die features toevoegen

**Evidence**:
- TEST_PAGE_ID staat in .env maar wordt niet gebruikt
- Handmatig testen kost tijd
- Bij nieuwe features geen check of het echt werkt

**Current workaround**: Handmatig testen

## Dependencies

**Affected areas**:
- `tests/` - Nieuwe test scripts

**Risks**:
- Tests maken echte API calls (langzamer)
- Rate limiting kan tests vertragen

**Security considerations**:
- NOTION_API_TOKEN nodig
- Test pagina's in test workspace (niet productie)
- Cleanup na tests

## Test opzet

**Simpel**:
1. Maak test pagina aan
2. Vul met blocks
3. Wijzig content (test diff)
4. Kloon pagina
5. Check dat master en clone gelijk zijn

**Structuur**:
```
tests/
├── test_columns.py      # Bestaand (pure functions)
├── test_width_ratio.py  # Bestaand (pure functions)
└── test_live.py         # Nieuw (echte Notion calls)
```

## Wat testen

**Start simpel**:
1. Pagina maken met blocks
2. Blocks ophalen (fetch)
3. Content wijzigen (diff)
4. Pagina klonen
5. Check master = clone

**Later**:
- Columns
- Nested blocks
- Edge cases

---
## Filled by /plan
---

## Solution

**Approach**: Simpel pytest script dat echte Notion calls maakt

**Details**:
- 1 bestand: `test_live.py`
- Pytest fixture voor setup/cleanup
- Skip als geen NOTION_API_TOKEN

**Alternatives considered**:
- Mocks - Nee: we willen juist echte API testen
- Handmatig - Nee: niet herhaalbaar

**Good enough**:
- Start met basis flow (make, fetch, edit, clone)
- Uitbreiden kan later

## Scope

**Must have**:
- [x] Fixture: pagina maken/opruimen
- [x] Test: blocks maken
- [x] Test: blocks ophalen
- [x] Test: diff/sync
- [x] Test: clone + vergelijk

**Won't have**:
- Performance metrics
- Mocks
- Complexe edge cases (nu)

## Test Scenarios

### Happy path

**1. Create en fetch**
- Maak pagina "Test Master" met:
  - Heading 1: "Test Page"
  - Paragraph: "Initial content"
- Fetch blocks terug → Assert: 2 blocks, types kloppen, content klopt

**2. Update via diff**
- Start met pagina met paragraph "Version 1"
- Wijzig naar "Version 2" via diff
- Assert: 1 UPDATE operatie (geen DELETE + INSERT)
- Fetch terug → Content is "Version 2"

**3. Clone en sync**
- Maak master met heading + paragraph
- Clone → "Test Clone"
- Assert: Clone heeft identieke blocks
- Wijzig master paragraph naar "Updated"
- Pas zelfde wijziging toe op clone
- Fetch beide → Assert: master blocks == clone blocks

### Edge cases

**4. Lege pagina**
- Maak pagina zonder blocks
- Fetch → Assert: empty list, geen error

**5. Nested blocks**
- Maak toggle met 2 nested paragraphs
- Fetch recursive → Assert: toggle heeft _children met 2 items

### Error handling

**6. Geen token**
- NOTION_API_TOKEN niet gezet → Test skips met duidelijke message

**7. Cleanup werkt altijd**
- Test faalt middenin → Fixture ruimt pagina toch op

**Approved**: [x] Yes

## Files

**Created**:
- `tests/conftest.py` - Shared fixtures and helpers
- `tests/test_live_basic.py` - Basic operations (create, fetch, nested)
- `tests/test_live_diff.py` - Diff operations (UPDATE, DELETE, INSERT, REPLACE)
- `tests/test_live_clone.py` - Clone and sync tests

**Planned**:
- `tests/test_live_columns.py` - Column operations (not yet implemented)

## Tasks

### T1: Setup fixture
- **Files**: `tests/test_live.py`
- **Depends**: none
- **Scenarios**: #6 (token check), #7 (cleanup)
- **Test**: Fixture maakt test pagina aan en ruimt op
- **Done**:
  - Fixture `test_page` maakt pagina under TEST_PAGE_ID
  - Cleanup in finally (altijd)
  - Skip zonder NOTION_API_TOKEN

### T2: Create en fetch test
- **Files**: `tests/test_live.py`
- **Depends**: T1
- **Scenarios**: #1 (create/fetch), #4 (lege pagina), #5 (nested)
- **Test**: test_create_and_fetch(), test_empty_page(), test_nested_blocks()
- **Done**:
  - Kan pagina maken met blocks
  - Fetch geeft correcte blocks terug
  - Nested blocks hebben _children

### T3: Diff test
- **Files**: `tests/test_live.py`
- **Depends**: T1
- **Scenarios**: #2 (update via diff)
- **Test**: test_diff_update()
- **Done**:
  - Generate diff correcte operations
  - Execute diff werkt
  - Content na diff klopt

### T4: Clone test
- **Files**: `tests/test_live.py`
- **Depends**: T1, T3
- **Scenarios**: #3 (clone en sync)
- **Test**: test_clone_and_sync()
- **Done**:
  - Kan pagina clonen
  - Clone en master identiek na wijzigingen
  - Recursive diff werkt voor vergelijking

## Rollback

Delete `tests/test_live_*.py` and `tests/conftest.py`

---
## Progress
---

**Completed**:
- [x] T1-T4: Basic test setup (fixture, create/fetch, diff UPDATE, clone)
- [x] Extended diff operations: DELETE, INSERT, REPLACE
- [x] Restructured: Split into modules with shared helpers
- [x] Column tests: create_column_list, unwrap_column_list
- [x] **Fixed auto-sync bug**: Changed from `generate_recursive_diff` to `generate_diff`
- [x] **Added logging**: Full pytest logging with verification after each sync
- [x] **Fixed nested blocks**: `_prepare_block_for_api` now converts `_children` recursively
- [x] **Common block types**: Lists, to_do, code, quote, callout, divider
- [x] **Advanced operations**: INSERT middle, DELETE middle, nested operations
- [x] **Rich text formatting**: Bold, italic, links
- [x] **User action tests**: Manual reorder, delete all verification
- [x] **25 tests total in 6 files** (23 automated + 2 manual user action tests)

**Test coverage by file**:

`test_live_basic.py` (2 tests):
- ✅ Test #1: Create & fetch blocks (heading, paragraph)
- ✅ Test #2: Nested blocks (toggle with children)

`test_live_diff.py` (4 tests):
- ✅ Test #3: Diff UPDATE (paragraph text change)
- ✅ Test #5: Diff DELETE (remove block)
- ✅ Test #6: Diff INSERT (add new block at end)
- ✅ Test #7: Diff REPLACE (change block type)

`test_live_columns.py` (2 tests):
- ✅ Test #9: Columns: create 2-column layout with width_ratio
- ✅ Test #10: Columns: unwrap to flat blocks

`test_live_block_types.py` (7 tests):
- ✅ Test #11: bulleted_list (3 items)
- ✅ Test #12: numbered_list (2 items)
- ✅ Test #13: to_do (checked and unchecked)
- ✅ Test #14: code (python and javascript with language property)
- ✅ Test #15: quote
- ✅ Test #16: callout (with emoji icon)
- ✅ Test #17: divider

`test_live_advanced.py` (8 tests):
- ✅ Test #18: INSERT middle (block tussen bestaande)
- ✅ Test #19: DELETE middle (block uit midden verwijderen)
- ✅ Test #20: UPDATE nested content (child in toggle wijzigen via API)
- ✅ Test #21: INSERT child in toggle (append child via API)
- ✅ Test #22: DELETE child from toggle (delete child via API)
- ✅ Test #23: Deep nesting (3 levels: toggle → toggle → paragraph)
- ✅ Test #24: Rich text formatting (bold, italic, link)
- ✅ Test #25: Bulk INSERT (15 blocks in 1 operation)

`test_live_zz_user_actions.py` (2 tests - require manual user actions):
- ✅ Test #98: USER REORDER (user manually reorders blocks A,B,C → C,A,B, then sync to clone)
- ✅ Test #99: DELETE ALL (user deletes all blocks, verify both pages empty)

**Auto-sync mechanism**:
- ✅ Works correctly with `generate_diff` + `execute_diff`
- ✅ Logs block counts and operation counts
- ✅ Verifies clone has same number of blocks after sync
- ✅ Handles nested blocks (toggles, column_list) correctly
- ✅ Skips auto-sync for user action tests (#98, #99) which handle syncing manually

**Not yet tested**:
- ❌ Bulk operations (>100 blocks) - currently tested up to 15
- ❌ generate_recursive_diff + execute_recursive_diff (UPDATE-only workflow for translations)
- ❌ Empty content edge cases
- ❌ Tables (table + table_row blocks)
- ❌ Bookmarks
- ❌ Images/files
