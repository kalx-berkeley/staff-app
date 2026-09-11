"""Detection of non-value-neutral language in on-air show descriptions.

KALX is a non-commercial station, so the copy a DJ reads on air about a show we
are giving passes away for has to stay value neutral. It may state facts about
the event, but it may not praise the band, promote the show, or tell listeners
to go. This module flags copy that reads promotionally so that the promotions
staff member writing it gets a heads up before a DJ ever sees it.

Two passes run over the description:

* A curated lexicon of promotional phrasing -- qualitative praise, comparative
  and superlative claims, calls to action, station endorsement and hype
  punctuation -- matched as whole words and phrases.
* VADER (Valence Aware Dictionary and sEntiment Reasoner), a lexicon and rule
  based sentiment model, which scores the description as a whole and supplies
  valence for evaluative words the curated lexicon does not list.

Both passes are heuristics. Band names ("Legendary Shack Shakers"), genre
vocabulary and ordinary factual copy can all trip them, so every result is
advisory: the caller is expected to present findings as a suggestion that can
be ignored, never as a validation error.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Minimum VADER valence for a word not covered by the curated lexicon to be
# reported as subjective. The lexicon runs from -4.0 to +4.0; 1.5 keeps mildly
# positive words such as "play" (1.4) out of the results.
_SUBJECTIVE_VALENCE_THRESHOLD = 1.5

# Overall sentiment above which the description as a whole reads as enthusiastic
# rather than neutral, even when no individual phrase was flagged.
_PROMOTIONAL_POSITIVE_RATIO = 0.20
_PROMOTIONAL_COMPOUND = 0.40

# Words VADER scores positively that are ordinary factual vocabulary for a pass
# giveaway, a venue or a genre, and so must not be reported as opinion.
_NEUTRAL_WORDS = frozenset({
    "benefit",
    "benefits",
    "free",
    "hope",
    "party",
    "peace",
    "please",
    "share",
    "shares",
    "special",
    "support",
    "supported",
    "supporting",
    "supports",
    "thank",
    "thanks",
    "welcome",
    "welcomes",
    "win",
    "winner",
    "winners",
    "winning",
    "wins",
    "won",
})

# Capitalised strings that are names or initialisms rather than shouted emphasis.
_ALLOWED_ACRONYMS = frozenset({
    "KALX",
    "KPFA",
    "KQED",
    "BART",
    "NPR",
    "PBS",
    "LGBTQ",
    "LGBTQIA",
    "ASAP",
    "BYOB",
    "RSVP",
    "AAPI",
})

# Praise of the band or the show. These describe how good the act is rather
# than what the act is.
_ENDORSEMENT_WORDS = (
    "acclaimed",
    "amazing",
    "astonishing",
    "astounding",
    "awe-inspiring",
    "awesome",
    "beloved",
    "blistering",
    "breathtaking",
    "brilliant",
    "can't-miss",
    "celebrated",
    "critically acclaimed",
    "crowd favorite",
    "crowd-pleasing",
    "cult classic",
    "cult favorite",
    "dazzling",
    "definitive",
    "electrifying",
    "essential",
    "exceptional",
    "excellent",
    "exhilarating",
    "explosive",
    "extraordinary",
    "fabulous",
    "fan favorite",
    "fantastic",
    "flawless",
    "genre-defining",
    "groundbreaking",
    "iconic",
    "in fine form",
    "in top form",
    "incendiary",
    "incredible",
    "inimitable",
    "instant classic",
    "irresistible",
    "jaw-dropping",
    "legendary",
    "magical",
    "magnificent",
    "marvelous",
    "masterful",
    "mesmerizing",
    "mind-bending",
    "mind-blowing",
    "must-attend",
    "must-hear",
    "must-listen",
    "must-see",
    "next-level",
    "outstanding",
    "phenomenal",
    "powerhouse",
    "red-hot",
    "remarkable",
    "renowned",
    "revered",
    "revolutionary",
    "riveting",
    "scorching",
    "searing",
    "seminal",
    "sensational",
    "show-stopping",
    "showstopping",
    "spectacular",
    "spellbinding",
    "stellar",
    "storied",
    "sublime",
    "superb",
    "thrilling",
    "top-notch",
    "tour de force",
    "transcendent",
    "tremendous",
    "unbelievable",
    "unforgettable",
    "unmissable",
    "unstoppable",
    "virtuosic",
    "visionary",
    "wonderful",
    "world-class",
    "worth the price of admission",
    "worth the wait",
)

# Informal praise. Common in music writing and more likely than the words above
# to be part of a band name or a genre, so these are reported as lower
# confidence.
_COLLOQUIAL_PRAISE_WORDS = (
    "banging",
    "bonkers",
    "insane",
    "killer",
    "sick",
    "slaps",
    "straight fire",
    "the real deal",
)

# Comparative and superlative claims. "best known for" is factual attribution,
# not a ranking, so it is excluded below.
_COMPARATIVE_WORDS = (
    "better than",
    "bigger than",
    "finest",
    "greatest",
    "hands down",
    "hardest-working",
    "hottest",
    "like no other",
    "most anticipated",
    "most beloved",
    "most celebrated",
    "most exciting",
    "most important",
    "most influential",
    "most popular",
    "most talented",
    "no other band",
    "one of the best",
    "one of the finest",
    "one of the greatest",
    "one of the most",
    "second to none",
    "the biggest",
    "unparalleled",
    "unrivaled",
    "unrivalled",
)

# Weaker comparative claims: arguably verifiable, but still puffery on air.
_CREDENTIAL_WORDS = (
    "award-winning",
    "best-selling",
    "chart-topping",
    "number one",
    "premier",
    "top-selling",
)

# Telling the listener to attend, to act, or to hurry.
_CALL_TO_ACTION_WORDS = (
    "act fast",
    "act now",
    "be sure to",
    "be there",
    "bring a friend",
    "bring your friends",
    "check it out",
    "check out",
    "check them out",
    "come celebrate",
    "come check",
    "come down",
    "come join",
    "come out",
    "come see",
    "do not miss",
    "don't miss",
    "don't sleep on",
    "don't wait",
    "get your",
    "grab your",
    "head down",
    "head over",
    "hurry",
    "join us",
    "limited passes",
    "limited time",
    "make sure to",
    "make sure you",
    "mark your calendar",
    "not to be missed",
    "save the date",
    "see you there",
    "snag",
    "spread the word",
    "stop by",
    "swing by",
    "tell your friends",
    "while supplies last",
    "while they last",
    "you don't want to miss",
    "you have to",
    "you need to",
    "you won't want to miss",
    "you've got to",
)

# The station, or the listener, vouching for the show.
_HYPE_WORDS = (
    "believe us",
    "can't wait",
    "do yourself a favor",
    "excited to",
    "if you only see one show",
    "one of our favorites",
    "our favorite",
    "proud to present",
    "take our word",
    "thrilled to",
    "treat yourself",
    "trust us",
    "we are excited",
    "we are proud",
    "we are thrilled",
    "we love",
    "we're excited",
    "we're proud",
    "we're thrilled",
    "you will love",
    "you'll love",
    "your new favorite",
)


# A word, including internal apostrophes and hyphens.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")


@dataclass(frozen=True)
class Finding:
    """A single span of the description that may not be value neutral."""

    category: str
    severity: str
    phrase: str
    start: int
    end: int
    message: str
    suggestion: str


@dataclass(frozen=True)
class DescriptionAnalysis:
    """The result of analysing one on-air description."""

    findings: list[Finding]
    sentiment_compound: float
    sentiment_positive: float
    reads_promotional: bool
    summary: str


@dataclass(frozen=True)
class _Rule:
    """A compiled lexicon rule and how its matches should be reported."""

    pattern: re.Pattern[str]
    category: str
    severity: str
    message: str
    suggestion: str


def _phrase_regex(phrases: tuple[str, ...], suffix: str = "") -> re.Pattern[str]:
    """
    Compile a case-insensitive whole-word regex matching any of the phrases.

    Spaces in a phrase match any run of whitespace (so a phrase still matches
    across a line break), hyphens match a hyphen or a space, and apostrophes
    match both the ASCII and the typographic form.

    :param phrases: Literal words or phrases to match
    :type phrases: tuple[str, ...]
    :param suffix: Optional regex appended after the phrase alternation, used
        for lookarounds that exclude factual uses of a word
    :type suffix: str
    :returns: Compiled alternation of the phrases
    :rtype: re.Pattern[str]
    """
    alternatives = []
    # Longest first so that "one of the best" wins over "the best".
    for phrase in sorted(phrases, key=len, reverse=True):
        escaped = re.escape(phrase)
        escaped = escaped.replace(r"\ ", r"\s+")
        escaped = escaped.replace(r"\-", r"[-\s]")
        escaped = escaped.replace("'", "['’]")
        alternatives.append(escaped)
    return re.compile(r"\b(?:" + "|".join(alternatives) + r")\b" + suffix, re.IGNORECASE)


_RULES: tuple[_Rule, ...] = (
    _Rule(
        pattern=re.compile(r"\btickets?\b", re.IGNORECASE),
        category="terminology",
        severity="high",
        message='"{phrase}" cannot be used on air.',
        suggestion='We give away passes, not tickets. Use "pass" or "passes".',
    ),
    _Rule(
        pattern=_phrase_regex(_CALL_TO_ACTION_WORDS),
        category="call_to_action",
        severity="high",
        message='"{phrase}" urges the listener to go to the show.',
        suggestion="Drop the exhortation and let the event details stand on their own.",
    ),
    _Rule(
        pattern=_phrase_regex(_COMPARATIVE_WORDS),
        category="comparative",
        severity="high",
        message='"{phrase}" ranks the act against others.',
        suggestion="Remove the comparison, or replace it with a checkable fact.",
    ),
    _Rule(
        # "best" on its own, except in "best known for", which is attribution.
        pattern=re.compile(r"\bbest\b(?!\s+known\b)", re.IGNORECASE),
        category="comparative",
        severity="high",
        message='"{phrase}" is a superlative claim about the act.',
        suggestion="Remove the comparison, or replace it with a checkable fact.",
    ),
    _Rule(
        pattern=_phrase_regex(_CREDENTIAL_WORDS),
        category="comparative",
        severity="medium",
        message='"{phrase}" is promotional shorthand for the act\'s standing.',
        suggestion=(
            "State the specific fact instead (which award, which chart, which year)"
            " or leave it out."
        ),
    ),
    _Rule(
        pattern=_phrase_regex(_ENDORSEMENT_WORDS),
        category="endorsement",
        severity="high",
        message='"{phrase}" praises the act rather than describing it.',
        suggestion=(
            "Say what the act is -- genre, members, releases, history -- instead of"
            " how good it is."
        ),
    ),
    _Rule(
        pattern=_phrase_regex(_COLLOQUIAL_PRAISE_WORDS),
        category="endorsement",
        severity="medium",
        message='"{phrase}" reads as informal praise for the act.',
        suggestion=(
            "Say what the act is -- genre, members, releases, history -- instead of"
            " how good it is."
        ),
    ),
    _Rule(
        pattern=_phrase_regex(_HYPE_WORDS),
        category="hype",
        severity="high",
        message='"{phrase}" has the station vouching for the show.',
        suggestion="Keep KALX's own enthusiasm out of the description.",
    ),
)


# Every single word the curated rules above own, so that the sentiment pass does
# not second-guess them -- notably "best", which the rule above deliberately
# leaves alone in "best known for".
_CURATED_VOCABULARY = frozenset(
    phrase.lower()
    for group in (
        _ENDORSEMENT_WORDS,
        _COLLOQUIAL_PRAISE_WORDS,
        _COMPARATIVE_WORDS,
        _CREDENTIAL_WORDS,
        _CALL_TO_ACTION_WORDS,
        _HYPE_WORDS,
    )
    for phrase in group
) | {"best", "ticket", "tickets"}


@lru_cache(maxsize=1)
def _analyzer() -> SentimentIntensityAnalyzer:
    """
    Return the shared VADER analyzer.

    The analyzer parses its 7,500 term lexicon on construction, so it is built
    once and reused for the life of the process.

    :returns: Sentiment analyzer
    :rtype: SentimentIntensityAnalyzer
    """
    return SentimentIntensityAnalyzer()


def _is_proper_noun(text: str, match: re.Match[str]) -> bool:
    """
    Guess whether a matched word is a name rather than an ordinary word.

    A word that is capitalised but not at the start of a sentence is far more
    likely to belong to a band, album or venue name ("The Amazing Snakeheads")
    than to be an evaluation. At the start of a sentence capitalisation says
    nothing on its own, so a capitalised word immediately followed by another
    capitalised one is taken to be a name there ("Joy Division plays ..."),
    while a lone capitalised word is not. Words in all capitals are excluded,
    since those are shouted emphasis rather than names.

    :param text: The full description
    :type text: str
    :param match: A word match within that description
    :type match: re.Match[str]
    :returns: True if the word looks like part of a proper noun
    :rtype: bool
    """
    word = match.group(0)
    if not word[0].isupper() or word.isupper():
        return False
    preceding = text[: match.start()].rstrip()
    if preceding and preceding[-1] not in ".!?:":
        return True
    following = _WORD_RE.search(text, match.end())
    return bool(following) and following.group(0)[0].isupper()


def _evaluative_text(text: str) -> str:
    """
    Strip the words that would skew the whole-description sentiment score.

    Names and factual giveaway vocabulary carry sentiment in the VADER lexicon
    without expressing any opinion about the show -- "Joy Division", "free
    parking" and "a pair of passes to win" would otherwise score as strongly
    positive copy. Removing them leaves the evaluative content to be scored.

    :param text: Description to analyse
    :type text: str
    :returns: The description with names and neutral vocabulary removed
    :rtype: str
    """

    def keep(match: re.Match[str]) -> str:
        if match.group(0).lower().strip("'’-") in _NEUTRAL_WORDS:
            return " "
        return " " if _is_proper_noun(text, match) else match.group(0)

    return _WORD_RE.sub(keep, text)


def _lexicon_findings(text: str) -> list[Finding]:
    """
    Match every curated rule against the text.

    :param text: Description to analyse
    :type text: str
    :returns: Findings in the order the rules are declared
    :rtype: list[Finding]
    """
    findings = []
    for rule in _RULES:
        for match in rule.pattern.finditer(text):
            phrase = match.group(0)
            findings.append(
                Finding(
                    category=rule.category,
                    severity=rule.severity,
                    phrase=phrase,
                    start=match.start(),
                    end=match.end(),
                    message=rule.message.format(phrase=phrase),
                    suggestion=rule.suggestion,
                )
            )
    return findings


def _sentiment_findings(text: str) -> list[Finding]:
    """
    Flag positively charged words that the curated lexicon does not list.

    Words are scored with the VADER lexicon. Only positive valence is
    considered: negative valence in this domain is almost always genre
    vocabulary ("death", "doom", "kill") rather than an opinion about the show.
    Words that are capitalised mid-sentence are skipped, since they are far more
    likely to be part of a band, album or venue name than an evaluation.

    :param text: Description to analyse
    :type text: str
    :returns: Findings for each subjective word occurrence
    :rtype: list[Finding]
    """
    lexicon = _analyzer().lexicon
    findings = []
    for match in _WORD_RE.finditer(text):
        word = match.group(0)
        lowered = word.lower().strip("'’-")
        if lowered in _NEUTRAL_WORDS or lowered in _CURATED_VOCABULARY:
            continue
        valence = lexicon.get(lowered)
        if valence is None or valence < _SUBJECTIVE_VALENCE_THRESHOLD:
            continue
        if _is_proper_noun(text, match):
            continue
        findings.append(
            Finding(
                category="subjective",
                severity="low",
                phrase=word,
                start=match.start(),
                end=match.end(),
                message=(
                    f'"{word}" carries positive sentiment (VADER valence'
                    f" {valence:+.1f}), so it reads as an opinion."
                ),
                suggestion="Use neutral wording, or cut the description of quality.",
            )
        )
    return findings


def _emphasis_findings(text: str) -> list[Finding]:
    """
    Flag typographic hype: exclamation points and shouted words.

    :param text: Description to analyse
    :type text: str
    :returns: Findings for emphatic punctuation and capitalisation
    :rtype: list[Finding]
    """
    findings = []
    exclamations = [match.start() for match in re.finditer(r"!", text)]
    if exclamations:
        count = len(exclamations)
        findings.append(
            Finding(
                category="emphasis",
                severity="low",
                phrase="!",
                start=exclamations[0],
                end=exclamations[0] + 1,
                message=(
                    f"The description uses {count} exclamation"
                    f" point{'s' if count > 1 else ''}, which reads as excitement"
                    " about the show."
                ),
                suggestion="Use a period instead.",
            )
        )
    for match in re.finditer(r"\b[A-Z]{4,}\b", text):
        word = match.group(0)
        if word in _ALLOWED_ACRONYMS:
            continue
        findings.append(
            Finding(
                category="emphasis",
                severity="low",
                phrase=word,
                start=match.start(),
                end=match.end(),
                message=f'"{word}" is in all capitals, which reads as emphasis.',
                suggestion=(
                    "Use ordinary capitalisation unless the name is styled that way."
                ),
            )
        )
    return findings


def _deduplicate(findings: list[Finding]) -> list[Finding]:
    """
    Drop findings whose span is already covered by an earlier, stronger finding.

    Rules overlap by design -- "one of the best" matches both the comparative
    phrase list and the bare "best" rule -- and the text should only be flagged
    once per span.

    :param findings: Findings from every pass, strongest rule first
    :type findings: list[Finding]
    :returns: Non-overlapping findings ordered by position in the text
    :rtype: list[Finding]
    """
    kept: list[Finding] = []
    for finding in findings:
        overlaps = any(
            finding.start < existing.end and existing.start < finding.end
            for existing in kept
        )
        if not overlaps:
            kept.append(finding)
    return sorted(kept, key=lambda finding: finding.start)


def _summarize(findings: list[Finding], reads_promotional: bool) -> str:
    """
    Build the one-line summary shown above the list of findings.

    :param findings: Deduplicated findings
    :type findings: list[Finding]
    :param reads_promotional: Whether overall sentiment reads as enthusiastic
    :type reads_promotional: bool
    :returns: Human readable summary
    :rtype: str
    """
    terminology = sum(1 for f in findings if f.category == "terminology")
    neutrality = len(findings) - terminology
    parts = []
    if neutrality:
        parts.append(
            f"{neutrality} phrase{'s' if neutrality > 1 else ''} may not be value neutral"
        )
    if terminology:
        parts.append(
            f"{terminology} use{'s' if terminology > 1 else ''} of \"ticket\" needs to"
            ' be "pass"'
        )
    if not parts:
        if reads_promotional:
            return "The description reads as enthusiastic rather than neutral overall."
        return "No non-value-neutral language detected."
    summary = " and ".join(parts).capitalize() + "."
    if reads_promotional:
        summary += " Overall the description reads as enthusiastic rather than neutral."
    return summary


def analyze_description(text: str | None) -> DescriptionAnalysis:
    """
    Analyse an on-air description for language that is not value neutral.

    :param text: The on-air description as typed by the promotions staff member
    :type text: str | None
    :returns: Findings, overall sentiment scores and a summary line
    :rtype: DescriptionAnalysis
    """
    text = text or ""
    if not text.strip():
        return DescriptionAnalysis(
            findings=[],
            sentiment_compound=0.0,
            sentiment_positive=0.0,
            reads_promotional=False,
            summary="No non-value-neutral language detected.",
        )

    scores = _analyzer().polarity_scores(_evaluative_text(text))
    reads_promotional = (
        scores["pos"] >= _PROMOTIONAL_POSITIVE_RATIO
        and scores["compound"] >= _PROMOTIONAL_COMPOUND
    )
    findings = _deduplicate(
        _lexicon_findings(text) + _sentiment_findings(text) + _emphasis_findings(text)
    )
    return DescriptionAnalysis(
        findings=findings,
        sentiment_compound=scores["compound"],
        sentiment_positive=scores["pos"],
        reads_promotional=reads_promotional,
        summary=_summarize(findings, reads_promotional),
    )
