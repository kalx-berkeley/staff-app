"""Show API endpoints."""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.schemas.show import (
    ShowBandCreate,
    ShowBandResponse,
    ShowCreate,
    ShowResponse,
    ShowSummary,
    ShowUpdate,
    ShowAttemptResponse,
)
from app.services.show_service import ShowService
from app.auth import (
    get_user_role,
    get_user_role_or_dj,
    get_current_user_email,
    get_promotions_staff,
    check_dj_access,
    _get_promotions_staff_by_email,
    require_authentication,
)
from app.models.staff import Staff
from app.models.show import Show
from app.models.show_band import ShowBand
from app.services.cache_service import fetch_cached
from app.models.venue_owner import VenueOwner
from app.models.promoter_owner import PromoterOwner
from app.config import settings
from app.services import audit_service
from app.scheduler import (
    schedule_auto_close_job,
    unschedule_auto_close_job,
    schedule_lottery_job,
    unschedule_lottery_job,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shows", tags=["shows"])


class AttemptRequest(BaseModel):
    dj_name: str


def _notify_staff_guests_confirmed(db, show) -> None:
    """Notify staff members with pending +1 guests that their guest is confirmed."""
    from app.services import notification_service
    from app.models.pass_model import Pass

    guest_passes = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "staff",
            Pass.status == "claimed",
            Pass.has_guest.is_(True),
        )
        .all()
    )
    for pass_item in guest_passes:
        if not pass_item.staff or not pass_item.staff.email:
            continue
        guest_label = (
            f" and {pass_item.guest_name}" if pass_item.guest_name else " and your guest"
        )
        body = "\n".join([
            (
                f'Good news! Your staff pass for "{show.event_name}" at {show.venue.name}'
                f" on {show.show_date} has been confirmed."
            ),
            "",
            f"You{guest_label} are both on the guest list.",
            "",
            "The show has now been closed — please check with the venue for entry details.",
        ])
        notification_service.send_email(
            to_email=pass_item.staff.email,
            subject=f"Your guest is confirmed: {show.event_name}",
            body_text=body,
            db=db,
        )


def _build_promotions_contacts(show) -> list[dict]:
    """Build promotions contact list from effective promoter owners (or venue owners)."""
    effective_promoter = show.effective_promoter
    owners = effective_promoter.owners if effective_promoter else show.venue.owners
    contacts = []
    for owner in owners:
        if owner.staff:
            s = owner.staff
            contacts.append({"email": s.email, "name": s.name, "phone": s.phone})
    return contacts


