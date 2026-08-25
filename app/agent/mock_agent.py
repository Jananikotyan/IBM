"""
Sehat Saathi - Mock Agent (Demo Mode)
=======================================
Runs the FULL Sehat Saathi pipeline WITHOUT any API keys:
  - Safety layer          → still fully active (deterministic, no key needed)
  - Symptom triage tool   → still fully active (rule-based, no key needed)
  - Vaccination schedule  → still fully active (rule-based, no key needed)
  - Facility locator      → still active (uses free OpenStreetMap, no key)
  - LLM responses         → replaced with a smart rule-based mock engine
  - Language translation  → Hindi & Kannada via local Unicode detection (no API key)

Set MOCK_MODE=true in your .env to activate this mode.
"""
import logging
import re
from app.agent.safety_layer import check_red_flags
from app.agent.memory import get_memory
from app.tools.emergency_escalation import get_emergency_response
from app.tools.symptom_triage import symptom_triage_tool
from app.tools.vaccination_schedule import vaccination_schedule_tool
from app.tools.facility_locator import facility_locator_tool
from app.multilingual.local_translator import (
    detect_language,
    normalise_to_english,
    localise_disclaimer,
    localise_fallback,
    localise_topic,
    get_strings,
)

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "\n\n_I'm an AI assistant, not a doctor. "
    "For diagnosis or treatment, please consult a healthcare professional._"
)

# ---------------------------------------------------------------------------
# Keyword → tool routing patterns (English + Hindi + Kannada keywords)
# ---------------------------------------------------------------------------
ROUTING_PATTERNS = [
    # Vaccination / pregnancy
    {
        "patterns": [
            r"\b(\d+)\s*(week|month|year|day)s?\s*(old|ago)?\b",
            r"\bbaby\b", r"\bchild\b", r"\bkid\b", r"\binfant\b",
            r"\bvaccin\w+\b", r"\bimmuniz\w+\b", r"\bshots?\b",
            r"\bpregnant\b", r"\bpregnancy\b", r"\btrimester\b",
            r"\bantenatal\b", r"\banc\b", r"\bdue\s+date\b",
            # Hindi
            r"\bbacha\b", r"\bbaccha\b", r"\bgarbhwati\b", r"\btika\b",
            r"\bhafte\s*ka\b", r"\bmahine\s*ka\b",
            # Kannada
            r"\bmagu\b", r"\bmakkalu\b", r"\bgarbhini\b", r"\blasike\b",
            r"\bvaara\b", r"\btingalu\b",
        ],
        "tool": "vaccination",
    },
    # Facility locator
    {
        "patterns": [
            r"\bhospital\b", r"\bclinic\b", r"\bphc\b",
            r"\bdoctor\b", r"\bnear(by|est)?\b", r"\bwhere\b",
            r"\bpincode\b", r"\b\d{6}\b",
            r"\bhealth\s+cent(re|er)\b",
            # Hindi
            r"\baspatal\b", r"\baspataal\b", r"\bdawakhana\b",
            r"\bnazdeek\b", r"\bkahan\b",
            # Kannada
            r"\baspatre\b", r"\bchikitsaalaya\b", r"\bhatti\b",
        ],
        "tool": "facility",
    },
    # Symptom triage
    {
        "patterns": [
            r"\bfever\b", r"\bcough\b", r"\bpain\b", r"\bache\b",
            r"\bvomit\w*\b", r"\bdiarrhea\b", r"\bnausea\b",
            r"\brash\b", r"\bswelling\b", r"\bweak\w*\b",
            r"\bsick\b", r"\bill\b", r"\bsymptom\b",
            r"\bheadache\b",
            # Hindi
            r"\bbukhaar\b", r"\bbukhar\b", r"\bdard\b",
            r"\bkhansi\b", r"\bulti\b", r"\bdaast\b",
            r"\bkamzori\b", r"\bchakkar\b",
            # Kannada
            r"\bjwara\b", r"\bnovu\b", r"\bkheelu\b",
            r"\bvaanti\b", r"\bbathavara\b",
        ],
        "tool": "triage",
    },
]

