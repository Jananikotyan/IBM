"""
Sehat Saathi - Application Configuration
Loads all environment variables and exposes a typed settings object.

Supported modes:
  MOCK_MODE=true        → fully offline, rule-based (no API keys)
  OLLAMA_MODE=true      → Ollama local Granite LLM + Groq API (translation + STT)
  (default)             → IBM watsonx.ai + Watson Translator (original)
"""
import os
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    # ── Ollama (local Granite LLM) ─────────────────────────────────────────
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "granite3.1-dense:2b")

    # ── Groq API (translation via LLaMA + Whisper STT) ────────────────────
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    groq_whisper_model: str = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

    # ── IBM watsonx.ai (original — optional) ──────────────────────────────
    watsonx_api_key: str = os.getenv("WATSONX_API_KEY", "")
    watsonx_project_id: str = os.getenv("WATSONX_PROJECT_ID", "")
    watsonx_url: str = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    watsonx_model_id: str = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-chat-v2")

    # ── IBM Watson Translator (original — optional) ────────────────────────
    watson_translator_api_key: str = os.getenv("WATSON_TRANSLATOR_API_KEY", "")
    watson_translator_url: str = os.getenv("WATSON_TRANSLATOR_URL", "")

    # ── IBM Watson Speech-to-Text (optional — /voice API endpoint) ────────
    watson_stt_api_key: str = os.getenv("WATSON_STT_API_KEY", "")
    watson_stt_url: str = os.getenv("WATSON_STT_URL", "")

    # ── Facility Locator ───────────────────────────────────────────────────
    google_places_api_key: str = os.getenv("GOOGLE_PLACES_API_KEY", "")

    # ── Twilio / WhatsApp ──────────────────────────────────────────────────
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_whatsapp_from: str = os.getenv("TWILIO_WHATSAPP_FROM", "")

    # ── App ────────────────────────────────────────────────────────────────
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    vector_db_path: str = os.getenv("VECTOR_DB_PATH", "./data/vector_store")
    docs_path: str = os.getenv("DOCS_PATH", "./data/knowledge_base")

    # ── Mode flags ─────────────────────────────────────────────────────────
    # MOCK_MODE=true   → fully offline, no API keys needed
    # OLLAMA_MODE=true → Ollama local LLM + Groq API
    # (both false)     → IBM watsonx.ai + Watson Translator
    mock_mode: bool = os.getenv("MOCK_MODE", "false").lower() == "true"
    ollama_mode: bool = os.getenv("OLLAMA_MODE", "false").lower() == "true"

    # ── LangChain memory ───────────────────────────────────────────────────
    conversation_memory_k: int = 10

    class Config:
        arbitrary_types_allowed = True


settings = Settings()
