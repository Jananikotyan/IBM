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
from app.config import settings
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

# About Sehat Saathi — keywords that ask what/why/who this app is
_ABOUT_PATTERN = re.compile(
    r"\b(what|why|who|how|tell me about|explain|describe|introduce|what is|what are)\b"
    r".{0,50}\b(sehat\s*saat[hi][i]?|this\s+app|this\s+assistant|you|your purpose|"
    r"your\s+use|your\s+role|yourself)\b"
    r"|\b(sehat\s*saat[hi][i]?)\b.{0,50}\b(what|why|how|used|purpose|role|help|work|do|kya|hai|kaun)\b"
    r"|\b(sehat\s*saat[hi][i]?)\s+(kya|kaun|kyun|kaise|how|what|why)\b",
    re.IGNORECASE,
)

ABOUT_RESPONSE = (
    "## About Sehat Saathi 🏥\n\n"
    "**Sehat Saathi** means *'Health Companion'* in Hindi. "
    "It is a **multilingual AI-powered healthcare awareness assistant** "
    "built for rural and underserved communities across India.\n\n"

    "### 🎯 Purpose\n"
    "Millions of people in rural India lack timely access to healthcare. "
    "Sehat Saathi helps bridge this gap by:\n"
    "- Guiding people on **when and how to seek care** before it becomes an emergency\n"
    "- Raising awareness about **preventive healthcare** and vaccinations\n"
    "- Providing health information in **local languages** — no English required\n\n"

    "### 🛠️ What I Can Do\n"
    "- 🤒 **Symptom guidance** — describe your symptoms and I'll tell you whether to "
    "rest at home, see a doctor, or go to hospital urgently\n"
    "- 💉 **Vaccination schedules** — tell me your child's age or pregnancy stage "
    "and I'll show the next due vaccines (India's National Immunization Schedule)\n"
    "- 🏥 **Find nearby hospitals/PHCs** — give me your city or pincode\n"
    "- 🚨 **Emergency detection** — I automatically detect emergencies (chest pain, "
    "seizures, difficulty breathing) and immediately give you helpline numbers\n"
    "- 🩺 **Symptom Checker Wizard** — step-by-step guided triage with visual results\n"
    "- 📊 **Health information** — based on WHO and MoHFW India guidelines\n\n"

    "### 🌍 Languages Supported\n"
    "English · हिंदी (Hindi) · ಕನ್ನಡ (Kannada) · தமிழ் (Tamil) · "
    "తెలుగు (Telugu) · বাংলা (Bengali)\n\n"

    "### ⚙️ Technology\n"
    "Powered by **IBM watsonx.ai (Granite models)** + **LangChain** orchestration, "
    "with WHO/MoHFW knowledge retrieval (RAG) and Groq Whisper for voice input.\n\n"

    "### ⚠️ Important\n"
    "Sehat Saathi provides **health awareness and guidance only** — "
    "it is NOT a diagnostic tool and cannot replace a doctor. "
    "Always consult a qualified healthcare professional for medical advice.\n\n"
    "**Emergency helplines:** Ambulance **108** · Health Info **104** · "
    "Childline **1098** · Mental Health **9152987821**"
)

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

    # Check for "about Sehat Saathi" questions first — highest priority
    if _ABOUT_PATTERN.search(user_input) or _ABOUT_PATTERN.search(english_input):
        return ABOUT_RESPONSE + disclaimer

    # Check general knowledge topics
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
        # Broader location extraction: captures city/place after common prepositions
        # Handles: "near mangalore", "in mangalore", "at mangalore",
        #          "hospital near mangalore", "nearest hospital in mangalore",
        #          "find hospital near mangalore"
        location_match = re.search(
            r"(?:near(?:est)?|in|at|around)\s+([A-Za-z][\w\s]{1,28}?)(?:\s*\?|$|\.|,)",
            english_input, re.IGNORECASE
        )
        if not location_match:
            # Second pass: grab last capitalised word/phrase (likely a city name)
            location_match = re.search(
                r"(?:hospital|clinic|phc|doctor|health\s+cent(?:re|er))\s+.*?([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\s*(?:\?|$|\.|,)?$",
                user_input, re.MULTILINE
            )
        location = (
            pincode_match.group(0) if pincode_match
            else location_match.group(1).strip() if location_match
            else english_input  # pass full query — facility_locator_tool will try to geocode it
        )
        try:
            en_response = facility_locator_tool.run(location)
        except Exception as e:
            logger.error("Facility locator failed for location='%s': %s", location, e)
            en_response = (
                f"I had trouble searching for facilities near **{location}**.\n\n"
                "Please try:\n"
                "- Call **National Health Helpline: 104** (free, 24/7)\n"
                "- Visit https://hfr.abdm.gov.in to find nearby facilities\n\n"
                "_I'm an AI assistant, not a doctor. Please consult a healthcare professional._"
            )
        return _localise_facility(en_response, lang)

    # Try Ollama for general questions if available
    if settings.ollama_mode:
        ollama_response = _ask_ollama(user_input, lang)
        if ollama_response:
            return ollama_response + disclaimer

    # Fallback
    fb = localise_fallback(lang)
    return (fb if fb else FALLBACK_RESPONSE) + disclaimer


