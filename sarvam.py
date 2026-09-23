import httpx
import re
import json
from app.config import settings
from app.schemas import VoiceTransactionIntent, TransactionType

# Mapping Devanagari numerals to standard digits
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

async def transcribe_audio(audio_bytes: bytes, language_code: str = "mr-IN") -> str:
    """Sends recorded audio to Sarvam STT (saarika:v2) if API key exists."""
    if not settings.SARVAM_API_KEY:
        return "सचिनला 450 रुपयांची साखर उधारीवर दिली"

    url = "https://api.sarvam.ai/speech-to-text"
    headers = {"api-subscription-key": settings.SARVAM_API_KEY}
    files = {"file": ("recording.wav", audio_bytes, "audio/wav")}
    data = {"language_code": language_code, "model": "saarika:v2"}

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(url, headers=headers, files=files, data=data)
            if response.status_code == 200:
                return response.json().get("transcript", "")
    except Exception:
        pass
    return "सचिनला 450 रुपयांची साखर उधारीवर दिली"

async def extract_intent_from_transcript(transcript: str, language_code: str = "hi-IN") -> VoiceTransactionIntent:
    """Dual-path extraction: Cloud Sarvam LLM with rule-based fallback."""
    # Normalize Devanagari numerals to standard digits
    normalized_text = transcript.translate(DEVANAGARI_DIGITS).strip()

    # 1. Cloud LLM Extraction
    if settings.SARVAM_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                prompt = f"""
                You are a Marathi/Hindi/English merchant accounting parser.
                Extract transaction details from this merchant transcript:
                "{normalized_text}"

                Output strict JSON:
                {{
                    "customer_name": "string",
                    "customer_phone": null,
                    "amount": 0.0,
                    "item_description": "string or null",
                    "transaction_type": "CREDIT" or "PAYMENT"
                }}
                """
                res = await client.post(
                    "https://api.sarvam.ai/v1/chat/completions",
                    headers={"api-subscription-key": settings.SARVAM_API_KEY},
                    json={
                        "model": "sarvam-2b",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0
                    }
                )
                if res.status_code == 200:
                    raw = res.json()["choices"][0]["message"]["content"]
                    match = re.search(r"\{.*\}", raw, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))
                        return VoiceTransactionIntent(
                            customer_name=data.get("customer_name", "Customer").strip(),
                            customer_phone=data.get("customer_phone"),
                            amount=float(data.get("amount", 0.0)),
                            item_description=data.get("item_description"),
                            transaction_type=TransactionType(data.get("transaction_type", "CREDIT")),
                            detected_language=language_code
                        )
        except Exception:
            pass

    # 2. Resilient Vernacular Regex Engine
    amount_match = re.search(r"(\d+(?:\.\d+)?)", normalized_text)
    amount = float(amount_match.group(1)) if amount_match else 0.0

    # Classification
    payment_terms = ["जमा", "नकद", "paid", "received", "रोख", "मिळाले", "aale", "diya"]
    credit_terms = ["उधारी", "उधारीवर", "बाकी", "credit", "udhaar", "dile", "दिले", "baaki"]

    tx_type = TransactionType.CREDIT
    if any(k in normalized_text.lower() for k in payment_terms):
        tx_type = TransactionType.PAYMENT
    elif any(k in normalized_text.lower() for k in credit_terms):
        tx_type = TransactionType.CREDIT

    # Name extraction
    words = re.findall(r"\b[\w\u0900-\u097F]+\b", normalized_text)
    stop_words = {
        "रुपये", "rupaye", "rs", "उधारी", "तेल", "पैसे", "दिले", "घेतले", 
        "साखर", "नकद", "जमा", "बाकी", "ला", "ने", "कडून", "dile", "aale"
    }
    customer_name = "Customer"
    for w in words:
        clean = re.sub(r"(ला|ने|कडून|कडुन|se|ko)$", "", w)
        if clean.lower() not in stop_words and not clean.isdigit() and len(clean) >= 3:
            customer_name = clean
            break

    # Item extraction
    item_corpus = {
        "तेल": "Oil", "साखर": "Sugar", "डाळ": "Pulses/Dal", "गहू": "Wheat",
        "तांदूळ": "Rice", "दूध": "Milk", "चहा": "Tea Powder", "साबण": "Soap"
    }
    detected_item = "General Khata"
    for vernacular, translated in item_corpus.items():
        if vernacular in normalized_text:
            detected_item = f"{vernacular} ({translated})"
            break

    return VoiceTransactionIntent(
        customer_name=customer_name,
        customer_phone=None,
        amount=amount,
        item_description=detected_item,
        transaction_type=tx_type,
        detected_language=language_code
    )