"""Shared fuzzy-matching rules for tying artist/band names to shows.

Three services independently match artist/band names against shows by the
same two rules, just in different directions:

- feature_bin_service: many feature-bin artists against one show
- kalx_live_service: many KALX Live! bands against one show
- spin_match_service: one Spinitron spin artist against many candidate shows

The rules themselves (and their thresholds) are identical across all three,
so they live here once:

1. A tagged artist (ShowBand) is already an isolated, normalized name, so
   the only slop expected is casing/punctuation — matched with a single
   high-threshold `fuzz.ratio` call (`is_band_name_match`).
2. Otherwise, fall back to fuzzy-matching against the show's event_name.
   Multi-word names use `token_set_ratio`, which scores 100 whenever one
   side's tokens are a full subset of the other's — right for names with
   extra supporting-act/venue text around them, but unsafe for single-word
   names, where it would score 100 for any coincidental shared word
   regardless of context. Single-word names instead get a stricter,
   separate per-word `fuzz.ratio` comparison, gated by a minimum length and
   a cap on how many words the event name can have — see the constants
   below for the full rationale (in particular why 90 is safe: it accepts
   plausible single-letter typos like "Trough"/"Trogh" (91) while still
   rejecting genuinely different short words like "Cat"/"Bat" (67) or
   "Live"/"Life" (75)).
"""

import re

from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process

BAND_MATCH_THRESHOLD = 90
EVENT_NAME_MATCH_THRESHOLD = 85
SINGLE_WORD_EVENT_NAME_MATCH_THRESHOLD = BAND_MATCH_THRESHOLD
MIN_SINGLE_WORD_LENGTH = 4
MAX_EVENT_NAME_WORDS_FOR_SINGLE_WORD_MATCH = 3

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def event_name_words(event_name: str) -> list[str]:
    """Split an event name into individual words, for single-word name matching."""
    return _WORD_RE.findall(event_name)


def is_band_name_match(name_a: str, name_b: str) -> bool:
    """Whether two tagged artist/band names are the same, allowing for typos."""
    return fuzz.ratio(name_a, name_b, processor=default_process) >= BAND_MATCH_THRESHOLD


def match_names_against_event_name(event_name: str, candidates: dict[int, str]) -> set[int]:
    """Which of `candidates` (id -> artist/band name) fuzzy-match one event_name.

    Used when many candidate names are checked against a single fixed
    event_name (feature-bin releases or KALX Live! appearances against one
    show).
    """
    matched_ids: set[int] = set()

    multi_word = {cid: name for cid, name in candidates.items() if len(name.split()) > 1}
    if multi_word:
        results = process.extract(
            event_name,
            multi_word,
            # token_set_ratio (not token_sort_ratio) since event names typically
            # have extra words around the artist name — supporting acts, "w/",
            # venue framing — that token_sort_ratio's full-string comparison
            # would otherwise penalize heavily.
            scorer=fuzz.token_set_ratio,
            processor=default_process,
            score_cutoff=EVENT_NAME_MATCH_THRESHOLD,
            limit=None,
        )
        matched_ids.update(cid for _name, _score, cid in results)

    words = event_name_words(event_name)
    if words and len(words) <= MAX_EVENT_NAME_WORDS_FOR_SINGLE_WORD_MATCH:
        for cid, name in candidates.items():
            if (
                cid in matched_ids
                or len(name.split()) != 1
                or len(name) < MIN_SINGLE_WORD_LENGTH
            ):
                continue
            if any(
                fuzz.ratio(name, word, processor=default_process)
                >= SINGLE_WORD_EVENT_NAME_MATCH_THRESHOLD
                for word in words
            ):
                matched_ids.add(cid)

    return matched_ids


def match_event_names_against_name(name: str, candidates: dict[int, str]) -> set[int]:
    """Which of `candidates` (id -> event_name) fuzzy-match one fixed artist/band name.

    Mirror image of `match_names_against_event_name`, for when one fixed
    name is checked against many candidate event_names (a Spinitron spin's
    artist against many candidate shows). Multi/single-word handling is
    still driven by `name` (the artist), never by the candidate event_names,
    which are free-text and usually multi-word regardless.
    """
    matched_ids: set[int] = set()

    if len(name.split()) > 1:
        results = process.extract(
            name,
            candidates,
            scorer=fuzz.token_set_ratio,
            processor=default_process,
            score_cutoff=EVENT_NAME_MATCH_THRESHOLD,
            limit=None,
        )
        matched_ids.update(cid for _event_name, _score, cid in results)
        return matched_ids

    if len(name) < MIN_SINGLE_WORD_LENGTH:
        return matched_ids

    for cid, event_name in candidates.items():
        words = event_name_words(event_name)
        if not words or len(words) > MAX_EVENT_NAME_WORDS_FOR_SINGLE_WORD_MATCH:
            continue
        if any(
            fuzz.ratio(name, word, processor=default_process)
            >= SINGLE_WORD_EVENT_NAME_MATCH_THRESHOLD
            for word in words
        ):
            matched_ids.add(cid)

    return matched_ids
