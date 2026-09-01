"""Tests for CIDR network matching functionality."""

import pytest
from pathlib import Path
from unittest.mock import patch
from app.auth import is_ip_in_network
from app.main import check_network_config


def test_single_ip_match():
    """Test matching a single IP with /32 CIDR."""
    assert is_ip_in_network("192.168.1.100", "192.168.1.100/32") is True
    assert is_ip_in_network("192.168.1.101", "192.168.1.100/32") is False


def test_subnet_match():
    """Test matching IPs within a subnet."""
    network = "192.168.1.0/24"

    # Should match
    assert is_ip_in_network("192.168.1.1", network) is True
    assert is_ip_in_network("192.168.1.100", network) is True
    assert is_ip_in_network("192.168.1.255", network) is True

    # Should not match
    assert is_ip_in_network("192.168.2.1", network) is False
    assert is_ip_in_network("192.168.0.255", network) is False
    assert is_ip_in_network("10.0.0.1", network) is False


def test_larger_network():
    """Test matching IPs within a larger network."""
    network = "192.168.0.0/16"

    # Should match
    assert is_ip_in_network("192.168.0.1", network) is True
    assert is_ip_in_network("192.168.1.100", network) is True
    assert is_ip_in_network("192.168.255.255", network) is True

    # Should not match
    assert is_ip_in_network("192.167.1.1", network) is False
    assert is_ip_in_network("192.169.1.1", network) is False
    assert is_ip_in_network("10.0.0.1", network) is False


def test_invalid_ip():
    """Test handling of invalid IP addresses."""
    network = "192.168.1.0/24"

    assert is_ip_in_network("invalid", network) is False
    assert is_ip_in_network("999.999.999.999", network) is False
    assert is_ip_in_network("", network) is False


def test_invalid_network():
    """Test handling of invalid network CIDR."""
    ip = "192.168.1.100"

    assert is_ip_in_network(ip, "invalid") is False
    assert is_ip_in_network(ip, "192.168.1.0/99") is False
    assert is_ip_in_network(ip, "") is False


def test_ipv6_support():
    """Test IPv6 address matching."""
    network = "2001:db8::/32"

    # Should match
    assert is_ip_in_network("2001:db8::1", network) is True
    assert is_ip_in_network("2001:db8:1234::1", network) is True

    # Should not match
    assert is_ip_in_network("2001:db9::1", network) is False
    assert is_ip_in_network("::1", network) is False


def test_network_without_strict():
    """Test that network matching works without strict mode."""
    # This should work even though 192.168.1.100 is not a network address
    assert is_ip_in_network("192.168.1.100", "192.168.1.100/24") is True
    assert is_ip_in_network("192.168.1.50", "192.168.1.100/24") is True


# ─── check_network_config tests ───────────────────────────────────────────────

_SETTINGS_BASE = {
    "dj_studio_network": "10.0.1.0/24",
    "station_office_network": "10.0.0.0/16",
    "environment": "production",
}


def _make_conf(tmp_path: Path, content: str) -> str:
    p = tmp_path / "kalx-variables.conf"
    p.write_text(content)
    return str(p)


def test_check_network_config_matching_values(tmp_path, caplog):
    """No critical log when Apache Define matches the env var."""
    conf = _make_conf(
        tmp_path,
        "Define KALX_DJ_STUDIO_NETWORK 10.0.1.0/24\n",
    )
    with patch("app.main.settings", **_SETTINGS_BASE):
        with caplog.at_level("CRITICAL"):
            check_network_config(conf)
    assert not any("MISMATCH" in r.message for r in caplog.records)
    assert not any("ERROR" in r.message for r in caplog.records)


def test_check_network_config_mismatched_values(tmp_path, caplog):
    """Critical log when Apache Define differs from the env var."""
    conf = _make_conf(
        tmp_path,
        "Define KALX_DJ_STUDIO_NETWORK 10.0.2.0/24\n",
    )
    with patch("app.main.settings", **_SETTINGS_BASE):
        with caplog.at_level("CRITICAL"):
            check_network_config(conf)
    assert any("MISMATCH" in r.message for r in caplog.records)


def test_check_network_config_staging_uses_kalxstage_define(tmp_path, caplog):
    """Staging environment checks KALXSTAGE_DJ_STUDIO_NETWORK, not KALX_DJ_STUDIO_NETWORK."""
    conf = _make_conf(
        tmp_path,
        "Define KALX_DJ_STUDIO_NETWORK 10.0.9.0/24\n"
        "Define KALXSTAGE_DJ_STUDIO_NETWORK 10.0.1.0/24\n",
    )
    staging_settings = {**_SETTINGS_BASE, "environment": "staging"}
    with patch("app.main.settings", **staging_settings):
        with caplog.at_level("CRITICAL"):
            check_network_config(conf)
    assert not any("MISMATCH" in r.message for r in caplog.records)


def test_check_network_config_missing_file(caplog):
    """Warning (not critical) when the Apache conf file is absent."""
    with patch("app.main.settings", **_SETTINGS_BASE):
        with caplog.at_level("WARNING"):
            check_network_config("/nonexistent/path/kalx-variables.conf")
    assert any("not found" in r.message for r in caplog.records)
    assert not any(r.levelname == "CRITICAL" for r in caplog.records)


def test_check_network_config_missing_define(tmp_path, caplog):
    """Warning when the file exists but the expected Define is absent."""
    conf = _make_conf(tmp_path, "# no defines here\n")
    with patch("app.main.settings", **_SETTINGS_BASE):
        with caplog.at_level("WARNING"):
            check_network_config(conf)
    assert any("Could not find" in r.message for r in caplog.records)


def test_check_network_config_dj_not_subnet_of_office(tmp_path, caplog):
    """Critical log when DJ_STUDIO_NETWORK is not a subnet of STATION_OFFICE_NETWORK."""
    conf = _make_conf(
        tmp_path,
        "Define KALX_DJ_STUDIO_NETWORK 10.0.1.0/24\n",
    )
    bad_settings = {**_SETTINGS_BASE, "station_office_network": "192.168.0.0/16"}
    with patch("app.main.settings", **bad_settings):
        with caplog.at_level("CRITICAL"):
            check_network_config(conf)
    assert any("not a subnet" in r.message for r in caplog.records)


def test_check_network_config_dj_is_subnet_of_office(tmp_path, caplog):
    """No critical log when DJ_STUDIO_NETWORK is correctly contained in STATION_OFFICE_NETWORK."""
    conf = _make_conf(
        tmp_path,
        "Define KALX_DJ_STUDIO_NETWORK 10.0.1.0/24\n",
    )
    with patch("app.main.settings", **_SETTINGS_BASE):
        with caplog.at_level("CRITICAL"):
            check_network_config(conf)
    assert not any("not a subnet" in r.message for r in caplog.records)


def test_check_network_config_invalid_cidr(tmp_path, caplog):
    """Critical log when a CIDR value is unparseable."""
    conf = _make_conf(
        tmp_path,
        "Define KALX_DJ_STUDIO_NETWORK 10.0.1.0/24\n",
    )
    bad_settings = {**_SETTINGS_BASE, "station_office_network": "not-a-cidr"}
    with patch("app.main.settings", **bad_settings):
        with caplog.at_level("CRITICAL"):
            check_network_config(conf)
    assert any("Invalid CIDR" in r.message for r in caplog.records)
