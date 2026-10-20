"""Specialty shows' Spinitron show IDs: parsing pasted URLs and resolving them to shows."""

import re
from dataclasses import dataclass
from typing import List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.common.services.spinitron_service import SpinitronService
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_spinitron_show import SpecialtyShowSpinitronShow

# e.g. https://widgets.spinitron.com/KALX/show/301137/Take-Five
_SHOW_URL_RE = re.compile(
    r"^https?://(?:widgets\.)?spinitron\.com/KALX/show/(\d+)(?:[/?#]|$)"
)
# e.g. https://widgets.spinitron.com/KALX/pl/23203968/Take-Five
_PLAYLIST_URL_RE = re.compile(
    r"^https?://(?:widgets\.)?spinitron\.com/KALX/pl/(\d+)(?:[/?#]|$)"
)


@dataclass
class ResolvedShow:
    """A Spinitron show a pasted URL resolved to."""

    id: int
    title: Optional[str]


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


async def resolve_url(url: str) -> ResolvedShow:
    """
    Resolve a pasted Spinitron show or playlist URL to its show.

    A show URL holds the show ID. A playlist URL holds a playlist ID, so the
    playlist is looked up to find its show. Either way the show is fetched,
    to check it exists and get its title.

    :param url: A `…/KALX/show/<id>/…` or `…/KALX/pl/<id>/…` URL, on
        spinitron.com or widgets.spinitron.com.
    :raises HTTPException: 400 if the URL isn't one of those, or Spinitron
        has no such show or playlist; 502 if Spinitron can't be reached.
    """
    url = url.strip()
    try:
        if match := _SHOW_URL_RE.match(url):
            show_id = int(match.group(1))
        elif match := _PLAYLIST_URL_RE.match(url):
            playlist = await SpinitronService.fetch_playlist(int(match.group(1)))
            if playlist is None or playlist.get("show_id") is None:
                raise _bad_request(f"Spinitron has no playlist for {url}")
            show_id = int(playlist["show_id"])
        else:
            raise _bad_request(
                f"{url} isn't a Spinitron show or playlist link. Paste a link like "
                "https://spinitron.com/KALX/show/301137/Take-Five"
            )
        show = await SpinitronService.fetch_show(show_id)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Couldn't look up {url} in Spinitron: {e}",
        )
    if show is None:
        raise _bad_request(f"Spinitron has no show for {url}")
    title = (show.get("title") or "").strip() or None
    return ResolvedShow(id=show_id, title=title)


async def resolve_urls(urls: List[str]) -> List[ResolvedShow]:
    """Resolve each URL (see `resolve_url`), dropping blanks and repeats of a show."""
    shows: List[ResolvedShow] = []
    for url in urls:
        if not url.strip():
            continue
        show = await resolve_url(url)
        if all(s.id != show.id for s in shows):
            shows.append(show)
    return shows


def set_spinitron_shows(
    db: Session, specialty_show: SpecialtyShow, shows: List[ResolvedShow]
) -> None:
    """
    Replace a specialty show's Spinitron shows. A show held by a deleted
    specialty show moves to this one.

    :raises HTTPException: 400 if one of the shows belongs to another specialty show.
    """
    for show in shows:
        other = (
            db.query(SpecialtyShowSpinitronShow)
            .filter(
                SpecialtyShowSpinitronShow.spinitron_show_id == show.id,
                SpecialtyShowSpinitronShow.specialty_show_id != specialty_show.id,
            )
            .first()
        )
        if other is not None and other.specialty_show.deleted:
            # A deleted show was a mistake, so the ID can move to this one
            db.delete(other)
        elif other is not None:
            raise _bad_request(
                f"Spinitron show {show.title or show.id} already belongs to the "
                f"specialty show {other.specialty_show.name!r}"
            )
    existing = {s.spinitron_show_id: s for s in specialty_show.spinitron_show_rows}
    wanted = {s.id for s in shows}
    for show_id, row in existing.items():
        if show_id not in wanted:
            db.delete(row)
    db.flush()
    for show in shows:
        if show.id in existing:
            existing[show.id].title = show.title
        else:
            db.add(
                SpecialtyShowSpinitronShow(
                    specialty_show_id=specialty_show.id,
                    spinitron_show_id=show.id,
                    title=show.title,
                )
            )


def specialty_show_ids(db: Session) -> Set[int]:
    """
    The Spinitron show IDs of every specialty show that isn't deleted, retired
    ones included. Registered from `main.py` as the Staff Directory's specialty
    show IDs provider.
    """
    return {
        show_id
        for (show_id,) in (
            db.query(SpecialtyShowSpinitronShow.spinitron_show_id)
            .join(SpecialtyShow)
            .filter(SpecialtyShow.deleted.is_(False))
        )
    }
