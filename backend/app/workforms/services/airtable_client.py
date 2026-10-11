"""Read and write the Airtable workforms table."""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx2 as httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

AIRTABLE_API_URL = "https://api.airtable.com/v0"


def _table_url(record_id: Optional[str] = None) -> str:
    url = (
        f"{AIRTABLE_API_URL}/{settings.airtable_base_id}/"
        f"{quote(settings.airtable_workforms_table_name, safe='')}"
    )
    return f"{url}/{record_id}" if record_id else url


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.airtable_api_key}",
        "Content-Type": "application/json",
    }


def _require_config() -> None:
    if not settings.airtable_api_key or not settings.airtable_base_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Airtable is not configured, so workforms can't be read or saved",
        )


def _raise_for_airtable_error(e: Exception, action: str) -> None:
    """
    Log an Airtable failure and raise it as an HTTP error.

    A field Airtable doesn't know (for example a department whose
    "<Dept> : Hours" column is missing) comes back as a 422 naming the field,
    and that message is passed on so it can be fixed in Airtable.
    """
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
            "Airtable workforms table %r: %s failed: %s - %s",
            settings.airtable_workforms_table_name,
            action,
            e.response.status_code,
            message,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Airtable couldn't {action}: {message}",
        )
    logger.error(
        "Airtable workforms table %r: %s failed: %s",
        settings.airtable_workforms_table_name,
        action,
        e,
    )
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Couldn't reach Airtable to {action}",
    )


async def list_records(formula: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch every record of the workforms table, or those matching *formula*.

    :param formula: An Airtable ``filterByFormula`` expression
    :returns: Records as dicts with "id", "createdTime" and "fields"
    :raises HTTPException: 503 if Airtable isn't configured, 502 if the call fails
    """
    _require_config()
    records: List[Dict[str, Any]] = []
    try:
        async with httpx.AsyncClient() as client:
            offset = None
            while True:
                params: Dict[str, str] = {}
                if formula:
                    params["filterByFormula"] = formula
                if offset:
                    params["offset"] = offset
                response = await client.get(
                    _table_url(), headers=_headers(), params=params, timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                records.extend(data.get("records", []))
                offset = data.get("offset")
                if not offset:
                    break
    except Exception as e:
        _raise_for_airtable_error(e, "list workforms")
    return records


async def get_record(record_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch one record of the workforms table.

    :returns: The record, or None if it no longer exists
    :raises HTTPException: 503 if Airtable isn't configured, 502 if the call fails
    """
    _require_config()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                _table_url(record_id), headers=_headers(), timeout=30.0
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
    except Exception as e:
        _raise_for_airtable_error(e, "read the workform")
    return None  # pragma: no cover - _raise_for_airtable_error always raises


async def create_record(fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a record in the workforms table.

    :returns: The created record
    :raises HTTPException: 503 if Airtable isn't configured, 502 if the call fails
    """
    _require_config()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _table_url(),
                headers=_headers(),
                json={"fields": fields, "typecast": True},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        _raise_for_airtable_error(e, "save the workform")
    return {}  # pragma: no cover


async def update_record(record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Change some fields of a record in the workforms table.

    A field set to None is cleared.

    :returns: The updated record
    :raises HTTPException: 503 if Airtable isn't configured, 502 if the call fails
    """
    _require_config()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                _table_url(record_id),
                headers=_headers(),
                json={"fields": fields, "typecast": True},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        _raise_for_airtable_error(e, "save the workform")
    return {}  # pragma: no cover
