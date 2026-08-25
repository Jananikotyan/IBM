"""
Sehat Saathi - Application Configuration
Loads all environment variables and exposes a typed settings object.
"""
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

load_dotenv()


class Settings(BaseModel):
    # IBM watsonx.ai
    watsonx_api_key: str = os.getenv("WATSONX_API_KEY", "")
    watsonx_project_id: str = os.getenv("WATSONX_PROJECT_ID", "")
    watsonx_url: str = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    watsonx_model_id: str = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-chat-v2")

    # IBM Watson Language Translator
    watson_translator_api_key: str = os.getenv("WATSON_TRANSLATOR_API_KEY", "")
    watson_translator_url: str = os.getenv(
        "WATSON_TRANSLATOR_URL",
        "https://api.us-south.language-translator.watson.cloud.ibm.com/instances/your_instance_id",
    )

    # IBM Watson Speech-to-Text
    watson_stt_api_key: str = os.getenv("WATSON_STT_API_KEY", "")
    watson_stt_url: str = os.getenv("WATSON_STT_URL", "")

    # Facility Locator
    google_places_api_key: str = os.getenv("GOOGLE_PLACES_API_KEY", "")

    # Infermedica (optional)
    infermedica_app_id: str = os.getenv("INFERMEDICA_APP_ID", "")
    infermedica_app_key: str = os.getenv("INFERMEDICA_APP_KEY", "")

    # App
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    vector_db_path: str = os.getenv("VECTOR_DB_PATH", "./data/vector_store")
    docs_path: str = os.getenv("DOCS_PATH", "./data/knowledge_base")

    # Mock / Demo mode — set MOCK_MODE=true to run without any API keys
    mock_mode: bool = os.getenv("MOCK_MODE", "false").lower() == "true"

    # LangChain memory
    conversation_memory_k: int = 10  # last N exchanges to retain

    class Config:
        arbitrary_types_allowed = True


settings = Settings()
