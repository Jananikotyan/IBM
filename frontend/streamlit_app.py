"""
Sehat Saathi - Streamlit Frontend
===================================
A conversational chat interface for the Sehat Saathi healthcare assistant.
Connects to the FastAPI backend (or directly to the agent if running locally).

Features:
  - Recents sidebar (Gemini-style) with switch / rename / delete
  - Per-session message history stored in st.session_state
  - Download Health Report as PDF (per session)
  - Voice input via Groq Whisper
  - Multilingual support
"""
import streamlit as st
import requests
import uuid
import os
from datetime import datetime

# Detect mock mode (reads same .env as backend)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass
IS_MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sehat Saathi - Health Companion",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Constants ────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

LANGUAGE_OPTIONS = {
    "English": "en",
    "हिंदी (Hindi)": "hi",
    "தமிழ் (Tamil)": "ta",
    "తెలుగు (Telugu)": "te",
    "বাংলা (Bengali)": "bn",
    "मराठी (Marathi)": "mr",
    "ગુજરાતી (Gujarati)": "gu",
    "ಕನ್ನಡ (Kannada)": "kn",
    "ਪੰਜਾਬੀ (Punjabi)": "pa",
    "മലയാളം (Malayalam)": "ml",
}
LANG_CODE_TO_NAME = {v: k for k, v in LANGUAGE_OPTIONS.items()}

EMERGENCY_KEYWORDS_UI = ["chest pain", "can't breathe", "unconscious", "seizure", "bleeding heavily", "suicidal"]

# ── Feature 1: Health Tip of the Day ─────────────────────────────────────────
import hashlib
_HEALTH_TIPS = [
    "💧 Drink at least 8 glasses of water daily to stay hydrated.",
    "🥬 Eat green leafy vegetables to prevent anaemia — especially important for pregnant women.",
    "💉 All vaccines in India's National Immunization Schedule are FREE at government PHCs.",
    "🧼 Wash hands with soap for 20 seconds before eating and after using the toilet.",
    "🤱 Breastfeed exclusively for the first 6 months — it protects your baby from infections.",
    "🌙 Sleep 7–8 hours daily. Poor sleep weakens your immune system.",
    "🚶 Walk 30 minutes daily — it reduces risk of diabetes, BP, and heart disease.",
    "🍋 Vitamin C (citrus fruits, amla) helps your body absorb iron from food.",
    "🧂 Reduce salt in food — high salt increases blood pressure risk.",
    "🚭 Tobacco causes mouth, lung, and throat cancer. It's never too late to quit.",
    "🏥 Visit your nearest PHC for free blood pressure and blood sugar screening.",
    "👶 Weigh your baby every month — steady weight gain means healthy growth.",
    "🤰 ANC (Antenatal Care) checkups are FREE at government hospitals — don't skip them.",
    "💊 Iron-Folic Acid tablets are FREE at PHCs — take daily during pregnancy.",
    "🦟 Sleep under a mosquito net to prevent malaria and dengue.",
    "🪣 Store drinking water in a covered, clean container to prevent waterborne disease.",
    "😷 Cover mouth when coughing or sneezing — it prevents spread of TB and flu.",
    "👁️ Get your child's eyes checked at school age — vision problems affect learning.",
    "🩺 Know your numbers: normal BP is below 120/80, normal blood sugar is below 100 mg/dL.",
    "🏃 Regular physical activity reduces risk of depression and anxiety.",
    "🍼 Start solid food for babies at 6 months — not before.",
    "🌿 ORS (Oral Rehydration Solution) saves lives in diarrhea — give immediately.",
    "🔬 TB is curable with 6 months of free medicines from government health centres.",
    "❤️ Know the signs of a heart attack: chest pain, left arm pain, sweating, breathlessness.",
    "🧠 Mental health matters. Call iCall: 9152987821 for free counselling.",
    "📞 National Health Helpline 104 is free — call anytime for health guidance.",
    "👂 Clean ears gently — never insert objects into ear canal.",
    "🦷 Brush teeth twice a day — dental health affects overall health.",
    "🧪 Test for diabetes every year if you are overweight or have family history.",
    "🫁 Good ventilation at home reduces risk of respiratory diseases.",
]

def _get_daily_tip() -> str:
    """Return a tip that rotates daily (same tip all day)."""
    day_key = datetime.now().strftime("%Y-%m-%d")
    idx = int(hashlib.md5(day_key.encode()).hexdigest(), 16) % len(_HEALTH_TIPS)
    return _HEALTH_TIPS[idx]

# ── Feature 2: Quick Symptom Buttons ─────────────────────────────────────────
QUICK_SYMPTOMS = [
    ("🤒", "Fever",         "I have fever for 2 days"),
    ("🤧", "Cold & Cough",  "I have cold and cough"),
    ("🤰", "Pregnancy",     "I am pregnant, what care do I need?"),
    ("💉", "Vaccine",       "What vaccines does my child need?"),
    ("🏥", "Hospital",      "Find nearest hospital Pincode: 110001"),
    ("🩺", "Checkup",       "I need a general health checkup"),
    ("🤢", "Vomiting",      "I have nausea and vomiting"),
    ("💊", "ORS",           "How to make ORS at home?"),
]

# ── Feature 3: Follow-up Suggestions ─────────────────────────────────────────
_FOLLOWUPS = {
    "triage":      ["🏥 Find nearby hospital", "💊 What medicines help?", "💧 Home remedies?"],
    "vaccination": ["📅 Next vaccine schedule?", "🏥 Where to get vaccines free?", "🤰 Pregnancy vaccines?"],
    "facility":    ["🗺️ Show me on map", "📞 What is the helpline number?", "🕐 Clinic timings?"],
    "general":     ["🤒 Check my symptoms", "💉 Vaccination schedule", "🏥 Find hospital near me"],
}

def _get_followups(category: str) -> list:
    return _FOLLOWUPS.get(category, _FOLLOWUPS["general"])

EXAMPLE_QUERIES = [
    "🤒 My baby is 6 weeks old. What vaccines are due?",
    "🌡️ I have fever for 2 days and headache",
    "🏥 Where is the nearest government hospital? Pincode: 110001",
    "🤰 I am 3 months pregnant. What checkups do I need?",
    "💊 What is ORS and when should I give it?",
    "😷 I have a cough for 3 weeks and weight loss",
]

HINDI_EXAMPLES = [
    "🤒 Mera baccha 6 hafte ka hai. Kaun si vaccine lagni chahiye?",
    "🌡️ Mujhe 2 din se bukhaar hai aur sar dard hai",
    "🏥 Nearest sarkari hospital kahan hai? Pincode: 110001",
    "🤰 Main 3 mahine ki garbhwati hoon. Kya checkup chahiye?",
]

