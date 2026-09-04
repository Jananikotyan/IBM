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
API_BASE_URL = "http://127.0.0.1:8000"

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
    "💊 ORS endre enu?",
]

TAMIL_EXAMPLES = [
    "🤒 என் குழந்தைக்கு 6 வாரம். என்ன தடுப்பூசி போட வேண்டும்?",
    "🌡️ எனக்கு 2 நாளாக காய்ச்சல் இருக்கிறது",
    "🏥 அருகிலுள்ள மருத்துவமனை எங்கே? Pincode: 600001",
    "💊 ORS என்றால் என்ன?",
]

TELUGU_EXAMPLES = [
    "🤒 నా బిడ్డకు 6 వారాలు. ఏ వ్యాక్సిన్ వేయాలి?",
    "🌡️ నాకు 2 రోజులుగా జ్వరంగా ఉంది",
    "🏥 దగ్గరలో ఆసుపత్రి ఎక్కడ ఉంది? Pincode: 500001",
    "💊 ORS అంటే ఏమిటి?",
]

BENGALI_EXAMPLES = [
    "🤒 আমার শিশুর ৬ সপ্তাহ। কোন টিকা দিতে হবে?",
    "🌡️ আমার ২ দিন ধরে জ্বর হচ্ছে",
    "🏥 কাছের হাসপাতাল কোথায়? Pincode: 700001",
    "💊 ORS কী এবং কখন দেবো?",
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

    # ── PDF Health Report Download ────────────────────────────────────────────
    st.markdown("")
    if st.session_state.messages:
        try:
            from app.report_generator import generate_pdf
            pdf_bytes = generate_pdf(
                st.session_state.messages,
                session_id=st.session_state.session_id,
            )
            from datetime import datetime as _dt
            fname = f"sehat_saathi_report_{_dt.now().strftime('%Y%m%d_%H%M')}.pdf"
            st.download_button(
                label="📄 Download Health Report (PDF)",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                use_container_width=True,
                help="Downloads a PDF summary of this conversation",
            )
        except Exception as _pdf_err:
            st.caption(f"⚠️ PDF unavailable: {_pdf_err}")
    else:
        st.button(
            "📄 Download Health Report (PDF)",
            disabled=True,
            use_container_width=True,
            help="Start a conversation first",
        )

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
    st.markdown("### 🇮🇳 தமிழ் (Tamil)")
    for example in TAMIL_EXAMPLES:
        if st.button(example, use_container_width=True, key=f"ta_{example[:20]}"):
            st.session_state["pending_message"] = example.split(" ", 1)[1]
            st.rerun()

    st.markdown("---")
    st.markdown("### 🇮🇳 తెలుగు (Telugu)")
    for example in TELUGU_EXAMPLES:
        if st.button(example, use_container_width=True, key=f"te_{example[:20]}"):
            st.session_state["pending_message"] = example.split(" ", 1)[1]
            st.rerun()

    st.markdown("---")
    st.markdown("### 🇧🇩 বাংলা (Bengali)")
    for example in BENGALI_EXAMPLES:
        if st.button(example, use_container_width=True, key=f"bn_{example[:20]}"):
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


# ─── Voice Input (Groq Whisper STT) ─────────────────────────────────────────
# Show transcription result ABOVE the expander so it's visible after send
if "transcribed_voice" in st.session_state:
    _tv = st.session_state["transcribed_voice"]
    st.success(f"🎙️ Transcribed: **{_tv}**")
    col_send, col_cancel = st.columns([3, 1])
    if col_send.button("📤 Send voice message", key="voice_send_btn", type="primary", use_container_width=True):
        st.session_state["voice_message"] = _tv
        st.session_state.pop("transcribed_voice", None)
        st.session_state.pop("last_audio_hash", None)
        st.rerun()
    if col_cancel.button("✖ Cancel", key="voice_cancel_btn", use_container_width=True):
        st.session_state.pop("transcribed_voice", None)
        st.session_state.pop("last_audio_hash", None)
        st.rerun()

with st.expander("🎙️ Voice Input — Speak in English, Hindi or Kannada", expanded=False):
    st.caption("Record → Stop → click **Send voice message** above")

    audio = st.audio_input("🎙️ Click mic, speak, then click stop", key="voice_recorder")

    if audio is not None:
        groq_key = os.getenv("GROQ_API_KEY", "")
        if not groq_key or groq_key == "your_groq_api_key_here":
            st.warning(
                "⚠️ **GROQ_API_KEY not set.**\n\n"
                "1. Get a free key at **console.groq.com**\n"
                "2. Add it to your `.env` file: `GROQ_API_KEY=your_key`\n"
                "3. Restart the backend"
            )
        else:
            # Use audio hash to avoid re-transcribing the same clip on every rerun
            audio_bytes = audio.read()
            audio_hash = hash(audio_bytes)

            if st.session_state.get("last_audio_hash") != audio_hash:
                # New audio clip — transcribe it once
                st.session_state["last_audio_hash"] = audio_hash
                st.session_state.pop("transcribed_voice", None)

                try:
                    from groq import Groq
                    import tempfile, os as _os

                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp.write(audio_bytes)
                        tmp_path = tmp.name

                    with st.spinner("🔄 Transcribing with Groq Whisper..."):
                        client = Groq(api_key=groq_key)
                        with open(tmp_path, "rb") as f:
                            resp = client.audio.transcriptions.create(
                                model="whisper-large-v3-turbo",
                                file=("audio.wav", f),
                                response_format="text",
                            )
                        transcribed = str(resp).strip()
                    _os.unlink(tmp_path)

                    if transcribed:
                        st.session_state["transcribed_voice"] = transcribed
                        st.rerun()   # rerun to show Send button ABOVE the expander
                    else:
                        st.warning("Could not hear clearly. Please try again.")

                except ImportError:
                    st.info("📦 Install Groq: `pip install groq`")
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

# Handle voice message — set by Send button above
if "voice_message" in st.session_state:
    prompt = st.session_state.pop("voice_message")

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
        with st.spinner("⏳ Sehat Saathi is thinking... (may take 5-10 sec for AI responses)"):
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
