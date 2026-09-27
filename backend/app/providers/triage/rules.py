"""RuleBasedTriage — deterministic keyword triage. Always available, never fails.

It is both a selectable provider (TRIAGE_PROVIDER=rules) and the fallback for
every other provider. It must not raise for any string input.
"""

from __future__ import annotations

import re

from app.domain import SUMMARY_MAX, Category, Priority, TriagedBy
from app.providers.triage.base import TriageResult

# Order matters on ties: earlier categories win.
_CATEGORY_KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.WATER: (
        "water",
        "pani",
        "paani",
        "main",
        "pipeline",
        "pipe",
        "leak",
        "tap",
        "supply",
        "tanker",
        "flood",
        "flooding",
        "burst",
        "valve",
        "hydrant",
        "meter",
    ),
    Category.ELECTRICITY: (
        "bijli",
        "electric",
        "electricity",
        "power",
        "wire",
        "wires",
        "transformer",
        "load shedding",
        "loadshedding",
        "outage",
        "voltage",
        "k-electric",
        "ke ",
        "sparking",
        "spark",
        "current",
        "pole",
        "shock",
        "tripping",
    ),
    Category.SANITATION: (
        "gutter",
        "sewage",
        "sewer",
        "drain",
        "nala",
        "nullah",
        "garbage",
        "kachra",
        "trash",
        "waste",
        "dump",
        "smell",
        "stink",
        "overflow",
        "manhole",
        "mosquito",
    ),
    Category.ROADS: (
        "road",
        "sarak",
        "sadak",
        "pothole",
        "potholes",
        "footpath",
        "speed breaker",
        "asphalt",
        "carpet",
        "bridge",
        "traffic",
        "signal",
        "crack",
        "construction",
        "zebra",
        "crossing",
        "road markings",
    ),
    Category.STREETLIGHTS: (
        "streetlight",
        "street light",
        "street lights",
        "streetlights",
        "lamp",
        "bulb",
        "dark",
        "andhera",
        "light pole",
        "lights off",
        "light not working",
    ),
}

_HIGH = (
    "flood",
    "flooding",
    "burst",
    "entering",
    "ground floor",
    "live wire",
    "sparking",
    "spark",
    "shock",
    "fire",
    "danger",
    "dangerous",
    "collapse",
    "collapsed",
    "accident",
    "injured",
    "child",
    "children",
    "hospital",
    "emergency",
    "open manhole",
    "electrocut",
    "sewage entering",
    "into homes",
    "into houses",
    "urgent",
    "fell",
    "no water for",
)
_LOW = (
    "suggest",
    "suggestion",
    "request",
    "please consider",
    "cosmetic",
    "paint",
    "faded",
    "minor",
    "small",
    "slightly",
    "whenever possible",
    "information",
)

_WORD_CACHE: dict[str, re.Pattern[str]] = {}


def _hits(text: str, words: tuple[str, ...]) -> int:
    count = 0
    for w in words:
        pat = _WORD_CACHE.get(w)
        if pat is None:
            pat = re.compile(r"(?<![a-z])" + re.escape(w.strip()) + r"(?![a-z])")
            _WORD_CACHE[w] = pat
        if pat.search(text):
            count += 1
    return count


def _summarise(text: str) -> str:
    """First sentence of the complaint, whitespace-collapsed, capped at 140 chars."""
    first = re.split(r"(?<=[.!?])\s|\n", text.strip(), maxsplit=1)[0]
    first = " ".join(first.split()) or "Complaint received (no description)"
    if len(first) > SUMMARY_MAX:
        first = first[: SUMMARY_MAX - 1].rstrip() + "…"
    return first


class RuleBasedTriage:
    def __init__(self, name: str = TriagedBy.RULES.value) -> None:
        self.name = name

    def triage(self, text: str, location: str) -> TriageResult:
        lowered = f" {text.lower()} "
        scores = {cat: _hits(lowered, words) for cat, words in _CATEGORY_KEYWORDS.items()}
        best = max(scores, key=lambda c: scores[c])
        category = best if scores[best] > 0 else Category.OTHER

        high, low = _hits(lowered, _HIGH), _hits(lowered, _LOW)
        if high > 0:
            priority = Priority.HIGH
        elif low > 0:
            priority = Priority.LOW
        else:
            priority = Priority.NORMAL

        confidence = 0.3 if category is Category.OTHER else min(0.4 + 0.1 * scores[best], 0.7)
        return TriageResult(
            category=category,
            priority=priority,
            summary=_summarise(text),
            confidence=round(confidence, 2),
        )
