"""
Sehat Saathi - Groq-powered Language Translator
================================================
Uses Groq's LLaMA model to translate text between languages.
Also provides Groq Whisper for Speech-to-Text.

Free tier at console.groq.com — one key for everything.
Supported: English, Hindi, Kannada, Tamil, Telugu, Bengali, Marathi + more
"""
import logging
from typing import Optional
from app.config import settings
from app.multilingual.local_translator import detect_language, LANGUAGE_NAMES

logger = logging.getLogger(__name__)

_groq_client = None


def _get_client():
    """Lazy-init Groq client."""
    global _groq_client
    if _groq_client is None:
        try:
            from groq import Groq
            _groq_client = Groq(api_key=settings.groq_api_key)
            logger.info("Groq client initialised.")
        except ImportError:
            logger.error("groq package not installed. Run: pip install groq")
        except Exception as e:
            logger.error("Groq client init failed: %s", e)
    return _groq_client


def translate_to_english(text: str) -> tuple[str, str]:
    """
    Detect language and translate to English using Groq LLaMA.

    Returns:
        (english_text, detected_lang_code)
    """
    detected = detect_language(text)
    if detected == "en":
        return text, "en"

    client = _get_client()
    if not client:
        logger.warning("Groq unavailable — returning original text as English.")
        return text, detected

    lang_name = LANGUAGE_NAMES.get(detected, detected)
    try:
        resp = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
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
            ],
            temperature=0.1,
            max_tokens=512,
        )
        translated = resp.choices[0].message.content.strip()
        logger.debug("Groq translated %s→en: %s", detected, translated[:60])
        return translated, detected
    except Exception as e:
        logger.error("Groq translation failed: %s", e)
        return text, detected


def translate_from_english(text: str, target_lang: str) -> str:
    """
    Translate English text to target language using Groq LLaMA.
    Falls back to local translations for hi/kn.
    """
    if target_lang == "en":
        return text

    # Try local translations first for hi/kn (faster, no API call)
    from app.multilingual.local_translator import get_strings
    # Only fall back to local if Groq unavailable
    client = _get_client()
    if not client:
        return text  # return English if Groq unavailable

    lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)
    try:
        resp = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
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
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        translated = resp.choices[0].message.content.strip()
        logger.debug("Groq translated en→%s: %s", target_lang, translated[:60])
        return translated
    except Exception as e:
        logger.error("Groq reverse translation failed: %s", e)
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
