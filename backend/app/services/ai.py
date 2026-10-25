import logging
import re
from typing import Optional

import httpx
from backend.app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Saathi AI, an emergency cybercrime reporting assistant for cyber fraud victims in India. "
    "Answer directly in 2-4 short bullet points suitable for a WhatsApp message. "
    "Priorities: "
    "1. Advise calling the National Cyber Crime Helpline at 1930 immediately (Golden Hour). "
    "2. Advise contacting their bank immediately to block accounts/cards/UPI. "
    "3. Direct them to https://cybercrime.gov.in to file a formal complaint. "
    "4. Strictly warn never to share OTP, PIN, passwords, or install remote access apps. "
    "Be reassuring, concise, and professional."
)

FALLBACK_RESPONSE = (
    "Namaste! I am Saathi AI, your cybercrime reporting companion.\n\n"
    "If you have lost money to cyber fraud, please take these immediate actions:\n"
    "1. 📞 Call the National Cyber Crime Helpline at 1930 immediately.\n"
    "2. 🏦 Contact your bank right away to block your account/UPI.\n"
    "3. 🌐 Lodge a formal complaint at https://cybercrime.gov.in\n\n"
    "Never share OTPs, PINs, or passwords with anyone. How can I assist you with your report?"
)


def clean_think_tags(text: str) -> str:
    """Removes internal reasoning <think>...</think> tags if produced by reasoning models."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text.strip()


class AIService:
    """
    Local AI Service communicating with Ollama for Saathi AI response generation.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 40.0,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout or 45.0

    async def generate_response(self, user_message: str) -> str:
        """
        Generates an empathetic, actionable response using the local Ollama LLM.
        Falls back safely to emergency guidance if Ollama is unreachable or times out.
        """
        if not user_message or not user_message.strip():
            return FALLBACK_RESPONSE

        url = f"{self.base_url}/api/generate"
        formatted_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"User message: {user_message.strip()}\n\n"
            f"Saathi AI Response:"
        )

        payload = {
            "model": self.model,
            "prompt": formatted_prompt,
            "stream": False,
            "options": {
                "temperature": 0.4,
                "top_p": 0.9,
                "num_predict": 800,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    raw_content = data.get("response", "")
                    cleaned = clean_think_tags(raw_content)
                    if cleaned:
                        logger.info(
                            f"Generated AI response using Ollama ({self.model}), length: {len(cleaned)}"
                        )
                        return cleaned
                else:
                    logger.error(
                        f"Ollama returned HTTP {response.status_code}: {response.text}"
                    )
        except httpx.TimeoutException:
            logger.warning(
                f"Ollama inference timed out after {self.timeout}s. Falling back to default guidance."
            )
        except Exception as exc:
            logger.error(f"Error calling Ollama service: {exc}")

        return FALLBACK_RESPONSE


ai_service = AIService()
