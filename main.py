from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from app.schemas import VoiceTransactionIntent, LedgerResponse, TransactionType
from app.services.sarvam import extract_intent_from_transcript
from app.config import settings

app = FastAPI(
    title="VyaparSetu Core Engine",
    description="Autonomous Vernacular Khata & Marketing Agent for Paytm Merchants",
    version="0.1.0"
)

class TranscriptRequest(BaseModel):
    transcript: str
    language_code: str = "hi-IN"

@app.get("/")
def health_check():
    return {"status": "online", "system": "VyaparSetu", "env": settings.APP_ENV}

@app.post("/api/v1/ledger/record-intent", response_model=LedgerResponse)
async def record_ledger_intent(payload: TranscriptRequest):
    """
    Ingests regional language transcript, extracts structured transaction,
    and forwards event payload to n8n orchestration.
    """
    intent = await extract_intent_from_transcript(payload.transcript, payload.language_code)
    
    # Payload prepared for n8n webhook (UPI link generation & WhatsApp reminder)
    n8n_payload = {
        "event": "NEW_TRANSACTION",
        "customer": intent.customer_name,
        "amount": intent.amount,
        "item": intent.item_description,
        "type": intent.transaction_type.value,
        "language": intent.detected_language,
        "upi_intent": f"upi://pay?pa=merchant@paytm&am={intent.amount}&pn=VyaparSetu&tn=Khata_{intent.customer_name}"
    }

    # Asynchronously dispatch to n8n webhook if available
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(settings.N8N_WEBHOOK_URL, json=n8n_payload)
    except Exception:
        # Don't fail the API call if local n8n isn't running yet
        pass

    return LedgerResponse(
        status="SUCCESS",
        intent=intent,
        message=f"Recorded {intent.transaction_type.value} of ₹{intent.amount} for {intent.customer_name}"
    )