# Compile
_COMPILED_ROUTES = [
    {
        "tool": r["tool"],
        "patterns": [re.compile(p, re.IGNORECASE) for p in r["patterns"]],
    }
    for r in ROUTING_PATTERNS
]

# General health Q&A topic keywords (English + Hindi + Kannada)
TOPIC_KEYWORDS = {
    "ors":    ["ors", "oral rehydration", "rehydration"],
    "malaria":["malaria", "malarial", "मलेरिया", "ಮಲೇರಿಯಾ"],
    "tb":     ["tuberculosis", " tb ", "t.b", "खांसी हफ्तों", "kshaya", "ಕ್ಷಯ"],
    "dengue": ["dengue", "डेंगू", "ಡೆಂಗ್ಯೂ"],
    "anemia": ["anemia", "anaemia", "एनीमिया", "ರಕ್ತಹೀನತೆ", "khoon ki kami",
               "hemoglobin", "haemoglobin"],
}

# English fallback responses (used when no localised version found)
GENERAL_RESPONSES = {
    "ors": (
        "**ORS (Oral Rehydration Solution)** is a simple mixture used to treat dehydration "
        "caused by diarrhea or vomiting.\n\n"
        "**How to make ORS at home:**\n"
        "- 1 litre of clean/boiled water\n"
        "- 6 level teaspoons of sugar\n"
        "- ½ teaspoon of salt\n"
        "Mix well and give in small sips. ORS packets are also available **free** at all "
        "government health centres.\n\n"
        "**Give ORS when:** diarrhea starts, especially in children and elderly.\n\n"
        "_Source: WHO Oral Rehydration Therapy guidelines_"
    ),
    "malaria": (
        "**Malaria** is a disease spread by mosquito bites.\n\n"
        "**Symptoms:** Fever with chills and shivering, headache, body ache, sweating.\n\n"
        "**What to do:**\n"
        "- Get a malaria blood test immediately at your nearest PHC (it's free)\n"
        "- Do NOT delay — untreated malaria can be life-threatening\n"
        "- Sleep under insecticide-treated bed nets to prevent it\n\n"
        "**Treatment is FREE** at all government health centres.\n\n"
        "_Source: WHO Malaria guidelines_"
    ),
    "tb": (
        "**TB (Tuberculosis)** is a curable disease that mainly affects the lungs.\n\n"
        "**Symptoms:** Cough for more than 2 weeks, blood in sputum, night sweats, "
        "weight loss, low-grade fever.\n\n"
        "**Important:**\n"
        "- Free testing and treatment at all government health centres\n"
        "- Treatment takes 6 months — do NOT stop early\n"
        "- Nikshay Poshan Yojana gives ₹500/month support during treatment\n\n"
        "_Source: MoHFW India TB guidelines_"
    ),
    "dengue": (
        "**Dengue** is a viral fever spread by mosquito bites (Aedes mosquito).\n\n"
        "**Symptoms:** Sudden high fever, severe headache, pain behind eyes, "
        "joint/muscle pain, rash.\n\n"
        "**Warning signs** (go to hospital immediately):\n"
        "- Bleeding from nose/gums\n"
        "- Severe abdominal pain\n"
        "- Persistent vomiting\n\n"
        "**Prevention:** Remove standing water around your home. Use mosquito repellent.\n\n"
        "_Source: WHO Dengue guidelines_"
    ),
    "anemia": (
        "**Anaemia** means low blood/haemoglobin levels.\n\n"
        "**Symptoms:** Tiredness, weakness, pale skin, dizziness, shortness of breath.\n\n"
        "**Common causes in India:** Iron deficiency (most common), poor diet.\n\n"
        "**What helps:**\n"
        "- Iron-rich foods: green leafy vegetables, lentils, jaggery, dates\n"
        "- Iron-Folic Acid (IFA) tablets — free at all PHCs\n"
        "- Pregnant women and children are most at risk\n\n"
        "_Source: MoHFW India National Iron Plus Initiative_"
    ),
}

