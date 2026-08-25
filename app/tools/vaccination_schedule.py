"""
Sehat Saathi - Vaccination Schedule Tool
=========================================
Calculates upcoming immunization milestones based on:
  - Child's age (in weeks/months) — India's National Immunization Schedule
  - Pregnancy trimester — ANC (Antenatal Care) checkup schedule

Source: MoHFW India National Immunization Schedule (NIS)
        https://nhm.gov.in/index1.php?lang=1&level=2&sublinkid=824&lid=220
"""
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# India National Immunization Schedule (NIS) - MoHFW
# ---------------------------------------------------------------------------
CHILD_VACCINE_SCHEDULE = [
    {
        "age_weeks": 0,
        "age_label": "At Birth",
        "vaccines": ["BCG", "OPV-0 (Zero dose)", "Hepatitis B (Birth dose)"],
        "notes": "Given within 24 hours of birth at the health facility.",
    },
    {
        "age_weeks": 6,
        "age_label": "6 Weeks",
        "vaccines": ["OPV-1", "Pentavalent-1 (DPT+HepB+Hib)", "RVV-1 (Rotavirus)", "fIPV-1 (Fractional IPV)"],
        "notes": "First round of primary immunization series.",
    },
    {
        "age_weeks": 10,
        "age_label": "10 Weeks",
        "vaccines": ["OPV-2", "Pentavalent-2", "RVV-2"],
        "notes": "Second dose of primary series.",
    },
    {
        "age_weeks": 14,
        "age_label": "14 Weeks",
        "vaccines": ["OPV-3", "Pentavalent-3", "RVV-3", "fIPV-2"],
        "notes": "Completing primary immunization series.",
    },
    {
        "age_weeks": 36,  # ~9 months
        "age_label": "9 Months",
        "vaccines": ["Measles-Rubella (MR) Dose 1", "Vitamin A (1st dose)", "JE Vaccine Dose 1 (endemic areas)"],
        "notes": "First dose of measles-rubella. Vitamin A supplementation begins.",
    },
    {
        "age_weeks": 65,  # ~15 months
        "age_label": "15 Months",
        "vaccines": ["Measles-Rubella (MR) Dose 2", "DPT Booster-1", "OPV Booster", "Vitamin A (2nd dose)"],
        "notes": "Booster doses to strengthen immunity.",
    },
    {
        "age_weeks": 104,  # ~2 years
        "age_label": "2 Years",
        "vaccines": ["Vitamin A (3rd dose)"],
        "notes": "Continue Vitamin A supplementation every 6 months until age 5.",
    },
    {
        "age_weeks": 260,  # ~5 years
        "age_label": "5 Years",
        "vaccines": ["DPT Booster-2"],
        "notes": "Final childhood booster dose.",
    },
    {
        "age_weeks": 520,  # ~10 years
        "age_label": "10 Years",
        "vaccines": ["Td (Tetanus-diphtheria)"],
        "notes": "School-age booster.",
    },
    {
        "age_weeks": 780,  # ~15 years
        "age_label": "15-16 Years",
        "vaccines": ["Td Booster"],
        "notes": "Adolescent booster dose.",
    },
]

