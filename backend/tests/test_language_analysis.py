"""Tests for on-air description language analysis."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.services.language_analysis_service import analyze_description


@pytest.fixture
def test_promotions_staff(db: Session):
    """Create a test promotions staff member."""
    staff = Staff(email="promotions@test.com", name="Test Promotions", phone="555-0100")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


def _categories(text: str) -> set[str]:
    """
    Return the set of finding categories reported for the text.

    :param text: Description to analyse
    :type text: str
    :returns: Categories of every finding
    :rtype: set[str]
    """
    return {finding.category for finding in analyze_description(text).findings}


def _phrases(text: str) -> list[str]:
    """
    Return the flagged phrases reported for the text, in order.

    :param text: Description to analyse
    :type text: str
    :returns: Matched phrases
    :rtype: list[str]
    """
    return [finding.phrase for finding in analyze_description(text).findings]


def test_neutral_description_has_no_findings():
    """Factual copy about the event is left alone."""
    result = analyze_description(
        "Fake Fruit plays the Rickshaw Stop on March 3 with Sour Widows. "
        "Doors at 8pm, 21+. The band released their second album in 2024."
    )

    assert result.findings == []
    assert result.reads_promotional is False
    assert result.summary == "No non-value-neutral language detected."


def test_empty_description_has_no_findings():
    """An empty or whitespace-only description is not analysed."""
    for text in (None, "", "   \n  "):
        result = analyze_description(text)
        assert result.findings == []
        assert result.sentiment_compound == 0.0


def test_tickets_are_flagged_as_terminology():
    """The word "tickets" must be replaced with "passes"."""
    result = analyze_description("Two tickets are available for this show.")

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.category == "terminology"
    assert finding.severity == "high"
    assert finding.phrase == "tickets"
    assert "passes" in finding.suggestion


@pytest.mark.parametrize("word", ["ticket", "Tickets", "TICKET"])
def test_ticket_is_flagged_in_any_form(word):
    """Singular, plural and shouted forms of "ticket" are all caught."""
    assert "terminology" in _categories(f"Winners pick up a {word} at will call.")


def test_ticketing_is_not_flagged():
    """Only the word itself is flagged, not longer words containing it."""
    assert _categories("Ticketing is handled by the venue.") == set()


def test_endorsement_language_is_flagged():
    """Praise of the act is reported as an endorsement."""
    result = analyze_description(
        "This legendary band delivers an unforgettable, electrifying set."
    )

    assert {f.category for f in result.findings} == {"endorsement"}
    assert [f.phrase for f in result.findings] == [
        "legendary",
        "unforgettable",
        "electrifying",
    ]


def test_call_to_action_is_flagged():
    """Telling the listener to attend is reported as a call to action."""
    assert "call_to_action" in _categories("Don't miss this show. Come out early.")


def test_comparative_claims_are_flagged():
    """Superlative and comparative claims about the act are reported."""
    assert "comparative" in _categories("One of the greatest live acts touring today.")
    assert "comparative" in _categories("They are better than anyone else on the bill.")


def test_best_known_for_is_not_a_comparative_claim():
    """ "Best known for" is factual attribution rather than a ranking."""
    assert _categories("The trio is best known for their 1997 debut.") == set()


def test_station_endorsement_is_flagged():
    """The station vouching for the show is reported as hype."""
    assert "hype" in _categories("We're thrilled to bring you this show.")


def test_exclamation_points_are_flagged_once():
    """Exclamation points produce a single aggregated finding."""
    findings = [
        f
        for f in analyze_description("Tonight! On stage!!").findings
        if f.category == "emphasis"
    ]

    assert len(findings) == 1
    assert "3 exclamation points" in findings[0].message


def test_shouted_words_are_flagged_but_known_acronyms_are_not():
    """All-caps emphasis is flagged; station and transit initialisms are not."""
    assert "emphasis" in _categories("This show is HUGE for the local scene.")
    assert _categories("KALX has a pair of passes. The venue is near BART.") == set()


def test_sentiment_pass_flags_words_outside_the_curated_lexicon():
    """Positively charged words VADER knows are reported as subjective."""
    result = analyze_description("A joyful, triumphant night of soul music.")

    assert "subjective" in {f.category for f in result.findings}
    assert result.reads_promotional is True


def test_giveaway_vocabulary_is_not_treated_as_opinion():
    """Words like "free" and "win" are factual in a pass giveaway."""
    assert (
        _categories("Enter to win a pair of passes. Parking is free and doors open at 7pm.")
        == set()
    )


def test_capitalised_words_are_treated_as_names_by_the_sentiment_pass():
    """Mid-sentence capitalised words are assumed to be names, not opinions."""
    assert (
        _categories("Joy Division tribute act Warsaw plays the UC Theatre on Friday.")
        == set()
    )


def test_overlapping_rules_report_one_finding():
    """ "One of the best" is reported once, not also as a bare "best"."""
    result = analyze_description("One of the best bands in Oakland.")

    assert [f.phrase for f in result.findings] == ["One of the best"]


def test_findings_are_ordered_by_position():
    """Findings are returned in the order they appear in the text."""
    result = analyze_description(
        "Don't miss this iconic band. Tickets are limited and they are amazing!"
    )

    positions = [f.start for f in result.findings]
    assert positions == sorted(positions)


def test_summary_counts_both_kinds_of_problem():
    """The summary mentions neutrality findings and ticket wording separately."""
    summary = analyze_description(
        "Don't miss this iconic band. Two tickets are up for grabs."
    ).summary

    assert "value neutral" in summary
    assert '"ticket"' in summary


def test_analyze_description_endpoint(client: TestClient, test_promotions_staff):
    """Promotions staff can analyse a description through the API."""
    response = client.post(
        "/api/shows/analyze-description",
        json={"text": "Don't miss this legendary band! Tickets are limited."},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )

    assert response.status_code == 200
    data = response.json()
    categories = {finding["category"] for finding in data["findings"]}
    assert {"call_to_action", "endorsement", "terminology"} <= categories
    assert data["summary"]
    assert -1.0 <= data["sentiment_compound"] <= 1.0


def test_analyze_description_endpoint_requires_promotions_staff(client: TestClient):
    """Only promotions staff can use the analysis endpoint."""
    unauthenticated = client.post(
        "/api/shows/analyze-description", json={"text": "Don't miss this show."}
    )
    assert unauthenticated.status_code == 400

    other_staff = client.post(
        "/api/shows/analyze-description",
        json={"text": "Don't miss this show."},
        headers={"X-Forwarded-User": "dj@test.com"},
    )
    assert other_staff.status_code == 403


def test_analyze_description_endpoint_rejects_overlong_text(
    client: TestClient, test_promotions_staff
):
    """Text longer than the description field is rejected."""
    response = client.post(
        "/api/shows/analyze-description",
        json={"text": "x" * 2001},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )

    assert response.status_code == 422
