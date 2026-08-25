"""
Sehat Saathi - Local Language Translator (No API Key Required)
==============================================================
Detects Hindi and Kannada using Unicode script ranges.
Provides hardcoded phrase-level translations for all Sehat Saathi responses
so the app works fully in Hindi and Kannada without Watson Translator.

Supported in mock/demo mode:
  - en  English  (passthrough)
  - hi  Hindi    (Devanagari script detection + full translated responses)
  - kn  Kannada  (Kannada script detection + full translated responses)
"""
import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unicode script ranges for script-based language detection
# ---------------------------------------------------------------------------
# Devanagari: U+0900–U+097F (Hindi, Marathi, Sanskrit)
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
# Kannada:    U+0C80–U+0CFF
_KANNADA_SCRIPT = re.compile(r"[\u0C80-\u0CFF]")

# Common Hindi transliteration keywords (Latin script)
_HINDI_LATIN = re.compile(
    r"\b(bukhaar|dard|sar\s*dard|pet\s*dard|khoon|saans|bacha|baccha|"
    r"hafte|mahine|garbhwati|dawai|aspatal|bukhar|ulti|daast|khansi|"
    r"mujhe|mera|meri|hai|hain|ho\s*raha|nahi|nahin|kya|kahan|kaun)\b",
    re.IGNORECASE,
)

# Common Kannada transliteration keywords (Latin script)
_KANNADA_LATIN = re.compile(
    r"\b(jwara|novu|talaanu|hecchu|maduve|magu|makkalu|rasthe|aspatre|"
    r"doddavaru|hotte|shirasunovu|khansi|vomiti|nanna|nimma|avaru|idu|"
    r"hogi|onde|eradu|mooru|varsha|tingalu|vaara)\b",
    re.IGNORECASE,
)


def detect_language(text: str) -> str:
    """
    Detect language from text using Unicode script ranges + transliteration hints.
    Returns ISO 639-1 code: 'hi', 'kn', or 'en'.
    """
    if _DEVANAGARI.search(text):
        logger.debug("Detected: Hindi (Devanagari script)")
        return "hi"
    if _KANNADA_SCRIPT.search(text):
        logger.debug("Detected: Kannada (Kannada script)")
        return "kn"
    if _HINDI_LATIN.search(text):
        logger.debug("Detected: Hindi (transliteration keywords)")
        return "hi"
    if _KANNADA_LATIN.search(text):
        logger.debug("Detected: Kannada (transliteration keywords)")
        return "kn"
    return "en"


# ---------------------------------------------------------------------------
# Hindi keyword → English normalisation map
# (converts transliterated Hindi symptom words to English for tool routing)
# ---------------------------------------------------------------------------
HINDI_TO_ENGLISH = {
    # Symptoms
    "bukhaar": "fever", "bukhar": "fever",
    "sar dard": "headache", "sar-dard": "headache", "sardard": "headache",
    "pet dard": "abdominal pain", "pet mein dard": "abdominal pain",
    "khansi": "cough", "khasi": "cough",
    "ulti": "vomiting", "utti": "vomiting",
    "daast": "diarrhea", "dast": "diarrhea",
    "saans": "breathing", "saans lena": "breathe",
    "saans nahi": "cannot breathe", "saans lene mein takleef": "difficulty breathing",
    "khoon": "blood", "khoon aana": "bleeding",
    "kamzori": "weakness", "thakaan": "fatigue",
    "chakkar": "dizziness", "chakkar aana": "dizziness",
    "peeth dard": "back pain",
    # People
    "bacha": "baby", "baccha": "baby", "bachcha": "baby",
    "bacha hafte ka": "weeks old baby",
    "garbhwati": "pregnant", "pregnancy": "pregnant",
    "maa": "mother",
    # Places
    "aspatal": "hospital", "aspataal": "hospital",
    "dawakhana": "clinic", "dawai": "medicine",
    # Time
    "din se": "days", "hafte se": "weeks", "mahine se": "months",
    "hafte ka": "weeks old", "mahine ka": "months old",
}