# Antenatal Care Schedule - India MoHFW
ANC_SCHEDULE = [
    {
        "trimester": 1,
        "weeks_range": "Up to 12 weeks",
        "visits": [
            {
                "visit": "1st ANC Visit (Register as early as possible)",
                "checkups": [
                    "Blood group and Rh factor",
                    "Hemoglobin (Hb) test",
                    "Blood pressure",
                    "Weight and BMI",
                    "Urine test (protein/sugar)",
                    "HIV test (with consent)",
                    "Thyroid function test",
                ],
                "vaccines": ["TT-1 (Tetanus Toxoid) — if not previously immunized"],
                "supplements": ["Iron-Folic Acid (IFA) tablets — start immediately"],
            }
        ],
    },
    {
        "trimester": 2,
        "weeks_range": "14–26 weeks",
        "visits": [
            {
                "visit": "2nd ANC Visit (around 14–16 weeks)",
                "checkups": [
                    "Blood pressure",
                    "Weight",
                    "Fetal growth check",
                    "Anomaly scan (18–20 weeks)",
                ],
                "vaccines": ["TT-2 (4 weeks after TT-1)"],
                "supplements": ["Continue IFA tablets", "Calcium supplements"],
            }
        ],
    },
    {
        "trimester": 3,
        "weeks_range": "28–40 weeks",
        "visits": [
            {
                "visit": "3rd ANC Visit (28 weeks)",
                "checkups": [
                    "Blood pressure",
                    "Hemoglobin re-check",
                    "Fetal position",
                    "Growth scan",
                ],
                "vaccines": [],
                "supplements": ["IFA", "Calcium", "Vitamin D if deficient"],
            },
            {
                "visit": "4th ANC Visit (36 weeks — prepare for delivery)",
                "checkups": [
                    "Blood pressure",
                    "Fetal position and presentation",
                    "Birth plan discussion",
                    "Discuss institutional delivery",
                ],
                "vaccines": [],
                "supplements": ["Continue all supplements"],
            },
        ],
    },
]


def _find_next_vaccines_for_child(age_weeks: float) -> dict:
    """Find the next upcoming and current due vaccines for a child."""
    current_due = None
    next_due = None

    for milestone in CHILD_VACCINE_SCHEDULE:
        if abs(milestone["age_weeks"] - age_weeks) <= 1:
            current_due = milestone
        elif milestone["age_weeks"] > age_weeks:
            if next_due is None:
                next_due = milestone

    return {"current_due": current_due, "next_due": next_due}


@tool
def vaccination_schedule_tool(query: str) -> str:
    """
    Calculates the upcoming vaccination/immunization milestones for a child
    based on their age, or the antenatal care (ANC) schedule for a pregnant woman.

    Use this tool when:
    - A user mentions their baby's or child's age (e.g., "my baby is 6 weeks old")
    - A user mentions being pregnant and asks about checkups or vaccines

    Args:
        query: A description containing the child's age (e.g., '6 weeks old', '3 months',
               '9 months') or pregnancy stage (e.g., 'first trimester', '20 weeks pregnant').
    """
    logger.info("Vaccination schedule query: %s", query[:100])
    query_lower = query.lower()

    # --- Detect pregnancy ---
    if any(word in query_lower for word in ["pregnant", "pregnancy", "trimester", "antenatal", "anc", "weeks pregnant"]):
        return _get_anc_schedule(query_lower)

    # --- Detect child age ---
    age_weeks = _parse_age_to_weeks(query_lower)
    if age_weeks is not None:
        return _get_child_vaccine_info(age_weeks)

    return (
        "I need a bit more information. Could you tell me:\n"
        "- Your child's age (e.g., '6 weeks old', '3 months old', '9 months old'), OR\n"
        "- Your pregnancy stage (e.g., 'I am 20 weeks pregnant' or '2nd trimester')?\n\n"
        "This will help me find the right vaccination or checkup schedule for you.\n\n"
        "_I'm an AI assistant, not a doctor. Please consult a healthcare professional "
        "for personalized medical advice._"
    )


def _parse_age_to_weeks(text: str) -> float | None:
    """Parse age from text and convert to weeks."""
    import re

    # Match "X weeks"
    m = re.search(r"(\d+(?:\.\d+)?)\s*week", text)
    if m:
        return float(m.group(1))

    # Match "X months"
    m = re.search(r"(\d+(?:\.\d+)?)\s*month", text)
    if m:
        return float(m.group(1)) * 4.33  # approximate weeks per month

    # Match "X years"
    m = re.search(r"(\d+(?:\.\d+)?)\s*year", text)
    if m:
        return float(m.group(1)) * 52

    # Match "X days" (newborn)
    m = re.search(r"(\d+(?:\.\d+)?)\s*day", text)
    if m:
        return float(m.group(1)) / 7

    return None


