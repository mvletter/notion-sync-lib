"""Notion Sync Utilities - Helper functions for Notion API interactions."""

import os
import re
import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Auto-load .env from project root
_env_loaded = False


def _ensure_env_loaded() -> None:
    """Load .env file if not already loaded."""
    global _env_loaded
    if _env_loaded:
        return

    # Find project root (look for .env going up from this file)
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        env_file = parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            logger.debug(f"Loaded environment from {env_file}")
            break

    _env_loaded = True


def get_notion_token() -> str:
    """Get Notion API token from environment.

    Automatically loads .env file from project root if present.

    Returns:
        The NOTION_API_TOKEN environment variable value.

    Raises:
        ValueError: If NOTION_API_TOKEN is not set.
    """
    _ensure_env_loaded()

    token = os.environ.get("NOTION_API_TOKEN")
    if not token:
        raise ValueError(
            "NOTION_API_TOKEN environment variable not set.\n"
            "Get your token at: https://www.notion.so/my-integrations"
        )
    return token


def extract_page_title(page: dict) -> str:
    """Extract plain text title from a Notion page object.

    Args:
        page: Page object from Notion API (from client.get_page()).

    Returns:
        Plain text title of the page.

    Raises:
        ValueError: If title property is not found.
    """
    properties = page.get("properties", {})

    # Look for title property (usually "Name" or "title")
    for prop_name, prop_data in properties.items():
        if prop_data.get("type") == "title":
            title_array = prop_data.get("title", [])
            # Concatenate all text parts
            return "".join(item.get("plain_text", "") for item in title_array)

    raise ValueError("Could not find title property in page")


def extract_page_id(url: str) -> str:
    """Extract page ID from Notion URL and format as UUID.

    Supports formats:
    - https://notion.so/workspace/Page-Title-abc123def456
    - https://notion.so/abc123def456
    - https://www.notion.so/workspace/abc123def456

    Args:
        url: A Notion page URL.

    Returns:
        32-character page ID formatted as UUID with dashes.
        Example: "2d240e6d-8f97-8077-8b8d-fd8dae6ed382"

    Raises:
        ValueError: If page ID cannot be extracted from URL.
    """
    # Remove query params
    url = url.split("?")[0]

    # Get last path segment
    last_segment = url.rstrip("/").split("/")[-1]

    # Extract 32-char hex ID from END of string (titles can contain hex chars like "guide")
    # Pattern: 32 hex chars at the end, after removing dashes
    match = re.search(r"([a-f0-9]{32})$", last_segment.replace("-", ""))
    if match:
        raw_id = match.group(1)
        # Format as UUID with dashes
        return f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"

    raise ValueError(f"Could not extract page ID from URL: {url}")
