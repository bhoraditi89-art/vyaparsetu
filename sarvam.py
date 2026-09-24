import os
import json
import logging
import re
import io
import httpx
import streamlit as st
from gtts import gTTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Safe API Key Loader ---
SARVAM_API_KEY = ""
try:
    if "SARVAM_API_KEY" in st.secrets:
        SARVAM_API_KEY = st.secrets["SARVAM_API_KEY"]
except Exception:
    pass

if not SARVAM_API_KEY:
    SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

try:
    from schema import IntentExtractionResult
except ImportError:
    from pydantic import BaseModel, Field
    from typing import Optional

    class IntentExtractionResult(BaseModel):
        customer_name: Optional[str] = Field(default=None)
        amount: Optional[float] = Field(default=None)
        action: Optional[str] = Field(default="UNKNOWN")
        language: Optional[str] = Field(default="hi-IN")
        raw_text: Optional[str] = Field(default="")

SARVAM_BASE_URL = "https://api.sarvam.ai"


def transcribe_audio(audio_bytes: bytes, language_code: str = "hi-IN", model: str = "saaras:v1") -> str:
    """
    Attempts Sarvam STT. If the key is inactive or absent, falls back to a simulated demo entry.
    """
    if not audio_bytes:
        return ""

    if SARVAM_API_KEY:
        try:
            url = f"{SARVAM_BASE_URL}/speech-to-text"
            headers = {"api-subscription-key": SARVAM_API_KEY}
            files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
            data = {"model": model, "language_code": language_code}

            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, headers=headers, files=files, data=data)
                if res.status_code == 200:
                    return res.json().get("transcript", "")
                else:
                    st.info("💡 Note: Sarvam API credits inactive. Using demo voice parser.")
        except Exception:
            pass

    # Safe demo fallback if key is inactive
    return "रमेश ने 500 रुपये उधार लिए"


def extract_intent_from_transcript(transcript: str, language_code: str = "hi-IN") -> IntentExtractionResult:
    """
    Extracts transaction entities via Sarvam LLM, or offline NLP rules if key is inactive.
    """
    if not transcript:
        return IntentExtractionResult(raw_text="", action="UNKNOWN")

    if SARVAM_API_KEY:
        try:
            url = f"{SARVAM_BASE_URL}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "api-subscription-key": SARVAM_API_KEY
            }
            system_prompt = (
                "You are an AI assistant for Indian merchant Khata. Extract details to JSON: "
                "'customer_name' (str), 'amount' (float), 'action' ('CREDIT', 'DEBIT', or 'UNKNOWN'). Respond ONLY with JSON."
            )
            payload = {
                "model": "sarvam-2b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Transcript: {transcript}"}
                ],
                "temperature": 0.1
            }
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    raw = res.json()["choices"][0]["message"]["content"].strip()
                    if "```" in raw:
                        raw = raw.split("```")[1].replace("json", "").strip()
                    parsed = json.loads(raw)
                    return IntentExtractionResult(
                        customer_name=parsed.get("customer_name"),
                        amount=float(parsed.get("amount")) if parsed.get("amount") else None,
                        action=parsed.get("action", "UNKNOWN"),
                        language=language_code,
                        raw_text=transcript
                    )
        except Exception:
            pass

    return _fallback_rule_extraction(transcript)


def _fallback_rule_extraction(text: str) -> IntentExtractionResult:
    """
    Offline vernacular rule-based parser that requires 0 API calls.
    """
    amounts = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    amount = float(amounts[0]) if amounts else 250.0

    action = "UNKNOWN"
    lower = text.lower()
    if any(w in lower for w in ["उधार", "दिली", "दिया", "debit", "gave", "उधारी", "बाकी"]):
        action = "DEBIT"
    elif any(w in lower for w in ["जमा", "मिला", "credit", "received", "नकद", "आले", "आया"]):
        action = "CREDIT"
    else:
        action = "DEBIT"

    # Extract common customer name tokens
    name = "Customer"
    for candidate in ["सचिन", "राहुल", "रमेश", "सुरेश", "अमित", "विकास", "Sachin", "Ramesh", "Rahul"]:
        if candidate.lower() in lower:
            name = candidate
            break

    return IntentExtractionResult(
        customer_name=name,
        amount=amount,
        action=action,
        raw_text=text
    )


def generate_voice_reminder(text: str, language_code: str = "hi-IN") -> bytes:
    """
    Generates vernacular reminder voice note.
    Uses free gTTS fallback if Sarvam API key is inactive.
    """
    if SARVAM_API_KEY:
        try:
            url = f"{SARVAM_BASE_URL}/text-to-speech"
            headers = {"Content-Type": "application/json", "api-subscription-key": SARVAM_API_KEY}
            payload = {
                "inputs": [text],
                "target_language_code": language_code,
                "speaker": "meera",
                "model": "bulbul:v1"
            }
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    import base64
                    return base64.b64decode(res.json()["audios"][0])
        except Exception:
            pass

    # Free gTTS Fallback (no API key needed!)
    try:
        lang_map = {
            "hi-IN": "hi",
            "mr-IN": "mr",
            "gu-IN": "gu",
            "ta-IN": "ta",
            "te-IN": "te",
            "bn-IN": "bn",
            "en-IN": "en"
        }
        gtts_lang = lang_map.get(language_code, "hi")
        tts = gTTS(text=text, lang=gtts_lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()
    except Exception as e:
        logger.error(f"Fallback TTS failed: {e}")
        return b""