def _get_child_vaccine_info(age_weeks: float) -> str:
    """Build a vaccination info response for a child of given age in weeks."""
    result = _find_next_vaccines_for_child(age_weeks)
    lines = []

    age_months = age_weeks / 4.33
    if age_months < 1:
        age_display = f"{int(age_weeks * 7)} days"
    elif age_months < 24:
        age_display = f"{age_months:.0f} months"
    else:
        age_display = f"{age_months / 12:.1f} years"

    lines.append(f"📋 **Vaccination Schedule for a child aged ~{age_display}**")
    lines.append("_(As per India's National Immunization Schedule — MoHFW)_")
    lines.append("")

    if result["current_due"]:
        m = result["current_due"]
        lines.append(f"🔔 **Due NOW ({m['age_label']}):**")
        for v in m["vaccines"]:
            lines.append(f"  • {v}")
        lines.append(f"  📝 {m['notes']}")
        lines.append("")

    if result["next_due"]:
        m = result["next_due"]
        lines.append(f"⏭️ **Coming Up Next ({m['age_label']}):**")
        for v in m["vaccines"]:
            lines.append(f"  • {v}")
        lines.append(f"  📝 {m['notes']}")
        lines.append("")

    if not result["current_due"] and not result["next_due"]:
        lines.append("✅ Your child appears to be past the primary immunization window.")
        lines.append("Please consult your nearest PHC for a full vaccination record review.")
        lines.append("")

    lines += [
        "💡 **Where to get vaccines:** All vaccines in the National Immunization Schedule "
        "are **FREE** at government health centres (PHCs, Sub-centres, CHCs).",
        "",
        "📅 Visit your nearest Aanganwadi/PHC on a fixed vaccination day (usually Tuesday/Friday).",
        "",
        "_I'm an AI assistant, not a doctor. For diagnosis or treatment, please consult a healthcare professional._",
    ]

    return "\n".join(lines)


def _get_anc_schedule(text: str) -> str:
    """Return relevant ANC schedule information."""
    import re

    lines = []
    lines.append("🤰 **Antenatal Care (ANC) Schedule**")
    lines.append("_(As per MoHFW India guidelines)_")
    lines.append("")

    # Try to detect trimester or weeks
    trimester = None
    m = re.search(r"(\d+)\s*(st|nd|rd)?\s*trimester", text)
    if m:
        trimester = int(m.group(1))

    weeks_pregnant = None
    m = re.search(r"(\d+)\s*weeks?\s*pregnant", text)
    if m:
        weeks_pregnant = int(m.group(1))
        if weeks_pregnant <= 12:
            trimester = 1
        elif weeks_pregnant <= 26:
            trimester = 2
        else:
            trimester = 3

    relevant_schedules = (
        [s for s in ANC_SCHEDULE if s["trimester"] == trimester]
        if trimester
        else ANC_SCHEDULE
    )

    for schedule in relevant_schedules:
        lines.append(f"**Trimester {schedule['trimester']} ({schedule['weeks_range']}):**")
        for visit in schedule["visits"]:
            lines.append(f"\n  🏥 **{visit['visit']}**")
            if visit["checkups"]:
                lines.append("  _Tests & checkups:_")
                for c in visit["checkups"]:
                    lines.append(f"    • {c}")
            if visit["vaccines"]:
                lines.append("  _Vaccines:_")
                for v in visit["vaccines"]:
                    lines.append(f"    💉 {v}")
            if visit["supplements"]:
                lines.append("  _Supplements:_")
                for s in visit["supplements"]:
                    lines.append(f"    💊 {s}")
        lines.append("")

    lines += [
        "💡 **All ANC checkups and vaccines are FREE** at government health centres.",
        "Register early at your nearest PHC/Sub-Centre — the earlier, the better!",
        "",
        "🔖 Under the **Pradhan Mantri Matru Vandana Yojana (PMMVY)**, you may also be "
        "eligible for ₹5,000 in financial assistance for your first child.",
        "",
        "_I'm an AI assistant, not a doctor. For diagnosis or treatment, please consult a healthcare professional._",
    ]

    return "\n".join(lines)
