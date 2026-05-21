import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json
import base64
import time

# --- THEME CONFIG ---
def get_theme_css(mode):
    bg = "#ffffff" if mode == "Day" else "#000000"
    txt = "#000000" if mode == "Day" else "#ffffff"
    row = "#f0f0f0" if mode == "Day" else "#1e2124"
    return f"""
    <style>
    .stApp {{ background-color: {bg}; color: {txt}; }}
    .asset-row {{ border-bottom: 1px solid {row}; padding: 10px 0; }}
    </style>
    """

st.set_page_config(page_title="Portfolio Pro", layout="centered")

# --- INITIALIZATION ---
if "assets" not in st.session_state: st.session_state.assets = []
if "mode" not in st.session_state: st.session_state.mode = "Night"
if "currency" not in st.session_state: st.session_state.currency = "USD"

st.markdown(get_theme_css(st.session_state.mode), unsafe_allow_html=True)

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.session_state.mode = st.radio("Display Mode", ["Day", "Night"], index=1)
    st.session_state.currency = st.selectbox("Currency", ["USD", "EUR", "GBP"])
    st.markdown("---")
    
    ticker = st.text_input("Add Ticker").upper().strip()
    shares = st.number_input("Shares", min_value=0.0)
    cost = st.number_input("Avg Cost", min_value=0.0)
    
    if st.button("Add/Update Asset"):
        if ticker:
            st.session_state.assets = [a for a in st.session_state.assets if a['ticker'] != ticker]
            st.session_state.assets.append({"ticker": ticker, "shares": shares, "cost": cost})
            st.rerun()

    st.markdown("### Your Portfolio")
    for i, asset in enumerate(st.session_state.assets):
        col1, col2 = st.columns([3, 1])
        col1.write(f"{asset['ticker']} ({asset['shares']})")
        if col2.button("🗑️", key=f"del_{i}"):
            st.session_state.assets.pop(i)
            st.rerun()

# --- LIVE ENGINE ---
chart_placeholder = st.empty()

if not st.session_state.assets:
    st.info("Add a ticker to begin tracking.")
else:
    # Build data
    total_val = 0
    series = []
    
    for asset in st.session_state.assets:
        tkr = yf.Ticker(asset['ticker'])
        hist = tkr.history(period="1d", interval="1m")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
            total_val += (price * asset['shares'])
            series.append(hist['Close'] * asset['shares'])
    
    # Calculate daily curve
    if series:
        df = pd.concat(series, axis=1).sum(axis=1)
        
        # ROBINHOOD STYLE CHART
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df, fill='tozeroy', line=dict(color="#00C805")))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, showticklabels=False),
            margin=dict(l=0, r=0, t=0, b=0), height=300
        )
        
        chart_placeholder.plotly_chart(fig, use_container_width=True)
        st.metric("Total Portfolio Value", f"{st.session_state.currency} {total_val:,.2f}")

    # FORCE REFRESH
    time.sleep(10)
    st.rerun()