FALLBACK_RESPONSE = (
    "I'm Sehat Saathi, your health awareness companion! 🏥\n\n"
    "I can help you with:\n"
    "- 🤒 **Symptom guidance** — describe your symptoms\n"
    "- 💉 **Vaccination schedules** — tell me your child's age or pregnancy stage\n"
    "- 🏥 **Find a hospital/PHC** — give me your pincode or city\n"
    "- 📚 **Health information** — ask about fever, ORS, malaria, TB, dengue, anaemia\n\n"
    "**Try asking:** *'My baby is 6 weeks old'* or *'I have fever for 2 days'*"
)

def _get_disclaimer(lang: str) -> str:
    return localise_disclaimer(lang)


def _route_to_tool(text: str) -> str:
    """Decide which tool to call based on keywords in text."""
    scores = {"vaccination": 0, "facility": 0, "triage": 0}
    for route in _COMPILED_ROUTES:
        for pattern in route["patterns"]:
            if pattern.search(text):
                scores[route["tool"]] += 1

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def _mock_llm_response(user_input: str, lang: str = "en") -> str:
    """
    Smart rule-based response engine — replaces Granite LLM in mock mode.
    Routes to tools or returns general health info.
    Responds in the detected language (en / hi / kn).
    """
    disclaimer = _get_disclaimer(lang)

    # Normalise input to English for routing (handles Hindi/Kannada keywords)
    english_input = normalise_to_english(user_input, lang)
    text_lower = english_input.lower()

    # Check general knowledge topics first
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text_lower or kw in user_input.lower() for kw in keywords):
            # Try localised response first, fall back to English
            localised = localise_topic(topic, lang)
            if localised:
                return localised + disclaimer
            return GENERAL_RESPONSES[topic] + disclaimer

    # Route to appropriate tool
    tool = _route_to_tool(text_lower)

    if tool == "triage":
        en_response = symptom_triage_tool.run(english_input)
        return _localise_triage(en_response, lang) + disclaimer

    if tool == "vaccination":
        en_response = vaccination_schedule_tool.run(english_input)
        return _localise_vaccination(en_response, lang)

    if tool == "facility":
        pincode_match = re.search(r"\b\d{6}\b", user_input)
        location_match = re.search(
            r"(?:near|in|at|pincode[:\s]+)([\w\s,]+?)(?:\?|$|\.|,)", english_input, re.IGNORECASE
        )
        location = (
            pincode_match.group(0) if pincode_match
            else location_match.group(1).strip() if location_match
            else english_input
        )
        en_response = facility_locator_tool.run(location)
        return _localise_facility(en_response, lang)

    # Fallback
    fb = localise_fallback(lang)
    return (fb if fb else FALLBACK_RESPONSE) + disclaimer


def _localise_triage(en_response: str, lang: str) -> str:
    """Replace English triage tier labels with localised versions."""
    if lang == "en":
        return en_response
    s = get_strings(lang)
    result = en_response
    result = result.replace("✅ Self-care at home", s.get("triage_tier1", "✅ Self-care at home"))
    result = result.replace("🟡 See a doctor within a few days", s.get("triage_tier2", "🟡 See a doctor within a few days"))
    result = result.replace("🔴 Seek urgent care now", s.get("triage_tier3", "🔴 Seek urgent care now"))
    # Replace tip lines
    result = result.replace(
        "💧 **Home care tips:**",
        s.get("triage_tip_tier1", "💧 **Home care tips:**").split("\n")[0]
    )
    result = result.replace(
        "💡 **Tip:** Find your nearest Primary Health Centre",
        s.get("triage_tip_tier2", "💡 **Tip:**")
    )
    result = result.replace(
        "⚠️ **Important:** If at any point you experience chest pain",
        s.get("triage_tip_tier3", "⚠️ **Important:**")
    )
    result = result.replace(
        "_I'm an AI assistant, not a doctor. For diagnosis or treatment, "
        "please consult a healthcare professional._",
        localise_disclaimer(lang).strip().lstrip("\n").lstrip("_").rstrip("_"),
    )
    return result