def _build_show_response(show, pass_adjustment=None, is_mine: bool = False) -> dict:
    """
    Build show response with nested venue info and promotions contacts.
    Includes all pass details and attempt history.
    """
    available_pair_count = sum(
        1 for t in show.passes if t.pass_type == "pair" and t.status == "available"
    )
    available_staff_count = sum(
        1 for t in show.passes if t.pass_type == "staff" and t.status == "available"
    )

    passes = []
    for pass_item in show.passes:
        pass_data = {
            "id": pass_item.id,
            "show_id": pass_item.show_id,
            "pass_type": pass_item.pass_type,
            "status": pass_item.status,
            "recipient_name": pass_item.recipient_name,
            "recipient_phone": pass_item.recipient_phone,
            "recipient_email": pass_item.recipient_email,
            "given_away_by_dj": pass_item.given_away_by_dj,
            "given_away_at": pass_item.given_away_at,
            "staff_id": pass_item.staff_id,
            "staff_name": pass_item.staff.name if pass_item.staff else None,
            "staff_phone": pass_item.staff.phone if pass_item.staff else None,
            "staff_email": pass_item.staff.email if pass_item.staff else None,
            "claimed_at": pass_item.claimed_at,
            "has_guest": pass_item.has_guest,
            "guest_name": pass_item.guest_name,
            "only_attend_with_guest": pass_item.only_attend_with_guest,
            "guest_of_pass_id": pass_item.guest_of_pass_id,
            "preassigned_dj": pass_item.preassigned_dj,
            "preassigned_date": pass_item.preassigned_date,
            "preassigned_specialty_show_id": pass_item.preassigned_specialty_show_id,
            "preassigned_specialty_show_name": pass_item.preassigned_specialty_show_name,
            "created_at": pass_item.created_at,
            "updated_at": pass_item.updated_at,
        }
        passes.append(pass_data)

    attempts = [
        {"id": a.id, "dj_name": a.dj_name, "attempted_at": a.attempted_at}
        for a in show.attempts or []
    ]

    return {
        "id": show.id,
        "event_name": show.event_name,
        "genre": show.genre,
        "promoter_id": show.promoter_id,
        "venue": {
            "id": show.venue.id,
            "name": show.venue.name,
            "address": show.venue.address,
            "pass_call_instructions": show.venue.pass_call_instructions,
            "win_frequency_days": show.venue.win_frequency_days,
            "default_wheelchair_accessible": show.venue.default_wheelchair_accessible,
            "default_age_restriction": show.venue.default_age_restriction,
            "default_num_pass_pairs": show.venue.default_num_pass_pairs,
            "requires_phone_number": show.venue.requires_phone_number,
            "requires_email_address": show.venue.requires_email_address,
            "staff_guest_requires_name": show.venue.staff_guest_requires_name,
            "default_lottery_enabled": show.venue.default_lottery_enabled,
            "default_lottery_window_hours": show.venue.default_lottery_window_hours,
            "default_dj_preassign_prohibition_days": (
                show.venue.default_dj_preassign_prohibition_days
            ),
            "has_logo": bool(show.venue.logo_filename),
            "deleted": show.venue.deleted,
            "owner_emails": [o.promotions_staff_email for o in show.venue.owners],
            "contacts": [
                {
                    "id": c.id,
                    "name": c.name,
                    "title": c.title,
                    "email": c.email,
                    "phone": c.phone,
                }
                for c in show.venue.contacts
            ],
        },
        "show_date": show.show_date,
        "show_time": show.show_time,
        "show_start_date": show.show_start_date,
        "on_air_description": show.on_air_description,
        "caller_special_instructions": show.caller_special_instructions,
        "age_restriction": show.age_restriction,
        "wheelchair_accessible": show.wheelchair_accessible,
        "num_pass_pairs": show.num_pass_pairs,
        "promotions_contacts": _build_promotions_contacts(show),
        "status": show.status,
        "planned_close_date": show.planned_close_date,
        "planned_close_time": show.planned_close_time,
        "auto_close": show.auto_close,
        "co_announce": show.co_announce,
        "lottery_enabled": show.lottery_enabled,
        "lottery_window_hours": show.lottery_window_hours,
        "dj_preassign_prohibition_days": show.dj_preassign_prohibition_days,
        "published_at": show.published_at,
        "available_pair_count": available_pair_count,
        "available_staff_count": available_staff_count,
        "pass_adjustment": pass_adjustment,
        "is_mine": is_mine,
        "passes": passes,
        "attempts": attempts,
        "bands": [
            {
                "id": b.id,
                "show_id": b.show_id,
                "musicbrainz_id": b.musicbrainz_id,
                "band_name": b.band_name,
                "start_pos": b.start_pos,
                "end_pos": b.end_pos,
                "artist_type": b.artist_type,
                "artist_country": b.artist_country,
                "artist_disambiguation": b.artist_disambiguation,
                "artist_tags": b.artist_tags,
            }
            for b in show.bands or []
        ],
    }


def _precompute_pass_counts(db: Session, show_ids: list[int]) -> dict[int, list[int]]:
    """Return {show_id: [pair_count, staff_count, guest_hold_count]} in two queries."""
    from sqlalchemy import func
    from app.models.pass_model import Pass

    if not show_ids:
        return {}
    available_rows = (
        db.query(Pass.show_id, Pass.pass_type, func.count(Pass.id))
        .filter(Pass.show_id.in_(show_ids), Pass.status == "available")
        .group_by(Pass.show_id, Pass.pass_type)
        .all()
    )
    counts: dict[int, list[int]] = {}
    for show_id, pass_type, cnt in available_rows:
        counts.setdefault(show_id, [0, 0, 0])
        if pass_type == "pair":
            counts[show_id][0] = cnt
        elif pass_type == "staff":
            counts[show_id][1] = cnt

    guest_rows = (
        db.query(Pass.show_id, func.count(Pass.id))
        .filter(
            Pass.show_id.in_(show_ids),
            Pass.pass_type == "staff",
            Pass.status == "claimed",
            Pass.guest_of_pass_id.isnot(None),
        )
        .group_by(Pass.show_id)
        .all()
    )
    for show_id, cnt in guest_rows:
        counts.setdefault(show_id, [0, 0, 0])
        counts[show_id][2] = cnt

    return counts


