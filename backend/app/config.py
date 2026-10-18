"""Configuration management for the application."""

import os
from typing import Optional
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(env_file=".env", case_sensitive=False)

    # Database
    database_url: str = "sqlite:///./staff-app.db"

    # Airtable
    airtable_api_key: Optional[str] = None
    airtable_base_id: Optional[str] = None
    airtable_table_name: str = "Online Staff App Directory"
    # Table that the staff table's "Department" linked-record field links to.
    # Its "Department" (primary) field holds each department's name.
    airtable_departments_table_name: str = "All departments"
    # Where the Airtable sync stores resized staff directory photos. Relative
    # paths are relative to the backend's working directory; in deployments
    # that's backend/, so this is backend/data/staff_photos alongside the
    # database, which deploys leave in place.
    staff_photo_dir: str = "data/staff_photos"
    # KALX Workforms: the table submitted workforms are written to. Staging uses
    # "Testing Workforms"; production sets "Workforms" (same structure).
    airtable_workforms_table_name: str = "Testing Workforms"
    # Maps each department ("Department", linked to the departments table) to
    # its heads ("Department Heads", linked to the staff table). Its
    # departments are the departments a workform can report hours in.
    airtable_department_heads_table_name: str = "Department Heads"

    # Whether the KALX Workforms sub-site is on: its API, scheduled jobs and
    # Airtable syncs, and its home page card. Off by default; deploy.yml turns
    # it on in staging only while the sub-site is under construction.
    workforms_enabled: bool = False
    # KALX Workforms: a month's workform is due by the end of this day of the
    # following month (Pacific time); later submissions are marked late.
    workforms_deadline_day: int = 5
    # Whether to send the workforms reminder and review emails. Off while the
    # sub-site is under construction and not the official way to submit.
    workforms_emails_enabled: bool = False
    # The department whose heads review departments that have no head, and
    # department heads' own hours.
    workforms_operations_department: str = "Operations"

    # Spinitron
    spinitron_api_key: Optional[str] = None

    # Spinitron persona IDs that represent a rotating slot rather than a specific DJ
    # (e.g. "DJ Trainee", "KALX Overnights") — comma-separated. A show hosted by one
    # of these is treated the same as a show with no persona listed at all: the
    # on-air schedule sync stores no DJ name for it, so the DJ Name field is neither
    # auto-filled nor flagged as mismatched during that show.
    # Current list: DJ Trainee (176287), Special Events Staff (186839),
    # KALX Overnights (169919), Sports Staff (195674), Campus Podcasts (176342),
    # Rotating Dj (193517).
    spinitron_placeholder_persona_ids: str = "176287,186839,169919,195674,176342,193517"
    # Spinitron show titles that aren't a DJ or specialty show anyone could be
    # pre-assigned passes for — comma-separated, matched case-insensitively.
    # FREEFORM is the default title of every regular DJ's show, and OVERNIGHTS
    # is pre-recorded with no live DJ. They're left out of every DJ name
    # suggestion and autocomplete.
    spinitron_non_dj_show_titles: str = "FREEFORM,OVERNIGHTS"

    # Authentication
    dj_studio_network: str = "192.168.1.0/24"
    station_office_network: str = "192.168.0.0/16"
    # Extra site admins, besides department heads and Paid Staff: a
    # comma-separated list of emails, matched case-insensitively. They must
    # still be Active staff. Set per environment via SITE_ADMIN_EMAILS.
    site_admin_emails: str = ""

    # CORS - comma-separated list of allowed origins
    # For production, set to your actual domain(s)
    # Example: "https://promotions.example.com,https://www.example.com"
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Environment - controls staging-only features
    environment: str = "production"

    # Contact URL included in User-Agent for external API requests
    api_contact_url: str = "https://cs.cementhorizon.com/contact/"

    # Email notifications via smtp2go (primary) or the OS's local SMTP relay (fallback)
    smtp2go_api_key: Optional[str] = None
    email_from_address: str = "noreply@kalx.berkeley.edu"
    local_smtp_host: str = "localhost"
    local_smtp_port: int = 25

    # Venue logo storage directory (must be writable)
    venue_logo_dir: str = "./data/venue-logos"

    # Base URL for frontend links included in emails. Must be set per-environment
    # (deploy.yml derives this from SITE_DOMAIN: https://staff.<SITE_DOMAIN> in
    # production, https://staff.stage.<SITE_DOMAIN> in staging) — otherwise emails
    # sent from staging link back to production, or vice versa.
    frontend_base_url: str = "https://staff.kalx.berkeley.edu"

    # Webmaster email address for receiving user feedback
    webmaster_email: Optional[str] = None

    # Legacy paper-form import feature — set to True only during cutover from paper forms
    legacy_import_enabled: bool = False

    # Feature bin (KALX music library new-arrivals) Google Sheet, fetched nightly.
    # Not given a default here since the sheet ID isn't public data and this repo
    # is public — set via the FEATURE_BIN_SHEET_ID/FEATURE_BIN_SHEET_GID env vars.
    # FeatureBinService treats the feature as disabled when either is unset.
    # Currently a public sheet fetched via CSV export; no auth required. If it
    # becomes restricted, FeatureBinService.fetch_sheet_csv is the only place that
    # needs to change (e.g. to an authenticated Sheets API v4 call).
    feature_bin_sheet_id: Optional[str] = None
    feature_bin_sheet_gid: Optional[str] = None

    # KALX Live! (weekly in-studio live band performances) public Google
    # Calendar, fetched nightly as an ICS export. Not given a default here
    # since this repo is public — set via the KALX_LIVE_CALENDAR_ID env var.
    # KalxLiveService treats the feature as disabled when unset.
    kalx_live_calendar_id: Optional[str] = None


# Global settings instance. The test suite ignores .env so it runs with the same
# settings locally as in CI, where there is no .env.
settings = Settings(_env_file=None) if os.getenv("TESTING") == "1" else Settings()
