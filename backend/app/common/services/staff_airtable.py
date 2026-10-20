"""Read one record of, and write to, the Airtable staff table (AIRTABLE_TABLE_NAME)."""

import base64
import logging
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx2 as httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

AIRTABLE_API_URL = "https://api.airtable.com/v0"
AIRTABLE_CONTENT_URL = "https://content.airtable.com/v0"
PHOTO_FIELD = "Photo"


def _record_url(record_id: str) -> str:
    return (
        f"{AIRTABLE_API_URL}/{settings.airtable_base_id}/"
        f"{quote(settings.airtable_table_name, safe='')}/{record_id}"
    )


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.airtable_api_key}",
        "Content-Type": "application/json",
    }


def _require_config() -> None:
    if not settings.airtable_api_key or not settings.airtable_base_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Airtable is not configured",
        )


def _raise_for_airtable_error(e: Exception, action: str) -> None:
    """Log an Airtable failure and raise it as a 502, passing on Airtable's message."""
    if isinstance(e, httpx.HTTPStatusError):
        message = e.response.text
        try:
            error = e.response.json().get("error")
            if isinstance(error, dict):
                message = error.get("message") or message
            elif isinstance(error, str):
                message = error
        except ValueError:
            pass
        logger.error(
            "Airtable staff table: %s failed: %s - %s",
            action,
            e.response.status_code,
            message,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Airtable couldn't {action}: {message}",
        )
    logger.error("Airtable staff table: %s failed: %s", action, e)
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Couldn't reach Airtable to {action}",
    )


async def get_staff_record(record_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch one record of the staff table.

    :param record_id: The Airtable record ID ("rec...").
    :returns: The record ("id" and "fields"), or None if it doesn't exist.
    :raises HTTPException: 503 if Airtable isn't configured, 502 if the call fails.
    """
    _require_config()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                _record_url(record_id), headers=_headers(), timeout=30.0
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        _raise_for_airtable_error(e, "read the staff record")
    return {"id": data.get("id"), "fields": data.get("fields", {})}


async def update_staff_record(record_id: str, fields: Dict[str, Any]) -> None:
    """
    Change fields of one staff table record. Fields not given are left as they are.

    :param record_id: The Airtable record ID.
    :param fields: Airtable field name to new value.
    :raises HTTPException: 503 if Airtable isn't configured, 502 if the call fails.
    """
    _require_config()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                _record_url(record_id),
                headers=_headers(),
                json={"fields": fields},
                timeout=30.0,
            )
            response.raise_for_status()
    except Exception as e:
        _raise_for_airtable_error(e, "save the staff record")


async def replace_staff_photo(
    record_id: str, filename: str, content_type: str, data: bytes
) -> None:
    """
    Make an image the staff record's only "Photo" attachment.

    Airtable's uploadAttachment endpoint adds the file to the field, so the
    field is then set to just the new attachment.

    :param record_id: The Airtable record ID.
    :param filename: The image's file name.
    :param content_type: "image/jpeg" or "image/png".
    :param data: The image, at most 5 MB (Airtable's limit for this endpoint).
    :raises HTTPException: 503 if Airtable isn't configured, 502 if a call fails.
    """
    _require_config()
    upload_url = (
        f"{AIRTABLE_CONTENT_URL}/{settings.airtable_base_id}/{record_id}/"
        f"{quote(PHOTO_FIELD, safe='')}/uploadAttachment"
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                upload_url,
                headers=_headers(),
                json={
                    "contentType": content_type,
                    "file": base64.b64encode(data).decode("ascii"),
                    "filename": filename,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            # The response's "fields" holds just the attachment field, keyed
            # by its field ID rather than its name
            attachments = next(
                (
                    value
                    for value in response.json().get("fields", {}).values()
                    if isinstance(value, list)
                ),
                [],
            )
    except Exception as e:
        _raise_for_airtable_error(e, "upload the photo")
    if not attachments:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Airtable didn't return the uploaded photo",
        )
    # The upload is added last
    await update_staff_record(record_id, {PHOTO_FIELD: [{"id": attachments[-1]["id"]}]})
