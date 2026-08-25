"""
Sehat Saathi - Multilingual Support via IBM Watson Language Translator
======================================================================
Detects user's language, translates input to English for processing,
and translates the response back to the user's language.

Supported languages (subset): en, hi, ta, te, bn, mr, gu, kn, pa, ml, ur
"""
import logging
from typing import Optional
from ibm_watson import LanguageTranslatorV3
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from app.config import settings

logger = logging.getLogger(__name__)

# Language code to human-readable name mapping
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "pa": "Punjabi",
    "ml": "Malayalam",
    "ur": "Urdu",
    "ar": "Arabic",
    "fr": "French",
    "es": "Spanish",
}

# Languages supported by Watson for bidirectional translation
SUPPORTED_LANGUAGES = set(LANGUAGE_NAMES.keys())


class LanguageTranslator:
    """
    Wraps the IBM Watson Language Translator for detect + translate operations.
    Falls back gracefully to the original text if the API is unavailable.
    """

    def __init__(self):
        self._client: Optional[LanguageTranslatorV3] = None
        self._initialized = False
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the Watson Language Translator client."""
        if not settings.watson_translator_api_key or settings.watson_translator_api_key == "your_translator_api_key_here":
            logger.warning(
                "Watson Translator API key not configured. Multilingual support disabled. "
                "All text will be treated as English."
            )
            return

        try:
            authenticator = IAMAuthenticator(settings.watson_translator_api_key)
            self._client = LanguageTranslatorV3(
                version="2018-05-01",
                authenticator=authenticator,
            )
            self._client.set_service_url(settings.watson_translator_url)
            self._initialized = True
            logger.info("Watson Language Translator initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize Watson Language Translator: %s", e)

    def detect_language(self, text: str) -> str:
        """
        Detect the language of the given text.

        Args:
            text: Input text to detect language of.

        Returns:
            ISO 639-1 language code (e.g., 'hi' for Hindi). Defaults to 'en'.
        """
        if not self._initialized or not self._client:
            return "en"

        try:
            response = self._client.identify(text).get_result()
            languages = response.get("languages", [])
            if languages:
                top = max(languages, key=lambda x: x.get("confidence", 0))
                detected = top.get("language", "en")
                logger.debug(
                    "Detected language: %s (confidence: %.2f)",
                    detected,
                    top.get("confidence", 0),
                )
                return detected
        except Exception as e:
            logger.error("Language detection failed: %s", e)

        return "en"

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate text from source_lang to target_lang.

        Args:
            text: Text to translate.
            source_lang: Source language code (e.g., 'hi').
            target_lang: Target language code (e.g., 'en').

        Returns:
            Translated text, or original text if translation fails/is unavailable.
        """
        if source_lang == target_lang:
            return text

        if not self._initialized or not self._client:
            return text

        if source_lang not in SUPPORTED_LANGUAGES or target_lang not in SUPPORTED_LANGUAGES:
            logger.warning(
                "Unsupported language pair: %s -> %s. Returning original.",
                source_lang, target_lang,
            )
            return text

        try:
            response = self._client.translate(
                text=text,
                source=source_lang,
                target=target_lang,
            ).get_result()
            translated = response["translations"][0]["translation"]
            logger.debug("Translated %s -> %s: %s...", source_lang, target_lang, translated[:50])
            return translated
        except Exception as e:
            logger.error("Translation failed (%s -> %s): %s", source_lang, target_lang, e)
            return text

    def to_english(self, text: str) -> tuple[str, str]:
        """
        Detect language and translate to English if needed.

        Returns:
            (translated_text, detected_language_code)
        """
        detected_lang = self.detect_language(text)
        if detected_lang == "en":
            return text, "en"
        translated = self.translate(text, source_lang=detected_lang, target_lang="en")
        return translated, detected_lang

    def from_english(self, text: str, target_lang: str) -> str:
        """
        Translate English text to the target language.

        Args:
            text: English text.
            target_lang: Target language code.

        Returns:
            Translated text.
        """
        if target_lang == "en":
            return text
        return self.translate(text, source_lang="en", target_lang=target_lang)

    def get_language_name(self, lang_code: str) -> str:
        """Return human-readable language name for a given code."""
        return LANGUAGE_NAMES.get(lang_code, lang_code.upper())


# Singleton instance
translator = LanguageTranslator()
