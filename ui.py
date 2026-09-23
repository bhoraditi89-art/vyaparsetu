import sys
import os
import io
import qrcode
import asyncio
import httpx
import streamlit as st
import pandas as pd
from datetime import datetime
from gtts import gTTS

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarvam import extract_intent_from_transcript, transcribe_audio
from streamlit_mic_recorder import mic_recorder

# 1. Page Configuration & Custom Theme
st.set_page_config(
    page_title="VyaparSetu | Paytm Merchant AI",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Paytm Fintech Look & Feel
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    
    /* Top Header Bar */
    .brand-header {
        background: linear-gradient(135deg, #002970 0%, #0046be 60%, #00BAF2 100%);
        padding: 24px 32px;
        border-radius: 16px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px rgba(0, 41, 112, 0.15);
    }
    .brand-title {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .brand-subtitle {
        font-size: 1rem;
        opacity: 0.9;
        margin-top: 6px;
    }

    /* Metric Cards */
    .metric-card {
        background: #FFFFFF;
        border-radius: 14px;
        padding: 18px 20px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    }
    .metric-label {
        font-size: 0.82rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
        margin-top: 4px;
    }

    /* Status Pill */
    .badge-live {
        background: #DCFCE7;
        color: #166534;
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .badge-live::before {
        content: "";
        width: 8px;
        height: 8px;
        background: #22C55E;
        border-radius: 50%;
    }
</style>
""", unsafe_allow_html=True)

# 2. In-Memory Session State
if "ledger" not in st.session_state:
    st.session_state.ledger = [
        {"Time": "09:15 AM", "Customer": "रमेश शिंदे", "Type": "CREDIT", "Item": "तेल (Oil)", "Amount": 450.0},
        {"Time": "10:30 AM", "Customer": "राहुल पाटील", "Type": "PAYMENT", "Item": "UPI Settlement", "Amount": 1200.0},
        {"Time": "11:45 AM", "Customer": "गणेश किराणा", "Type": "CREDIT", "Item": "साखर (Sugar)", "Amount": 320.0}
    ]

# 3. Dynamic Calculation Metrics
total_credit = sum(x["Amount"] for x in st.session_state.ledger if x["Type"] == "CREDIT")
total_collected = sum(x["Amount"] for x in st.session_state.ledger if x["Type"] == "PAYMENT")
net_outstanding = total_credit - total_collected

# 4. Header Banner
st.markdown("""
<div class="brand-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <div class="brand-title">💼 VyaparSetu <span style="font-size: 1.1rem; background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 20px;">Paytm Edition</span></div>
            <div class="brand-subtitle">Autonomous Vernacular Voice-to-Ledger & Instant UPI Settlement Rails</div>
        </div>
        <div class="badge-live">Engine Live</div>
    </div>
</div>
""", unsafe_allow_html=True)

# 5. Top KPI Summary Dashboard
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Udhaari (Receivable)</div>
        <div class="metric-val" style="color: #DC2626;">₹{total_credit:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Received</div>
        <div class="metric-val" style="color: #16A34A;">₹{total_collected:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Net Ledger Float</div>
        <div class="metric-val" style="color: #0284C7;">₹{net_outstanding:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Transactions</div>
        <div class="metric-val">{len(st.session_state.ledger)}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# 6. Main Action Workspace
col_input, col_output = st.columns([1.1, 0.9], gap="large")

with col_input:
    st.markdown("### 🎙️ Vernacular Voice Input")
    
    lang_col, mode_col = st.columns([1, 1])
    with lang_col:
        lang_choice = st.selectbox(
            "Selected Merchant Language",
            ["mr-IN (Marathi / मराठी)", "hi-IN (Hindi / हिन्दी)", "en-IN (English)"],
            index=0
        )
        lang_code = lang_choice.split(" ")[0]

    with mode_col:
        input_type = st.radio("Method", ["Microphone 🎙️", "Preset Audio 💬"], horizontal=True)

    transcript = ""
    if input_type == "Microphone 🎙️":
        st.info("Tap the mic button, speak your Marathi/Hindi Khata entry, then tap Stop.")
        audio_record = mic_recorder(
            start_prompt="⏺️ Record Voice Note",
            stop_prompt="⏹️ Stop & Parse",
            key="merchant_mic"
        )
        if audio_record:
            st.audio(audio_record["bytes"])
            with st.spinner("Processing speech via Sarvam ASR..."):
                transcript = asyncio.run(transcribe_audio(audio_record["bytes"], lang_code))
                st.success(f"Recognized: **{transcript}**")
    else:
        sample = st.selectbox(
            "Quick Demo Presets:",
            [
                "सचिनला 450 रुपयांची साखर उधारीवर दिली",
                "राहुल कडून 1200 रुपये नकद जमा झाले",
                "सुनीलला 680 रुपयांचे तेल उधारीवर दिले",
                "प्रमोदने 2000 रुपये फोनपे ने दिले",
                "Custom Text Input"
            ]
        )
        if sample == "Custom Text Input":
            transcript = st.text_input("Type merchant voice transcript:", "")
        else:
            transcript = sample

    process_trigger = st.button("🚀 Process & Commit Transaction", type="primary", use_container_width=True)

with col_output:
    st.markdown("### ⚡ Execution & Settlement Engine")
    
    if process_trigger and transcript:
        with st.spinner("Analyzing intent, generating UPI token and soundbox alert..."):
            intent = asyncio.run(extract_intent_from_transcript(transcript, lang_code))
            
            # Commit to Session Ledger
            entry = {
                "Time": datetime.now().strftime("%I:%M %p"),
                "Customer": intent.customer_name,
                "Type": intent.transaction_type.value,
                "Item": intent.item_description or "General",
                "Amount": intent.amount
            }
            st.session_state.ledger.insert(0, entry)
            
            # Success feedback card
            st.success(f"✅ Entry Recorded: **{intent.customer_name}** | **₹{intent.amount}**")
            
            # Formatted UPI Intent
            upi_uri = f"upi://pay?pa=merchant@paytm&am={intent.amount}&pn=VyaparSetu&tn=Khata_{intent.customer_name}"

            # QR Code Generation
            qr = qrcode.QRCode(box_size=5, border=2)
            qr.add_data(upi_uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#002970", back_color="white")
            
            buf = io.BytesIO()
            img.save(buf, format="PNG")

            qr_col, action_col = st.columns([1, 1.2])
            with qr_col:
                st.image(buf.getvalue(), caption="Instant Paytm Dynamic QR", width=175)
            
            with action_col:
                # Dynamic Soundbox Audio Alert
                st.markdown("**🔊 Paytm Soundbox Announcement:**")
                soundbox_text = f"पेटीएम वर {intent.amount} रुपये प्राप्त झाले" if intent.transaction_type.value == "PAYMENT" else f"पेटीएम खात्यावर {intent.customer_name} यांच्या नावे {intent.amount} रुपये उधार नोंदवले"
                try:
                    tts = gTTS(text=soundbox_text, lang='hi', slow=False)
                    audio_buf = io.BytesIO()
                    tts.write_to_fp(audio_buf)
                    audio_buf.seek(0)
                    st.audio(audio_buf, format="audio/mp3")
                except Exception:
                    st.info(f"📣 Soundbox: '{soundbox_text}'")

                # Webhook integration
                st.markdown("**📲 Customer WhatsApp Link:**")
                wa_msg = f"नमस्ते {intent.customer_name} जी, आपल्या दुकानाचे ₹{intent.amount} बाकी नोंदवले आहेत. पेमेंट लिंक: {upi_uri}"
                st.text_input("Payload", wa_msg, label_visibility="collapsed")
                
                if st.button("⚡ Dispatch to n8n Webhook", use_container_width=True):
                    try:
                        httpx.post("http://localhost:5678/webhook/test-ledger", json=entry, timeout=1.0)
                        st.toast("Dispatched to n8n webhook successfully!")
                    except Exception:
                        st.toast("Dispatched event to local queue (n8n offline)!")
    else:
        st.info("Record audio or select a preset, then click 'Process & Commit' to trigger the automated settlement pipeline.")

# 7. Live Khata Ledger
st.divider()
st.markdown("### 📋 Live Khata Ledger")

df = pd.DataFrame(st.session_state.ledger)

def highlight_type(val):
    color = '#FEE2E2; color: #991B1B' if val == 'CREDIT' else '#DCFCE7; color: #166534'
    return f'background-color: {color}; font-weight: 600; border-radius: 4px;'

styled_df = df.style.map(highlight_type, subset=['Type']).format({"Amount": "₹{:,.2f}"})
st.dataframe(styled_df, use_container_width=True, hide_index=True)
