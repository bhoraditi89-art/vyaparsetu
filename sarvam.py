import os
import json
import logging
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Safe Root-Level Imports ---
try:
    from config import settings
    SARVAM_API_KEY = getattr(settings, "SARVAM_API_KEY", os.getenv("SARVAM_API_KEY", ""))
except ImportError:
    SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

try:
    from schema import IntentExtractionResult
except ImportError:
    from pydantic import BaseModel, Field
    from typing import Optional, List

    class IntentExtractionResult(BaseModel):
        customer_name: Optional[str] = Field(default=None, description="Name of the customer/merchant")
        amount: Optional[float] = Field(default=None, description="Transaction amount")
        action: Optional[str] = Field(default="UNKNOWN", description="Action type: CREDIT, DEBIT, REMINDER, UPI_PAY")
        language: Optional[str] = Field(default="hi-IN", description="Detected language code")
        raw_text: Optional[str] = Field(default="", description="Original transcript")


SARVAM_BASE_URL = "https://api.sarvam.ai"


def transcribe_audio(audio_bytes: bytes, language_code: str = "hi-IN", model: str = "saaras:v1") -> str:
    """
    Transcribes voice input using Sarvam AI Speech-to-Text API.
    """
    if not SARVAM_API_KEY:
        logger.warning("SARVAM_API_KEY not configured. Returning fallback mock response.")
        return "रमेश ने 500 रुपये उधार लिए"

    url = f"{SARVAM_BASE_URL}/speech-to-text"
    headers = {
        "api-subscription-key": SARVAM_API_KEY
    }
    files = {
        "file": ("audio.wav", audio_bytes, "audio/wav")
    }
    data = {
        "model": model,
        "language_code": language_code
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            result = response.json()
            return result.get("transcript", "")
    except Exception as e:
        logger.error(f"Error in Sarvam STT transcription: {e}")
        return ""


def extract_intent_from_transcript(transcript: str, language_code: str = "hi-IN") -> IntentExtractionResult:
    """
    Extracts structured Khata transaction details (Customer, Amount, Credit/Debit)
    from voice transcript using Sarvam AI LLM completion.
    """
    if not transcript:
        return IntentExtractionResult(raw_text="", action="UNKNOWN")

    if not SARVAM_API_KEY:
        logger.warning("SARVAM_API_KEY not found. Running rule-based local intent extraction fallback.")
        return _fallback_rule_extraction(transcript)

    url = f"{SARVAM_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY
    }

    system_prompt = (
        "You are an AI assistant for Indian small merchants (VyaparSetu Khata Ledger). "
        "Extract transaction details from the given merchant voice transcript into strict JSON format with keys: "
        "'customer_name' (string or null), 'amount' (number or null), "
        "'action' (must be one of: 'CREDIT', 'DEBIT', 'REMINDER', 'UPI_PAY', or 'UNKNOWN'). "
        "Respond ONLY with valid raw JSON."
    )

    payload = {
        "model": "sarvam-2b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Transcript: {transcript}"}
        ],
        "temperature": 0.1
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            
            # Clean markdown JSON block formatting if present
            cleaned_content = content.strip()
            if cleaned_content.startswith("```"):
                cleaned_content = cleaned_content.split("```")[1]
                if cleaned_content.startswith("json"):
                    cleaned_content = cleaned_content[4:]
            cleaned_content = cleaned_content.strip()

            parsed = json.loads(cleaned_content)
            return IntentExtractionResult(
                customer_name=parsed.get("customer_name"),
                amount=float(parsed.get("amount")) if parsed.get("amount") else None,
                action=parsed.get("action", "UNKNOWN"),
                language=language_code,
                raw_text=transcript
            )
    except Exception as e:
        logger.error(f"Sarvam LLM intent extraction failed: {e}. Using fallback parser.")
        return _fallback_rule_extraction(transcript)


def _fallback_rule_extraction(text: str) -> IntentExtractionResult:
    """
    Lightweight rule-based fallback when offline or during missing API key conditions.
    """
    import re
    amounts = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    amount = float(amounts[0]) if amounts else None

    action = "UNKNOWN"
    lower_text = text.lower()
    if any(word in lower_text for word in ["उधार", "दिया", "debit", "gave", "khata"]):
        action = "DEBIT"
    elif any(word in lower_text for word in ["जमा", "मिला", "credit", "received", "aaya"]):
        action = "CREDIT"
    elif any(word in lower_text for word in ["remind", "याद", "bhejo", "request"]):
        action = "REMINDER"

    return IntentExtractionResult(
        customer_name="Merchant Customer",
        amount=amount,
        action=action,
        raw_text=text
    )