def _localise_vaccination(en_response: str, lang: str) -> str:
    """Replace English vaccination response footer with localised version."""
    if lang == "en":
        return en_response
    s = get_strings(lang)
    result = en_response
    result = result.replace(
        "💡 **Where to get vaccines:** All vaccines in the National Immunization Schedule "
        "are **FREE** at government health centres (PHCs, Sub-centres, CHCs).",
        s.get("vaccine_free_note", "")
    )
    result = result.replace(
        "_I'm an AI assistant, not a doctor. For diagnosis or treatment, please consult a healthcare professional._",
        localise_disclaimer(lang).strip().lstrip("\n"),
    )
    return result


def _localise_facility(en_response: str, lang: str) -> str:
    """Replace English facility response footer with localised version."""
    if lang == "en":
        return en_response
    s = get_strings(lang)
    result = en_response
    result = result.replace(
        "💡 **Tip:** Government PHCs (Primary Health Centres) provide **free consultations** "
        "and medicines under the National Health Mission.",
        s.get("facility_tip", "")
    )
    result = result.replace(
        "📞 **National Health Helpline: 104** — for health information and facility guidance.",
        s.get("facility_helpline", "")
    )
    result = result.replace(
        "_I'm an AI assistant, not a doctor. For diagnosis or treatment, please consult a healthcare professional._",
        localise_disclaimer(lang).strip().lstrip("\n"),
    )
    return result


class MockSehatAgent:
    """
    Demo-mode agent — runs without any IBM or Google API keys.
    Supports English, Hindi, and Kannada via local Unicode-based detection.
    The safety layer, triage, vaccination, and facility tools all work normally.
    Only the LLM is replaced with a rule-based responder.
    """

    def chat(self, user_message: str, session_id: str = "default") -> dict:
        # Step 1: Detect language locally (no API key)
        lang = detect_language(user_message)
        logger.info("MOCK MODE | session=%s | lang=%s | msg=%s...", session_id, lang, user_message[:50])

        result = {
            "response": "",
            "detected_language": lang,
            "is_emergency": False,
            "triage_tier": None,
            "mock_mode": True,
        }

        # Step 2: Red-flag safety check (always active — deterministic)
        is_emergency, category = check_red_flags(user_message)
        if is_emergency:
            result["is_emergency"] = True
            s = get_strings(lang)
            emergency_resp = get_emergency_response(category)
            # Prepend localised emergency prefix
            prefix = s.get("emergency_prefix", "")
            result["response"] = prefix + emergency_resp if prefix else emergency_resp
            logger.critical("MOCK MODE — Emergency triggered: %s", category)
            return result

        # Step 3: Mock LLM routing with language awareness
        try:
            response = _mock_llm_response(user_message, lang=lang)
        except Exception as e:
            logger.error("Mock agent error: %s", e)
            disc = localise_disclaimer(lang)
            if lang == "hi":
                response = "माफ़ करें, कुछ गड़बड़ी हुई। कृपया दोबारा कोशिश करें या **104** पर कॉल करें।" + disc
            elif lang == "kn":
                response = "ಕ್ಷಮಿಸಿ, ತೊಂದರೆ ಆಯಿತು. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ ಅಥವಾ **104** ಗೆ ಕರೆ ಮಾಡಿ।" + disc
            else:
                response = "I'm sorry, I had trouble processing that. Please try again or call **104**." + disc

        # Step 4: Save to memory
        try:
            memory = get_memory(session_id)
            memory.save_context({"input": user_message}, {"output": response})
        except Exception:
            pass

        result["response"] = response
        return result