def _build_show_summary(
    show,
    pair_count: int = 0,
    staff_count: int = 0,
    guest_hold_count: int = 0,
    is_mine: bool = False,
) -> dict:
    """Build lean show dict for list endpoints — no passes or attempts."""
    return {
        "id": show.id,
        "event_name": show.event_name,
        "genre": show.genre,
        "venue": {"id": show.venue.id, "name": show.venue.name},
        "show_date": show.show_date,
        "show_time": show.show_time,
        "show_start_date": show.show_start_date,
        "caller_special_instructions": show.caller_special_instructions,
        "age_restriction": show.age_restriction,
        "wheelchair_accessible": show.wheelchair_accessible,
        "status": show.status,
        "num_pass_pairs": show.num_pass_pairs,
        "available_pair_count": pair_count,
        "available_staff_count": staff_count,
        "guest_hold_staff_count": guest_hold_count,
        "co_announce": show.co_announce,
        "published_at": show.published_at,
        "bands": [
            {
                "id": b.id,
                "show_id": b.show_id,
                "musicbrainz_id": b.musicbrainz_id,
                "band_name": b.band_name,
                "start_pos": b.start_pos,
                "end_pos": b.end_pos,
                "artist_type": b.artist_type,
                "artist_country": b.artist_country,
                "artist_disambiguation": b.artist_disambiguation,
                "artist_tags": b.artist_tags,
            }
            for b in show.bands or []
        ],
        "is_mine": is_mine,
    }


def _compute_mine_set(staff_id: int, db: Session) -> set[int]:
    """Return venue IDs that are 'mine' for a staff member (direct or via promoter)."""
    from app.models.venue import Venue as VenueModel

    owned_venue_ids = {
        row[0]
        for row in (
            db.query(VenueOwner.venue_id).filter(VenueOwner.staff_id == staff_id).all()
        )
    }
    owned_promoter_ids = {
        row[0]
        for row in (
            db.query(PromoterOwner.promoter_id)
            .filter(PromoterOwner.staff_id == staff_id)
            .all()
        )
    }
    via_promoter_venue_ids = {
        row[0]
        for row in (
            db.query(VenueModel.id)
            .filter(VenueModel.promoter_id.in_(owned_promoter_ids))
            .all()
        )
    }
    return owned_venue_ids, owned_promoter_ids, via_promoter_venue_ids


def _show_is_mine(
    show,
    owned_venue_ids: set[int],
    owned_promoter_ids: set[int],
    via_promoter_venue_ids: set[int],
) -> bool:
    if show.promoter_id is None:
        return show.venue_id in owned_venue_ids or show.venue_id in via_promoter_venue_ids
    return show.promoter_id in owned_promoter_ids


@router.get("", response_model=list[ShowSummary])
def list_shows(
    date_from: date | None = None,
    date_to: date | None = None,
    user_role: str = Depends(get_user_role_or_dj),
    email: str | None = Depends(get_current_user_email),
    db: Session = Depends(get_db),
):
    """List shows filtered by user role and optional date range."""
    shows = ShowService.list_shows(db, user_role, date_from=date_from, date_to=date_to)
    counts = _precompute_pass_counts(db, [s.id for s in shows])
    staff = _get_promotions_staff_by_email(db, email) if email else None
    if staff:
        owned_venue_ids, owned_promoter_ids, via_promoter_venue_ids = _compute_mine_set(
            staff.id, db
        )
        return [
            _build_show_summary(
                show,
                pair_count=counts.get(show.id, [0, 0, 0])[0],
                staff_count=counts.get(show.id, [0, 0, 0])[1],
                guest_hold_count=counts.get(show.id, [0, 0, 0])[2],
                is_mine=_show_is_mine(
                    show, owned_venue_ids, owned_promoter_ids, via_promoter_venue_ids
                ),
            )
            for show in shows
        ]
    return [
        _build_show_summary(
            show,
            pair_count=counts.get(show.id, [0, 0, 0])[0],
            staff_count=counts.get(show.id, [0, 0, 0])[1],
            guest_hold_count=counts.get(show.id, [0, 0, 0])[2],
        )
        for show in shows
    ]


