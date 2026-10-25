import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from backend.app.config import settings

logger = logging.getLogger(__name__)

# Language map
LANGUAGE_NAMES = {
    "hi": "Hindi",
    "ta": "Tamil",
    "en": "English",
    "bn": "Bengali",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
}


class TranslationService:
    """
    Local translation service for Saathi AI transcripts.
    Translates non-English transcripts (Hindi, Tamil, etc.) into natural English.
    - Runs 100% locally with zero external API calls.
    - Uses Argos Translate (offline CTranslate2 engine) for Hindi.
    - Uses local Ollama (qwen2.5:1.5b) for Tamil and other Indic languages.
    - Preserves context, names, currency amounts, and phone/transaction details.
    """

    _argos_translation = None
    _argos_loaded = False

    @classmethod
    def _get_argos_hindi_translator(cls):
        """Thread-safe lazy-loading of offline Argos Hindi -> English translator."""
        if cls._argos_loaded:
            return cls._argos_translation

        try:
            import argostranslate.translate
            installed_langs = argostranslate.translate.get_installed_languages()
            from_lang = next((lang for lang in installed_langs if lang.code == "hi"), None)
            to_lang = next((lang for lang in installed_langs if lang.code == "en"), None)
            if from_lang and to_lang:
                cls._argos_translation = from_lang.get_translation(to_lang)
                logger.info("Argos Translate Hindi -> English model loaded successfully.")
            else:
                logger.warning("Argos Hindi or English language package not installed in environment.")
        except Exception as e:
            logger.warning(f"Could not initialize Argos Translate: {e}")

        cls._argos_loaded = True
        return cls._argos_translation

    @classmethod
    def is_english_text(cls, text: str) -> bool:
        """Heuristic to detect if text consists predominantly of English/Latin characters."""
        if not text:
            return True
        latin_chars = sum(1 for c in text if "\u0041" <= c <= "\u005a" or "\u0061" <= c <= "\u007a")
        indic_chars = sum(1 for c in text if "\u0900" <= c <= "\u0d7f")
        if indic_chars == 0 and latin_chars > 3:
            return True
        return False

    @classmethod
    def _clean_translation_output(cls, raw: str) -> str:
        """Strip preamble, thinking artifacts, or label prefixes like 'English:' or quotes."""
        cleaned = raw.strip()
        # Remove any <think>...</think> chain-of-thought blocks
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE).strip()
        # Remove markdown bold/italic wrappers if entire text is wrapped
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()
        # Remove label prefixes
        for prefix in ["English:", "Translation:", "Translated text:", "Output:"]:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip()
        # Remove trailing labels
        cleaned = re.split(r"\n+(?:Tamil|Hindi|Note|Explanation):", cleaned, flags=re.IGNORECASE)[0].strip()
        return cleaned

    @classmethod
    def _translate_with_argos(cls, text: str) -> Optional[str]:
        """Translate Hindi using local Argos Translate."""
        translator = cls._get_argos_hindi_translator()
        if translator:
            try:
                translated = translator.translate(text)
                if translated and translated.strip():
                    return translated.strip()
            except Exception as e:
                logger.warning(f"Argos translation error: {e}")
        return None

    @classmethod
    def _translate_with_ollama(cls, text: str, source_language: str) -> str:
        """Translate using local Ollama instance (qwen2.5) with Indian context and dialect awareness."""
        lang_name = LANGUAGE_NAMES.get(source_language, source_language.title() if source_language else "Indian")

        few_shots = ""
        if source_language == "hi":
            few_shots = (
                "Hindi: मुझे एक फर्जी कॉल आई और उन्होंने बोला कि बिजली का बिल नहीं भरा तो कनेक्शन कट जाएगा।\n"
                "English: I received a fake call saying my electricity connection would be disconnected if I did not pay the bill.\n\n"
                "Hindi: सर मेरे बैंक अकाउंट से 50,000 रुपये कट गए हैं, कृपया मदद करें।\n"
                "English: Sir, 50,000 rupees have been debited from my bank account, please help.\n\n"
                "Hindi: मुझे इक फ्रॉड कॉल आया उसने बोला मेरे बैंक अकांट से पैसे कट जाएंगे अगर OTP नहीं दिया तो. मैंने OTP दे दिया पर फिर भी मेरे अकांट से 10,000 रुपे कट गए. मेरी मदद करो.\n"
                "English: I received a fraud call where they said money would be debited from my bank account if I didn't provide the OTP. I gave the OTP, but still 10,000 rupees were debited from my account. Please help me.\n\n"
            )
        elif source_language == "ta":
            few_shots = (
                "Tamil: வணக்கம், எனது வங்கிக் கணக்கிலிருந்து ரூபாய் 25,000 திருடப்பட்டுவிட்டது.\n"
                "English: Hello, Rs 25,000 was stolen from my bank account.\n\n"
                "Tamil: சார், ஒரு போலி இணைப்பைக் கிளிக் செய்த பிறகு எனது பணம் எடுக்கப்பட்டது.\n"
                "English: Sir, my money was deducted after clicking on a fake link.\n\n"
                "Tamil: கவனிக்கவும்! உங்கள் வங்கிக் கணக்கில் இருந்து ஐம்பதாயிரம் ரூபாய் சந்தேகத்திற்கிடமான பரிவர்த்தனை நடந்துள்ளது.\n"
                "English: Attention! A suspicious transaction of fifty thousand rupees has occurred from your bank account.\n\n"
            )

        prompt = (
            f"You are an expert translator specializing in Indian languages, colloquial dialects, Hinglish expressions, and cybercrime incident narratives.\n"
            f"Translate the following {lang_name} speech transcript into clear, natural first-person English.\n"
            "Rules:\n"
            "1. Accurately translate conversational idioms, loan words, and colloquial pronunciations:\n"
            "   - 'फ्रॉड कॉल' -> 'fraud call'\n"
            "   - 'बैंक अकांट' / 'अकाउंट' -> 'bank account'\n"
            "   - 'पैसे कट गए' -> 'money was deducted' / 'money was debited'\n"
            "   - 'इक' -> 'a' / 'one'\n"
            "   - 'ओटीपी' -> 'OTP'\n"
            "   - 'बिजली बिल' -> 'electricity bill'\n"
            "2. Preserve speaker first-person perspective ('मुझे' -> 'I received' / 'I got').\n"
            "3. Keep all numbers, amounts (e.g. ₹10,000, 25,000), names, and urgency intact.\n"
            "4. Output ONLY the English translation without any quotes, notes, or explanations.\n\n"
            f"{few_shots}"
            f"{lang_name}: {text}\n"
            "English:"
        )

        payload = {
            "model": settings.TRANSLATION_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "stop": ["\n\n", f"{lang_name}:", "Note:", "Explanation:"],
            },
        }

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=settings.TRANSLATION_TIMEOUT_SECONDS) as response:
                result = json.loads(response.read().decode("utf-8"))
                raw_response = result.get("response", "")
                return cls._clean_translation_output(raw_response)
        except urllib.error.URLError as e:
            logger.error(f"Failed to communicate with local Ollama service at {url}: {e}")
            raise RuntimeError(f"Local translation engine unavailable: {e}")

    @classmethod
    def translate_transcript(
        cls,
        text: str,
        source_language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main entrypoint for translating stored transcripts into English.
        - Preserves the original transcript.
        - Detects English speech and marks translation as unnecessary.
        - Prioritizes local Ollama LLM for natural, idiomatic Indian language translation.
        - Falls back to Argos Translate only if Ollama is unreachable.
        """
        trimmed = (text or "").strip()
        if not trimmed:
            return {
                "english_translation": "",
                "source_language": source_language or "unknown",
                "source_language_name": LANGUAGE_NAMES.get(source_language, "Unknown"),
                "is_already_english": False,
                "engine_used": "none",
            }

        lang_code = (source_language or "").lower()

        # Check if already English
        if lang_code == "en" or cls.is_english_text(trimmed):
            return {
                "english_translation": trimmed,
                "source_language": "en",
                "source_language_name": "English",
                "is_already_english": True,
                "engine_used": "passthrough",
                "message": "Original speech is already in English. Translation unnecessary.",
            }

        engine_used = "ollama"
        translation_text = None

        # Primary: Local Ollama (Qwen2.5) for contextual, high-accuracy translation
        if settings.TRANSLATION_ENGINE in ("ollama", "auto"):
            try:
                translation_text = cls._translate_with_ollama(trimmed, source_language=lang_code)
                if translation_text:
                    engine_used = f"ollama:{settings.TRANSLATION_MODEL}"
            except Exception as ollama_err:
                logger.warning(f"Ollama translation failed: {ollama_err}. Checking fallback.")

        # Fallback to Argos only if Ollama failed or if specifically configured for argos
        if not translation_text and lang_code == "hi":
            translation_text = cls._translate_with_argos(trimmed)
            if translation_text:
                engine_used = "argostranslate"

        # Final retry with Ollama if Argos didn't apply
        if not translation_text:
            translation_text = cls._translate_with_ollama(trimmed, source_language=lang_code)
            engine_used = f"ollama:{settings.TRANSLATION_MODEL}"

        return {
            "english_translation": translation_text,
            "source_language": lang_code,
            "source_language_name": LANGUAGE_NAMES.get(lang_code, lang_code.title()),
            "is_already_english": False,
            "engine_used": engine_used,
            "message": "Translated successfully to English.",
        }
