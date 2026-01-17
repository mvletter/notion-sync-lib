# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-15

### Added

- **RateLimitedNotionClient**: Wrapper around `notion_client.Client` with automatic rate limiting (0.35s between requests) and exponential backoff on 429 errors
- **Block operations**: `fetch_page_blocks`, `fetch_blocks_recursive`, `delete_all_blocks`, `append_blocks`
- **Diff system**: Content-based diffing using `SequenceMatcher` for minimal API calls
  - `generate_diff` for smart content matching
  - `generate_diff_positional` for simple position-based comparison
  - `generate_recursive_diff` for tree structures with identical hierarchy
  - `execute_diff` and `execute_recursive_diff` for applying changes
- **Utility functions**: `extract_page_id`, `extract_page_title`, `extract_block_text`
- **Leading insert handling**: Workaround for Notion API's lack of `before` parameter

### Fixed

- Import paths corrected for standalone pip installation

[0.1.0]: https://github.com/mvletter/notion-sync-lib/releases/tag/v0.1.0
