"""
Sehat Saathi - Streamlit Frontend
===================================
A conversational chat interface for the Sehat Saathi healthcare assistant.
Connects to the FastAPI backend (or directly to the agent if running locally).
"""
import streamlit as st
import requests
import uuid
import json
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
    layout="centered",
    initial_sidebar_state="expanded",
)

# ─── Constants ────────────────────────────────────────────────────────────────
API_BASE_URL = "http://localhost:8000"

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

EMERGENCY_KEYWORDS_UI = ["chest pain", "can't breathe", "unconscious", "seizure", "bleeding heavily", "suicidal"]

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
    "💊 ORS kya hai aur kab dena chahiye?",
    "😷 Mujhe malaria ke lakshan hain",
]

KANNADA_EXAMPLES = [
    "🤒 Nanna magu 6 varaddu. Yaava lasike koḍabeku?",
    "🌡️ Nanage 2 dinagaḷinda jwara ide mattu tala novu ide",
    "🏥 Hattira aspatre ellidhe? Pincode: 560001",
    "🤰 Naanu 3 tingaḷu garbhini. Yaava checkup beku?",
    "💊 ORS endre enu? Yavaga kodabeku?",
    "😷 Nanage maleria lakshana ide",
]

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main header */
    .main-header {
        background: linear-gradient(135deg, #1a5276 0%, #2e86ab 100%);
        padding: 20px 24px;
        border-radius: 12px;
        color: white;
        margin-bottom: 20px;
        text-align: center;
    }
    .main-header h1 { 
        font-size: 2rem; 
        margin: 0; 
        color: white !important;
        font-weight: 700;
    }
    .main-header p { 
        font-size: 0.95rem; 
        margin: 6px 0 0; 
        opacity: 0.9; 
        color: white !important;
    }

    /* Chat messages */
    .user-msg {
        background: #e8f4fd;
        border-left: 4px solid #2e86ab;
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin: 8px 0;
        font-size: 0.95rem;
    }
    .assistant-msg {
        background: #f0f9f0;
        border-left: 4px solid #27ae60;
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin: 8px 0;
        font-size: 0.95rem;
        line-height: 1.6;
    }
    .emergency-msg {
        background: #fdf2f2;
        border-left: 4px solid #e74c3c;
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin: 8px 0;
        font-size: 0.95rem;
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0%, 100% { border-left-color: #e74c3c; }
        50% { border-left-color: #c0392b; }
    }

    /* Language badge */
    .lang-badge {
        display: inline-block;
        background: #e8f4fd;
        color: #2e86ab;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 4px;
    }

    /* Emergency banner */
    .emergency-banner {
        background: #e74c3c;
        color: white;
        padding: 12px;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
        font-size: 1.1rem;
        margin-bottom: 16px;
    }

    /* Disclaimer footer */
    .disclaimer {
        background: #fff9e6;
        border: 1px solid #f0c040;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 0.8rem;
        color: #856404;
        margin-top: 12px;
    }

    /* Sidebar */
    .sidebar-section {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ─── Session State Init ───────────────────────────────────────────────────────
def init_session_state():
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "preferred_lang" not in st.session_state:
        st.session_state.preferred_lang = "en"
    if "total_queries" not in st.session_state:
        st.session_state.total_queries = 0


init_session_state()


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
                "⚠️ Could not connect to the Sehat Saathi backend.\n\n"
                "Please ensure the FastAPI server is running:\n"
                "```\nuvicorn app.api.routes:app --reload --port 8000\n```\n\n"
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
                "⏱️ The request timed out. Please try again.\n\n"
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


def clear_session():
    """Clear session memory and reset chat."""
    try:
        requests.post(
            f"{API_BASE_URL}/clear-memory",
            json={"session_id": st.session_state.session_id},
            timeout=5,
        )
    except Exception:
        pass
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.total_queries = 0


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏥 Sehat Saathi")
    st.markdown("*Your AI Health Companion*")
    st.markdown("---")

    # Emergency banner
    st.markdown("""
    <div style='background:#e74c3c;color:white;padding:10px;border-radius:8px;text-align:center;font-weight:bold;'>
    🚨 EMERGENCY? Call 108
    </div>
    """, unsafe_allow_html=True)
    st.markdown("")

    # Session info
    st.markdown("### 📋 Session")
    st.code(st.session_state.session_id[:16] + "...", language=None)
    st.caption(f"Messages: {len(st.session_state.messages)}")

    if st.button("🔄 New Conversation", use_container_width=True):
        clear_session()
        st.rerun()

    st.markdown("---")

    # Quick example queries
    st.markdown("### 💬 English")
    for example in EXAMPLE_QUERIES[:4]:
        if st.button(example, use_container_width=True, key=f"ex_{example[:20]}"):
            st.session_state["pending_message"] = example.split(" ", 1)[1]
            st.rerun()

    st.markdown("---")
    st.markdown("### 🇮🇳 हिंदी (Hindi)")
    for example in HINDI_EXAMPLES:
        if st.button(example, use_container_width=True, key=f"hi_{example[:20]}"):
            st.session_state["pending_message"] = example.split(" ", 1)[1]
            st.rerun()

    st.markdown("---")
    st.markdown("### 🇮🇳 ಕನ್ನಡ (Kannada)")
    for example in KANNADA_EXAMPLES:
        if st.button(example, use_container_width=True, key=f"kn_{example[:20]}"):
            st.session_state["pending_message"] = example.split(" ", 1)[1]
            st.rerun()

    st.markdown("---")

    # About
    with st.expander("ℹ️ About Sehat Saathi"):
        st.markdown("""
        **Sehat Saathi** ("Health Companion") is an AI-powered healthcare awareness 
        tool for rural and underserved communities.

        **Powered by:**
        - IBM watsonx.ai (Granite)
        - LangChain Agents
        - WHO/MoHFW Knowledge Base
        - Watson Language Translator

        ⚠️ *Not a diagnostic tool. Always consult a doctor.*
        """)

    with st.expander("📞 Important Helplines"):
        st.markdown("""
        | Service | Number |
        |---------|--------|
        | 🚑 Ambulance | **108** |
        | 🚓 Police | **100** |
        | 🏥 Health Info | **104** |
        | 👶 Childline | **1098** |
        | 👩 Women | **1091** |
        | 🧠 Mental Health | **iCall: 9152987821** |
        | ☠️ Poison Control | **1800-116-117** |
        """)

    with st.expander("🌍 Supported Languages"):
        for lang_name in LANGUAGE_OPTIONS:
            st.markdown(f"• {lang_name}")


# ─── Main Header ──────────────────────────────────────────────────────────────
if IS_MOCK_MODE:
    st.markdown("""
    <div style="background:#7c5cd8;color:#fff;text-align:center;padding:8px;border-radius:8px;
                font-size:0.85rem;font-weight:600;margin-bottom:10px;">
        🧪 DEMO MODE — Running without API keys &nbsp;|&nbsp;
        All tools active &nbsp;·&nbsp; LLM replaced with rule-based engine
    </div>
    """, unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🏥 Sehat Saathi</h1>
    <p>Your AI Health Companion — Powered by IBM watsonx.ai</p>
    <p style="font-size:0.8rem; opacity:0.8;">Multilingual • Rural Healthcare • Awareness Only</p>
</div>
""", unsafe_allow_html=True)

# Disclaimer
st.markdown("""
<div class="disclaimer">
⚠️ <strong>Important:</strong> Sehat Saathi provides health <em>awareness</em> information only — 
not medical diagnosis or treatment. For medical emergencies, call <strong>108</strong> immediately. 
Always consult a qualified healthcare professional for medical advice.
</div>
""", unsafe_allow_html=True)

st.markdown("")

# ─── Chat History ─────────────────────────────────────────────────────────────
chat_container = st.container()

with chat_container:
    if not st.session_state.messages:
        # Welcome message
        with st.chat_message("assistant", avatar="🏥"):
            st.markdown("""
**Namaste! 🙏 Welcome to Sehat Saathi.**

I'm your AI health awareness companion. I can help you with:

- 🤒 **Symptom guidance** — understand when to see a doctor
- 💉 **Vaccination schedules** — for children and pregnant women  
- 🏥 **Find healthcare facilities** — nearest PHCs and hospitals
- 📚 **Health information** — based on WHO and MoHFW guidelines

**You can write to me in Hindi, Tamil, Telugu, Bengali, or English** — I'll reply in your language!

👉 Start by typing your health question below, or try one of the examples in the sidebar.

---
*For emergencies, call **108** immediately.*
            """)

    # Display message history
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        is_emergency = msg.get("is_emergency", False)
        detected_lang = msg.get("detected_language", "en")

        if role == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(content)
        else:
            with st.chat_message("assistant", avatar="🏥"):
                if is_emergency:
                    st.error("🚨 EMERGENCY ALERT")
                if detected_lang != "en":
                    lang_name = {v: k for k, v in LANGUAGE_OPTIONS.items()}.get(
                        detected_lang, detected_lang.upper()
                    )
                    st.caption(f"🌐 Detected: {lang_name}")
                st.markdown(content)
                st.caption(f"🕒 {msg.get('timestamp', '')}")


# ─── Handle pending message from sidebar buttons ──────────────────────────────
if "pending_message" in st.session_state:
    pending = st.session_state.pop("pending_message")
    st.session_state["auto_send"] = pending


# ─── Voice Input (Whisper STT — no API key needed) ───────────────────────────
with st.expander("🎙️ Voice Input — Click to speak your question", expanded=False):
    st.caption("Record your voice → it gets transcribed → auto-sent as your message")

    audio = st.audio_input("🎙️ Click the mic, speak, then click stop")

    if audio is not None:
        # Try transcribe with faster-whisper (offline, no API key)
        try:
            import io
            import tempfile
            import os
            from faster_whisper import WhisperModel

            # Save audio bytes to a temp wav file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio.read())
                tmp_path = tmp.name

            with st.spinner("🔄 Transcribing your voice..."):
                model = WhisperModel("tiny", device="cpu", compute_type="int8")
                segments, info = model.transcribe(tmp_path, beam_size=1)
                transcribed = " ".join(seg.text for seg in segments).strip()
            os.unlink(tmp_path)

            if transcribed:
                st.success(f"✅ Heard: **{transcribed}**")
                st.session_state["auto_send"] = transcribed
                st.rerun()
            else:
                st.warning("Could not hear clearly. Please try again.")

        except ImportError:
            # faster-whisper not installed — show install tip
            st.info(
                "📦 To enable voice transcription, run this command in PowerShell:\n\n"
                "```\nC:\\Users\\janani\\AppData\\Local\\Programs\\Python\\Python313\\python.exe "
                "-m pip install faster-whisper\n```\n\n"
                "Then refresh this page. *(Free, works offline, no API key needed)*"
            )
        except Exception as e:
            st.error(f"Voice error: {e}")


# ─── Chat Input ───────────────────────────────────────────────────────────────
prompt = st.chat_input(
    "Type or paste your health question here... (English, Hindi, ಕನ್ನಡ, etc.)",
    key="chat_input",
)

# Handle auto-send from example buttons
if "auto_send" in st.session_state:
    prompt = st.session_state.pop("auto_send")

if prompt:
    # Add user message to history
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now().strftime("%H:%M"),
    })
    st.session_state.total_queries += 1

    # Display user message
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Check for emergency keywords in UI (soft warning before API call)
    has_emergency_keyword = any(kw in prompt.lower() for kw in EMERGENCY_KEYWORDS_UI)
    if has_emergency_keyword:
        st.warning("⚠️ This looks like it could be an emergency. **Call 108 NOW** if needed.")

    # Get response from API
    with st.chat_message("assistant", avatar="🏥"):
        with st.spinner("Sehat Saathi is thinking..."):
            api_response = send_message(prompt, st.session_state.session_id)

        response_text = api_response.get("response", "I'm unable to respond right now.")
        is_emergency = api_response.get("is_emergency", False)
        detected_lang = api_response.get("detected_language", "en")

        # Emergency UI
        if is_emergency:
            st.error("🚨 EMERGENCY ALERT — CALL 108 NOW")

        # Language indicator
        if detected_lang != "en":
            lang_name = {v: k for k, v in LANGUAGE_OPTIONS.items()}.get(
                detected_lang, detected_lang.upper()
            )
            st.caption(f"🌐 Responding in: {lang_name}")

        st.markdown(response_text)
        timestamp = datetime.now().strftime("%H:%M")
        st.caption(f"🕒 {timestamp}")

    # Save to history
    st.session_state.messages.append({
        "role": "assistant",
        "content": response_text,
        "is_emergency": is_emergency,
        "detected_language": detected_lang,
        "timestamp": datetime.now().strftime("%H:%M"),
    })

    st.rerun()

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#57606a; font-size:0.8rem; padding:8px;">
    🏥 Sehat Saathi v1.0 &nbsp;|&nbsp; Powered by IBM watsonx.ai (Granite) + LangChain &nbsp;|&nbsp; 
    Emergency: <strong>108</strong> &nbsp;|&nbsp; Health Helpline: <strong>104</strong>
    <br><br>
    <em>Not a medical diagnostic tool. Always consult a qualified healthcare professional.</em>
</div>
""", unsafe_allow_html=True)