# Pre-built answers for very common general questions — instant, no Ollama needed
_INSTANT_RESPONSES = {
    "headache": (
        "**Headache** can have many causes — stress, dehydration, lack of sleep, or eye strain.\n\n"
        "**Try at home:**\n"
        "- Drink a full glass of water\n"
        "- Rest in a quiet, dark room\n"
        "- Apply a cold or warm cloth to your forehead\n\n"
        "**See a doctor if:** headache is severe, sudden, or with fever, stiff neck, or vision changes."
    ),
    "cold": (
        "**Common Cold** is caused by a virus — antibiotics do NOT help.\n\n"
        "**Home care:**\n"
        "- Rest and drink warm fluids (warm water, soup, kadha)\n"
        "- Steam inhalation helps with congestion\n"
        "- Honey + ginger for sore throat\n\n"
        "Usually gets better in 5-7 days. See a doctor if fever is high or lasts more than 7 days."
    ),
    "diabetes": (
        "**Diabetes** is a condition where blood sugar levels are too high.\n\n"
        "**Types:**\n"
        "- Type 1 — body doesn't make insulin\n"
        "- Type 2 — most common, often due to diet/lifestyle\n\n"
        "**Symptoms:** Excessive thirst, frequent urination, blurred vision, slow wound healing.\n\n"
        "**Management:** Diet control, exercise, medicines prescribed by a doctor. "
        "Free testing at all government PHCs.\n\n"
        "_Source: MoHFW India National Programme for NCD_"
    ),
    "blood pressure": (
        "**High Blood Pressure (Hypertension)** often has no symptoms — called the 'silent killer'.\n\n"
        "**Risk factors:** High salt diet, stress, obesity, smoking, family history.\n\n"
        "**What to do:**\n"
        "- Get BP checked regularly — free at govt PHCs\n"
        "- Reduce salt and oil in food\n"
        "- Exercise 30 minutes daily\n"
        "- Do NOT stop medicines without doctor's advice\n\n"
        "_Source: MoHFW India Hypertension guidelines_"
    ),
    "covid": (
        "**COVID-19** symptoms include fever, cough, loss of taste/smell, fatigue, body ache.\n\n"
        "**What to do:**\n"
        "- Isolate yourself from family members\n"
        "- Wear a mask, ventilate the room\n"
        "- Stay hydrated and rest\n"
        "- Contact your nearest health centre for testing\n\n"
        "**Emergency signs:** Difficulty breathing, persistent chest pain, confusion — call **108** immediately."
    ),
    "pregnancy": (
        "**Pregnancy care** is important for both mother and baby.\n\n"
        "**Key steps:**\n"
        "- Register at the nearest PHC as soon as pregnancy is confirmed — ANC checkups are FREE\n"
        "- Take Iron-Folic Acid (IFA) tablets daily — free at PHCs\n"
        "- Get all 4 ANC checkups done\n"
        "- Deliver at a hospital or health centre — Janani Suraksha Yojana gives cash benefit\n\n"
        "_Source: MoHFW India Reproductive, Maternal & Child Health guidelines_"
    ),
}

