"""
Sehat Saathi - Emergency Escalation Tool
========================================
Returns hardcoded emergency helpline numbers.
This tool is ALWAYS triggered by the deterministic safety layer —
it NEVER depends on LLM output to decide when to call it.
"""
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded emergency contacts (India-focused, extensible)
# ---------------------------------------------------------------------------
EMERGENCY_CONTACTS = {
    "ambulance": {"number": "108", "description": "National Ambulance Service (Free)"},
    "police": {"number": "100", "description": "Police Emergency"},
    "women_helpline": {"number": "1091", "description": "Women Helpline"},
    "child_helpline": {"number": "1098", "description": "Childline India"},
    "disaster_management": {"number": "1077", "description": "Disaster Management"},
    "mental_health": {
        "number": "iCall: 9152987821",
        "description": "iCall Mental Health Helpline (Tata Institute)",
    },
    "poison_control": {
        "number": "1800-116-117",
        "description": "National Poison Control Helpline",
    },
    "covid_helpline": {"number": "1075", "description": "National Health Helpline"},
}

EMERGENCY_RESPONSE_TEMPLATE = """
🚨 **THIS IS AN EMERGENCY — PLEASE ACT IMMEDIATELY** 🚨

**Call 108 RIGHT NOW** for a free ambulance.

**Emergency Helplines (India):**
- 🚑 Ambulance: **108** (Free, 24/7)
- 🚓 Police: **100**
- 🏥 National Health Helpline: **1075**
- ☎️ Women Helpline: **1091**
- 👶 Childline: **1098**
- 🧠 Mental Health (iCall): **9152987821**
- ☠️ Poison Control: **1800-116-117** (Toll-free)

**While waiting for help:**
{situation_advice}

Do NOT wait. Please call for help immediately.
"""

SITUATION_ADVICE = {
    "cardiac_emergency": (
        "- Keep the person calm and still.\n"
        "- Loosen any tight clothing around the chest or neck.\n"
        "- If the person becomes unresponsive and stops breathing, begin CPR if you know how.\n"
        "- Do NOT give food, water, or medication."
    ),
    "breathing_emergency": (
        "- Help the person sit upright — do not lay them flat.\n"
        "- Loosen tight clothing around neck and chest.\n"
        "- Keep the person calm and reassured.\n"
        "- Open windows/doors for fresh air."
    ),
    "stroke": (
        "- Do NOT give food, water, or any medication.\n"
        "- Keep the person lying down with head slightly elevated.\n"
        "- Note the time symptoms started — doctors need this.\n"
        "- Do NOT leave the person alone."
    ),
    "severe_bleeding": (
        "- Apply firm, direct pressure on the wound with a clean cloth.\n"
        "- Do NOT remove the cloth — add more on top if it soaks through.\n"
        "- Elevate the injured limb above heart level if possible.\n"
        "- Keep the person still and calm."
    ),
    "unresponsive": (
        "- Check if the person is breathing — watch for chest movement.\n"
        "- If not breathing, begin CPR if you know how.\n"
        "- Place them in the recovery position (on their side) if breathing.\n"
        "- Do NOT give anything by mouth."
    ),
    "infant_emergency": (
        "- Keep the child calm and cool — remove excess clothing.\n"
        "- Do NOT put anything in the child's mouth during a seizure.\n"
        "- Lay the child on a flat, safe surface on their side.\n"
        "- Note how long the seizure lasts — tell the doctor."
    ),
    "mental_health_emergency": (
        "- Stay with the person — do not leave them alone.\n"
        "- Speak calmly and without judgment.\n"
        "- Call iCall: 9152987821 or Vandrevala Foundation: 1860-2662-345.\n"
        "- Remove access to any potentially harmful objects."
    ),
    "poisoning": (
        "- Call Poison Control: 1800-116-117 immediately.\n"
        "- Do NOT induce vomiting unless instructed by a medical professional.\n"
        "- Keep the container/substance packaging to show doctors.\n"
        "- If person is unconscious, turn them on their side."
    ),
    "default": (
        "- Keep the person calm and still.\n"
        "- Do NOT give food or water.\n"
        "- Stay with them until help arrives.\n"
        "- Call 108 immediately."
    ),
}


@tool
def emergency_escalation_tool(category: str = "default") -> str:
    """
    Returns emergency helpline numbers and immediate first-aid advice.
    This tool is triggered by the deterministic safety layer for red-flag situations
    such as chest pain, difficulty breathing, stroke, severe bleeding, unresponsiveness,
    infant emergencies, or suicidal thoughts.

    Args:
        category: The emergency category detected by the safety layer.
    """
    logger.critical(
        "Emergency escalation triggered | category=%s", category
    )
    advice = SITUATION_ADVICE.get(category, SITUATION_ADVICE["default"])
    response = EMERGENCY_RESPONSE_TEMPLATE.format(situation_advice=advice)
    return response.strip()


def get_emergency_response(category: str = "default") -> str:
    """
    Direct (non-tool) version for use by the safety layer bypass path.
    Returns the same emergency guidance without going through LangChain.
    """
    advice = SITUATION_ADVICE.get(category, SITUATION_ADVICE["default"])
    return EMERGENCY_RESPONSE_TEMPLATE.format(situation_advice=advice).strip()
