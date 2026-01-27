"""Notion Sync Client - Rate-limited wrapper around Notion API."""

import logging
import time
from typing import Any

from notion_client import Client, APIResponseError, HTTPResponseError

from notion_sync.utils import get_notion_token

logger = logging.getLogger(__name__)

# Rate limiting: max 3 requests/second
MIN_REQUEST_INTERVAL = 0.35
MAX_RETRIES = 5


class RateLimitedNotionClient:
    """Wrapper around Notion client with rate limiting and exponential backoff.

    Implements rate limiting (min 0.35s between requests) and automatic retry
    with exponential backoff on 429 (rate limit) errors.

    Attributes:
        notion: The underlying notion_client.Client instance.
        request_count: Total number of API requests made.
    """

    def __init__(self, notion: Client):
        """Initialize the rate-limited client.

        Args:
            notion: A configured notion_client.Client instance.
        """
        self.notion = notion
        self._last_request_time: float = 0
        self.request_count: int = 0

    def _wait_for_rate_limit(self) -> None:
        """Wait if needed to respect rate limit."""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()
        self.request_count += 1

    def _handle_rate_limit_error(self, e: APIResponseError | HTTPResponseError, attempt: int) -> bool:
        """Handle API errors with exponential backoff (429, 502, 503, 504).

        Args:
            e: The API response error (APIResponseError or HTTPResponseError).
            attempt: Current retry attempt number (0-indexed).

        Returns:
            True if should retry, False if should give up.
        """
        # Retryable errors: 429 (rate limit), 502/503/504 (server errors)
        retryable_statuses = {429, 502, 503, 504}
        if e.status not in retryable_statuses:
            return False
        if attempt >= MAX_RETRIES - 1:
            logger.error(f"Max retry attempts reached after {e.status} errors")
            return False
        wait_time = 2 ** attempt
        logger.warning(f"API error {e.status}, waiting {wait_time}s before retry (attempt {attempt + 1}/{MAX_RETRIES})...")
        time.sleep(wait_time)
        return True

    def get_page(self, page_id: str) -> dict[str, Any]:
        """Get page metadata.

        Args:
            page_id: The Notion page ID.

        Returns:
            Page metadata dictionary from Notion API.

        Raises:
            APIResponseError: On API errors after retries exhausted.
            Exception: If all retries fail.
        """
        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                return self.notion.pages.retrieve(page_id=page_id)
            except (APIResponseError, HTTPResponseError) as e:
                if self._handle_rate_limit_error(e, attempt):
                    continue
                raise
        raise Exception(f"Failed to get page {page_id} after {MAX_RETRIES} retries")

    def get_blocks(self, block_id: str) -> list[dict[str, Any]]:
        """Get child blocks of a block or page.

        Args:
            block_id: The Notion block or page ID.

        Returns:
            List of child block dictionaries.

        Raises:
            APIResponseError: On API errors after retries exhausted.
            Exception: If all retries fail.
        """
        from notion_client.helpers import collect_paginated_api

        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                blocks = collect_paginated_api(
                    self.notion.blocks.children.list,
                    block_id=block_id
                )
                return list(blocks)
            except (APIResponseError, HTTPResponseError) as e:
                if self._handle_rate_limit_error(e, attempt):
                    continue
                raise
        raise Exception(f"Failed to get blocks for {block_id} after {MAX_RETRIES} retries")

    def append_blocks(
        self,
        page_id: str,
        blocks: list[dict[str, Any]],
        after: str | None = None,
    ) -> dict[str, Any]:
        """Append blocks to a page.

        Args:
            page_id: The Notion page ID to append to.
            blocks: List of block objects to append.
            after: Optional block ID to insert after.

        Returns:
            API response with appended block information.

        Raises:
            APIResponseError: On API errors after retries exhausted.
            Exception: If all retries fail.
        """
        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                kwargs: dict[str, Any] = {"block_id": page_id, "children": blocks}
                if after:
                    kwargs["after"] = after
                return self.notion.blocks.children.append(**kwargs)
            except (APIResponseError, HTTPResponseError) as e:
                if self._handle_rate_limit_error(e, attempt):
                    continue
                raise
        raise Exception(f"Failed to append blocks to {page_id} after {MAX_RETRIES} retries")

    def delete_block(self, block_id: str) -> dict[str, Any]:
        """Delete a block.

        Args:
            block_id: The Notion block ID to delete.

        Returns:
            API response confirming deletion.

        Raises:
            APIResponseError: On API errors after retries exhausted.
            Exception: If all retries fail.
        """
        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                return self.notion.blocks.delete(block_id=block_id)
            except (APIResponseError, HTTPResponseError) as e:
                if self._handle_rate_limit_error(e, attempt):
                    continue
                raise
        raise Exception(f"Failed to delete block {block_id} after {MAX_RETRIES} retries")

    def update_block(self, block_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a block.

        Args:
            block_id: The Notion block ID to update.
            data: Block data to update (block type and properties).

        Returns:
            API response with updated block information.

        Raises:
            APIResponseError: On API errors after retries exhausted.
            Exception: If all retries fail.
        """
        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                return self.notion.blocks.update(block_id=block_id, **data)
            except (APIResponseError, HTTPResponseError) as e:
                if self._handle_rate_limit_error(e, attempt):
                    continue
                raise
        raise Exception(f"Failed to update block {block_id} after {MAX_RETRIES} retries")

    def update_page_title(self, page_id: str, title: str) -> dict[str, Any]:
        """Update a page's title.

        Args:
            page_id: The Notion page ID to update.
            title: New title text (plain text, no formatting).

        Returns:
            API response with updated page information.

        Raises:
            APIResponseError: On API errors after retries exhausted.
            Exception: If all retries fail.
        """
        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                return self.notion.pages.update(
                    page_id=page_id,
                    properties={
                        "title": {
                            "title": [
                                {
                                    "type": "text",
                                    "text": {"content": title}
                                }
                            ]
                        }
                    }
                )
            except (APIResponseError, HTTPResponseError) as e:
                if self._handle_rate_limit_error(e, attempt):
                    continue
                raise
        raise Exception(f"Failed to update page title {page_id} after {MAX_RETRIES} retries")


def get_notion_client() -> RateLimitedNotionClient:
    """Factory function to create a configured RateLimitedNotionClient.

    Reads the NOTION_API_TOKEN from environment and creates a rate-limited
    client ready for use.

    Returns:
        A configured RateLimitedNotionClient instance.

    Raises:
        ValueError: If NOTION_API_TOKEN environment variable is not set.
    """
    token = get_notion_token()
    notion = Client(auth=token)
    return RateLimitedNotionClient(notion)