MARATHI_EXAMPLES = [
    "🤒 माझ्या बाळाला 6 आठवडे आहेत. कोणती लस द्यायची?",
    "🌡️ मला ताप आणि डोकेदुखी आहे",
    "🏥 जवळचे सरकारी दवाखाना कुठे आहे? Pincode: 400001",
]

KANNADA_EXAMPLES = [
    "🤒 Nanna magu 6 varaddu. Yaava lasike kodabeku?",
    "🌡️ Nanage 2 dinagalinda jwara ide mattu tala novu ide",
    "🏥 Hattira aspatre ellidhe? Pincode: 560001",
]

TAMIL_EXAMPLES = [
    "🤒 என் குழந்தைக்கு 6 வாரம். என்ன தடுப்பூசி போட வேண்டும்?",
    "🌡️ எனக்கு 2 நாளாக காய்ச்சல் இருக்கிறது",
    "🏥 அருகிலுள்ள மருத்துவமனை எங்கே? Pincode: 600001",
]

TELUGU_EXAMPLES = [
    "🤒 నా బిడ్డకు 6 వారాలు. ఏ వ్యాక్సిన్ వేయాలి?",
    "🌡️ నాకు 2 రోజులుగా జ్వరంగా ఉంది",
    "🏥 దగ్గరలో ఆసుపత్రి ఎక్కడ ఉంది? Pincode: 500001",
]

BENGALI_EXAMPLES = [
    "🤒 আমার শিশুর ৬ সপ্তাহ। কোন টিকা দিতে হবে?",
    "🌡️ আমার ২ দিন ধরে জ্বর হচ্ছে",
    "🏥 কাছের হাসপাতাল কোথায়? Pincode: 700001",
]

GUJARATI_EXAMPLES = [
    "🤒 મારા બાળકને 6 અઠવાડિયા છે. કઈ રસી આપવી?",
    "🌡️ મને તાવ અને માથાનો દુખાવો છે",
    "🏥 નજીકની સરકારી હૉસ્પિટલ ક્યાં છે? Pincode: 380001",
]

PUNJABI_EXAMPLES = [
    "🤒 ਮੇਰੇ ਬੱਚੇ ਨੂੰ 6 ਹਫ਼ਤੇ ਹਨ। ਕਿਹੜੀ ਵੈਕਸੀਨ ਲੱਗਣੀ ਚਾਹੀਦੀ?",
    "🌡️ ਮੈਨੂੰ ਬੁਖ਼ਾਰ ਅਤੇ ਸਿਰਦਰਦ ਹੈ",
    "🏥 ਨੇੜੇ ਦਾ ਸਰਕਾਰੀ ਹਸਪਤਾਲ ਕਿੱਥੇ ਹੈ? Pincode: 143001",
]

