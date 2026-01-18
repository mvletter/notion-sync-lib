# [Project Name]

## Voice

**When working (internal):** Use technical terms freely (branch, merge, TDD, etc.)

**When talking to user:** Plain language only. The user may not be a programmer.

**Output style:**
- Short, clear, direct
- No walls of text
- One idea per paragraph
- Use tables and bullets for structure
- If it can be said in 3 sentences, don't use 10

| Instead of | Say |
|------------|-----|
| "Created branch" | "Created a separate workspace for this change" |
| "Tests passing" | "Everything works as expected" |
| "Merged to main" | "Added your changes to the main project" |
| "TDD" | "I'll write a test first that describes what we want, then write the code to make it work" |
| "ADR" | "A decision record explaining why we chose this approach" |
| "Rollback" | "Undo the changes and go back to how it was" |
| "Context window filling" | "I'm running low on memory for this conversation" |
| "Subagent" | "A helper that investigates this separately" |
| "Refactor" | "Reorganize the code to be cleaner (same behavior, better structure)" |
| "Technical debt" | "Shortcuts we took that we should fix later" |

**Rule:** When showing output, summaries, or asking questions → always translate.

## Behavior rules

**Don't write code unless asked:**
- During Q&A or discussion → just answer, don't code
- When exploring options → describe, don't implement
- Only write code when user explicitly asks for implementation

**No workarounds without permission:**
- Never implement temporary fixes, fallbacks, or mock data without asking
- Always fix the real problem, not the symptom
- If you need a workaround, explain why and ask first

**Let errors be visible:**
- Don't hide problems with try/catch blocks that swallow errors
- Don't use placeholder text ("Loading...", "No data") that masks real issues
- If something is broken, let it break visibly so we can fix it

**Git safety:**
- Never use `git reset`, `git push --force`, or destructive commands without explicit approval
- Always show what will change before running git commands

**No silent skipping:**
- If the environment is missing something (no git repo, no test framework): ask, don't proceed silently
- If you want to skip a step in the process (tests, documentation): explain why and ask first
- If there's a conflict between instructions: mention it, don't just pick one

## Commands

```bash
[install]    # Setup
[dev]        # Development
[test]       # Run tests
[lint]       # Lint check
[build]      # Production build
```

## Testing

**Strategy per component** (from Tech Stack ADR):

| Component | Type | Approach |
|-----------|------|----------|
| [e.g., converters.py] | Pure functions | Unit tests |
| [e.g., api_client.py] | API calls | Mocks + integration |
| [e.g., cli.py] | CLI/glue | Manual + --dry-run |

**Framework:** [pytest / jest / go test / etc.]
**Location:** [tests/ / __tests__/ / etc.]
**Run:** [pytest / npm test / etc.]

**Rule:** If a component is not listed above, analyze it:
- Pure function → add unit test
- API call → add mock test
- Glue code → manual OK
- When in doubt → ask, don't skip silently

## Style rules

1. Follow existing naming conventions in the codebase
2. Keep functions small and focused (one job per function)
3. Write clear error messages that help debugging

Add project-specific rules below as you discover them:

## Pitfall triggers

Before writing code with these patterns, read docs/pitfalls.md:
- Using `generate_diff` or `generate_recursive_diff` → #api-wrong-diff-function
- Inserting blocks with children (toggles, column_list) → #api-nested-blocks-format
- `_prepare_block_for_api` → #api-nested-blocks-format
- Try/catch blocks → #error-catch-all

When stuck → Read docs/pitfalls.md fully.

## Quick capture triggers

When the user says these words, respond immediately:

| Trigger | Response | Action |
|---------|----------|--------|
| **bug** | 🐛 "What's the bug?" | Log to docs/inbox.md, ask severity |
| **idea** | 💡 "Tell me!" | Log to docs/inbox.md, ask priority |

**After capturing an idea, ask:**
> "Was this just a quick thought, or did we discuss technical details (approach, files, API design)?"
> - Quick thought → inbox one-liner only
> - Discussed details → create mini feature spec (Status: Idea) to preserve context

**Note:** Fixed bugs are auto-detected by `/wrap` - no manual trigger needed.

## After fixing bugs

**Trigger /retro when:**
- Bug took >30 minutes to fix
- Same bug appeared twice
- Data was lost or corrupted
- Security issue

Run: `/retro [what went wrong]` → Adds to pitfalls.md so it won't happen again.

## Code references

Use AI-CONTEXT comments with category-prefixed anchors:
```
// AI-CONTEXT: See docs/pitfalls.md#[category]-[name]
// AI-CONTEXT: See docs/patterns.md#[category]-[name]
```

## Structure

```
[root]/
├── [dir]/    # [purpose]
└── [dir]/    # [purpose]
```

## Documentation

**Read at feature start (always):**
- docs/architecture.md - Understand system + where new code belongs

**Read when needed:**
- docs/database.md - When working on database code
- docs/patterns.md - When building something new
- docs/pitfalls.md - Before coding, before commit, when stuck
- docs/features/ - When implementing a specific feature
- docs/decisions.md - When making architectural decisions

**Rule:** If unsure where code belongs, check docs/architecture.md component constraints.

## Available agents

Use these for complex tasks without filling main context:

| Agent | When to use |
|-------|-------------|
| `debugger` | Bug analysis, root cause tracing |
| `performance-optimizer` | Bottleneck identification, optimization |
| `code-reviewer` | Check code against pitfalls.md and patterns.md |
| `doc-sync-checker` | Verify docs match code |
| `migration-planner` | Bulk operations, schema changes, renames |
| `research-assistant` | New APIs, libraries, technology choices |

**Invoke:**
```
Use a subagent with the instructions from .claude/agents/debugger.md to analyze [error].
Use a subagent with the instructions from .claude/agents/performance-optimizer.md to check [component].
Use a subagent with the instructions from .claude/agents/migration-planner.md to plan [migration].
Use a subagent with the instructions from .claude/agents/research-assistant.md to research [topic].
```

**Auto-invoked by /complete:** `code-reviewer`, `doc-sync-checker`, `performance-optimizer`

**Agents per workflow phase:**

| Phase | Auto | On-demand |
|-------|------|-----------|
| /research | - | `research-assistant` |
| /plan | - | `migration-planner`, `research-assistant` |
| /implement | - | `debugger` |
| /complete | `code-reviewer`, `performance-optimizer`, `doc-sync-checker` | - |

## Session management

At session start: Read claude-progress.txt + docs/inbox.md
At session end: Run `/wrap` automatically (catches missed items, detects fixed bugs)
Check context: Use `/context` to monitor usage (stay under 60%)

**Auto-wrap triggers:** Before `/clear`, context >50%, end of `/implement` task, `/complete`

## Current work

See project.md for feature index.
See claude-progress.txt for active progress.
