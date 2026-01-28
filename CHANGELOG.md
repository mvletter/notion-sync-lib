# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.4] - 2026-01-28

### Fixed

- **Table block updates**: Fixed `body.table.table_width should be not present` error when updating table blocks. The `table_width` property is creation-only and cannot be updated via the Notion API. Now strips `table_width` (and `children`) from table block content before sending UPDATE requests.

## [1.0.3] - 2026-01-28

### Fixed

- **Block type property children**: Fixed `body.children[0].<type> should be defined` error when REPLACE operations encounter blocks with children in their type-specific property (e.g., `column.children`). Now strips `children` from the `<type>` dictionary in `_prepare_block_for_api` before processing `_children` separately.

## [1.0.2] - 2026-01-28

### Fixed

- **execute_recursive_diff children handling**: Fixed `body.children[0].{type} should be defined` error when updating blocks that contain children in their type-specific data (e.g., column blocks with `column.children`). The Notion API does not accept `children` properties in UPDATE requests - children are managed separately via the blocks API. Now strips `children` from block content before sending UPDATE requests, consistent with `execute_diff` behavior.

## [1.0.1] - 2026-01-27

### Fixed

- **File-based blocks** (image, video, pdf, file, audio): Fixed `body.image.type should be not present` error. Only caption can be updated after creation, not type/file/external properties.
- **Synced block copies**: Added detection and skip logic for read-only synced block copies (`synced_from != None`). These blocks cannot be updated via API.
- **Synced block originals**: Fixed `body.synced_block.synced_from should be defined` error. Field must be present with `null` value, not removed entirely.
- **Server error retry**: Extended retry logic to handle 502/503/504 Bad Gateway errors with exponential backoff (1s, 2s, 4s, 8s, 16s). Previously only 429 rate limit errors were retried.
- **HTTPResponseError import**: Fixed import error by importing `HTTPResponseError` from `notion_client.errors` module (not exported in top-level `notion_client`).
- **Table blocks**: Fixed `body.table.table_width should be not present` error. Table structural properties (table_width, has_column_header, has_row_header) are immutable after creation.
- **Numbered list items**: Fixed `body.numbered_list_item.list_start_index should be not present` error. The list_start_index property is immutable after creation.
- **Audio blocks**: Added audio to file-based blocks category. Same handling as image/video/pdf/file (only caption can be updated).
- **Variable scope**: Fixed `UnboundLocalError: cannot access local variable 'local_type'` by moving variable definition before usage.
- **NoneType safety**: Added None checks before calling `_is_synced_copy()` to prevent `'NoneType' object has no attribute 'get'` errors.

### Changed

- Added `_FILE_BASED_BLOCKS` constant for blocks where only caption can be updated
- Added `_STRUCTURE_ONLY_BLOCKS` constant for blocks with immutable structural properties
- Added `_is_synced_copy()` helper function to detect read-only synced block copies

## [1.0.0] - 2025-01-18

### 🎉 Production Release

This release marks the library as production-ready with comprehensive documentation, code quality improvements, and proven stability in production environments.

### Added

- **Block builders module** (`builders.py`):
  - `make_paragraph`, `make_heading`, `make_toggle`, `make_bulleted_list_item`
  - `make_numbered_list_item`, `make_to_do`, `make_code`, `make_callout`
  - `make_quote`, `make_divider`
- **TypedDict return types** for better IDE autocomplete:
  - `ColumnCreationResult`, `ColumnContent`, `UnwrapResult`
- **Input validation** on all public functions (type checking, range validation)
- **Complete documentation suite**:
  - Comprehensive usage guide with 5 real-world implementations
  - Full API reference documentation
  - Development and contributing guide
  - Common pitfalls documentation

### Changed

- **Iterative deletion**: Rewrote `_delete_block_recursive` to use iterative approach (prevents stack overflow)
- **Error handling**: Added proper re-raise after logging (no error swallowing)
- **Code organization**: Removed code duplication with shared constants
- **Development Status**: Updated from Beta to Production/Stable

### Removed

- **Backwards compatibility module** (`blocks.py`): Removed deprecated import shim

## [0.3.0] - 2025-01-17

### Added

- **Column operations module** (`columns.py`):
  - `extract_block_ids`: Recursively extract path-to-ID mapping from block trees
  - `build_column_list_block`: Build column_list block structures for Notion API
  - `create_column_list`: Create column_list in Notion and return structure with IDs
  - `read_column_content`: Read content from all columns in a column_list
  - `unwrap_column_list`: Extract column content to flat blocks

### Fixed

- Rate limiting now properly applied to all column operations

## [0.2.0] - 2025-01-16

### Added

- **Recursive diff**: `generate_recursive_diff` and `execute_recursive_diff` for tree structures with identical hierarchy
- **Block type handling**: Special handling for callout, toggle, and heading blocks to avoid Notion API errors
- **Table content comparison**: Tables now compared by content, not just structure

### Changed

- Improved error handling and logging throughout
- Synced with production-tested version

### Fixed

- Table diff now includes row content for accurate comparison
- REPLACE operations properly handle blocks with children

## [0.1.0] - 2025-01-15

### Added

- **RateLimitedNotionClient**: Wrapper around `notion_client.Client` with automatic rate limiting (0.35s between requests) and exponential backoff on 429 errors
- **Block operations**: `fetch_page_blocks`, `fetch_blocks_recursive`, `delete_all_blocks`, `append_blocks`
- **Diff system**: Content-based diffing using `SequenceMatcher` for minimal API calls
  - `generate_diff` for smart content matching
  - `execute_diff` for applying changes
- **Utility functions**: `extract_page_id`, `extract_page_title`, `extract_block_text`

### Fixed

- Import paths corrected for standalone pip installation

[1.0.1]: https://github.com/mvletter/notion-sync-lib/releases/tag/v1.0.1
[1.0.0]: https://github.com/mvletter/notion-sync-lib/releases/tag/v1.0.0
[0.3.0]: https://github.com/mvletter/notion-sync-lib/releases/tag/v0.3.0
[0.2.0]: https://github.com/mvletter/notion-sync-lib/releases/tag/v0.2.0
[0.1.0]: https://github.com/mvletter/notion-sync-lib/releases/tag/v0.1.0
