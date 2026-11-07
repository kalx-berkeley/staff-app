"""Guard the version links at the bottom of CHANGELOG.md."""

import re
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[3] / "CHANGELOG.md"
REPO_URL = "https://github.com/kalx-berkeley/staff-app"


def _expected_links(versions: list[str]) -> dict[str, str]:
    """
    Work out the link each version should have.

    :param versions: The versions in the changelog's headings, newest first
    :return: Each version's URL: a compare with the previous version, or the
        release page for the first version, which has nothing to compare with
    """
    links = {
        version: f"{REPO_URL}/compare/v{previous}...v{version}"
        for version, previous in zip(versions, versions[1:])
    }
    links[versions[-1]] = f"{REPO_URL}/releases/tag/v{versions[-1]}"
    return links


def test_every_version_has_the_right_link() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    versions = re.findall(r"^## \[([^\]]+)\]", text, flags=re.MULTILINE)
    links = dict(re.findall(r"^\[([^\]]+)\]: (\S+)$", text, flags=re.MULTILINE))

    assert versions, "found no version headings"
    assert links == _expected_links(versions)