# Kannada keyword → English normalisation map
KANNADA_TO_ENGLISH = {
    # Symptoms
    "jwara": "fever", "jvara": "fever",
    "talaanu novu": "headache", "tala novu": "headache",
    "hotte novu": "abdominal pain",
    "khansi": "cough", "kheelu": "cough",
    "vomiti": "vomiting", "vaanti": "vomiting",
    "bathavara": "diarrhea",
    "usiru tegoodu kashta": "difficulty breathing",
    "rakte": "blood", "raktasraava": "bleeding",
    "saktihiinata": "weakness", "dhauvaa": "fatigue",
    "tala suttuvike": "dizziness",
    # People
    "magu": "baby", "makkaḷu": "children", "makkalu": "children",
    "garbhiṇi": "pregnant", "garbhini": "pregnant",
    # Places
    "aspatre": "hospital", "chikitsaalaya": "clinic",
    # Time
    "vaara": "weeks old", "tingalu": "months old", "varsha": "years old",
}


def normalise_to_english(text: str, lang: str) -> str:
    """
    Convert Hindi or Kannada (transliterated or native keywords) to English
    so the routing and triage tools can process them correctly.
    """
    if lang == "en":
        return text

    result = text
    mapping = HINDI_TO_ENGLISH if lang == "hi" else KANNADA_TO_ENGLISH

    # Replace multi-word phrases first (longest match first)
    for native, english in sorted(mapping.items(), key=lambda x: -len(x[0])):
        result = re.sub(re.escape(native), english, result, flags=re.IGNORECASE)

    return result