@router.get("/search", response_model=list[ShowSummary])
def search_shows(
    freetext: str | None = None,
    venue_id: int | None = None,
    artist: str | None = None,
    genre: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    user_role: str = Depends(get_user_role_or_dj),
    db: Session = Depends(get_db),
):
    """Search shows with freetext and filters."""
    shows = ShowService.search_shows(
        db=db,
        user_role=user_role,
        freetext=freetext,
        venue_id=venue_id,
        artist=artist,
        genre=genre,
        date_from=date_from,
        date_to=date_to,
    )
    counts = _precompute_pass_counts(db, [s.id for s in shows])
    return [
        _build_show_summary(
            show,
            pair_count=counts.get(show.id, [0, 0, 0])[0],
            staff_count=counts.get(show.id, [0, 0, 0])[1],
            guest_hold_count=counts.get(show.id, [0, 0, 0])[2],
        )
        for show in shows
    ]


@router.post("", response_model=ShowResponse, status_code=status.HTTP_201_CREATED)
def create_show(
    show_data: ShowCreate,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Create a new show (promotions staff only)."""
    show = ShowService.create_show(db, show_data)

    if show_data.bands:
        new_bands = [ShowBand(show_id=show.id, **b.model_dump()) for b in show_data.bands]
        db.add_all(new_bands)
        db.commit()
        db.refresh(show)

    if show.auto_close and show.planned_close_date and show.planned_close_time:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        _LA = ZoneInfo("America/Los_Angeles")
        close_dt = datetime.combine(
            show.planned_close_date, show.planned_close_time, tzinfo=_LA
        )
        if close_dt > datetime.now(_LA):
            schedule_auto_close_job(show.id, close_dt)
    audit_service.log_event(
        db,
        event_type="show_created",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="show",
        entity_id=show.id,
        details={
            "event_name": show.event_name,
            "venue_id": show.venue_id,
            "show_date": str(show.show_date),
        },
    )
    return _build_show_response(show)


@router.get("/deleted", response_model=list[ShowResponse])
def list_deleted_shows(
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """List all soft-deleted shows (promotions staff only)."""
    shows = ShowService.list_deleted_shows(db)
    return [_build_show_response(show) for show in shows]


@router.get("/genres", response_model=list[str])
def list_genres(db: Session = Depends(get_db)):
    """
    Get all distinct genres used in existing shows, sorted alphabetically.

    Useful for autocomplete when creating or editing shows.
    """
    rows = (
        db.query(Show.genre).filter(Show.genre.isnot(None), Show.status != "deleted").all()
    )
    genres: set[str] = set()
    for (genre_list,) in rows:
        if genre_list:
            genres.update(genre_list)
    return sorted(genres)


@router.get("/suggest-genre")
def suggest_genre(event_name: str, db: Session = Depends(get_db)):
    """
    Suggest a genre for the given event name.

    First checks local DB for past shows with a matching name and returns the
    most recent genre. Falls back to a MusicBrainz artist tag lookup.
    """
    local_show = (
        db.query(Show)
        .filter(Show.event_name.ilike(f"%{event_name.strip()}%"), Show.genre.isnot(None))
        .order_by(Show.show_date.desc())
        .first()
    )
    if local_show and local_show.genre:
        return {"genres": local_show.genre}

    try:
        import musicbrainzngs

        musicbrainzngs.set_useragent(
            "kalx-promotions",
            "1.0",
            settings.api_contact_url,
        )
        result = musicbrainzngs.search_artists(artist=event_name, limit=1)
        artists = result.get("artist-list", [])
        if artists:
            artist = artists[0]
            tags = artist.get("tag-list", [])
            if tags:
                top_tag = max(tags, key=lambda t: int(t.get("count", 0)))
                genre = top_tag.get("name", "").title()
                if genre:
                    return {"genres": [genre]}
    except Exception as exc:
        logger.warning("MusicBrainz lookup failed for '%s': %s", event_name, exc)

    return {"genres": []}


@router.get("/musicbrainz/search")
def musicbrainz_search(name: str):
    """Proxy MusicBrainz artist search, returns top 10 matches with metadata."""
    try:
        import musicbrainzngs

        musicbrainzngs.set_useragent(
            "kalx-promotions",
            "1.0",
            settings.api_contact_url,
        )
        result = musicbrainzngs.search_artists(artist=name, limit=10)
        return [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "type": a.get("type"),
                "country": a.get("country"),
                "disambiguation": a.get("disambiguation"),
                "score": a.get("ext:score"),
                "tags": [t["name"] for t in (a.get("tag-list") or [])[:5]],
            }
            for a in result.get("artist-list", [])
        ]
    except Exception as exc:
        logger.warning("MusicBrainz search failed for '%s': %s", name, exc)
        return []


@router.get("/musicbrainz/artist/{artist_id}/wikipedia")
def get_artist_wikipedia(artist_id: str, db: Session = Depends(get_db)):
    """Fetch Wikipedia extract for a MusicBrainz artist via Wikidata sitelink."""
    import re

    headers = {
        "User-Agent": f"kalx-promotions/1.0 ({settings.api_contact_url})",
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        mb_data = fetch_cached(
            db,
            f"https://musicbrainz.org/ws/2/artist/{artist_id}?inc=url-rels&fmt=json",
            headers=headers,
        )

        wikidata_id = None
        for rel in mb_data.get("relations", []):
            if rel.get("type") == "wikidata":
                resource = rel.get("url", {}).get("resource", "")
                m = re.search(r"wikidata\.org/wiki/(Q\d+)", resource)
                if m:
                    wikidata_id = m.group(1)
                    break

        if not wikidata_id:
            return {"extract": None}

        wd_data = fetch_cached(
            db,
            "https://www.wikidata.org/w/api.php"
            f"?action=wbgetentities&ids={wikidata_id}&props=sitelinks"
            "&sitefilter=enwiki&format=json",
            headers=headers,
        )

        entity = wd_data.get("entities", {}).get(wikidata_id, {})
        wiki_title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
        if not wiki_title:
            return {"extract": None}

        wp_data = fetch_cached(
            db,
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_title.replace(' ', '_')}",
            headers=headers,
        )

        return {
            "extract": wp_data.get("extract"),
            "wikipedia_url": wp_data.get("content_urls", {}).get("desktop", {}).get("page"),
        }

    except Exception as exc:
        logger.warning("Wikipedia lookup failed for artist '%s': %s", artist_id, exc)
        return {"extract": None, "wikipedia_url": None}


@router.put("/{show_id}/bands", response_model=list[ShowBandResponse])
def update_show_bands(
    show_id: int,
    bands: list[ShowBandCreate],
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Replace the complete band annotation list for a show (promotions only)."""
    show = ShowService.get_show(db, show_id)
    db.query(ShowBand).filter(ShowBand.show_id == show.id).delete()
    new_bands = [ShowBand(show_id=show.id, **b.model_dump()) for b in bands]
    db.add_all(new_bands)
    db.commit()
    db.refresh(show)
    return show.bands


@router.get("/{show_id}", response_model=ShowResponse)
def get_show(show_id: int, db: Session = Depends(get_db)):
    """Get a show by ID."""
    show = ShowService.get_show(db, show_id)
    return _build_show_response(show)


@router.put("/{show_id}", response_model=ShowResponse)
def update_show(
    show_id: int,
    show_data: ShowUpdate,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Update a show (promotions staff only)."""
    from app.services.pass_service import PassService

    existing = ShowService.get_show(db, show_id)

    _fields_set = show_data.model_fields_set
    merged_close_date = (
        show_data.planned_close_date
        if "planned_close_date" in _fields_set
        else existing.planned_close_date
    )
    merged_close_time = (
        show_data.planned_close_time
        if "planned_close_time" in _fields_set
        else existing.planned_close_time
    )
    merged_show_date = (
        show_data.show_date if "show_date" in _fields_set else existing.show_date
    )
    merged_show_time = (
        show_data.show_time if "show_time" in _fields_set else existing.show_time
    )
    merged_show_start_date = (
        show_data.show_start_date
        if "show_start_date" in _fields_set
        else existing.show_start_date
    )
    if merged_close_date is not None:
        effective_show_date = (
            merged_show_start_date
            if merged_show_start_date is not None
            else merged_show_date
        )
        effective_show_time = (
            None if merged_show_start_date is not None else merged_show_time
        )
        if merged_close_date > effective_show_date or (
            merged_close_date == effective_show_date
            and (
                effective_show_time is None
                or (
                    merged_close_time is not None
                    and merged_close_time >= effective_show_time
                )
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="planned close date/time must be before the show date/time",
            )

    old_num_pass_pairs = existing.num_pass_pairs
    _tracked_fields = [
        "event_name",
        "genre",
        "venue_id",
        "show_date",
        "show_time",
        "show_start_date",
        "on_air_description",
        "caller_special_instructions",
        "age_restriction",
        "wheelchair_accessible",
        "num_pass_pairs",
        "planned_close_date",
        "planned_close_time",
        "auto_close",
    ]
    before = {f: str(getattr(existing, f)) for f in _tracked_fields}

    show = ShowService.update_show(db, show_id, show_data)

    if show_data.bands is not None:
        db.query(ShowBand).filter(ShowBand.show_id == show.id).delete()
        new_bands = [ShowBand(show_id=show.id, **b.model_dump()) for b in show_data.bands]
        db.add_all(new_bands)
        db.commit()
        db.refresh(show)

    # Adjust physical pass records when num_pass_pairs changes
    pass_adjustment = None
    if (
        show_data.num_pass_pairs is not None
        and show_data.num_pass_pairs != old_num_pass_pairs
    ):
        result = PassService.adjust_passes_for_show(db, show, show.num_pass_pairs)
        if result["affected_djs"] or result["affected_staff"]:
            pass_adjustment = result
            ShowService._notify_venue_owners_of_pass_reduction(
                db,
                show,
                result["affected_djs"],
                result["affected_staff"],
            )

    after = {f: str(getattr(show, f)) for f in _tracked_fields}
    changed_fields = {
        f: {"before": before[f], "after": after[f]}
        for f in _tracked_fields
        if before[f] != after[f]
    }
    audit_service.log_event(
        db,
        event_type="show_updated",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="show",
        entity_id=show.id,
        details={"event_name": show.event_name, "changed_fields": changed_fields},
    )

    if show.auto_close and show.planned_close_date and show.planned_close_time:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        _LA = ZoneInfo("America/Los_Angeles")
        close_dt = datetime.combine(
            show.planned_close_date, show.planned_close_time, tzinfo=_LA
        )
        if close_dt > datetime.now(_LA):
            schedule_auto_close_job(show.id, close_dt)
        else:
            unschedule_auto_close_job(show.id)
    else:
        unschedule_auto_close_job(show.id)
    return _build_show_response(show, pass_adjustment=pass_adjustment)


@router.post("/{show_id}/publish", response_model=ShowResponse)
def publish_show(
    show_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Publish a show (promotions staff only)."""
    from datetime import datetime, timedelta, timezone

    show = ShowService.publish_show(db, show_id)

    # Record publication timestamp for lottery window calculation
    show.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(show)

    # Schedule lottery draw if enabled
    if show.lottery_enabled:
        lottery_deadline = show.published_at + timedelta(hours=show.lottery_window_hours)
        schedule_lottery_job(show.id, lottery_deadline)

    audit_service.log_event(
        db,
        event_type="show_published",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="show",
        entity_id=show.id,
        details={"event_name": show.event_name},
    )
    return _build_show_response(show)


@router.post("/{show_id}/close", response_model=ShowResponse)
def close_show(
    show_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Close a show (promotions staff only)."""
    show = ShowService.close_show(db, show_id)
    unschedule_auto_close_job(show_id)
    _notify_staff_guests_confirmed(db, show)
    audit_service.log_event(
        db,
        event_type="show_closed",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="show",
        entity_id=show.id,
        details={"event_name": show.event_name},
    )
    return _build_show_response(show)


@router.post("/{show_id}/unpublish", response_model=ShowResponse)
def unpublish_show(
    show_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Unpublish a show, returning it to draft status (promotions staff only)."""
    from app.models.lottery_entry import LotteryEntry
    from app.services.lottery_service import LotteryService

    # Collect and notify pending lottery entrants before unpublishing
    pending_entries = (
        db.query(LotteryEntry)
        .filter(LotteryEntry.show_id == show_id, LotteryEntry.status == "pending")
        .all()
    )

    show = ShowService.get_show(db, show_id)
    if pending_entries:
        LotteryService.notify_entries_cancelled(db, show, pending_entries)
        for entry in pending_entries:
            db.delete(entry)
        db.commit()

    show = ShowService.unpublish_show(db, show_id)
    unschedule_auto_close_job(show_id)
    unschedule_lottery_job(show_id)

    audit_service.log_event(
        db,
        event_type="show_unpublished",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="show",
        entity_id=show.id,
        details={"event_name": show.event_name},
    )
    return _build_show_response(show)


@router.post("/{show_id}/reopen", response_model=ShowResponse)
def reopen_show(
    show_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Reopen a closed show, returning it to published status (promotions staff only)."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    show = ShowService.reopen_show(db, show_id)
    _LA = ZoneInfo("America/Los_Angeles")
    if show.auto_close and show.planned_close_date and show.planned_close_time:
        close_dt = datetime.combine(
            show.planned_close_date, show.planned_close_time, tzinfo=_LA
        )
        if close_dt > datetime.now(_LA):
            schedule_auto_close_job(show.id, close_dt)

    # Re-schedule lottery job if the window hasn't expired
    if show.lottery_enabled and show.published_at:
        lottery_deadline = show.published_at + timedelta(hours=show.lottery_window_hours)
        if lottery_deadline > datetime.now(timezone.utc):
            schedule_lottery_job(show.id, lottery_deadline)

    audit_service.log_event(
        db,
        event_type="show_reopened",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="show",
        entity_id=show.id,
        details={"event_name": show.event_name},
    )
    return _build_show_response(show)


@router.delete("/{show_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_show(
    show_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Soft-delete a show by marking its status as 'deleted' (promotions staff only)."""
    show = ShowService.get_show(db, show_id)
    event_name = show.event_name
    ShowService.delete_show(db, show_id, actor_email=promotions.email)
    unschedule_auto_close_job(show_id)
    unschedule_lottery_job(show_id)
    audit_service.log_event(
        db,
        event_type="show_deleted",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="show",
        entity_id=show_id,
        details={"event_name": event_name},
    )


@router.post("/{show_id}/undelete", response_model=ShowResponse)
def undelete_show(
    show_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Restore a soft-deleted show to draft status (promotions staff only)."""
    show = ShowService.undelete_show(db, show_id)
    audit_service.log_event(
        db,
        event_type="show_undeleted",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="show",
        entity_id=show.id,
        details={"event_name": show.event_name},
    )
    return _build_show_response(show)


@router.post("/{show_id}/attempt", response_model=ShowAttemptResponse)
def record_show_attempt(
    show_id: int,
    body: AttemptRequest,
    dj_access: bool = Depends(check_dj_access),
    db: Session = Depends(get_db),
):
    """
    Record a failed giveaway attempt for a show.

    Requires DJ access (DJ studio IP or promotions staff authentication).
    """
    attempt = ShowService.record_attempt(db, show_id, body.dj_name)
    return ShowAttemptResponse.model_validate(attempt)
