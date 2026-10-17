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


@pytest.mark.parametrize("conf", ["staff.conf", "staff.stage.conf"])
def test_staff_site_proxies_short_links(conf):
    text = (SITES / conf).read_text()
    lines = [line.strip() for line in text.splitlines()]

    assert any(line.startswith("ProxyPass        /go/ http://127.0.0.1:") for line in lines)
    # DJ studio computers can follow short links instead of being sent to the
    # DJ view
    assert "RewriteCond %{REQUEST_URI} !^/go/" in lines
    # Only trusted-network clients skip the Google login; the backend then
    # asks them to sign in.
    block = text.split("<Location /go/>")[1].split("</Location>")[0]
    assert "<If \"-R '${KALX_STATION_OFFICE_NETWORK}'\">" in block
    assert block.index("OIDCUnAuthAction pass") > block.index("<If ")
    assert block.index("OIDCUnAuthAction pass") < block.index("</If>")