# ---------------------------------------------------------------------------
# Localised UI strings — Hindi
# ---------------------------------------------------------------------------
HINDI = {
    "disclaimer": (
        "\n\n_मैं एक AI सहायक हूँ, डॉक्टर नहीं। "
        "निदान या उपचार के लिए कृपया किसी स्वास्थ्य विशेषज्ञ से मिलें।_"
    ),
    "fallback": (
        "नमस्ते! मैं **सेहत साथी** हूँ — आपका स्वास्थ्य जागरूकता सहायक 🏥\n\n"
        "मैं इन विषयों में मदद कर सकता हूँ:\n"
        "- 🤒 **लक्षण मार्गदर्शन** — अपने लक्षण बताएं\n"
        "- 💉 **टीकाकरण कार्यक्रम** — बच्चे की उम्र या गर्भावस्था बताएं\n"
        "- 🏥 **नज़दीकी अस्पताल/PHC खोजें** — पिनकोड या शहर बताएं\n"
        "- 📚 **स्वास्थ्य जानकारी** — बुखार, ORS, मलेरिया, TB, डेंगू के बारे में पूछें\n\n"
        "**उदाहरण:** *'मेरा बच्चा 6 हफ्ते का है'* या *'मुझे 2 दिन से बुखार है'*"
    ),
    "emergency_prefix": "🚨 **यह आपातकाल है — तुरंत कार्रवाई करें!**\n\n📞 **108 पर अभी कॉल करें** (मुफ़्त एम्बुलेंस)\n\n",
    "welcome": (
        "नमस्ते! 🙏 **सेहत साथी** में आपका स्वागत है।\n\n"
        "मैं आपकी स्वास्थ्य जागरूकता में मदद करने के लिए यहाँ हूँ।\n"
        "आप हिंदी या अंग्रेज़ी में पूछ सकते हैं।\n\n"
        "**आपातकाल में:** तुरंत **108** पर कॉल करें।"
    ),
    # Triage translations
    "triage_tier1": "✅ घर पर देखभाल करें",
    "triage_tier2": "🟡 कुछ दिनों में डॉक्टर से मिलें",
    "triage_tier3": "🔴 अभी तुरंत अस्पताल जाएं",
    "triage_why": "**क्यों:** ",
    "triage_tip_tier1": "💧 **घरेलू देखभाल:** आराम करें, खूब पानी पिएं। एंटीबायोटिक दवा खुद से न लें।",
    "triage_tip_tier2": "💡 **सुझाव:** नज़दीकी PHC (सरकारी स्वास्थ्य केंद्र) में जाएं — जाँच और दवाई मुफ़्त है।",
    "triage_tip_tier3": "⚠️ **जरूरी:** अगर सीने में दर्द या साँस लेने में तकलीफ हो — तुरंत **108** पर कॉल करें।",
    # Vaccination
    "vaccine_child_header": "📋 **{age} के बच्चे के लिए टीकाकरण कार्यक्रम**\n_(भारत राष्ट्रीय टीकाकरण कार्यक्रम — MoHFW)_\n",
    "vaccine_due_now": "🔔 **अभी देना है ({label}):**",
    "vaccine_next": "⏭️ **अगली बार ({label}):**",
    "vaccine_free_note": "💡 राष्ट्रीय टीकाकरण कार्यक्रम के सभी टीके सरकारी स्वास्थ्य केंद्रों पर **मुफ़्त** हैं।",
    "vaccine_visit": "📅 नज़दीकी आँगनवाड़ी/PHC में तय टीकाकरण दिवस (मंगलवार/शुक्रवार) पर जाएं।",
    # Facility
    "facility_header": "🏥 **{location} के पास स्वास्थ्य केंद्र:**\n",
    "facility_type": "📍 प्रकार:",
    "facility_address": "🗺️ पता:",
    "facility_phone": "📞 फ़ोन:",
    "facility_tip": "💡 सरकारी PHC में **मुफ़्त परामर्श और दवाएं** मिलती हैं।",
    "facility_helpline": "📞 **राष्ट्रीय स्वास्थ्य हेल्पलाइन: 104**",
    "facility_not_found": (
        "मुझे **{location}** के पास कोई स्वास्थ्य केंद्र नहीं मिला।\n\n"
        "कृपया कोशिश करें:\n"
        "- **104** (राष्ट्रीय स्वास्थ्य हेल्पलाइन) पर कॉल करें\n"
        "- अपने गाँव की ASHA या आँगनवाड़ी कार्यकर्ता से मिलें"
    ),
    # ORS
    "ors": (
        "**ORS (मौखिक पुनर्जलीकरण घोल)** दस्त या उल्टी से होने वाली कमज़ोरी के लिए उपयोग किया जाता है।\n\n"
        "**घर पर ORS बनाने का तरीका:**\n"
        "- 1 लीटर साफ/उबला पानी\n"
        "- 6 चम्मच चीनी\n"
        "- आधा चम्मच नमक\n"
        "अच्छे से मिलाएं और थोड़ा-थोड़ा पिलाएं। ORS के पैकेट सरकारी स्वास्थ्य केंद्रों पर **मुफ़्त** मिलते हैं।\n\n"
        "_स्रोत: WHO मौखिक पुनर्जलीकरण थेरेपी दिशानिर्देश_"
    ),
    "malaria": (
        "**मलेरिया** मच्छर के काटने से फैलने वाली बीमारी है।\n\n"
        "**लक्षण:** बुखार के साथ कंपकंपी, सिरदर्द, बदन दर्द, पसीना।\n\n"
        "**क्या करें:**\n"
        "- नज़दीकी PHC में तुरंत मलेरिया जाँच कराएं (मुफ़्त)\n"
        "- देरी न करें — इलाज न होने पर खतरनाक हो सकता है\n"
        "- मच्छरदानी का उपयोग करें\n\n"
        "**इलाज सरकारी स्वास्थ्य केंद्रों पर मुफ़्त है।**\n\n"
        "_स्रोत: WHO मलेरिया दिशानिर्देश_"
    ),
    "tb": (
        "**TB (तपेदिक)** एक इलाज योग्य बीमारी है जो मुख्यतः फेफड़ों को प्रभावित करती है।\n\n"
        "**लक्षण:** 2 हफ्ते से ज़्यादा खाँसी, बलगम में खून, रात को पसीना, वज़न कम होना।\n\n"
        "**ज़रूरी बातें:**\n"
        "- सरकारी स्वास्थ्य केंद्रों पर मुफ़्त जाँच और इलाज\n"
        "- इलाज 6 महीने का होता है — बीच में बंद न करें\n"
        "- निक्षय पोषण योजना के तहत ₹500/माह की सहायता\n\n"
        "_स्रोत: MoHFW भारत TB दिशानिर्देश_"
    ),
    "dengue": (
        "**डेंगू** एडीज मच्छर के काटने से फैलने वाला वायरल बुखार है।\n\n"
        "**लक्षण:** अचानक तेज़ बुखार, आँखों के पीछे दर्द, जोड़ों में दर्द, रैश।\n\n"
        "**खतरनाक लक्षण** (तुरंत अस्पताल जाएं):\n"
        "- नाक या मसूड़ों से खून\n"
        "- पेट में तेज़ दर्द\n"
        "- बार-बार उल्टी\n\n"
        "**बचाव:** घर के पास पानी जमा न होने दें। मच्छर भगाने वाली क्रीम लगाएं।\n\n"
        "_स्रोत: WHO डेंगू दिशानिर्देश_"
    ),
    "anemia": (
        "**एनीमिया** यानी खून/हीमोग्लोबिन की कमी।\n\n"
        "**लक्षण:** थकान, कमज़ोरी, पीली त्वचा, चक्कर आना, साँस फूलना।\n\n"
        "**क्या मदद करता है:**\n"
        "- आयरन युक्त खाना: हरी सब्ज़ियाँ, दालें, गुड़, खजूर\n"
        "- आयरन-फोलिक एसिड (IFA) गोलियाँ — PHC पर मुफ़्त\n"
        "- गर्भवती महिलाएं और बच्चे सबसे ज़्यादा प्रभावित होते हैं\n\n"
        "_स्रोत: MoHFW भारत राष्ट्रीय आयरन प्लस पहल_"
    ),
}

