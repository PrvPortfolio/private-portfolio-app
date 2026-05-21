import streamlit as st
import pandas as pd
import yfinance as yf
import json
import base64
from datetime import datetime
import pytz
import plotly.express as px
import time
import extra_streamlit_components as stx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# --- TIMEZONE CONFIG ---
def get_chicago_now():
    return datetime.now(pytz.timezone('America/Chicago'))

# --- CRYPTOGRAPHY ENGINE ---
def generate_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
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
        raise ValueError("Decryption failed.")

# --- WEB PAGE CONFIG ---
st.set_page_config(page_title="Portfolio Pro | Private Tracker", layout="wide")

cookie_manager = stx.CookieManager()

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div.stButton > button:first-child { background-color: #262730; color: white; border-radius: 6px; border: 1px solid #4a4b50; }
    div.stButton > button:first-child:hover { background-color: #ff4b4b; border-color: #ff4b4b; }
    .metric-card { background-color: #161a24; padding: 20px; border-radius: 10px; border-left: 5px solid #00f2fe; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div style="padding:10px 0px;"><h1 style="color:white;margin-bottom:0;">💼 PORTFOLIO PRO</h1><p style="color:#8a93a6;font-size:14px;margin-top:2px;">Autonomous Client Caching Engine • No Database Server</p></div>', unsafe_allow_html=True)
st.markdown("---")

# Global session variables
if "assets" not in st.session_state:
    st.session_state.assets = []
if "streaming_history" not in st.session_state:
    st.session_state.streaming_history = []

# --- BACKGROUND AUTOMATION ---
time.sleep(0.2)  
cached_enc_data = cookie_manager.get(cookie="secure_portfolio_data")
cached_key_pass = cookie_manager.get(cookie="secure_portfolio_key")

if cached_enc_data and cached_key_pass and len(st.session_state.assets) == 0:
    try:
        decrypted = decrypt_data(cached_enc_data, cached_key_pass)
        st.session_state.assets = json.loads(decrypted)
        st.rerun()
    except Exception:
        pass

# --- SIDEBAR INTERFACE ---
st.sidebar.markdown('<h2 style="margin-top:0;">⚡ Asset Intake</h2>', unsafe_allow_html=True)
asset_type = st.sidebar.selectbox("Asset Classification", ["Stock", "Crypto"])
ticker = st.sidebar.text_input("Ticker Label", placeholder="BTC-USD...").upper().strip()
amount = st.sidebar.number_input("Position Size", min_value=0.0, step=0.01, format="%.6f")

if st.sidebar.button("➕ Inject into Position"):
    if ticker and amount > 0:
        existing_tickers = [a["ticker"] for a in st.session_state.assets]
        if ticker in existing_tickers:
            st.sidebar.warning(f"Position for {ticker} already exists!")
        else:
            st.session_state.assets.append({"type": asset_type, "ticker": ticker, "holdings": amount})
            st.sidebar.success(f"Added position for {ticker}")
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📡 Stream Controls")
live_stream_active = st.sidebar.toggle("Enable Live Tick Feed", value=True)
refresh_interval = st.sidebar.slider("Refresh Interval (Seconds)", min_value=5, max_value=60, value=10)

# --- DASHBOARD CALCULATION AND RENDER ---
if len(st.session_state.assets) == 0:
    st.info("💡 Your workspace is clean. Use the input on the left to add assets.")
else:
    now = get_chicago_now()
    updated_data = []
    total_portfolio_value = 0.0
    
    for asset in st.session_state.assets:
        try:
            ticker_obj = yf.Ticker(asset["ticker"])
            
            # THE FIX: Force a fresh 1-minute interval payload to bypass yfinance caching
            hist_data = ticker_obj.history(period="1d", interval="1m")
            
            if not hist_data.empty:
                live_price = float(hist_data["Close"].iloc[-1])
            else:
                live_price = float(ticker_obj.fast_info['lastPrice'])
        except Exception:
            live_price = 0.0
            
        total_value = live_price * asset["holdings"]
        total_portfolio_value += total_value
        updated_data.append({
            "Date": now.strftime('%Y-%m-%d %H:%M:%S'),
            "Type": asset["type"],
            "Ticker": asset["ticker"],
            "Holdings": asset["holdings"],
            "Price ($)": round(live_price, 2) if live_price > 1 else round(live_price, 6),
            "Total Value ($)": round(total_value, 2)
        })
        
    df = pd.DataFrame(updated_data)
    st.session_state.streaming_history.append({
        "Timestamp": now.strftime('%H:%M:%S'), 
        "Total Portfolio Worth ($)": round(total_portfolio_value, 2)
    })
    
    if len(st.session_state.streaming_history) > 100:
        st.session_state.streaming_history.pop(0)

    st.markdown(f"""
        <div class="metric-card">
            <span style="color:#8a93a6; font-size:13px; text-transform:uppercase; font-weight:bold; letter-spacing:1px;">Net Asset Valuation</span>
            <h1 style="color:white; margin:5px 0 0 0; font-size:38px; font-weight:700;">${total_portfolio_value:,.2f}</h1>
        </div>
    """, unsafe_allow_html=True)

    col_dash1, col_dash2 = st.columns([4, 3])
    with col_dash1:
        st.markdown('<h4 style="color:white;margin-bottom:15px;">📊 Monitored Allocations</h4>', unsafe_allow_html=True)
        st.dataframe(df[["Type", "Ticker", "Holdings", "Price ($)", "Total Value ($)"]], use_container_width=True, hide_index=True)
    
    with col_dash2:
        st.markdown('<h4 style="color:white;margin-bottom:0px;">⚙️ Visual Framework</h4>', unsafe_allow_html=True)
        chart_choice = st.selectbox("Select Visual Template:", ["Live Zero-Delay Tracker", "Donut Chart Breakdown", "Bar Graph Distribution"], label_visibility="collapsed")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if chart_choice == "Live Zero-Delay Tracker":
            fig_stream = px.line(pd.DataFrame(st.session_state.streaming_history), x="Timestamp", y="Total Portfolio Worth ($)", template="plotly_dark")
            fig_stream.update_traces(line_color="#00f2fe", line_width=4, mode="lines+markers")
            
            # THE FIX: Force the Y-Axis to dynamically zoom in on micro-cents so small changes show as huge spikes visually
            fig_stream.update_yaxes(autorange=True, fixedrange=False)
            fig_stream.update_layout(margin=dict(l=20, r=20, t=10, b=20), height=250, xaxis_title=None)
            
            st.plotly_chart(fig_stream, use_container_width=True)
            
        elif chart_choice == "Donut Chart Breakdown":
            fig = px.pie(df, values="Total Value ($)", names="Ticker", hole=0.4, template="plotly_dark")
            fig.update_layout(margin=dict(l=20, r=20, t=10, b=20), height=250)
            st.plotly_chart(fig, use_container_width=True)
            
        elif chart_choice == "Bar Graph Distribution":
            fig_bar = px.bar(df, x="Ticker", y="Total Value ($)", color="Ticker", template="plotly_dark")
            fig_bar.update_layout(margin=dict(l=20, r=20, t=10, b=20), height=250, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    st.subheader("🔒 Remember Me (Secure Browser Auto-Vault)")
    col_lock1, col_lock2 = st.columns(2)
    with col_lock1:
        vault_password = st.text_input("Create a Master Password to lock down local storage:", type="password", placeholder="Enter password...", key="v_pass")
    with col_lock2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔒 Securely Save to This Browser", use_container_width=True):
            if vault_password:
                raw_json = json.dumps(st.session_state.assets)
                encrypted_payload = encrypt_data(raw_json, vault_password)
                cookie_manager.set("secure_portfolio_data", encrypted_payload, key="set_data_widget")
                cookie_manager.set("secure_portfolio_key", vault_password, key="set_key_widget")
                st.success("Vault engaged! This browser will now auto-load your portfolio instantly on refresh.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Please enter a password to encrypt your storage partition.")

    st.markdown("---")

    st.subheader("🗄️ Local Data Extraction Suite")
    col_file1, col_file2, col_file3, col_file4 = st.columns(4)
    with col_file1:
        st.download_button(label=f"📥 Daily {now.strftime('%Y-%m-%d')}.csv", data=df.to_csv(index=False).encode('utf-8'), file_name=f"investment_history_{now.strftime('%Y-%m-%d')}.csv", mime="text/csv")
    with col_file2:
        st.download_button(label=f"📥 Weekly Summary.csv", data=df.groupby(["Type"])["Total Value ($)"].sum().reset_index().to_csv(index=False).encode('utf-8'), file_name="weekly_summary.csv", mime="text/csv")
    with col_file3:
        st.download_button(label=f"📥 Monthly Summary.csv", data=df.groupby(["Type"])["Total Value ($)"].sum().reset_index().to_csv(index=False).encode('utf-8'), file_name="monthly_summary.csv", mime="text/csv")
    with col_file4:
        st.download_button(label=f"📥 Yearly Summary.csv", data=df.groupby(["Type"])["Total Value ($)"].sum().reset_index().to_csv(index=False).encode('utf-8'), file_name="yearly_summary.csv", mime="text/csv")

    st.markdown("---")
    
    if st.button("🔴 Purge and Log Out of This Browser Session", use_container_width=True):
        cookie_manager.delete("secure_portfolio_data", key="del_data_widget")
        cookie_manager.delete("secure_portfolio_key", key="del_key_widget")
        st.session_state.assets = []
        st.session_state.streaming_history = []
        st.success("Browser storage successfully deleted!")
        time.sleep(1)
        st.rerun()

    if live_stream_active:
        time.sleep(refresh_interval)
        st.rerun()
