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


def extract_page_icon(page: dict) -> dict | None:
    """Extract icon object from a Notion page API response.

    Returns the raw icon dict or None if no icon is set.

    Icon types returned by the API:
    - 'emoji':        {"type": "emoji", "emoji": "🚀"}
    - 'external':     {"type": "external", "external": {"url": "..."}}
    - 'file':         {"type": "file", "file": {"url": "...", "expiry_time": "..."}}
    - 'custom_emoji': {"type": "custom_emoji", "custom_emoji": {"id": "...", "url": "..."}}

    Args:
        page: Page object from Notion API (from client.pages.retrieve()).

    Returns:
        Icon dict or None if no icon is set.
    """
    return page.get("icon") or None


def prepare_icon_for_api(icon: dict | None, notion_token: str | None = None) -> dict | None:
    """Convert a page icon from Notion API response format to API request format.

    For 'file' type icons (Notion-hosted S3 files with expiring URLs), downloads
    and re-uploads via the Notion File Upload API when a token is provided. The
    resulting 'file_upload' reference is permanent and does not expire.

    Requires the ``notion-upload`` package for file re-upload. Falls back to
    'external' with the S3 URL when notion-upload is unavailable or upload fails.

    API response types (read):
      - 'emoji':        {"type": "emoji", "emoji": "🚀"}
      - 'external':     {"type": "external", "external": {"url": "..."}}
      - 'file':         {"type": "file", "file": {"url": "...", "expiry_time": "..."}}
      - 'custom_emoji': {"type": "custom_emoji", "custom_emoji": {"id": "...", ...}}

    API request types (write):
      - 'emoji':        {"type": "emoji", "emoji": "🚀"}
      - 'external':     {"type": "external", "external": {"url": "..."}}
      - 'file_upload':  {"type": "file_upload", "file_upload": {"id": "..."}}
      - 'custom_emoji': {"type": "custom_emoji", "custom_emoji": {"id": "..."}}

    Args:
        icon: Icon dict from Notion API response, or None.
        notion_token: Optional Notion API token for re-uploading file icons.

    Returns:
        Icon dict ready for Notion API request, or None if no icon.
    """
    if not icon:
        return None

    icon_type = icon.get("type")

    if icon_type == "emoji":
        return {"type": "emoji", "emoji": icon["emoji"]}

    if icon_type == "external":
        return {"type": "external", "external": {"url": icon["external"]["url"]}}

    if icon_type == "custom_emoji":
        return {"type": "custom_emoji", "custom_emoji": {"id": icon["custom_emoji"]["id"]}}

    if icon_type == "file":
        url = icon.get("file", {}).get("url")
        if not url:
            logger.warning("'file' icon has no URL, skipping icon sync")
            return None

        if notion_token:
            file_id = _reupload_file_icon(url, notion_token)
            if file_id:
                return {"type": "file_upload", "file_upload": {"id": file_id}}

        # Fallback: S3 URL expires after ~1 hour — icon will disappear
        logger.warning(
            "Converting 'file' icon to 'external' without re-upload — "
            "icon will disappear when S3 URL expires"
        )
        return {"type": "external", "external": {"url": url}}

    logger.warning(f"Unknown icon type '{icon_type}', skipping icon sync")
    return None


def _reupload_file_icon(url: str, notion_token: str) -> str | None:
    """Download a Notion-hosted file icon and re-upload via the File Upload API.

    Args:
        url: Pre-signed S3 URL from Notion API response.
        notion_token: Notion API token for the upload.

    Returns:
        File upload ID string, or None on failure.
    """
    import hashlib

    try:
        from notion_upload import notion_upload  # type: ignore[import]
    except ImportError:
        logger.warning("notion-upload not installed; cannot re-upload file icon")
        return None

    try:
        url_path = url.split("?")[0]
        ext = ".png"
        if "." in url_path.rsplit("/", 1)[-1]:
            ext = "." + url_path.rsplit(".", 1)[-1][:4]
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"icon_{url_hash}{ext}"

        logger.debug(f"Re-uploading file icon: {filename}")
        file_id = notion_upload(url, filename, notion_token).upload()
        if file_id:
            logger.debug(f"Re-uploaded file icon → file_upload id={file_id}")
            return str(file_id)
    except Exception as e:
        logger.warning(f"Failed to re-upload file icon: {e}")

    return None


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
