"""Configuration management for the application."""

import os
from typing import Optional
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(env_file=".env", case_sensitive=False)

    # Database
    database_url: str = "sqlite:///./promotions.db"

    # Airtable
    airtable_api_key: Optional[str] = None
    airtable_base_id: Optional[str] = None
    airtable_table_name: str = "KALX Active Staff Directory"

    # Spinitron
    spinitron_api_key: Optional[str] = None

    # Authentication
    dj_studio_network: str = "192.168.1.0/24"
    station_office_network: str = "192.168.0.0/16"

    # CORS - comma-separated list of allowed origins
    # For production, set to your actual domain(s)
    # Example: "https://promotions.example.com,https://www.example.com"
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Environment - controls staging-only features
    environment: str = "production"

    # Contact URL included in User-Agent for external API requests
    api_contact_url: str = "https://kalx.berkeley.edu"

    # Email notifications via smtp2go (primary) or the OS's local SMTP relay (fallback)
    smtp2go_api_key: Optional[str] = None
    email_from_address: str = "noreply@kalx.berkeley.edu"
    local_smtp_host: str = "localhost"
    local_smtp_port: int = 25

    # Venue logo storage directory (must be writable)
    venue_logo_dir: str = "./data/venue-logos"

    # Base URL for frontend links included in emails
    frontend_base_url: str = "https://kalx.berkeley.edu"

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


# Global settings instance
settings = Settings()
