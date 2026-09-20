"""
Sehat Saathi - Groq-powered Language Translator
================================================
Uses Groq's Qwen/LLaMA model to translate text between languages.
Also provides Groq Whisper for Speech-to-Text.

Free tier at console.groq.com — one key for everything.
Supported: English, Hindi, Kannada, Tamil, Telugu, Bengali, Marathi,
           Gujarati, Punjabi, Malayalam + more
"""
from __future__ import annotations

import logging
from app.config import settings
from app.multilingual.local_translator import detect_language, LANGUAGE_NAMES

logger = logging.getLogger(__name__)

_groq_client = None

# Fallback model list — tried in order if the configured model fails
_FALLBACK_MODELS = [
    "qwen/qwen3.8-27b",
    "groq/compound-mini",
    "groq/compound",
]


def _get_client():
    """Lazy-init Groq client."""
    global _groq_client
    if _groq_client is None:
        try:
            from groq import Groq
            _groq_client = Groq(api_key=settings.groq_api_key, timeout=30.0)
            logger.info("Groq client initialised.")
        except ImportError:
            logger.error("groq package not installed. Run: pip install groq")
        except Exception as e:
            logger.error("Groq client init failed: %s", e)
    return _groq_client


def _chat(messages: list, max_tokens: int = 512) -> str:
    """
    Call Groq chat completions. Tries the configured model first,
    then falls back through _FALLBACK_MODELS if it gets a 404/400.
    Returns empty string on total failure.
    """
    client = _get_client()
    if not client:
        return ""

    models_to_try = [settings.groq_model] + [
        m for m in _FALLBACK_MODELS if m != settings.groq_model
    ]

    for model in models_to_try:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content.strip()
            if model != settings.groq_model:
                logger.info("Used fallback Groq model: %s", model)
            return content
        except Exception as e:
            err_str = str(e)
            if "404" in err_str or "400" in err_str or "model" in err_str.lower():
                logger.warning("Groq model %s unavailable, trying next: %s", model, err_str[:80])
                continue
            # Non-model error (rate limit, network) — don't retry
            logger.error("Groq chat error with %s: %s", model, err_str[:120])
            return ""

    logger.error("All Groq models failed for translation.")
    return ""


def translate_to_english(text: str) -> tuple[str, str]:
    """
    Detect language and translate to English using Groq LLaMA.

    Returns:
        (english_text, detected_lang_code)
    """
    detected = detect_language(text)
    if detected == "en":
        return text, "en"

    if not _get_client():
        logger.warning("Groq unavailable — returning original text as English.")
        return text, detected

    lang_name = LANGUAGE_NAMES.get(detected, detected)
    translated = _chat([
        {
            "role": "system",
            "content": (
                "You are a translator. Translate the user's message to English. "
                "Output ONLY the translated text — no explanations, no quotes."
            ),
        },
        {
            "role": "user",
            "content": f"Translate this {lang_name} text to English:\n{text}",
        },
    ], max_tokens=512)

    if translated:
        logger.debug("Groq translated %s->en: %s", detected, translated[:60])
        return translated, detected
    logger.error("Groq translation to English failed for lang=%s", detected)
    return text, detected


def translate_from_english(text: str, target_lang: str) -> str:
    """
    Translate English text to target language using Groq.
    Falls back to English if Groq is unavailable.
    """
    if target_lang == "en":
        return text

    if not _get_client():
        logger.warning("Groq unavailable — returning English text for %s.", target_lang)
        return text

    lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)
    translated = _chat([
        {
            "role": "system",
            "content": (
                f"You are a translator. Translate the user's message to {lang_name}. "
                "Keep medical terms, numbers, and helpline numbers unchanged. "
                "Output ONLY the translated text — no explanations."
            ),
        },
        {
            "role": "user",
            "content": text,
        },
    ], max_tokens=1024)

    if translated:
        logger.debug("Groq translated en->%s: %s", target_lang, translated[:60])
        return translated
    logger.error("Groq reverse translation to %s failed", target_lang)
    return text


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """
    Transcribe audio using Groq Whisper API.
    Supports Hindi, Kannada, English and 90+ languages.

    Args:
        audio_bytes: Raw audio bytes (wav/mp3/ogg/m4a)
        filename: Filename hint for format detection

    Returns:
        Transcribed text string.
    """
    client = _get_client()
    if not client:
        raise RuntimeError("Groq client not available. Check GROQ_API_KEY.")

    import io
    try:
        resp = client.audio.transcriptions.create(
            model=settings.groq_whisper_model,
            file=(filename, io.BytesIO(audio_bytes)),
            response_format="text",
        )
        transcribed = str(resp).strip()
        logger.info("Groq Whisper transcribed: %s...", transcribed[:60])
        return transcribed
    except Exception as e:
        logger.error("Groq Whisper transcription failed: %s", e)
        raise
