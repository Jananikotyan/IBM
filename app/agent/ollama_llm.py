"""
Sehat Saathi - Ollama LLM Integration (Local Granite)
======================================================
Uses Ollama to run IBM Granite locally — no API key, no internet after setup.

Setup:
  1. Download Ollama: https://ollama.com
  2. Run: ollama pull granite3.1-dense:2b
  3. Ollama starts automatically on http://localhost:11434

The LangChain OllamaLLM wrapper is used so the existing ReAct agent
works without any changes.
"""
import logging
from app.config import settings

logger = logging.getLogger(__name__)


def get_ollama_llm():
    """
    Return a LangChain-compatible Ollama LLM pointed at local Granite model.
    """
    try:
        from langchain_ollama import OllamaLLM
        llm = OllamaLLM(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.3,
            num_predict=1024,
        )
        logger.info("Ollama LLM initialised: %s @ %s", settings.ollama_model, settings.ollama_base_url)
        return llm
    except ImportError:
        # Fallback to langchain_community if langchain_ollama not installed
        try:
            from langchain_community.llms import Ollama
            llm = Ollama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=0.3,
                num_predict=1024,
            )
            logger.info("Ollama LLM (community) initialised: %s", settings.ollama_model)
            return llm
        except ImportError:
            raise ImportError(
                "Ollama LLM not available. Run:\n"
                "pip install langchain-ollama\n"
                "or: pip install langchain-community"
            )


def check_ollama_running() -> bool:
    """Check if Ollama server is running and the model is available."""
    import httpx
    try:
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            model_base = settings.ollama_model.split(":")[0]
            available = any(model_base in m for m in models)
            if not available:
                logger.warning(
                    "Ollama running but model '%s' not found. "
                    "Run: ollama pull %s",
                    settings.ollama_model, settings.ollama_model,
                )
            return True
        return False
    except Exception:
        logger.error(
            "Ollama not running at %s. Start it with: ollama serve",
            settings.ollama_base_url,
        )
        return False
