import os
import io
import time
import pandas as pd
import streamlit as st
import qrcode
from streamlit_mic_recorder import mic_recorder

# --- Direct Root-Level Safe Imports ---
try:
    from config import settings
except ImportError:
    class Settings:
        UPI_VPA = "merchant@paytm"
        DEFAULT_LANGUAGE = "hi-IN"
    settings = Settings()

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

from sarvam import extract_intent_from_transcript, transcribe_audio

# --- Page Setup ---
st.set_page_config(
    page_title="VyaparSetu - Merchant AI Voice Ledger",
    page_icon="🏪",
    layout="wide"
)

# --- Session State Initialization ---
if "ledger" not in st.session_state:
    st.session_state.ledger = [
        {"Customer": "Ramesh Kumar", "Amount (₹)": 500.0, "Type": "DEBIT (उधार)", "Date": "2026-09-23"},
        {"Customer": "Suresh Kirana", "Amount (₹)": 1200.0, "Type": "CREDIT (जमा)", "Date": "2026-09-24"}
    ]

# --- Helper Functions ---
def generate_upi_qr(vpa: str, amount: float, payee_name: str = "Merchant"):
    upi_url = f"upi://pay?pa={vpa}&pn={payee_name}&am={amount}&cu=INR"
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- Header ---
st.title("🏪 VyaparSetu (व्यापारसेतु)")
st.caption("AI-Powered Vernacular Voice-to-Ledger & Automated UPI Payment Collections for Indian Merchants")
st.divider()

# --- Sidebar Controls ---
with st.sidebar:
    st.header("⚙️ Settings")
    lang_choice = st.selectbox(
        "Choose Voice Language (भाषा):",
        options=[
            ("Hindi (हिन्दी)", "hi-IN"),
            ("Marathi (मराठी)", "mr-IN"),
            ("Gujarati (ગુજરાતી)", "gu-IN"),
            ("Tamil (தமிழ்)", "ta-IN"),
            ("Telugu (తెలుగు)", "te-IN"),
            ("Bengali (বাংলা)", "bn-IN"),
            ("English (Indian)", "en-IN")
        ],
        format_func=lambda x: x[0]
    )
    lang_code = lang_choice[1]
    
    merchant_vpa = st.text_input("Merchant UPI VPA / ID:", value=getattr(settings, "UPI_VPA", "merchant@paytm"))
    st.info("Tip: Speak naturally like 'रमेश ने 500 रुपये दिए' or 'सचिनला 450 रुपयांची साखर उधारीवर दिली'")

# --- Main Columns ---
col_voice, col_ledger = st.columns([1, 1], gap="large")

with col_voice:
    st.subheader("🎙️ Voice Entry (आवाज़ से बहीखाता)")
    st.write("Click below to record your transaction entry:")
    
    # Microphone recorder
    audio_record = mic_recorder(
        start_prompt="🔴 Start Recording",
        stop_prompt="⏹️ Stop Recording",
        key="mic_recorder_widget"
    )

    transcript = ""
    
    if audio_record and audio_record.get("bytes"):
        with st.spinner("Transcribing audio using Sarvam AI..."):
            # DIRECT synchronous call - no asyncio.run to prevent TypeError
            transcript = transcribe_audio(audio_record["bytes"], language_code=lang_code)
            
        if transcript:
            st.success(f"Recognized Speech: **{transcript}**")
        else:
            st.warning("Could not capture speech. Try speaking closer to the mic.")
            
    st.markdown("---")
    st.write("**Or Select a Demo Preset:**")
    sample_text = st.selectbox(
        "Quick Presets:",
        [
            "",
            "सचिनला 450 रुपयांची साखर उधारीवर दिली",
            "राहुल कडून 1200 रुपये नकद जमा झाले",
            "रमेश ने 500 रुपये उधार लिए",
            "सुरेश ने 300 रुपये का दूध लिया"
        ]
    )
    
    manual_input = st.text_input("Or enter text manually:", value=sample_text if sample_text else "")
    
    final_text_to_process = transcript if transcript else manual_input

    if st.button("⚡ Process & Add to Ledger", use_container_width=True, type="primary"):
        if not final_text_to_process:
            st.warning("Please record your voice or provide a text entry first.")
        else:
            with st.spinner("Extracting customer and amount details..."):
                intent: IntentExtractionResult = extract_intent_from_transcript(final_text_to_process, language_code=lang_code)

            cust_name = intent.customer_name if intent.customer_name else "Cash Customer"
            amt = intent.amount if intent.amount is not None else 0.0
            act = intent.action if intent.action else "UNKNOWN"

            st.write(f"**Customer:** {cust_name}")
            st.write(f"**Amount:** ₹{amt}")
            st.write(f"**Action:** `{act}`")

            # Determine Credit or Debit
            tx_type = "DEBIT (उधार)" if act == "DEBIT" else "CREDIT (जमा)"
            
            # Save into Ledger
            today_str = time.strftime("%Y-%m-%d")
            st.session_state.ledger.insert(0, {
                "Customer": cust_name,
                "Amount (₹)": float(amt),
                "Type": tx_type,
                "Date": today_str
            })
            st.success(" Ledger updated successfully!")

            # Generate Dynamic UPI QR for instant settlement if Debit/Collection
            if amt > 0:
                st.subheader(f"📲 Instant UPI QR: Collect ₹{amt}")
                qr_img = generate_upi_qr(merchant_vpa, amt, payee_name=cust_name)
                st.image(qr_img, width=220, caption=f"Scan to pay ₹{amt} to {merchant_vpa}")

with col_ledger:
    st.subheader("📒 Live Merchant Khata (बहीखाता)")
    
    if st.session_state.ledger:
        df = pd.DataFrame(st.session_state.ledger)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Summary Metrics
        debit_total = df[df["Type"].str.contains("DEBIT")]["Amount (₹)"].sum()
        credit_total = df[df["Type"].str.contains("CREDIT")]["Amount (₹)"].sum()
        
        mcol1, mcol2 = st.columns(2)
        mcol1.metric("Total Udhar / Debit (उधार)", f"₹{debit_total:,.2f}")
        mcol2.metric("Total Received / Credit (जमा)", f"₹{credit_total:,.2f}")
    else:
        st.info("Your ledger is currently empty. Record your first transaction on the left!")
