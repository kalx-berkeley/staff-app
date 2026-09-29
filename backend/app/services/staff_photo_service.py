"""Staff directory photos: resized copies of each staff member's Airtable photo.

Airtable attachment URLs expire after a few hours, so the browser can't be
given them directly. Instead the Airtable sync downloads each photo when its
attachment changes and stores resized JPEG copies on disk, which the
directory API serves to authenticated staff.
"""

import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

import httpx2 as httpx
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from app.config import settings

logger = logging.getLogger(__name__)

# Let Pillow open HEIC/HEIF photos, the default format for iPhone cameras.
register_heif_opener()

# Square thumbnail for the directory table; bounding box for the detail panel.
# Both are about twice their largest display size, for high-DPI screens.
THUMB_SIZE = 128
MEDIUM_SIZE = 480
PHOTO_SIZES = ("thumb", "medium")


def photo_path(staff_id: int, size: str) -> Path:
    """
    Return where a staff member's resized photo is stored.

    :param staff_id: Staff ID.
    :param size: "thumb" or "medium".
    :returns: Path of the JPEG file (which may not exist).
    """
    return Path(settings.staff_photo_dir) / f"{staff_id}-{size}.jpg"


def photo_exists(staff_id: int) -> bool:
    """Return True if every size of the staff member's photo is on disk."""
    return all(photo_path(staff_id, size).is_file() for size in PHOTO_SIZES)


def select_photo_attachment(photo_field: Any) -> Optional[Dict[str, Any]]:
    """
    Pick the attachment to use from an Airtable "Photo" attachment field.

    :param photo_field: The field's value: a list of attachment objects, or None.
    :returns: The first image attachment with an ID and URL, or None.
    """
    if not isinstance(photo_field, list):
        return None
    for attachment in photo_field:
        if not isinstance(attachment, dict):
            continue
        if not attachment.get("id") or not attachment.get("url"):
            continue
        if not str(attachment.get("type", "image/")).startswith("image/"):
            continue
        return attachment
    return None


def _write_jpeg(image: Image.Image, path: Path) -> None:
    """Write *image* to *path* as a JPEG, replacing any existing file atomically."""
    tmp_path = path.with_suffix(".tmp")
    image.save(tmp_path, format="JPEG", quality=85, optimize=True)
    os.replace(tmp_path, path)


def save_photo(staff_id: int, image_bytes: bytes) -> None:
    """
    Resize a staff member's photo and store every size on disk.

    :param staff_id: Staff ID.
    :param image_bytes: The original image file's contents.
    :raises PIL.UnidentifiedImageError: If the bytes aren't a readable image.
    """
    with Image.open(BytesIO(image_bytes)) as original:
        image = ImageOps.exif_transpose(original)
        if image.mode != "RGB":
            # Flatten any transparency onto white rather than JPEG's black.
            rgba = image.convert("RGBA")
            image = Image.new("RGB", rgba.size, (255, 255, 255))
            image.paste(rgba, mask=rgba.getchannel("A"))

        Path(settings.staff_photo_dir).mkdir(parents=True, exist_ok=True)

        # Crop the thumbnail a little above center, where faces usually are.
        thumb = ImageOps.fit(image, (THUMB_SIZE, THUMB_SIZE), centering=(0.5, 0.35))
        _write_jpeg(thumb, photo_path(staff_id, "thumb"))

        medium = image.copy()
        medium.thumbnail((MEDIUM_SIZE, MEDIUM_SIZE))
        _write_jpeg(medium, photo_path(staff_id, "medium"))


def delete_photo(staff_id: int) -> None:
    """Remove every size of a staff member's photo from disk, if present."""
    for size in PHOTO_SIZES:
        photo_path(staff_id, size).unlink(missing_ok=True)


async def download_photo(url: str) -> bytes:
    """
    Download an Airtable attachment.

    :param url: The attachment's (short-lived) URL.
    :returns: The file's contents.
    :raises httpx.HTTPError: If the download fails.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return response.content
