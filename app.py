import streamlit as st
import pandas as pd
import yfinance as yf
import json
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


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
    """Decrypts AES-GCM encrypted data. Returns readable text or raises an error."""
    try:
        salt = b"StaticSaltForLocalApp"
        key = generate_key(password, salt)

        # Decode data back from plain printable text characters
        combined = base64.b64decode(cipher_text_b64.encode())

        # Unpack the parameters exactly as they were packed during encryption
        iv = combined[:12]
        tag = combined[12:28]
        ciphertext = combined[28:]

        decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag)).decryptor()
        return (decryptor.update(ciphertext) + decryptor.finalize()).decode()
    except Exception:
        raise ValueError("Incorrect password or corrupted file.")


# --- WEB PAGE INTERFACE CONFIG ---
st.set_page_config(page_title="Zero-Knowledge Portfolio Tracker", layout="wide")

st.title("🛡️ Zero-Knowledge Portfolio Tracker")
st.caption("Purely client-side tracking. Your financial data never leaves your device.")
st.markdown("---")

if "assets" not in st.session_state:
    st.session_state.assets = []

# --- NEW FEATURE: SECURE FILE UPLOAD BOX ---
st.subheader("🔓 Load an Existing Portfolio")
uploaded_file = st.file_with_container = st.file_uploader("Upload your saved 'portfolio.enc' file:", type=["enc"])
import_password = st.text_input("Enter the File Password to Unlock", type="password", key="import_pass")

if uploaded_file and import_password:
    if st.button("🔓 Decrypt & Load Data"):
        try:
            # Read the encrypted text block from the file
            file_contents = uploaded_file.read().decode()

            # Decrypt the block locally in memory
            decrypted_json_string = decrypt_data(file_contents, import_password)

            # Load the assets array back into the browser session state
            st.session_state.assets = json.loads(decrypted_json_string)
            st.success("Success! Portfolio decrypted and loaded safely in-memory.")
            st.rerun()
        except ValueError as e:
            st.error(f"❌ Decryption Failed: {e}")

st.markdown("---")

# --- SIDEBAR: ADD ASSETS MANUALLY ---
st.sidebar.header("Add to Portfolio")
asset_type = st.sidebar.selectbox("Asset Type", ["Stock", "Crypto"])
ticker = st.sidebar.text_input("Ticker Symbol (e.g., TSLA, ETH-USD)").upper().strip()
amount = st.sidebar.number_input("Amount Owned / Holdings", min_value=0.0, step=0.1)

if st.sidebar.button("Add Asset"):
    if ticker and amount > 0:
        existing_tickers = [a["ticker"] for a in st.session_state.assets]
        if ticker in existing_tickers:
            st.sidebar.warning(f"{ticker} is already in your portfolio!")
        else:
            st.session_state.assets.append({"type": asset_type, "ticker": ticker, "holdings": amount})
            st.sidebar.success(f"Added {amount} {ticker}!")
            st.rerun()
    else:
        st.sidebar.error("Please enter a valid ticker and amount.")

# --- MAIN DASHBOARD VIEW ---
if len(st.session_state.assets) == 0:
    st.info(
        "💡 Your dashboard is empty. Either upload your encrypted data profile above or add a new asset in the sidebar to begin.")
else:
    st.subheader("Your Live Dashboard")

    updated_data = []
    total_portfolio_value = 0.0

    with st.spinner("Fetching live market prices..."):
        for asset in st.session_state.assets:
            try:
                ticker_data = yf.Ticker(asset["ticker"])
                live_price = ticker_data.history(period="1d")["Close"].iloc[-1]
            except Exception:
                live_price = 0.0

            total_value = live_price * asset["holdings"]
            total_portfolio_value += total_value

            updated_data.append({
                "Type": asset["type"],
                "Ticker": asset["ticker"],
                "Holdings": asset["holdings"],
                "Live Price ($)": round(live_price, 2) if live_price > 1 else round(live_price, 6),
                "Total Value ($)": round(total_value, 2)
            })

    st.metric(label="Total Portfolio Net Worth", value=f"${total_portfolio_value:,.2f}")
    df = pd.DataFrame(updated_data)
    st.dataframe(df, use_container_width=True)

    st.markdown("---")

    # --- SECURE DATA EXPORT BOX ---
    st.subheader("🔒 Secure Data Export")
    export_password = st.text_input("Create a File Encryption Password", type="password", key="export_pass")

    if export_password:
        raw_portfolio_json = json.dumps(st.session_state.assets)
        encrypted_string = encrypt_data(raw_portfolio_json, export_password)

        st.download_button(
            label="⬇️ Download Encrypted Portfolio File (.enc)",
            data=encrypted_string,
            file_name="portfolio.enc",
            mime="text/plain"
        )
        st.success("🔒 Portfolio encrypted! Click the download button to save your backup.")

    if st.button("🔴 Clear Active Session"):
        st.session_state.assets = []
        st.rerun()
