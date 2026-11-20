"""Shared fuzzy-matching rule for tying artist/band names to shows.

Three services match artist/band names against a show's tagged artists
(ShowBand), just in different directions:

- feature_bin_service: many feature-bin artists against one show
- kalx_live_service: many KALX Live! bands against one show
- spin_match_service: one Spinitron spin artist against many candidate shows

None of them match against a show's event_name: promotions tags every band,
and an event name often holds other words (supporting acts, venue framing,
tour names) that an unrelated artist can coincidentally match. A show with
no tagged artists never matches.

A tagged artist is already an isolated, normalized name, so the only slop
expected is casing, punctuation and the odd typo, matched with a single
high-threshold `fuzz.ratio` call. 90 accepts plausible single-letter typos
like "Trough"/"Trogh" (91) while rejecting genuinely different short words
like "Cat"/"Bat" (67) or "Live"/"Life" (75).
"""

from rapidfuzz import fuzz
from rapidfuzz.utils import default_process

BAND_MATCH_THRESHOLD = 90


def is_band_name_match(name_a: str, name_b: str) -> bool:
    """Whether two tagged artist/band names are the same, allowing for typos."""
    return fuzz.ratio(name_a, name_b, processor=default_process) >= BAND_MATCH_THRESHOLD