# ---------------------------------------------------------------------------
# Localised UI strings — Kannada
# ---------------------------------------------------------------------------
KANNADA = {
    "disclaimer": (
        "\n\n_ನಾನು AI ಸಹಾಯಕ, ವೈದ್ಯರಲ್ಲ. "
        "ರೋಗನಿರ್ಣಯ ಅಥವಾ ಚಿಕಿತ್ಸೆಗಾಗಿ ದಯವಿಟ್ಟು ಆರೋಗ್ಯ ತಜ್ಞರನ್ನು ಸಂಪರ್ಕಿಸಿ._"
    ),
    "fallback": (
        "ನಮಸ್ಕಾರ! ನಾನು **ಸೇಹತ್ ಸಾಥಿ** — ನಿಮ್ಮ ಆರೋಗ್ಯ ಜಾಗೃತಿ ಸಹಾಯಕ 🏥\n\n"
        "ನಾನು ಈ ವಿಷಯಗಳಲ್ಲಿ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ:\n"
        "- 🤒 **ರೋಗಲಕ್ಷಣ ಮಾರ್ಗದರ್ಶನ** — ನಿಮ್ಮ ರೋಗಲಕ್ಷಣಗಳನ್ನು ತಿಳಿಸಿ\n"
        "- 💉 **ಲಸಿಕೆ ವೇಳಾಪಟ್ಟಿ** — ಮಗುವಿನ ವಯಸ್ಸು ಅಥವಾ ಗರ್ಭಾವಸ್ಥೆ ತಿಳಿಸಿ\n"
        "- 🏥 **ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ/PHC ಹುಡುಕಿ** — ಪಿನ್‌ಕೋಡ್ ಅಥವಾ ನಗರ ತಿಳಿಸಿ\n"
        "- 📚 **ಆರೋಗ್ಯ ಮಾಹಿತಿ** — ಜ್ವರ, ORS, ಮಲೇರಿಯಾ, TB ಬಗ್ಗೆ ಕೇಳಿ\n\n"
        "**ಉದಾಹರಣೆ:** *'ನನ್ನ ಮಗು 6 ವಾರದ್ದು'* ಅಥವಾ *'ನನಗೆ 2 ದಿನದಿಂದ ಜ್ವರ ಇದೆ'*"
    ),
    "emergency_prefix": "🚨 **ಇದು ತುರ್ತು ಪರಿಸ್ಥಿತಿ — ತಕ್ಷಣ ಕ್ರಮ ತೆಗೆದುಕೊಳ್ಳಿ!**\n\n📞 **108 ಗೆ ಈಗಲೇ ಕರೆ ಮಾಡಿ** (ಉಚಿತ ಆಂಬ್ಯುಲೆನ್ಸ್)\n\n",
    "welcome": (
        "ನಮಸ್ಕಾರ! 🙏 **ಸೇಹತ್ ಸಾಥಿ**ಗೆ ಸ್ವಾಗತ.\n\n"
        "ನೀವು ಕನ್ನಡ ಅಥವಾ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ಕೇಳಬಹುದು.\n\n"
        "**ತುರ್ತು ಪರಿಸ್ಥಿತಿಯಲ್ಲಿ:** ತಕ್ಷಣ **108** ಗೆ ಕರೆ ಮಾಡಿ."
    ),
    "triage_tier1": "✅ ಮನೆಯಲ್ಲಿ ಆರೈಕೆ ಮಾಡಿ",
    "triage_tier2": "🟡 ಕೆಲವು ದಿನಗಳಲ್ಲಿ ವೈದ್ಯರನ್ನು ಭೇಟಿ ಮಾಡಿ",
    "triage_tier3": "🔴 ಈಗಲೇ ತುರ್ತು ಆರೈಕೆ ಪಡೆಯಿರಿ",
    "triage_tip_tier1": "💧 **ಮನೆ ಆರೈಕೆ:** ವಿಶ್ರಾಂತಿ ತೆಗೆದುಕೊಳ್ಳಿ, ಹೆಚ್ಚು ನೀರು ಕುಡಿಯಿರಿ.",
    "triage_tip_tier2": "💡 **ಸಲಹೆ:** ಹತ್ತಿರದ PHCಗೆ ಭೇಟಿ ನೀಡಿ — ತಪಾಸಣೆ ಮತ್ತು ಔಷಧಿ ಉಚಿತ.",
    "triage_tip_tier3": "⚠️ **ಮುಖ್ಯ:** ಎದೆ ನೋವು ಅಥವಾ ಉಸಿರಾಟ ತೊಂದರೆ ಇದ್ದರೆ — ತಕ್ಷಣ **108** ಗೆ ಕರೆ ಮಾಡಿ.",
    "vaccine_free_note": "💡 ರಾಷ್ಟ್ರೀಯ ಲಸಿಕೆ ಕಾರ್ಯಕ್ರಮದ ಎಲ್ಲಾ ಲಸಿಕೆಗಳು ಸರ್ಕಾರಿ ಆರೋಗ್ಯ ಕೇಂದ್ರಗಳಲ್ಲಿ **ಉಚಿತ**.",
    "facility_tip": "💡 ಸರ್ಕಾರಿ PHCಯಲ್ಲಿ **ಉಚಿತ ಸಲಹೆ ಮತ್ತು ಔಷಧಿ** ಸಿಗುತ್ತದೆ.",
    "facility_helpline": "📞 **ರಾಷ್ಟ್ರೀಯ ಆರೋಗ್ಯ ಸಹಾಯವಾಣಿ: 104**",
    "ors": (
        "**ORS (ಮೌಖಿಕ ಪುನರ್ಜಲೀಕರಣ ದ್ರಾವಣ)** ಅತಿಸಾರ ಅಥವಾ ವಾಂತಿಯಿಂದ ಆಗುವ ನಿರ್ಜಲೀಕರಣಕ್ಕೆ ಬಳಸಲಾಗುತ್ತದೆ.\n\n"
        "**ಮನೆಯಲ್ಲಿ ORS ತಯಾರಿಸುವ ವಿಧಾನ:**\n"
        "- 1 ಲೀಟರ್ ಶುದ್ಧ/ಕುದಿಸಿದ ನೀರು\n"
        "- 6 ಟೀ ಚಮಚ ಸಕ್ಕರೆ\n"
        "- ½ ಟೀ ಚಮಚ ಉಪ್ಪು\n"
        "ಚೆನ್ನಾಗಿ ಬೆರೆಸಿ ಸ್ವಲ್ಪ ಸ್ವಲ್ಪ ಕೊಡಿ. ORS ಪ್ಯಾಕೆಟ್‌ಗಳು ಸರ್ಕಾರಿ ಕೇಂದ್ರಗಳಲ್ಲಿ **ಉಚಿತ**.\n\n"
        "_ಮೂಲ: WHO ಮೌಖಿಕ ಪುನರ್ಜಲೀಕರಣ ಚಿಕಿತ್ಸೆ ಮಾರ್ಗಸೂಚಿಗಳು_"
    ),
    "malaria": (
        "**ಮಲೇರಿಯಾ** ಸೊಳ್ಳೆ ಕಡಿತದಿಂದ ಹರಡುವ ರೋಗ.\n\n"
        "**ಲಕ್ಷಣಗಳು:** ಜ್ವರ ಮತ್ತು ನಡುಕ, ತಲೆನೋವು, ಮೈಕೈ ನೋವು.\n\n"
        "**ಏನು ಮಾಡಬೇಕು:**\n"
        "- ಹತ್ತಿರದ PHCಯಲ್ಲಿ ತಕ್ಷಣ ರಕ್ತ ಪರೀಕ್ಷೆ ಮಾಡಿಸಿ (ಉಚಿತ)\n"
        "- ತಡ ಮಾಡಬೇಡಿ — ಚಿಕಿತ್ಸೆ ಮಾಡದಿದ್ದರೆ ಅಪಾಯಕಾರಿ\n"
        "- ಸೊಳ್ಳೆ ಪರದೆ ಬಳಸಿ\n\n"
        "**ಚಿಕಿತ್ಸೆ ಸರ್ಕಾರಿ ಕೇಂದ್ರಗಳಲ್ಲಿ ಉಚಿತ.**\n\n"
        "_ಮೂಲ: WHO ಮಲೇರಿಯಾ ಮಾರ್ಗಸೂಚಿಗಳು_"
    ),
    "tb": (
        "**TB (ಕ್ಷಯರೋಗ)** ಗುಣಪಡಿಸಬಹುದಾದ ರೋಗ, ಮುಖ್ಯವಾಗಿ ಶ್ವಾಸಕೋಶಗಳ ಮೇಲೆ ಪರಿಣಾಮ ಮಾಡುತ್ತದೆ.\n\n"
        "**ಲಕ್ಷಣಗಳು:** 2 ವಾರಕ್ಕಿಂತ ಹೆಚ್ಚು ಕೆಮ್ಮು, ರಕ್ತ ಕಫ, ರಾತ್ರಿ ಬೆವರು, ತೂಕ ಕಡಿಮೆ.\n\n"
        "**ಮುಖ್ಯ ವಿಷಯಗಳು:**\n"
        "- ಸರ್ಕಾರಿ ಕೇಂದ್ರಗಳಲ್ಲಿ ಉಚಿತ ಪರೀಕ್ಷೆ ಮತ್ತು ಚಿಕಿತ್ಸೆ\n"
        "- ಚಿಕಿತ್ಸೆ 6 ತಿಂಗಳು — ಮಧ್ಯದಲ್ಲಿ ನಿಲ್ಲಿಸಬೇಡಿ\n\n"
        "_ಮೂಲ: MoHFW ಭಾರತ TB ಮಾರ್ಗಸೂಚಿಗಳು_"
    ),
    "dengue": (
        "**ಡೆಂಗ್ಯೂ** ಏಡೀಸ್ ಸೊಳ್ಳೆ ಕಡಿತದಿಂದ ಹರಡುವ ವೈರಲ್ ಜ್ವರ.\n\n"
        "**ಲಕ್ಷಣಗಳು:** ಏಕಾಏಕಿ ತೀವ್ರ ಜ್ವರ, ಕಣ್ಣಿನ ಹಿಂದೆ ನೋವು, ಕೀಲು ನೋವು, ದದ್ದು.\n\n"
        "**ಅಪಾಯದ ಸಂಕೇತಗಳು** (ತಕ್ಷಣ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ):\n"
        "- ಮೂಗು/ಒಸಡಿನಿಂದ ರಕ್ತ\n"
        "- ತೀವ್ರ ಹೊಟ್ಟೆ ನೋವು\n\n"
        "**ತಡೆಗಟ್ಟುವಿಕೆ:** ನೀರು ನಿಲ್ಲದಂತೆ ನೋಡಿಕೊಳ್ಳಿ.\n\n"
        "_ಮೂಲ: WHO ಡೆಂಗ್ಯೂ ಮಾರ್ಗಸೂಚಿಗಳು_"
    ),
    "anemia": (
        "**ರಕ್ತಹೀನತೆ** ಎಂದರೆ ರಕ್ತ/ಹಿಮೋಗ್ಲೋಬಿನ್ ಕಡಿಮೆ.\n\n"
        "**ಲಕ್ಷಣಗಳು:** ದಣಿವು, ದೌರ್ಬಲ್ಯ, ಬಿಳಿಚಿದ ಚರ್ಮ, ತಲೆ ತಿರುಗುವಿಕೆ.\n\n"
        "**ಏನು ಸಹಾಯ ಮಾಡುತ್ತದೆ:**\n"
        "- ಕಬ್ಬಿಣಾಂಶ ಭರಿತ ಆಹಾರ: ಹಸಿರು ತರಕಾರಿ, ಬೆಲ್ಲ, ಖರ್ಜೂರ\n"
        "- IFA ಮಾತ್ರೆಗಳು — PHCಯಲ್ಲಿ ಉಚಿತ\n\n"
        "_ಮೂಲ: MoHFW ರಾಷ್ಟ್ರೀಯ ಕಬ್ಬಿಣ ಪ್ಲಸ್ ಉಪಕ್ರಮ_"
    ),
}

LANG_STRINGS = {"hi": HINDI, "kn": KANNADA}


def get_strings(lang: str) -> dict:
    """Return the localised string dict for the given language code."""
    return LANG_STRINGS.get(lang, {})


def localise_disclaimer(lang: str) -> str:
    strings = get_strings(lang)
    return strings.get("disclaimer", (
        "\n\n_I'm an AI assistant, not a doctor. "
        "For diagnosis or treatment, please consult a healthcare professional._"
    ))


def localise_fallback(lang: str) -> str:
    strings = get_strings(lang)
    return strings.get("fallback", "")


def localise_topic(topic: str, lang: str) -> str:
    """Return a translated topic response (ors/malaria/tb/dengue/anemia) or empty string."""
    strings = get_strings(lang)
    return strings.get(topic, "")
