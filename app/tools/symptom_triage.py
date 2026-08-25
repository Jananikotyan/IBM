"""
Sehat Saathi - Symptom Triage Tool
====================================
Performs structured, rule-based risk scoring on reported symptoms.
Classifies the situation into one of three tiers:
  - Tier 1: "Self-care at home"
  - Tier 2: "See a doctor within a few days"
  - Tier 3: "Seek urgent care now"

Design principle: Rules are deterministic and conservative.
When in doubt, escalate to a higher tier.
"""
import logging
import re
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Symptom keyword database with tier assignments
# ---------------------------------------------------------------------------
SYMPTOM_RULES = [
    # --- Tier 3: Urgent Care Now ---
    {
        "tier": 3,
        "reason": "High-risk symptoms that may indicate a serious or life-threatening condition",
        "patterns": [
            r"\bhigh fever\b", r"\bfever.*above\s+103\b", r"\bfever.*104\b",
            r"\bfever.*105\b", r"\bfever\s+over\s+103\b",
            r"\bsevere\s+(headache|pain|abdominal\s+pain)\b",
            r"\bstiff\s+neck\b", r"\blight\s+sensitivity\b",
            r"\bbloody\s+(diarrhea|stool|urine|vomit)\b",
            r"\bvomiting\s+blood\b", r"\bblood\s+in\s+(stool|urine|vomit)\b",
            r"\byellow\s+(skin|eyes)\b", r"\bjaundice\b",
            r"\brapid\s+(breathing|heart\s*beat)\b",
            r"\bextreme\s+(fatigue|weakness)\b",
            r"\bbaby.*fever\b", r"\bnewborn.*sick\b",
            r"\bpregnant.*fever\b", r"\bpregnant.*bleeding\b",
            r"\bsudden.*vision\b", r"\bbluish\s+(lips|skin)\b",
            r"\bdehydrat\w+\b",
            r"\bno\s+urine\b", r"\bnot\s+urinating\b",
        ],
    },
    # --- Tier 2: See a Doctor Within a Few Days ---
    {
        "tier": 2,
        "reason": "Symptoms that need medical evaluation but are not immediately dangerous",
        "patterns": [
            r"\bfever\b", r"\btemperature\b",
            r"\bpersistent\s+(cough|headache|pain)\b",
            r"\bcough.*more\s+than\s+(3|4|5|7|10)\s+days\b",
            r"\bcough.*week\b",
            r"\brash\b", r"\bswelling\b",
            r"\bdiarrhea\b", r"\bvomit\w*\b",
            r"\bnausea\b",
            r"\bchest\s+discomfort\b",
            r"\bpain\s+(in|around)\b",
            r"\bjoint\s+pain\b",
            r"\bbody\s+ache\b",
            r"\bdark\s+urine\b",
            r"\bburning\s+urine\b", r"\bpain.*urinat\w+\b",
            r"\bwheezing\b",
            r"\bsore\s+throat.*\d+\s+days\b",
            r"\bearache\b", r"\bear\s+pain\b",
            r"\beye\s+(discharge|redness|pain)\b",
        ],
    },
    # --- Tier 1: Self-care at home ---
    {
        "tier": 1,
        "reason": "Mild symptoms that can typically be managed at home with rest and fluids",
        "patterns": [
            r"\bmild\s+(cold|cough|fever|headache|pain)\b",
            r"\bcommon\s+cold\b",
            r"\brunny\s+nose\b", r"\bstuff[y]?\s+nose\b",
            r"\bsneezing\b",
            r"\bsore\s+throat\b",
            r"\blow\s+grade\s+fever\b",
            r"\bfatigue\b", r"\btired\b",
            r"\bminor\s+(cut|bruise|scrape)\b",
            r"\bmuscle\s+ache\b",
            r"\bindigestion\b", r"\bheartburn\b",
            r"\bloose\s+stool\b",
        ],
    },
]

TIER_LABELS = {
    1: "✅ Self-care at home",
    2: "🟡 See a doctor within a few days",
    3: "🔴 Seek urgent care now",
}

TIER_EXPLANATIONS = {
    1: (
        "Your symptoms sound mild and can likely be managed with rest, fluids, "
        "and over-the-counter care. Monitor closely — if symptoms worsen or last "
        "more than 3 days, see a doctor."
    ),
    2: (
        "Your symptoms need a doctor's attention, but this is not an immediate emergency. "
        "Please visit your nearest Primary Health Centre (PHC) or clinic within "
        "the next 1–2 days."
    ),
    3: (
        "Your symptoms may indicate a serious condition that needs prompt medical attention. "
        "Please go to the nearest hospital or emergency department as soon as possible, "
        "or call 108 for a free ambulance."
    ),
}

# Pre-compile patterns
_COMPILED_RULES = [
    {
        "tier": rule["tier"],
        "reason": rule["reason"],
        "patterns": [re.compile(p, re.IGNORECASE) for p in rule["patterns"]],
    }
    for rule in SYMPTOM_RULES
]


def _score_symptoms(symptom_text: str) -> tuple[int, list[str]]:
    """
    Score the symptom text and return (highest_tier, matched_reasons).
    """
    highest_tier = 0
    matched_reasons = []

    for rule in _COMPILED_RULES:
        for pattern in rule["patterns"]:
            if pattern.search(symptom_text):
                if rule["tier"] > highest_tier:
                    highest_tier = rule["tier"]
                    matched_reasons = [rule["reason"]]
                elif rule["tier"] == highest_tier and rule["reason"] not in matched_reasons:
                    matched_reasons.append(rule["reason"])
                break  # One match per rule group is enough

    if highest_tier == 0:
        highest_tier = 1  # Default to self-care if no strong match
        matched_reasons = ["No high-risk patterns detected"]

    return highest_tier, matched_reasons


@tool
def symptom_triage_tool(symptom_description: str) -> str:
    """
    Analyzes a description of symptoms and classifies the situation into a care tier.
    Returns one of:
    - 'Self-care at home' (Tier 1): Mild symptoms manageable at home
    - 'See a doctor within a few days' (Tier 2): Needs medical evaluation
    - 'Seek urgent care now' (Tier 3): Potentially serious — go to hospital/call 108

    Args:
        symptom_description: A plain-language description of the patient's symptoms.
    """
    logger.info("Symptom triage requested: %s", symptom_description[:100])

    tier, reasons = _score_symptoms(symptom_description)
    label = TIER_LABELS[tier]
    explanation = TIER_EXPLANATIONS[tier]

    response_lines = [
        f"**Triage Assessment: {label}**",
        "",
        f"**Why:** {explanation}",
        "",
        f"**Detected concern:** {'; '.join(reasons)}",
        "",
    ]

    if tier == 3:
        response_lines += [
            "⚠️ **Important:** If at any point you experience chest pain, difficulty "
            "breathing, or loss of consciousness — call **108** immediately.",
            "",
        ]
    elif tier == 2:
        response_lines += [
            "💡 **Tip:** Find your nearest Primary Health Centre (PHC) using the "
            "facility locator — care at government PHCs is free.",
            "",
        ]
    else:
        response_lines += [
            "💧 **Home care tips:** Rest well, drink plenty of fluids (ORS if diarrhea), "
            "and monitor your temperature. Do NOT self-medicate with antibiotics.",
            "",
        ]

    response_lines.append(
        "_I'm an AI assistant, not a doctor. For diagnosis or treatment, "
        "please consult a healthcare professional._"
    )

    return "\n".join(response_lines)
