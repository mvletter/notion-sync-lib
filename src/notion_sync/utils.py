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
        emoji = icon.get("emoji")
        if not emoji:
            logger.warning("'emoji' icon has no emoji value, skipping icon sync")
            return None
        return {"type": "emoji", "emoji": emoji}

    if icon_type == "external":
        url = (icon.get("external") or {}).get("url")
        if not url:
            logger.warning("'external' icon has no URL, skipping icon sync")
            return None
        return {"type": "external", "external": {"url": url}}

    if icon_type == "custom_emoji":
        custom_id = (icon.get("custom_emoji") or {}).get("id")
        if not custom_id:
            logger.warning("'custom_emoji' icon has no id, skipping icon sync")
            return None
        return {"type": "custom_emoji", "custom_emoji": {"id": custom_id}}

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


def prepare_image_for_api(image_content: dict, notion_token: str | None = None) -> dict:
    """Convert a workspace-hosted image block to Notion API write format.

    Notion read API returns workspace-hosted images as {"type": "file", "file": {...}}.
    The write API only accepts "external" or "file_upload" types.

    When notion_token is provided, downloads the image and re-uploads via the File
    Upload API to get a permanent file_upload.id that never expires.
    Without a token, falls back to the S3 "external" URL (expires in ~1 hour).

    Args:
        image_content: The image block content dict (has "file", "external", or
            "file_upload" key).
        notion_token: Optional Notion API token for re-uploading hosted images.

    Returns:
        Image content dict ready for Notion API write.
    """
    caption = image_content.get("caption", [])

    if "file" in image_content:
        url = image_content["file"].get("url", "")
    elif "external" in image_content:
        url = image_content["external"].get("url", "")
    else:
        return image_content

    if not url:
        logger.warning("Image block has no URL — cannot convert for write")
        return image_content

    if notion_token:
        file_id = _reupload_file_icon(url, notion_token, prefix="image")
        if file_id:
            return {"type": "file_upload", "file_upload": {"id": file_id}, "caption": caption}
        logger.warning("Image re-upload failed — falling back to external URL (will expire)")

    return {"type": "external", "external": {"url": url}, "caption": caption}


def _reupload_file_icon(url: str, notion_token: str, prefix: str = "icon") -> str | None:
    """Download a Notion-hosted file and re-upload via the File Upload API.

    S3 pre-signed URLs cannot be passed directly to Notion's external_url upload
    mode — Notion tries to fetch them itself but they are not publicly accessible.
    Instead, this function downloads the file locally and uploads the raw bytes via
    the two-step file_uploads API (init → send), matching the pattern used for
    image blocks in Herald's new_page_blocks.py.

    Args:
        url: Pre-signed S3 URL from Notion API response.
        notion_token: Notion API token for the upload.
        prefix: Filename prefix for the temp file (e.g. "icon" or "image").

    Returns:
        File upload ID string, or None on failure.
    """
    import hashlib
    import mimetypes
    import os
    import tempfile

    try:
        import requests
    except ImportError:
        logger.warning("requests not installed; cannot re-upload file")
        return None

    url_path = url.split("?")[0]
    ext = ".png"
    if "." in url_path.rsplit("/", 1)[-1]:
        ext = "." + url_path.rsplit(".", 1)[-1][:4]
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    filename = f"{prefix}_{url_hash}{ext}"

    logger.debug(f"Re-uploading {prefix}: {filename}")

    tmp_path = None
    try:
        # Step 1: Download the file locally.
        # S3 pre-signed URLs may require auth — try without first, then with Bearer.
        resp = None
        for dl_headers in ({}, {"Authorization": f"Bearer {notion_token}"}):
            r = requests.get(url, headers=dl_headers, stream=True, timeout=30)
            if r.status_code == 200:
                resp = r
                break
            logger.debug(f"Icon download returned {r.status_code}, retrying with auth")

        if resp is None:
            logger.warning(f"Failed to download file icon for re-upload: {filename}")
            return None

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            for chunk in resp.iter_content(8192):
                tmp.write(chunk)
            tmp_path = tmp.name

        # Step 2: Upload to Notion via the two-step file_uploads API.
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        notion_headers = {
            "Authorization": f"Bearer {notion_token}",
            "Notion-Version": "2022-06-28",
        }

        init_resp = requests.post(
            "https://api.notion.com/v1/file_uploads",
            headers={**notion_headers, "Content-Type": "application/json"},
            json={"filename": filename, "content_type": mime_type},
            timeout=30,
        )
        if init_resp.status_code != 200:
            logger.warning(f"File upload init failed ({init_resp.status_code}) for {filename}: {init_resp.text}")
            return None

        file_id = init_resp.json().get("id")
        if not file_id:
            logger.warning(f"File upload init returned no id for {filename}")
            return None

        with open(tmp_path, "rb") as f:
            send_resp = requests.post(
                f"https://api.notion.com/v1/file_uploads/{file_id}/send",
                headers=notion_headers,
                files={"file": (filename, f, mime_type)},
                timeout=30,
            )

        if send_resp.status_code != 200:
            logger.warning(f"File upload send failed ({send_resp.status_code}) for {filename}: {send_resp.text}")
            return None

        logger.debug(f"Re-uploaded {prefix} → file_upload id={file_id}")
        return str(file_id)

    except Exception as e:
        logger.warning(f"Failed to re-upload {prefix}: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

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
