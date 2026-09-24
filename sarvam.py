import os
import json
import logging
import re
import httpx
import streamlit as st

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Safe API Key Loading (Streamlit Secrets + Env fallback) ---
SARVAM_API_KEY = ""
try:
    if "SARVAM_API_KEY" in st.secrets:
        SARVAM_API_KEY = st.secrets["SARVAM_API_KEY"]
except Exception:
    pass

if not SARVAM_API_KEY:
    SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

# --- Schema Import with Safe Fallback ---
try:
    from schema import IntentExtractionResult
except ImportError:
    from pydantic import BaseModel, Field
    from typing import Optional

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
    Displays clear UI errors if credentials or requests fail.
    """
    if not audio_bytes:
        st.warning("No audio recorded. Please try speaking into the microphone again.")
        return ""

    if not SARVAM_API_KEY:
        st.error("SARVAM_API_KEY not found! Please add SARVAM_API_KEY to Streamlit Secrets or Environment Variables.")
        return ""

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
            if response.status_code != 200:
                st.error(f"Sarvam STT API Error ({response.status_code}): {response.text}")
                return ""
            
            result = response.json()
            return result.get("transcript", "")
    except Exception as e:
        st.error(f"Sarvam audio transcription failed: {e}")
        return ""


def extract_intent_from_transcript(transcript: str, language_code: str = "hi-IN") -> IntentExtractionResult:
    """
    Extracts structured Khata transaction details (Customer, Amount, Credit/Debit)
    from voice transcript using Sarvam AI LLM completion.
    """
    if not transcript:
        return IntentExtractionResult(raw_text="", action="UNKNOWN")

    if not SARVAM_API_KEY:
        st.warning("Running offline rule-based parser (API key missing).")
        return _fallback_rule_extraction(transcript)

    url = f"{SARVAM_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY
    }

    system_prompt = (
        "You are an AI assistant for Indian small merchants (VyaparSetu Khata Ledger). "
        "Extract transaction details from the merchant voice transcript into strict JSON with keys: "
        "'customer_name' (string or null), 'amount' (number or null), "
        "'action' (one of: 'CREDIT', 'DEBIT', 'REMINDER', 'UPI_PAY', or 'UNKNOWN'). "
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
            if response.status_code != 200:
                st.warning(f"Sarvam LLM returned status {response.status_code}. Using local rule fallback.")
                return _fallback_rule_extraction(transcript)

            content = response.json()["choices"][0]["message"]["content"]
            
            # Clean markdown codeblocks if returned
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            return IntentExtractionResult(
                customer_name=parsed.get("customer_name"),
                amount=float(parsed.get("amount")) if parsed.get("amount") else None,
                action=parsed.get("action", "UNKNOWN"),
                language=language_code,
                raw_text=transcript
            )
    except Exception as e:
        logger.error(f"Intent extraction error: {e}. Defaulting to rule fallback.")
        return _fallback_rule_extraction(transcript)


def _fallback_rule_extraction(text: str) -> IntentExtractionResult:
    """
    Lightweight rule-based fallback when offline or during unexpected API responses.
    """
    amounts = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    amount = float(amounts[0]) if amounts else None

    action = "UNKNOWN"
    lower_text = text.lower()
    if any(word in lower_text for word in ["उधार", "दिया", "debit", "gave", "khata", "उधारी"]):
        action = "DEBIT"
    elif any(word in lower_text for word in ["जमा", "मिला", "credit", "received", "aaya", "नकद"]):
        action = "CREDIT"
    elif any(word in lower_text for word in ["remind", "याद", "bhejo", "request"]):
        action = "REMINDER"

    return IntentExtractionResult(
        customer_name="Merchant Customer",
        amount=amount,
        action=action,
        raw_text=text
    )