_INSTANT_KEYWORDS = {
    "headache": ["headache", "head pain", "sir dard", "talaigaval"],
    "cold":     ["common cold", "runny nose", "sneezing", "nazla", "zukam"],
    "diabetes": ["diabetes", "sugar", "blood sugar", "madhumeha", "madhumeh"],
    "blood pressure": ["blood pressure", "bp", "hypertension", "rakta chap"],
    "covid":    ["covid", "corona", "coronavirus"],
    "pregnancy":["pregnancy", "pregnant", "garbhwati", "garbha"],
}


def _ask_ollama(user_input: str, lang: str) -> str:
    """
    Returns an instant answer for common topics first.
    Falls back to Ollama Granite only if no instant match found.
    """
    # Check instant responses first — zero latency
    text_lower = user_input.lower()
    for topic, keywords in _INSTANT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return _INSTANT_RESPONSES[topic]

    # Fall back to Ollama for unknown general questions
    try:
        import httpx
        from app.config import settings as _s
        prompt = (
            "You are Sehat Saathi, a health awareness assistant for rural India. "
            "Answer in 3-4 SHORT sentences. Use simple language. "
            "No drug names. No diagnoses. "
            "End with: 'Please consult a healthcare professional.'\n\n"
            f"Question: {user_input}\nAnswer:"
        )
        resp = httpx.post(
            f"{_s.ollama_base_url}/api/generate",
            json={
                "model": _s.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 120,
                    "temperature": 0.1,
                    "top_k": 10,
                    "top_p": 0.9,
                },
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
    except Exception as e:
        logger.warning("Ollama call failed: %s", e)
    return ""


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
            "category": "general",
            "location": None,
            "mock_mode": True,
        }

        # Step 2: Red-flag safety check (always active — deterministic)
        is_emergency, category = check_red_flags(user_message)
        if is_emergency:
            result["is_emergency"] = True
            result["category"] = "emergency"
            s = get_strings(lang)
            emergency_resp = get_emergency_response(category)
            # Prepend localised emergency prefix
            prefix = s.get("emergency_prefix", "")
            result["response"] = prefix + emergency_resp if prefix else emergency_resp
            logger.critical("MOCK MODE — Emergency triggered: %s", category)
            return result

        # Step 3: Determine routing category for analytics
        english_input = normalise_to_english(user_message, lang)
        tool = _route_to_tool(english_input.lower())
        # Map tool name → analytics category
        _tool_to_cat = {
            "triage": "symptom",
            "vaccination": "vaccination",
            "facility": "facility",
            "general": "general",
        }
        result["category"] = _tool_to_cat.get(tool, "general")

        # Extract location hint for heatmap — only for facility queries
        if tool == "facility":
            pincode_match = re.search(r"\b\d{6}\b", user_message)
            city_match = re.search(
                r"(?:near|in|at|hospital in|clinic in|phc in)\s+([\w\s]{2,30}?)(?:\?|$|\.|,)",
                english_input, re.IGNORECASE,
            )
            if pincode_match:
                result["location"] = pincode_match.group(0)
            elif city_match:
                result["location"] = city_match.group(1).strip()

        # Step 4: Mock LLM routing with language awareness
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

        # Step 5: Save to memory
        try:
            memory = get_memory(session_id)
            memory.save_context({"input": user_message}, {"output": response})
        except Exception:
            pass

        result["response"] = response
        return result