MALAYALAM_EXAMPLES = [
    "🤒 എന്റെ കുഞ്ഞിന് 6 ആഴ്ച ആയി. എന്ത് വാക്സിൻ നൽകണം?",
    "🌡️ എനിക്ക് പനിയും തലവേദനയും ഉണ്ട്",
    "🏥 അടുത്തുള്ള സർക്കാർ ആശുപത്രി എവിടെ? Pincode: 682001",
]

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ══════════════════════════════════════════
       GLOBAL
    ══════════════════════════════════════════ */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, 'Segoe UI', system-ui, sans-serif !important;
    }

    /* Hide default streamlit top menu/footer only */
    #MainMenu, footer { visibility: hidden; }

    /* ══════════════════════════════════════════
       MAIN HEADER BANNER
    ══════════════════════════════════════════ */
    .main-header {
        background: linear-gradient(135deg, #0a2342 0%, #1a5276 55%, #2e86ab 100%);
        padding: 22px 32px 18px;
        border-radius: 16px;
        color: white;
        margin-bottom: 14px;
        text-align: center;
        box-shadow: 0 6px 24px rgba(10,35,66,0.22);
        position: relative;
        overflow: hidden;
    }
    .main-header::before {
        content: '';
        position: absolute;
        top: -40px; right: -40px;
        width: 160px; height: 160px;
        background: rgba(255,255,255,0.04);
        border-radius: 50%;
    }
    .main-header::after {
        content: '';
        position: absolute;
        bottom: -50px; left: -30px;
        width: 120px; height: 120px;
        background: rgba(255,255,255,0.04);
        border-radius: 50%;
    }
    .main-header h1 {
        font-size: 2.1rem; margin: 0;
        color: white !important; font-weight: 800;
        letter-spacing: -0.5px; line-height: 1.2;
        text-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    .main-header .tagline {
        font-size: 0.94rem; margin: 7px 0 0;
        opacity: 0.92; color: white !important; font-weight: 400;
    }
    .main-header .stats {
        font-size: 0.78rem; margin: 5px 0 0;
        opacity: 0.70; color: white !important;
    }
    .main-header .lang-pills {
        margin-top: 12px;
        display: flex; flex-wrap: wrap;
        gap: 5px; justify-content: center;
    }
    .lang-pill {
        background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.28);
        border-radius: 20px;
        padding: 3px 11px;
        font-size: 0.72rem;
        color: rgba(255,255,255,0.92);
        white-space: nowrap;
        backdrop-filter: blur(4px);
        transition: background 0.2s;
    }
    .lang-pill:hover { background: rgba(255,255,255,0.25); }

    /* ══════════════════════════════════════════
       DISCLAIMER BAR
    ══════════════════════════════════════════ */
    .disclaimer {
        background: linear-gradient(90deg, #fffbeb, #fff9e0);
        border: 1px solid #f6d860;
        border-left: 4px solid #f0b429;
        border-radius: 10px;
        padding: 10px 16px;
        font-size: 0.82rem;
        color: #7a5a00;
        margin-top: 10px;
        display: flex; align-items: center; gap: 8px;
    }

    /* ══════════════════════════════════════════
       WELCOME SCREEN
    ══════════════════════════════════════════ */
    .welcome-wrap {
        text-align: center;
        padding: 36px 20px 28px;
    }
    .welcome-icon {
        font-size: 4rem; line-height: 1;
        margin-bottom: 12px;
        filter: drop-shadow(0 4px 8px rgba(46,134,171,0.25));
    }
    .welcome-title {
        font-size: 1.4rem; font-weight: 800;
        color: #0a2342; margin-bottom: 8px;
        letter-spacing: -0.3px;
    }
    .welcome-sub {
        font-size: 0.92rem; color: #57606a;
        margin-bottom: 28px; line-height: 1.6;
    }
    .feature-grid {
        display: flex; flex-wrap: wrap;
        gap: 12px; justify-content: center;
        margin-bottom: 24px;
    }
    .feature-card {
        background: #ffffff;
        border: 1.5px solid #e5e7eb;
        border-radius: 14px;
        padding: 16px 18px;
        min-width: 148px; max-width: 175px;
        text-align: center;
        font-size: 0.83rem;
        color: #374151;
        line-height: 1.5;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
    }
    .feature-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(46,134,171,0.15);
        border-color: #2e86ab;
    }
    .feature-card .fc-icon  { font-size: 1.8rem; margin-bottom: 6px; }
    .feature-card .fc-title { font-weight: 700; font-size: 0.9rem; color: #0a2342; margin-bottom: 3px; }
    .welcome-examples {
        font-size: 0.84rem; color: #57606a;
        background: #f7f8fa;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 10px 16px;
        display: inline-block;
        margin-bottom: 10px;
    }
    .welcome-hint {
        font-size: 0.78rem; color: #9ca3af;
        margin-top: 8px;
    }

    /* ══════════════════════════════════════════
       CHAT MESSAGES
    ══════════════════════════════════════════ */
    /* User bubble */
    div[data-testid="stChatMessage"]:has(img[alt="👤"]) {
        background: #eef6ff !important;
        border-radius: 12px !important;
        border: 1px solid #dbeafe !important;
        margin: 4px 0 !important;
        padding: 2px 8px !important;
    }
    /* Assistant bubble */
    div[data-testid="stChatMessage"]:has(img[alt="🏥"]) {
        background: #ffffff !important;
        border-radius: 12px !important;
        border: 1px solid #e5e7eb !important;
        margin: 4px 0 !important;
        padding: 2px 8px !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    /* Emergency bubble */
    .emergency-msg {
        background: #fff1f0;
        border: 1.5px solid #fca5a5;
        border-left: 4px solid #ef4444;
        border-radius: 10px;
        padding: 12px 16px;
        margin: 6px 0;
        animation: pulse-border 1.5s infinite;
    }
    @keyframes pulse-border {
        0%, 100% { border-left-color: #ef4444; }
        50%       { border-left-color: #b91c1c; box-shadow: 0 0 0 3px rgba(239,68,68,0.1); }
    }

    /* ══════════════════════════════════════════
       SIDEBAR
    ══════════════════════════════════════════ */
    div[data-testid="stSidebarContent"] { padding-top: 0.5rem; }

    .sidebar-brand {
        padding: 10px 4px 6px;
        border-bottom: 1px solid #f0f0f0;
        margin-bottom: 10px;
    }
    .sidebar-brand h2 {
        font-size: 1.15rem; font-weight: 800;
        color: #0a2342; margin: 0; letter-spacing: -0.3px;
    }
    .sidebar-brand p {
        font-size: 0.78rem; color: #57606a; margin: 2px 0 0;
    }

    .recents-header {
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #9ca3af;
        padding: 6px 0 4px 2px;
        margin-top: 6px;
    }
    .chat-item {
        padding: 8px 10px;
        border-radius: 10px;
        margin-bottom: 3px;
        border: 1px solid transparent;
        transition: background 0.15s, border-color 0.15s;
    }
    .chat-item:hover  { background: #f0f6ff; border-color: #bfdbfe; }
    .chat-item.active {
        background: linear-gradient(90deg, #eff6ff, #e0f2fe);
        border-color: #2e86ab;
    }
    .chat-item-title {
        font-size: 0.875rem; font-weight: 600; color: #0a2342;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        max-width: 148px;
    }
    .chat-item-time  { font-size: 0.68rem; color: #9ca3af; white-space: nowrap; }
    .chat-item-sub   {
        font-size: 0.72rem; color: #6b7280;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        max-width: 148px; margin-top: 1px;
    }

    /* ══════════════════════════════════════════
       RENAME ROW
    ══════════════════════════════════════════ */
    div[data-testid="stSidebar"] div[data-testid="stForm"] {
        border: none !important; padding: 0 !important;
        background: transparent !important; box-shadow: none !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stForm"]
        div[data-testid="stHorizontalBlock"] {
        gap: 4px !important; align-items: center !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stForm"]
        div[data-testid="stTextInput"] { margin: 0 !important; padding: 0 !important; }
    div[data-testid="stSidebar"] div[data-testid="stForm"]
        div[data-testid="stTextInput"] label { display: none !important; }
    div[data-testid="stSidebar"] div[data-testid="stForm"]
        div[data-testid="stTextInput"] input {
        height: 34px !important; padding: 0 8px !important;
        font-size: 0.83rem !important; margin: 0 !important;
    }

    /* ══════════════════════════════════════════
       VOICE RECORDER WIDGET
    ══════════════════════════════════════════ */
    .wa-voice-wrap {
        display: flex;
        align-items: center;
        gap: 10px;
        background: linear-gradient(90deg, #f0fdf4, #ecfdf5);
        border: 1.5px solid #86efac;
        border-radius: 28px;
        padding: 8px 14px 8px 10px;
        margin: 6px 0 2px 0;
        min-height: 52px;
        box-shadow: 0 2px 8px rgba(39,174,96,0.08);
    }
    .wa-mic-btn {
        width: 42px; height: 42px; flex-shrink: 0;
        border-radius: 50%;
        border: none; cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.2rem;
        transition: background 0.2s, transform 0.15s, box-shadow 0.2s;
    }
    .wa-mic-btn.idle {
        background: linear-gradient(135deg, #27ae60, #1e8449);
        color: #fff;
        box-shadow: 0 3px 10px rgba(39,174,96,0.35);
    }
    .wa-mic-btn.idle:hover { transform: scale(1.08); box-shadow: 0 5px 16px rgba(39,174,96,0.45); }
    .wa-mic-btn.rec  {
        background: linear-gradient(135deg, #e74c3c, #c0392b);
        color: #fff;
        animation: mic-pulse 1s infinite;
    }
    @keyframes mic-pulse {
        0%,100% { box-shadow: 0 0 0 0 rgba(231,76,60,.5); }
        50%      { box-shadow: 0 0 0 10px rgba(231,76,60,0); }
    }
    .wa-timer {
        font-size: 0.95rem; font-weight: 700;
        color: #e74c3c; min-width: 42px; letter-spacing: 0.04em;
    }
    .wa-waveform { flex: 1; height: 32px; border-radius: 4px; overflow: hidden; }
    .wa-label    { font-size: 0.82rem; color: #57606a; white-space: nowrap; }
    .wa-preview-wrap {
        display: flex; align-items: center; gap: 8px;
        background: #f8faff; border: 1.5px solid #bfdbfe;
        border-radius: 28px; padding: 6px 12px 6px 8px; margin: 4px 0;
    }
    .wa-preview-wrap audio { flex: 1; height: 36px; min-width: 0; border-radius: 20px; accent-color: #2e86ab; }
    div[data-testid="stAudio"] { margin: 0 !important; padding: 0 !important; }
    div[data-testid="stAudio"] audio { border-radius: 20px !important; height: 36px !important; }

    /* ══════════════════════════════════════════
       STREAMLIT COMPONENT OVERRIDES
    ══════════════════════════════════════════ */
    /* Chat input box */
    div[data-testid="stChatInput"] textarea {
        border-radius: 14px !important;
        border: 1.5px solid #d1d5db !important;
        font-size: 0.95rem !important;
        padding: 10px 14px !important;
        transition: border-color 0.2s !important;
    }
    div[data-testid="stChatInput"] textarea:focus {
        border-color: #2e86ab !important;
        box-shadow: 0 0 0 3px rgba(46,134,171,0.12) !important;
    }
    /* Primary buttons */
    div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(135deg, #1a5276, #2e86ab) !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        box-shadow: 0 3px 10px rgba(46,134,171,0.3) !important;
        transition: transform 0.15s, box-shadow 0.15s !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 5px 16px rgba(46,134,171,0.4) !important;
    }
    /* Expanders */
    div[data-testid="stExpander"] {
        border: 1px solid #e5e7eb !important;
        border-radius: 10px !important;
        margin-bottom: 6px !important;
    }
    /* Spinner */
    .stSpinner > div { border-top-color: #2e86ab !important; }

    /* Match button height to input */
    div[data-testid="stSidebar"] div[data-testid="stForm"] button {
        height: 34px !important; min-height: 34px !important;
        padding: 0 6px !important; font-size: 0.78rem !important;
        margin: 0 !important; line-height: 1 !important;
    }
    /* Remove bottom margin on the block holding the form columns */
    div[data-testid="stSidebar"] div[data-testid="stForm"]
        div[data-testid="stVerticalBlockBorderWrapper"] {
        padding: 0 !important; margin: 0 !important;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# STATE SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
# st.session_state.chat_sessions: dict[session_id → SessionRecord]
#
#   SessionRecord = {
#       "id":         str            — UUID
#       "title":      str            — auto-generated or user-renamed
#       "created_at": str (ISO)      — creation timestamp
#       "updated_at": str (ISO)      — last message timestamp
#       "messages":   list[MsgDict]  — full message history
#       "msg_count":  int            — message count
#   }
#
# st.session_state.active_session_id: str — currently open session
# st.session_state.rename_id:         str | None — which session is being renamed
# ═══════════════════════════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now().isoformat()

def _fmt_time(iso: str) -> str:
    """Format ISO timestamp for sidebar display."""
    try:
        dt = datetime.fromisoformat(iso)
        now = datetime.now()
        delta = now - dt
        if delta.total_seconds() < 60:
            return "just now"
        if delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() // 60)}m ago"
        if delta.days == 0:
            return dt.strftime("%H:%M")
        if delta.days == 1:
            return "Yesterday"
        if delta.days < 7:
            return dt.strftime("%a")
        return dt.strftime("%d %b")
    except Exception:
        return ""

def _auto_title(messages: list) -> str:
    """Derive a short title from the first user message."""
    for msg in messages:
        if msg.get("role") == "user":
            text = msg["content"].strip()
            # Strip leading emoji
            import re
            text = re.sub(r"^[\U00010000-\U0010ffff\u2600-\u27BF\U0001F300-\U0001FAFF]\s*", "", text)
            # Trim to ~40 chars at word boundary
            if len(text) > 40:
                text = text[:38].rsplit(" ", 1)[0] + "…"
            return text or "New Chat"
    return "New Chat"

def _new_session_record() -> dict:
    sid = str(uuid.uuid4())
    return {
        "id":         sid,
        "title":      "New Chat",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "messages":   [],
        "msg_count":  0,
    }

def init_session_state():
    if "chat_sessions" not in st.session_state:
        first = _new_session_record()
        st.session_state.chat_sessions = {first["id"]: first}
        st.session_state.active_session_id = first["id"]
    if "active_session_id" not in st.session_state:
        first = _new_session_record()
        st.session_state.chat_sessions[first["id"]] = first
        st.session_state.active_session_id = first["id"]
    if "rename_id" not in st.session_state:
        st.session_state.rename_id = None
    if "preferred_lang" not in st.session_state:
        st.session_state.preferred_lang = "en"

init_session_state()

def _active() -> dict:
    """Return the active SessionRecord (always valid)."""
    sessions = st.session_state.chat_sessions
    sid = st.session_state.active_session_id
    if sid not in sessions:
        # Active session was deleted — fall back to most recent
        if sessions:
            sid = max(sessions, key=lambda k: sessions[k]["updated_at"])
        else:
            new = _new_session_record()
            sessions[new["id"]] = new
            sid = new["id"]
        st.session_state.active_session_id = sid
    return sessions[sid]

def _new_chat():
    """Create a new session and switch to it."""
    rec = _new_session_record()
    st.session_state.chat_sessions[rec["id"]] = rec
    st.session_state.active_session_id = rec["id"]
    st.session_state.rename_id = None
    # Tell backend to start fresh — fire-and-forget
    try:
        requests.post(
            f"{API_BASE_URL}/clear-memory",
            json={"session_id": rec["id"]},
            timeout=3,
        )
    except Exception:
        pass

def _switch_session(sid: str):
    st.session_state.active_session_id = sid
    st.session_state.rename_id = None

def _delete_session(sid: str):
    sessions = st.session_state.chat_sessions
    if sid in sessions:
        del sessions[sid]
    if st.session_state.active_session_id == sid:
        if sessions:
            st.session_state.active_session_id = max(sessions, key=lambda k: sessions[k]["updated_at"])
        else:
            new = _new_session_record()
            sessions[new["id"]] = new
            st.session_state.active_session_id = new["id"]
    st.session_state.rename_id = None

def _save_message(role: str, content: str, **meta):
    """Append a message to the active session."""
    rec = _active()
    rec["messages"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M"),
        **meta,
    })
    rec["msg_count"] = len(rec["messages"])
    rec["updated_at"] = _now_iso()
    # Auto-update title from first user message
    if rec["title"] == "New Chat":
        rec["title"] = _auto_title(rec["messages"])


# ─── API Communication ────────────────────────────────────────────────────────
def send_message(message: str, session_id: str) -> dict:
    """Send message to Sehat Saathi backend API."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={"message": message, "session_id": session_id},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {
            "response": (
                "Could not connect to the Sehat Saathi backend.\n\n"
                "Please ensure the FastAPI server is running:\n"
                "```\npython main.py\n```\n\n"
                "**For emergencies, call 108 immediately.**"
            ),
            "session_id": session_id,
            "detected_language": "en",
            "is_emergency": False,
            "error": "connection_error",
        }
    except requests.exceptions.Timeout:
        return {
            "response": (
                "The request timed out. Please try again.\n\n"
                "If you have an emergency, call **108** now."
            ),
            "session_id": session_id,
            "detected_language": "en",
            "is_emergency": False,
        }
    except Exception as e:
        return {
            "response": f"An error occurred: {str(e)}",
            "session_id": session_id,
            "detected_language": "en",
            "is_emergency": False,
        }


def _pdf_download_button(messages: list, session_id: str, label: str = "📄 Download Health Report (PDF)"):
    """Render a PDF download button for the given messages."""
    if not messages:
        st.button(label, disabled=True, use_container_width=True, help="Start a conversation first")
        return
    try:
        from app.report_generator import generate_pdf
        pdf_bytes = generate_pdf(messages, session_id=session_id)
        fname = f"sehat_saathi_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        st.download_button(
            label=label,
            data=pdf_bytes,
            file_name=fname,
            mime="application/pdf",
            use_container_width=True,
            help="Download a PDF summary of this conversation",
        )
    except Exception as err:
        st.caption(f"PDF unavailable: {err}")


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Recents + Controls
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # ── Branding ──────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="sidebar-brand">
        <h2>🏥 Sehat Saathi</h2>
        <p>AI Health Companion for Rural India</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='background:linear-gradient(135deg,#dc2626,#b91c1c);color:white;
                padding:9px 12px;border-radius:10px;text-align:center;
                font-weight:700;font-size:0.88rem;margin:8px 0;
                box-shadow:0 3px 10px rgba(220,38,38,0.3);letter-spacing:0.02em;'>
    🚨 EMERGENCY? Call <span style="font-size:1.1rem;">108</span>
    </div>
    """, unsafe_allow_html=True)

    # ── New Chat button ────────────────────────────────────────────────────────
    if st.button("✏️  New Chat", use_container_width=True, type="primary"):
        _new_chat()
        st.rerun()

    st.markdown("---")

    # ── Recents list ──────────────────────────────────────────────────────────
    sessions = st.session_state.chat_sessions
    active_sid = st.session_state.active_session_id

    # Sort: most recently updated first
    sorted_sessions = sorted(
        sessions.values(),
        key=lambda s: s["updated_at"],
        reverse=True,
    )

    # Group by Today / Yesterday / Older
    from datetime import date as _date, timedelta
    today     = _date.today()
    yesterday = today - timedelta(days=1)

    def _day_group(iso: str) -> str:
        try:
            d = datetime.fromisoformat(iso).date()
            if d == today:     return "Today"
            if d == yesterday: return "Yesterday"
            return "Older"
        except Exception:
            return "Older"

    groups: dict[str, list] = {"Today": [], "Yesterday": [], "Older": []}
    for s in sorted_sessions:
        groups[_day_group(s["updated_at"])].append(s)

    for group_label, group_sessions in groups.items():
        if not group_sessions:
            continue
        st.markdown(f'<div class="recents-header">{group_label}</div>', unsafe_allow_html=True)

        for rec in group_sessions:
            sid      = rec["id"]
            is_active = sid == active_sid
            title    = rec["title"]
            time_str = _fmt_time(rec["updated_at"])
            n_msgs   = rec["msg_count"]
            preview  = ""
            # Last assistant message as preview
            for m in reversed(rec["messages"]):
                if m["role"] == "assistant":
                    preview = m["content"][:55].replace("\n", " ") + "…"
                    break

            # ── Rename mode — single HTML row ─────────────────────────────
            if st.session_state.rename_id == sid:
                with st.form(key=f"rename_form_{sid}", clear_on_submit=False):
                    # All three widgets in ONE columns row → one visual line
                    ci, cs, cc = st.columns([5, 2, 2])
                    with ci:
                        new_title = st.text_input(
                            "t", value=title,
                            key=f"rename_input_{sid}",
                            label_visibility="collapsed",
                        )
                    with cs:
                        save = st.form_submit_button(
                            "Save", use_container_width=True
                        )
                    with cc:
                        cancel = st.form_submit_button(
                            "Cancel", use_container_width=True
                        )
                    if save:
                        sessions[sid]["title"] = new_title.strip() or title
                        st.session_state.rename_id = None
                        st.rerun()
                    if cancel:
                        st.session_state.rename_id = None
                        st.rerun()
                continue

            # ── Normal row ────────────────────────────────────────────────
            border = "2px solid #2e86ab" if is_active else "1px solid #e5e7eb"
            bg     = "#e8f4fd" if is_active else "#ffffff"
            st.markdown(
                f"""<div class="chat-item {'active' if is_active else ''}"
                     style="background:{bg};border:{border};">
                  <div style="flex:1;min-width:0;">
                    <div class="chat-item-title">{title}</div>
                    <div class="chat-item-sub">{preview if preview else f'{n_msgs} message{"s" if n_msgs != 1 else ""}'}</div>
                  </div>
                  <div class="chat-item-time">{time_str}</div>
                </div>""",
                unsafe_allow_html=True,
            )

            # Action buttons: Switch | Rename | Delete
            btn_cols = st.columns([3, 2, 2])
            with btn_cols[0]:
                if st.button(
                    "Open" if not is_active else "Active",
                    key=f"open_{sid}",
                    use_container_width=True,
                    disabled=is_active,
                ):
                    _switch_session(sid)
                    st.rerun()
            with btn_cols[1]:
                if st.button("Rename", key=f"rename_{sid}", use_container_width=True):
                    st.session_state.rename_id = sid
                    st.rerun()
            with btn_cols[2]:
                if st.button("Delete", key=f"del_{sid}", use_container_width=True):
                    _delete_session(sid)
                    st.rerun()

        st.markdown("")

    st.markdown("---")

    # ── Health Tip of the Day ─────────────────────────────────────────────────
    tip = _get_daily_tip()
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,#f0fdf4,#dcfce7);
                border:1px solid #86efac;border-left:4px solid #16a34a;
                border-radius:10px;padding:10px 12px;margin:4px 0 10px 0;
                font-size:0.82rem;color:#14532d;line-height:1.5;">
        <div style="font-size:0.68rem;font-weight:700;letter-spacing:0.08em;
                    text-transform:uppercase;color:#16a34a;margin-bottom:4px;">
            🌿 Health Tip of the Day
        </div>
        {tip}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Download Report for active session ───────────────────────────────────
    active_rec = _active()
    _pdf_download_button(active_rec["messages"], active_rec["id"])

    st.markdown("---")

    # ── Quick example queries ─────────────────────────────────────────────────
    _ALL_EXAMPLES = [
        ("English",     "ex",  EXAMPLE_QUERIES[:4]),
        ("हिंदी",        "hi",  HINDI_EXAMPLES[:3]),
        ("मराठी",        "mr",  MARATHI_EXAMPLES),
        ("தமிழ்",        "ta",  TAMIL_EXAMPLES),
        ("తెలుగు",       "te",  TELUGU_EXAMPLES),
        ("বাংলা",        "bn",  BENGALI_EXAMPLES),
        ("ગુજરાતી",      "gu",  GUJARATI_EXAMPLES),
        ("ਪੰਜਾਬੀ",       "pa",  PUNJABI_EXAMPLES),
        ("മലയാളം",      "ml",  MALAYALAM_EXAMPLES),
        ("ಕನ್ನಡ",        "kn",  KANNADA_EXAMPLES),
    ]
    with st.expander("💬 Try Example Queries", expanded=False):
        for lang_label, prefix, examples in _ALL_EXAMPLES:
            st.markdown(f"**{lang_label}**")
            for i, example in enumerate(examples):
                if st.button(example, use_container_width=True, key=f"{prefix}_{i}_{hash(example)}"):
                    st.session_state["pending_message"] = example.split(" ", 1)[1]
                    st.rerun()

    # ── About + Helplines ─────────────────────────────────────────────────────
    with st.expander("📞 Important Helplines"):
        st.markdown("""
| Service | Number |
|---------|--------|
| 🚑 Ambulance | **108** |
| 🚓 Police | **100** |
| 🏥 Health Info | **104** |
| 👶 Childline | **1098** |
| 👩 Women | **1091** |
| 🧠 Mental Health | **9152987821** |
| ☠️ Poison Control | **1800-116-117** |
        """)

    with st.expander("🌍 Supported Languages"):
        st.markdown("""
**10 languages supported:**
English · हिंदी · मराठी · தமிழ் · తెలుగు · বাংলা · ગુજરાતી · ਪੰਜਾਬੀ · മലയാളം · ಕನ್ನಡ

Type in any script — detection is automatic!
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT AREA
# ═══════════════════════════════════════════════════════════════════════════════

# Demo mode banner
if IS_MOCK_MODE:
    st.markdown("""
    <div style="background:#7c5cd8;color:#fff;text-align:center;padding:7px;border-radius:8px;
                font-size:0.82rem;font-weight:600;margin-bottom:8px;">
        🧪 DEMO MODE — Running without API keys · All tools active · Rule-based engine
    </div>
    """, unsafe_allow_html=True)

# ── Chat header: title + inline Download button ────────────────────────────
active_rec = _active()
_engine = "Ollama (Granite)" if os.getenv("OLLAMA_MODE","false").lower()=="true" else ("Demo Mode" if IS_MOCK_MODE else "IBM watsonx.ai")

hdr_left, hdr_right = st.columns([7, 3])
with hdr_left:
    st.markdown(f"""
    <div class="main-header">
        <h1>🏥 Sehat Saathi</h1>
        <p class="tagline">AI Health Companion for Rural India &nbsp;·&nbsp; Powered by {_engine}</p>
        <p class="stats">
            {active_rec['title']} &nbsp;·&nbsp;
            {active_rec['msg_count']} message{'s' if active_rec['msg_count'] != 1 else ''}
        </p>
        <div class="lang-pills">
            <span class="lang-pill">English</span>
            <span class="lang-pill">हिंदी</span>
            <span class="lang-pill">தமிழ்</span>
            <span class="lang-pill">తెలుగు</span>
            <span class="lang-pill">বাংলা</span>
            <span class="lang-pill">मराठी</span>
            <span class="lang-pill">ગુજરાતી</span>
            <span class="lang-pill">ಕನ್ನಡ</span>
            <span class="lang-pill">ਪੰਜਾਬੀ</span>
            <span class="lang-pill">മലയാളം</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
with hdr_right:
    st.markdown("<div style='padding-top:20px;'>", unsafe_allow_html=True)
    _pdf_download_button(active_rec["messages"], active_rec["id"], label="📄 Download Report")
    if st.button("✏️ New Chat", use_container_width=True, key="new_chat_header"):
        _new_chat()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# Disclaimer
st.markdown("""
<div class="disclaimer">
⚠️ <strong>Awareness only</strong> — not a diagnostic tool.
For emergencies call <strong>108</strong>. Always consult a healthcare professional.
</div>
""", unsafe_allow_html=True)

st.markdown("")

# ── Chat messages ──────────────────────────────────────────────────────────
chat_container = st.container()

with chat_container:
    messages = active_rec["messages"]
    if not messages:
        st.markdown("""
        <div class="welcome-wrap">
            <div class="welcome-icon">🏥</div>
            <div class="welcome-title">Namaste! I am Sehat Saathi</div>
            <div class="welcome-sub">Your free AI health companion — ask in any Indian language</div>
            <div class="feature-grid">
                <div class="feature-card">
                    <div class="fc-icon">🤒</div>
                    <div class="fc-title">Symptom Check</div>
                    <div>Describe how you feel</div>
                </div>
                <div class="feature-card">
                    <div class="fc-icon">💉</div>
                    <div class="fc-title">Vaccination</div>
                    <div>Child &amp; pregnancy schedule</div>
                </div>
                <div class="feature-card">
                    <div class="fc-icon">🏥</div>
                    <div class="fc-title">Find Hospital</div>
                    <div>Nearest PHC or clinic</div>
                </div>
                <div class="feature-card">
                    <div class="fc-icon">🌍</div>
                    <div class="fc-title">10 Languages</div>
                    <div>Type in any Indian script</div>
                </div>
            </div>
            <div style="font-size:0.82rem;color:#57606a;">
                Try: <em>"मुझे बुखार है"</em> &nbsp;·&nbsp;
                <em>"எனக்கு காய்ச்சல்"</em> &nbsp;·&nbsp;
                <em>"I have fever"</em>
            </div>
            <div style="font-size:0.78rem;margin-top:10px;color:#a0a0a0;">
                👈 Use example queries from the sidebar to get started
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Quick Symptom Buttons (shown only on empty chat) ──────────────
        st.markdown("<div style='margin-top:8px;'>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;font-size:0.82rem;color:#6b7280;margin-bottom:6px;'>👇 Quick start — tap a topic:</p>", unsafe_allow_html=True)
        qs_cols = st.columns(4)
        for qi, (icon, label, query) in enumerate(QUICK_SYMPTOMS):
            with qs_cols[qi % 4]:
                if st.button(
                    f"{icon} {label}",
                    key=f"qs_{qi}",
                    use_container_width=True,
                    help=query,
                ):
                    st.session_state["pending_message"] = query
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    else:
        is_last_assistant = False
        last_category = "general"
        for idx, msg in enumerate(messages):
            role          = msg["role"]
            content       = msg["content"]
            is_emergency  = msg.get("is_emergency", False)
            detected_lang = msg.get("detected_language", "en")
            via_voice     = msg.get("via_voice", False)
            category      = msg.get("category", "general")

            if role == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(content)
                    if via_voice:
                        vc1, vc2 = st.columns([6, 1])
                        with vc1:
                            st.caption("🎙️ Voice message")
                        with vc2:
                            if st.button(
                                "🗑️",
                                key=f"del_vmsg_{idx}",
                                help="Delete this voice message and its reply",
                            ):
                                to_remove = {idx}
                                if idx + 1 < len(messages) and messages[idx + 1]["role"] == "assistant":
                                    to_remove.add(idx + 1)
                                active_rec["messages"] = [
                                    m for i, m in enumerate(messages) if i not in to_remove
                                ]
                                active_rec["msg_count"] = len(active_rec["messages"])
                                st.rerun()
            else:
                with st.chat_message("assistant", avatar="🏥"):
                    if is_emergency:
                        st.error("🚨 EMERGENCY ALERT — CALL 108 NOW")
                    if detected_lang != "en":
                        lang_name = LANG_CODE_TO_NAME.get(detected_lang, detected_lang.upper())
                        st.caption(f"🌐 Detected: {lang_name}")
                    st.markdown(content)
                    st.caption(f"🕒 {msg.get('timestamp', '')}")
                    # Track last assistant message info for follow-ups
                    is_last_assistant = (idx == len(messages) - 1)
                    last_category = category

        # ── Follow-up Suggestions (after last assistant reply only) ──────
        if is_last_assistant and messages:
            followups = _get_followups(last_category)
            st.markdown(
                "<div style='margin:8px 0 4px 0;padding-left:48px;'>"
                "<span style='font-size:0.75rem;color:#9ca3af;font-weight:600;"
                "text-transform:uppercase;letter-spacing:0.06em;'>💡 You might also ask:</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            fu_cols = st.columns(len(followups))
            for fi, fu in enumerate(followups):
                with fu_cols[fi]:
                    if st.button(fu, key=f"fu_{idx}_{fi}", use_container_width=True):
                        st.session_state["pending_message"] = fu.split(" ", 1)[1]
                        st.rerun()


# ─── Handle pending message from example buttons ──────────────────────────
if "pending_message" in st.session_state:
    pending = st.session_state.pop("pending_message")
    st.session_state["auto_send"] = pending


# ─── WhatsApp-style Voice Input ───────────────────────────────────────────
def _voice_input_widget():
    """
    WhatsApp-style voice recorder:
      1. Mic button → records with live timer + animated waveform
      2. Stop → shows inline audio preview with playback
      3. Delete button → discard recording
      4. Send button → transcribe via Groq Whisper → inject into chat
    """
    groq_key = os.getenv("GROQ_API_KEY", "")
    has_groq  = bool(groq_key and groq_key != "your_groq_api_key_here")

    # ── State keys ────────────────────────────────────────────────────────
    if "va_audio_bytes"  not in st.session_state:
        st.session_state.va_audio_bytes  = None
    if "va_transcribing" not in st.session_state:
        st.session_state.va_transcribing = False
    # Hashes of recordings the user explicitly deleted — ignore if audio_input replays them
    if "va_deleted_hashes" not in st.session_state:
        st.session_state.va_deleted_hashes = set()

    # ── Recorder pill: mic button + live timer + animated bars ────────────
    st.markdown("""
    <div class="wa-voice-wrap" id="wa-wrap">
      <button class="wa-mic-btn idle" id="wa-mic-btn" onclick="waToggle()" title="Hold to record">
        🎙️
      </button>
      <span class="wa-timer" id="wa-timer" style="display:none">0:00</span>
      <canvas class="wa-waveform" id="wa-canvas" style="display:none"></canvas>
      <span class="wa-label" id="wa-label">Tap mic to record</span>
    </div>

    <script>
    (function(){
      // Guard: only init once per page load
      if (window._waInit) return;
      window._waInit = true;

      let mediaRec, audioCtx, analyser, animId, timerInt, startTs;
      let chunks = [];

      const btn    = () => document.getElementById('wa-mic-btn');
      const timer  = () => document.getElementById('wa-timer');
      const canvas = () => document.getElementById('wa-canvas');
      const label  = () => document.getElementById('wa-label');
      const wrap   = () => document.getElementById('wa-wrap');

      function fmtTime(ms) {
        const s = Math.floor(ms/1000);
        return Math.floor(s/60) + ':' + String(s%60).padStart(2,'0');
      }

      function drawWave() {
        if (!analyser) return;
        const c = canvas(), ctx = c.getContext('2d');
        const buf = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteTimeDomainData(buf);
        ctx.clearRect(0,0,c.width,c.height);
        ctx.strokeStyle = '#e74c3c';
        ctx.lineWidth = 2;
        ctx.beginPath();
        const slice = c.width / buf.length;
        let x = 0;
        buf.forEach((v,i) => {
          const y = (v/128)*c.height/2;
          i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
          x += slice;
        });
        ctx.stroke();
        animId = requestAnimationFrame(drawWave);
      }

      async function startRec() {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({audio:true});
          audioCtx  = new AudioContext();
          analyser  = audioCtx.createAnalyser();
          analyser.fftSize = 256;
          audioCtx.createMediaStreamSource(stream).connect(analyser);

          mediaRec = new MediaRecorder(stream);
          chunks   = [];
          mediaRec.ondataavailable = e => chunks.push(e.data);
          mediaRec.onstop = () => {
            const blob = new Blob(chunks, {type:'audio/webm'});
            const url  = URL.createObjectURL(blob);
            // Store blob URL in sessionStorage for Streamlit to read via hidden input
            sessionStorage.setItem('wa_blob_url', url);
            // Trigger hidden file-input bridge
            fetch(url).then(r=>r.arrayBuffer()).then(buf=>{
              const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
              const inp = document.getElementById('wa_b64_sink');
              if(inp){ inp.value = b64; inp.dispatchEvent(new Event('input',{bubbles:true})); }
            });
            // Show native audio preview
            const prev = document.getElementById('wa-native-preview');
            if(prev){ prev.src = url; prev.style.display='block'; }
          };
          mediaRec.start();

          // UI → recording state
          btn().className = 'wa-mic-btn rec';
          btn().innerHTML = '⏹️';
          btn().title     = 'Tap to stop';
          timer().style.display  = 'inline';
          canvas().style.display = 'block';
          label().style.display  = 'none';
          wrap().style.background = '#fff0f0';
          wrap().style.borderColor = '#e74c3c';
          startTs = Date.now();
          timerInt = setInterval(() => { timer().textContent = fmtTime(Date.now()-startTs); }, 500);
          drawWave();
        } catch(err) {
          label().textContent = '⚠️ Mic access denied — check browser permissions';
        }
      }

      function stopRec() {
        if(mediaRec && mediaRec.state !== 'inactive') mediaRec.stop();
        clearInterval(timerInt);
        cancelAnimationFrame(animId);
        if(audioCtx) audioCtx.close();
        // UI → idle
        btn().className = 'wa-mic-btn idle';
        btn().innerHTML = '🎙️';
        btn().title     = 'Tap to record';
        timer().style.display  = 'none';
        canvas().style.display = 'none';
        label().style.display  = 'inline';
        label().textContent    = 'Recording saved — preview below';
        wrap().style.background = '#f0f9f0';
        wrap().style.borderColor = '#27ae60';
      }

      window.waToggle = function() {
        if(!mediaRec || mediaRec.state==='inactive') startRec();
        else stopRec();
      };
    })();
    </script>
    """, unsafe_allow_html=True)

    # ── Native Streamlit recorder (captures the actual bytes) ─────────────
    raw_audio = st.audio_input(
        "🎙️ Or use this recorder (works in all browsers)",
        key="voice_recorder",
        label_visibility="collapsed",
    )

    # ── Preview + action row ───────────────────────────────────────────────
    if raw_audio is not None:
        audio_bytes = raw_audio.read()
        audio_hash  = hash(audio_bytes)
        # Ignore this recording if the user already deleted it this session
        already_deleted = audio_hash in st.session_state.va_deleted_hashes
        # Accept new bytes only when it's a genuinely new recording
        is_new = st.session_state.get("last_audio_hash") != audio_hash
        if is_new and not already_deleted:
            st.session_state.last_audio_hash  = audio_hash
            st.session_state.va_audio_bytes   = audio_bytes
            st.session_state.va_transcribing  = False

    if st.session_state.va_audio_bytes:
        ab = st.session_state.va_audio_bytes

        # ── Preview pill ──────────────────────────────────────────────────
        st.markdown('<div class="wa-preview-wrap">', unsafe_allow_html=True)
        st.audio(ab, format="audio/wav")
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Duration hint ─────────────────────────────────────────────────
        kb = len(ab) // 1024
        st.caption(f"🎵 Recording ready · {kb} KB · review above before sending")

        # ── Action row: Send | Delete ─────────────────────────────────────
        col_send, col_del, col_spacer = st.columns([3, 2, 5])

        with col_send:
            send_label = "⏳ Transcribing…" if st.session_state.va_transcribing else "📨 Send Voice Note"
            if st.button(
                send_label,
                key="va_send",
                use_container_width=True,
                disabled=st.session_state.va_transcribing or not has_groq,
                type="primary",
            ):
                if not has_groq:
                    st.error("Set GROQ_API_KEY in .env to enable voice transcription.")
                else:
                    st.session_state.va_transcribing = True
                    try:
                        from groq import Groq
                        import tempfile
                        client = Groq(api_key=groq_key)
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                            tmp.write(ab)
                            tmp_path = tmp.name
                        try:
                            with st.spinner("Transcribing your voice note…"):
                                with open(tmp_path, "rb") as f:
                                    resp = client.audio.transcriptions.create(
                                        model="whisper-large-v3-turbo",
                                        file=("audio.wav", f),
                                        response_format="text",
                                    )
                                transcribed = str(resp).strip()
                        finally:
                            os.unlink(tmp_path)

                        if transcribed:
                            # Clear the recording and inject text into chat
                            sent_hash = hash(ab)
                            st.session_state.va_deleted_hashes.add(sent_hash)
                            st.session_state.va_audio_bytes  = None
                            st.session_state.va_transcribing = False
                            st.session_state.last_audio_hash = None
                            st.session_state["auto_send"]      = transcribed
                            st.session_state["auto_send_voice"] = True   # tag it as voice
                            st.rerun()
                        else:
                            st.session_state.va_transcribing = False
                            st.warning("Could not understand the audio. Please try again.")

                    except ImportError:
                        st.session_state.va_transcribing = False
                        st.info("Run `pip install groq` to enable transcription.")
                    except Exception as e:
                        st.session_state.va_transcribing = False
                        st.error(f"Transcription failed: {e}")

        with col_del:
            if st.button("🗑️ Delete", key="va_delete", use_container_width=True):
                # Remember this hash so audio_input replaying it won't restore the preview
                current_hash = hash(st.session_state.va_audio_bytes)
                st.session_state.va_deleted_hashes.add(current_hash)
                st.session_state.va_audio_bytes  = None
                st.session_state.va_transcribing = False
                st.session_state.last_audio_hash = None
                st.rerun()

        if not has_groq:
            st.warning(
                "**GROQ_API_KEY not set** — voice transcription disabled.\n\n"
                "Get a free key at [console.groq.com](https://console.groq.com) "
                "and add `GROQ_API_KEY=your_key` to `.env`."
            )

    elif raw_audio is None and not st.session_state.va_audio_bytes:
        st.caption("🎙️ Record a voice note above · Preview plays before sending · Delete to discard")


_voice_input_widget()


# ─── Chat Input ───────────────────────────────────────────────────────────
prompt = st.chat_input(
    "Type your health question here... (any language)",
    key="chat_input",
)

# Handle auto-send from example buttons and voice input
is_voice_prompt = False
if "auto_send" in st.session_state:
    prompt = st.session_state.pop("auto_send")
    is_voice_prompt = st.session_state.pop("auto_send_voice", False)

if prompt:
    # Save user message — tag with via_voice so the delete button appears
    _save_message("user", prompt, via_voice=is_voice_prompt)

    # Display user message immediately
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Emergency keyword soft-warning
    if any(kw in prompt.lower() for kw in EMERGENCY_KEYWORDS_UI):
        st.warning("This looks like it could be an emergency. **Call 108 NOW** if needed.")

    # Get response from backend
    with st.chat_message("assistant", avatar="🏥"):
        with st.spinner("🏥 Sehat Saathi is thinking..."):
            api_response = send_message(prompt, active_rec["id"])

        response_text = api_response.get("response", "I'm unable to respond right now.")
        is_emergency  = api_response.get("is_emergency", False)
        detected_lang = api_response.get("detected_language", "en")
        category      = api_response.get("category", "general")

        if is_emergency:
            st.error("🚨 EMERGENCY ALERT — CALL 108 NOW")

        if detected_lang != "en":
            lang_name = LANG_CODE_TO_NAME.get(detected_lang, detected_lang.upper())
            st.caption(f"🌐 Responding in: {lang_name}")

        st.markdown(response_text)
        st.caption(f"🕒 {datetime.now().strftime('%H:%M')}")

    # Save assistant message (include category for follow-up suggestions)
    _save_message(
        "assistant",
        response_text,
        is_emergency=is_emergency,
        detected_language=detected_lang,
        category=category,
    )

    st.rerun()


# ─── Footer ───────────────────────────────────────────────────────────────
_footer_engine = "Ollama (Granite)" if os.getenv("OLLAMA_MODE","false").lower()=="true" else ("Demo Mode" if IS_MOCK_MODE else "IBM watsonx.ai")
st.markdown("---")
st.markdown(f"""
<div style="text-align:center;color:#9ca3af;font-size:0.76rem;padding:8px 4px 4px;">
    <span style="font-weight:600;color:#6b7280;">🏥 Sehat Saathi v1.0</span>
    &nbsp;·&nbsp; {_footer_engine} + LangChain
    &nbsp;·&nbsp; Emergency: <strong style="color:#dc2626;">108</strong>
    &nbsp;·&nbsp; Helpline: <strong style="color:#2e86ab;">104</strong><br>
    <span style="font-size:0.72rem;">
        Not a medical diagnostic tool. Always consult a qualified healthcare professional.
    </span>
</div>
""", unsafe_allow_html=True)
