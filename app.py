import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Professional Portfolio", layout="wide")

st.markdown("""
    <style>
    /* Professional Dark Mode Overhaul */
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Inter', sans-serif; }
    .metric-value { font-size: 3rem; font-weight: 600; color: #FFFFFF; }
    .metric-delta { font-size: 1.2rem; font-weight: 400; }
    .positive { color: #00C805; }
    .negative { color: #FF5000; }
    /* Clean Cards */
    .card { background-color: #0E0E0E; padding: 20px; border-radius: 12px; border: 1px solid #1E1E1E; }
    </style>
""", unsafe_allow_html=True)

# --- APP STATE ---
if "assets" not in st.session_state: st.session_state.assets = []

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.title("Settings")
    mode = st.selectbox("Interface Mode", ["Night Vision", "Day Light"])
    currency = st.selectbox("Currency", ["USD", "EUR", "GBP"])
    st.markdown("---")
    
    with st.form("add_asset"):
        ticker = st.text_input("Ticker Symbol").upper()
        shares = st.number_input("Quantity", min_value=0.0)
        submitted = st.form_submit_button("Add Position")
        if submitted and ticker:
            st.session_state.assets.append({"ticker": ticker, "shares": shares})
            st.rerun()

# --- MAIN CONTENT ---
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Market Performance")
    chart_placeholder = st.empty()
    
    if st.session_state.assets:
        all_data = []
        for asset in st.session_state.assets:
            data = yf.Ticker(asset['ticker']).history(period="1d", interval="5m")
            if not data.empty:
                all_data.append(data['Close'] * asset['shares'])
        
        if all_data:
            portfolio = pd.concat(all_data, axis=1).sum(axis=1)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=portfolio.index, y=portfolio, 
                fill='tozeroy', line=dict(color='#00C805', width=3),
                fillcolor='rgba(0, 200, 5, 0.1)'
            ))
            fig.update_layout(
                xaxis=dict(showgrid=False, visible=False),
                yaxis=dict(showgrid=False, visible=False),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=0, r=0, t=0, b=0), height=400
            )
            chart_placeholder.plotly_chart(fig, use_container_width=True)
            
            # Metric header
            current = portfolio.iloc[-1]
            st.markdown(f'<div class="metric-value">${current:,.2f}</div>', unsafe_allow_html=True)
    else:
        st.info("Portfolio empty. Add a position to start tracking.")

with col2:
    st.subheader("Holdings")
    for i, asset in enumerate(st.session_state.assets):
        st.markdown(f"""
        <div class="card">
            <strong>{asset['ticker']}</strong><br>
            {asset['shares']} Shares
        </div>
        """, unsafe_allow_html=True)
        if st.button("Remove", key=f"del_{i}"):
            st.session_state.assets.pop(i)
            st.rerun()

# --- AUTO-REFRESH ENGINE ---
time.sleep(30)
st.rerun()
