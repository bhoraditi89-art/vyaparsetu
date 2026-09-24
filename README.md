# 🏪 VyaparSetu (व्यापारसेतु)
### AI-Powered Vernacular Voice Ledger & Automated UPI Payment Collections for Indian Merchants

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Sarvam AI](https://img.shields.io/badge/Powered%20By-Sarvam%20AI-orange.svg)](https://www.sarvam.ai/)
[![Streamlit](https://img.shields.io/badge/Built%20With-Streamlit-red.svg)](https://streamlit.io/)

---

## 📌 Problem Statement
Millions of small Indian merchants and Kirana store owners manage daily credit (*उधार/Khata*) manually using paper notebooks. This traditional process suffers from:
1. **Time-Consuming Manual Logging:** Writing entries during peak shop hours leads to errors and missed records.
2. **Language & Literacy Barriers:** Most digital accounting software requires navigating complex English interfaces.
3. **Friction in Debt Recovery:** Calling or asking customers directly for overdue money creates awkward social friction, leading to delayed settlements and working capital crunches.

---

## 💡 The Solution: VyaparSetu
**VyaparSetu** bridges the digital divide for Bharat's merchants by transforming conversational vernacular speech into an automated, structured ledger and smart collection system:

- 🎙️ **Vernacular Voice-to-Ledger:** Merchants speak naturally in their local dialect (Hindi, Marathi, Gujarati, Tamil, etc.).
- 🧠 **Contextual Intent & Entity Extraction:** Automatically extracts customer names, transaction amounts, and credit/debit status.
- 📲 **Instant Dynamic UPI QR:** Generates on-the-fly UPI payment QR codes pre-filled with the exact transaction amount for instant countertop settlement.
- 📢 **AI Voice Note Reminders (TTS):** Synthesizes natural, polite voice payment reminders in the customer's native language.
- 💬 **1-Click WhatsApp Collection Links:** Sends payment reminders with embedded `upi://pay` deep links directly to the customer's WhatsApp.

---

## 🏗️ System Architecture

```text
       [Merchant Mic / Speech]
                  │
                  ▼
      [Sarvam AI Speech-to-Text] ── (saaras:v1)
                  │
                  ▼
    [Sarvam AI Intent Parser / LLM] ── (sarvam-2b)
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
 [Live Khata Ledger]   [Dynamic UPI QR Engine]
   (Streamlit DB)       (qrcode / UPI Intent)
        │
        ▼
 [Vernacular Voice Reminder Engine] ── (bulbul:v1 / gTTS)
        │
        ▼
 [WhatsApp 1-Click Payment Link]
