"""
Grouping on-air winners' names that are probably the same caller.

DJs type a caller's name as they hear it over the phone, so one caller can
show up as "Jon Smith", "John Smith", "John Smtih", "Jane Doe", "Jane M Doe"
or "Jane Melissa Doe". After `normalize_person_name`, the first word is the
first name, the last word is the last name, and any words between are middle
names. Two names match when:

- their first names match and their last names match, and
- their middle names are compatible: one name has none, or both have the
  same number of middle names and each pair matches, where an initial also
  matches a middle name starting with it ("M" and "Melissa").

A one-word name only matches another one-word name.

Two words match when they're:

- the same,
- one typo apart (an added, missing, changed or swapped letter), when both
  have at least 3 letters, or
- pronounced the same (the same Metaphone or NYSIIS code) and spelled close
  enough: up to 2 edits, or 3 when both have at least 5 letters. Both must
  have at least 4 letters, since the codes ignore most vowels. This matches
  "Steven" and "Stephen", "Sean" and "Shawn" or "Kristin" and "Christine",
  while "Jane" and "John" (both "JN") stay apart.

One typo can't tell "Jane" from "Jake", so the analytics show every
spelling and leave the call to the reader.

Matching is transitive: if A matches B and B matches C, all three are one
group.
"""

from collections import defaultdict
from functools import lru_cache
from typing import Iterable

import jellyfish
from rapidfuzz.distance import OSA

# Shortest word that may differ by a typo
MIN_TYPO_WORD = 3

# Shortest word that may match by sound
MIN_PHONETIC_WORD = 4

# Shortest word (in both names) allowed 3 edits in a match by sound,
# rather than 2
MIN_LONG_PHONETIC_WORD = 5


@lru_cache(maxsize=None)
def _sound_codes(word: str) -> frozenset[str]:
    """The word's Metaphone and NYSIIS codes, told apart by a prefix."""
    return frozenset({"m:" + jellyfish.metaphone(word), "n:" + jellyfish.nysiis(word)})


def is_same_word(a: str, b: str) -> bool:
    """Whether two words of a name are the same, allowing for a typo or sound."""
    if a == b:
        return True
    shorter = min(len(a), len(b))
    if shorter < MIN_TYPO_WORD:
        return False
    distance = OSA.distance(a, b, score_cutoff=3)
    if distance <= 1:
        return True
    if shorter < MIN_PHONETIC_WORD:
        return False
    allowed = 3 if shorter >= MIN_LONG_PHONETIC_WORD else 2
    return distance <= allowed and bool(_sound_codes(a) & _sound_codes(b))


def _same_middle(a: str, b: str) -> bool:
    if len(a) == 1 or len(b) == 1:
        return a[0] == b[0]
    return is_same_word(a, b)


def is_same_caller_name(a: str, b: str) -> bool:
    """
    Whether two normalized names are probably the same caller.

    Args:
        a: A name from `normalize_person_name`
        b: Another such name
    """
    if a == b:
        return bool(a)
    wa, wb = a.split(), b.split()
    if not wa or not wb:
        return False
    if len(wa) == 1 or len(wb) == 1:
        return len(wa) == len(wb) and is_same_word(wa[0], wb[0])
    if not (is_same_word(wa[0], wb[0]) and is_same_word(wa[-1], wb[-1])):
        return False
    ma, mb = wa[1:-1], wb[1:-1]
    if not ma or not mb:
        return True
    return len(ma) == len(mb) and all(_same_middle(x, y) for x, y in zip(ma, mb))


def _block_keys(name: str) -> set[tuple[str, str]]:
    """
    Keys that every name matching *name* shares with it.

    Matching names have matching last names (or, for one-word names,
    matching words). Two words one typo apart always share a one-letter
    deletion of themselves (or one is a deletion of the other), and two words
    that sound alike share a sound code. So each name is keyed by its last
    word, that word's deletions and its sound codes, and only names sharing
    a key need comparing.
    """
    words = name.split()
    kind = "one" if len(words) == 1 else "last"
    word = words[-1]
    keys = {(kind, word)}
    if len(word) >= MIN_TYPO_WORD:
        for i in range(len(word)):
            keys.add((kind, word[:i] + word[i + 1:]))  # fmt: skip
    if len(word) >= MIN_PHONETIC_WORD:
        keys.update((kind, code) for code in _sound_codes(word))
    return keys


def group_similar_names(names: Iterable[str]) -> dict[str, str]:
    """
    Group normalized names that are probably the same caller.

    Args:
        names: Names from `normalize_person_name` (duplicates and blanks are
            fine; blanks are left out)

    Returns:
        Each name → its group's key (the group's alphabetically first name)
    """
    keys = sorted({n for n in names if n})
    parent = {k: k for k in keys}

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    blocks: dict[tuple[str, str], list[str]] = defaultdict(list)
    for key in keys:
        for block in _block_keys(key):
            blocks[block].append(key)
    compared: set[tuple[str, str]] = set()
    for block in blocks.values():
        for i, a in enumerate(block):
            for b in block[i + 1:]:  # fmt: skip
                if (a, b) in compared:
                    continue
                compared.add((a, b))
                if is_same_caller_name(a, b):
                    ra, rb = find(a), find(b)
                    if ra != rb:
                        parent[max(ra, rb)] = min(ra, rb)
    return {k: find(k) for k in keys}
