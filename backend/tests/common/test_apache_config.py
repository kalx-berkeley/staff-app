"""
Check the Apache config the backend's access checks rely on.

The backend trusts X-Forwarded-User (who is signed in) and the X-DJ-Network /
X-Station-Office-Network headers (which network a guest is on) because Apache
removes any client-sent values before setting its own. If either staff VirtualHost
stopped removing them, anyone could claim to be any user.
"""

from pathlib import Path

import pytest

SITES = Path(__file__).resolve().parents[3] / "apache" / "sites"

STRIPPED_HEADERS = [
    "X-Forwarded-User",
    "X-Forwarded-For",
    "X-DJ-Network",
    "X-Station-Office-Network",
]


@pytest.mark.parametrize("conf", ["staff.conf", "staff.stage.conf"])
def test_staff_site_strips_client_identity_headers(conf):
    lines = [line.strip() for line in (SITES / conf).read_text().splitlines()]

    for header in STRIPPED_HEADERS:
        assert f"RequestHeader unset {header} early" in lines, f"{conf}: {header}"
    # X-Forwarded-User is only ever set from a signed-in OIDC session.
    assert (
        'RequestHeader set X-Forwarded-User "%{OIDC_CLAIM_email}e" env=OIDC_CLAIM_email'
        in lines
    )
