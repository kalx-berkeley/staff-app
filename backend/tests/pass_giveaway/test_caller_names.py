"""Tests for grouping on-air winners' names that are probably the same caller."""

import pytest

from app.common.services.tracking_service import normalize_person_name
from app.pass_giveaway.services.caller_names import (
    group_similar_names,
    is_same_caller_name,
)


@pytest.mark.parametrize(
    "a, b",
    [
        ("John Smith", "Jon Smith"),
        ("John Smith", "John Smtih"),
        ("Katherine Lee", "Catherine Lee"),
        ("Sara Jones", "Sarah Jones"),
        ("Steven Park", "Stephen Park"),
        ("Sean Lee", "Shawn Lee"),
        ("Kristin Smith", "Christine Smith"),
        ("Phillip Nguyen", "Filip Nguen"),
        ("Jane Doe", "Jane M Doe"),
        ("Jane Doe", "Jane Melissa Doe"),
        ("Jane M. Doe", "Jane Melissa Doe"),
        ("Jane Melisa Doe", "Jane Melissa Doe"),
        ("Jessica", "Jesica"),
        ("jane  doe.", "Jane Doe"),
    ],
)
def test_similar_names_match(a, b):
    assert is_same_caller_name(normalize_person_name(a), normalize_person_name(b))


@pytest.mark.parametrize(
    "a, b",
    [
        ("Jane Doe", "Jane Smith"),
        ("Li Wei", "Lu Wei"),
        ("Jane Doe", "Jane"),
        ("Jane Doe", "Jane D"),
        ("Jane Doe", "Doe Jane"),
        ("Jane Doe", "John Doe"),
        ("John Lee", "Jen Lee"),
        ("Alan Park", "Ellen Park"),
        ("Jane M Doe", "Jane K Doe"),
        ("Jane Melissa Doe", "Jane Michelle Doe"),
        ("Jane M Doe", "Jane Ann Marie Doe"),
        ("", ""),
    ],
)
def test_different_names_dont_match(a, b):
    assert not is_same_caller_name(normalize_person_name(a), normalize_person_name(b))


def test_groups_are_transitive_and_skip_blanks():
    groups = group_similar_names(
        ["jon smith", "john smith", "john a smtih", "stephen smith", "bob lee", ""]
    )
    assert groups["jon smith"] == groups["john smith"] == groups["john a smtih"]
    assert groups["stephen smith"] == "stephen smith"
    assert groups["bob lee"] == "bob lee"
    assert "" not in groups
