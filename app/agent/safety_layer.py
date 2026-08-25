"""
Sehat Saathi - Deterministic Safety / Guardrail Layer
=====================================================
This module is intentionally NOT LLM-based.
It uses a fast keyword-intercept approach to detect life-threatening
red-flag queries BEFORE they reach the LangChain agent or Granite model.

Red flags are intercepted synchronously, ensuring zero LLM latency on
life-critical queries.
"""
import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Red-flag keyword groups (English + transliterated Hindi/common variants)
# ---------------------------------------------------------------------------
RED_FLAG_PATTERNS: list[dict] = [
    {
        "category": "cardiac_emergency",
        "keywords": [
            r"\bchest\s+pain\b",
            r"\bchest\s+tightness\b",
            r"\bheart\s+attack\b",
            r"\bsina\s+dard\b",           # Hindi: chest pain
            r"\bchhati\s+mein\s+dard\b",
            r"\bedata\s+novu\b",          # Kannada: chest pain
            r"\bedata\s+novedu\b",
        ],
    },
    {
        "category": "breathing_emergency",
        "keywords": [
            r"\bcan'?t\s+breathe\b",
            r"\bcannot\s+breathe\b",
            r"\bdifficulty\s+breath\w*\b",
            r"\bshortness\s+of\s+breath\b",
            r"\bsaans\s+nahi\b",           # Hindi: can't breathe
            r"\bsaans\s+lene\s+mein\s+takleef\b",
            r"\busiru\s+tegoodu\s+kashta\b", # Kannada: difficulty breathing
            r"\busiru\s+tagolokke\s+kashta\b",
        ],
    },
    {
        "category": "stroke",
        "keywords": [
            r"\bstroke\b",
            r"\bface\s+drooping\b",
            r"\barm\s+weakness\b",
            r"\bsudden\s+numbness\b",
            r"\bsudden\s+confusion\b",
            r"\bslurred\s+speech\b",
            r"\bparalysis\b",
            r"\blakwa\b",                  # Hindi: paralysis
            r"\bpakshaghata\b",            # Kannada: paralysis
        ],
    },
    {
        "category": "severe_bleeding",
        "keywords": [
            r"\bsevere\s+bleeding\b",
            r"\bheavy\s+bleeding\b",
            r"\buncontrolled\s+bleed\w*\b",
            r"\bkhoon\s+band\s+nahi\b",    # Hindi: blood won't stop
            r"\braktasraava\b",            # Kannada: bleeding
            r"\brakte\s+bando\b",
        ],
    },
    {
        "category": "unresponsive",
        "keywords": [
            r"\bunresponsive\b",
            r"\bunconscious\b",
            r"\bpassed\s+out\b",
            r"\bnot\s+waking\s+up\b",
            r"\bhosh\s+nahi\b",            # Hindi: unconscious
            r"\bbehosh\b",
            r"\bprajne\s+illada\b",        # Kannada: unconscious
            r"\bmoorchha\b",               # Kannada/Hindi: fainted
        ],
    },
    {
        "category": "infant_emergency",
        "keywords": [
            r"\bbaby.*high\s+fever\b",
            r"\bnewborn.*fever\b",
            r"\binfant.*fever\b",
            r"\bchild.*seizure\b",
            r"\bbaby.*seizure\b",
            r"\bbaby.*convuls\w*\b",
            r"\bseizure\b",
            r"\bconvuls\w*\b",
            r"\bmagu.*jwara\b",            # Kannada: baby fever
            r"\bbacche.*bukhaar\b",        # Hindi: child fever
            r"\bfitsi\b",                  # Kannada colloquial: fits/seizure
        ],
    },
    {
        "category": "mental_health_emergency",
        "keywords": [
            r"\bsuicid\w*\b",
            r"\bkill\s+(my)?self\b",
            r"\bwant\s+to\s+die\b",
            r"\bend\s+my\s+life\b",
            r"\bkhud\s+ko\s+maar\b",    # Hindi: kill myself
            r"\bjaan\s+dena\b",
        ],
    },
    {
        "category": "poisoning",
        "keywords": [
            r"\bpoisoned\b",
            r"\bpoisoning\b",
            r"\bswallowed.*poison\b",
            r"\boverdose\b",
            r"\bzahar\s+kha\b",          # Hindi: ate poison
        ],
    },
]

# Pre-compile all patterns for performance
_COMPILED_PATTERNS: list[Tuple[str, re.Pattern]] = [
    (group["category"], re.compile("|".join(group["keywords"]), re.IGNORECASE))
    for group in RED_FLAG_PATTERNS
]


def check_red_flags(text: str) -> Tuple[bool, str]:
    """
    Scan `text` for life-threatening red-flag patterns.

    Returns:
        (is_emergency: bool, category: str)
        category is empty string if no red flag detected.
    """
    for category, pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            logger.warning(
                "RED FLAG intercepted | category=%s | text_snippet=%s",
                category,
                text[:80],
            )
            return True, category
    return False, ""
