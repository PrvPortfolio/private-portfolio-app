import streamlit as st
import pandas as pd
import yfinance as yf
import json
import base64
from datetime import datetime
import pytz
import plotly.express as px
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# --- TIMEZONE CONFIG ---
def get_chicago_now():
    return datetime.now(pytz.timezone('America/Chicago'))

# --- CRYPTOGRAPHY FUNCTIONS ---
def generate_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return kdf.derive(password.encode())

def encrypt_data(plain_text: str, password: str) -> str:
    salt = b"StaticSaltForLocalApp"
    key = generate_key(password, salt)
    import os
    iv = os.urandom(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(iv)).encryptor()
    ciphertext = encryptor.update(plain_text.encode()) + encryptor.finalize()
    combined = iv + encryptor.tag + ciphertext
    return base64.b64encode(combined).decode()

def decrypt_data(cipher_text_b64: str, password: str) -> str:
    try:
        salt = b"StaticSaltForLocalApp"
        key = generate_key(password, salt)
        combined = base64.b64decode(cipher_text_b64.encode())
        iv = combined[:12]
        tag = combined[12:28]
        ciphertext = combined[28:]
        decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag)).decryptor()
        return (decryptor.update(ciphertext) + decryptor.finalize()).decode()
    except Exception:
        raise ValueError("Incorrect password or corrupted file.")

# --- WEB PAGE CONFIG ---
st.set_page_config(page_title="Portfolio Pro | Private Tracker", layout="wide", initial_sidebar_state="expanded")

# Inject Custom CSS for a professional, clean UI appearance
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div.stButton > button:first-child {
        background-color: #262730; color: white; border-radius: 6px; border: 1px solid #4a4b50;
    }
    div.stButton > button:first-child:hover { background-color: #ff4b4b; border-color: #ff4b4b; }
    .metric-card {
        background-color: #161a24; padding: 20px; border-radius: 10px; 
        border-left: 5px solid #00f2fe; margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# Main Title Header Banner
st.markdown('<div style="padding:10px 0px;"><h1 style="color:white;margin-bottom:0;">💼 PORTFOLIO PRO</h1><p style="color:#8a93a6;font-size:14px;margin-top:2px;">Enterprise Privacy Core • Automated Local Archiving</p></div>', unsafe_allow_html=True)
st.markdown("---")

if "assets" not in st.session_state:
    st.session_state.assets = []

# --- TOP PANEL: FILE INTAKE LINK ---
with st.expander("🔓 Load Existing Profile Session (.enc)", expanded=False):
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        uploaded_file = st.file_uploader("Drop your encrypted backup here:", type=["enc"], label_visibility="collapsed")
    with col_up2:
        import_password = st.text_input("Enter secure file password:", type="password", placeholder="Password...")
    
    if uploaded_file and import_password:
        if st.button("🔓 Restore Session"):
            try:
                file_contents = uploaded_file.read().decode()
                decrypted_json_string = decrypt_data(file_contents, import_password)
                st.session_state.assets = json.loads(decrypted_json_string)
                st.success("Session state successfully restored in-memory.")
                st.rerun()
            except ValueError as e:
                st.error(f"Failed to access profile: {e}")

# --- SIDEBAR CONTROL UNIT ---
st.sidebar.markdown('<h2 style="margin-top:0;">⚡ Asset Intake</h2>', unsafe_allow_html=True)
asset_type = st.sidebar.selectbox("Asset Classification", ["Stock", "Crypto"])
ticker = st.sidebar.text_input("Ticker Label (e.g., TSLA, BTC-USD)", placeholder="NVDA...").upper().strip()
amount = st.sidebar.number_input("Current Position Size", min_value=0.0, step=0.01, format="%.6f")

if st.sidebar.button("➕ Inject into Position"):
    if ticker and amount > 0:
        existing_tickers = [a["ticker"] for a in st.session_state.assets]
        if ticker in existing_tickers:
            st.sidebar.warning(f"Position for {ticker} already exists!")
        else:
            st.session_state.assets.append({"type": asset_type, "ticker": ticker, "holdings": amount})
            st.sidebar.success(f"Added position for {ticker}")
            st.rerun()
    else:
        st.sidebar.error("Invalid entry criteria.")

# --- DASHBOARD SYSTEM PRESENTATION ---
if len(st.session_state.assets) == 0:
    st.info("💡 Application memory is unallocated. Restore an existing profile session above or input custom positions via the sidebar to initialize visual grids.")
else:
    now = get_chicago_now()
    updated_data = []
    total_portfolio_value = 0.0
    
    with st.spinner("Streaming premium financial metrics from API nodes..."):
        for asset in st.session_state.assets:
            try:
                ticker_data = yf.Ticker(asset["ticker"])
                live_price = ticker_data.history(period="1d")["Close"].iloc[-1]
            except Exception:
                live_price = 0.0
                
            total_value = live_price * asset["holdings"]
            total_portfolio_value += total_value
            
            updated_data.append({
                "Date": now.strftime('%Y-%m-%d %H:%M'),
                "Type": asset["type"],
                "Ticker": asset["ticker"],
                "Holdings": asset["holdings"],
                "Price ($)": round(live_price, 2) if live_price > 1 else round(live_price, 6),
                "Total Value ($)": round(total_value, 2)
            })
            
    df = pd.DataFrame(updated_data)

    # 1. VISUAL METRIC BOX
    st.markdown(f"""
        <div class="metric-card">
            <span style="color:#8a93a6; font-size:13px; text-transform:uppercase; font-weight:bold; letter-spacing:1px;">Net Asset Valuation</span>
            <h1 style="color:white; margin:5px 0 0 0; font-size:38px; font-weight:700;">${total_portfolio_value:,.2f}</h1>
        </div>
    """, unsafe_allow_html=True)

    # 2. COLUMNS FOR VISUAL BALANCING (Table left, Chart right)
    col_dash1, col_dash2 = st.columns([4, 3])
    
    with col_dash1:
        st.markdown('<h4 style="color:white;margin-bottom:15px;">📊 Monitored Allocations</h4>', unsafe_allow_html=True)
        st.dataframe(df[["Type", "Ticker", "Holdings", "Price ($)", "Total Value ($)"]], use_container_width=True, hide_index=True)
    
    with col_dash2:
        st.markdown('<h4 style="color:white;margin-bottom:15px;">🥧 Allocation Breakdown</h4>', unsafe_allow_html=True)
        fig = px.pie(df, values="Total Value ($)", names="Ticker", hole=0.4, template="plotly_dark")
        fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=260, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 3. NEW COMPONENT: GRANULAR DATA ARCHIVING SUITE
    st.subheader("🗄️ Local Data Extraction Suite")
    st.write("Generate and download segmented timeline snapshot files directly to your machine storage array.")
    
    col_file1, col_file2, col_file3, col_file4 = st.columns(4)
    
    with col_file1:
        st.info("**📅 Daily History File**")
        daily_csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"📥 Download {now.strftime('%Y-%m-%d')}.csv",
            data=daily_csv,
            file_name=f"investment_history_{now.strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
            key="dl_daily"
        )
        
    with col_file2:
        st.info("**🗓️ Weekly Summary**")
        current_week = now.strftime('%Y-W%U')
        df_weekly = df.groupby(["Type"])["Total Value ($)"].sum().reset_index()
        weekly_csv = df_weekly.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"📥 Download {current_week}.csv",
            data=weekly_csv,
            file_name=f"weekly_summary_{current_week}.csv",
            mime="text/csv",
            key="dl_weekly"
        )
        
    with col_file3:
        st.info("**🗂️ Monthly Summary**")
        current_month = now.strftime('%Y-%m')
        df_monthly = df.groupby(["Type"])["Total Value ($)"].sum().reset_index()
        monthly_csv = df_monthly.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"📥 Download {current_month}.csv",
            data=monthly_csv,
            file_name=f"monthly_summary_{current_month}.csv",
            mime="text/csv",
            key="dl_monthly"
        )
        
    with col_file4:
        st.info("**🏛️ Yearly Macro Summary**")
        current_year = now.strftime('%Y')
        df_yearly = df.groupby(["Type"])["Total Value ($)"].sum().reset_index()
        yearly_csv = df_yearly.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"📥 Download {current_year}.csv",
            data=yearly_csv,
            file_name=f"yearly_summary_{current_year}.csv",
            mime="text/csv",
            key="dl_yearly"
        )

    st.markdown("---")

    # 4. ENCRYPTED SYSTEM KEY BACKUP
    st.subheader("🔒 Secure Profile Encryption Profile")
    export_password = st.text_input("Deploy master passphrase to scramble profile structure:", type="password", placeholder="Passphrase...")
    
    col_ex1, col_ex2 = st.columns([3, 1])
    with col_ex1:
        if export_password:
            raw_portfolio_json = json.dumps(st.session_state.assets)
            encrypted_string = encrypt_data(raw_portfolio_json, export_password)
            
            st.download_button(
                label="🔒 Download Encrypted Profile Key (.enc)",
                data=encrypted_string,
                file_name="portfolio.enc",
                mime="text/plain",
                use_container_width=True
            )
    with col_ex2:
        if st.button("🔴 Purge Local Memory", use_container_width=True):
            st.session_state.assets = []
            st.rerun()
