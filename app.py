import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json
import base64
from streamlit_autorefresh import st_autorefresh

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(
    page_title="Portfolio Tracker",
    layout="centered",
    initial_sidebar_state="expanded"
)

# auto refresh (live chart)
st_autorefresh(interval=60000, key="refresh")

# -------------------------------
# SESSION STATE
# -------------------------------
if "assets" not in st.session_state:
    st.session_state.assets = []

if "theme" not in st.session_state:
    st.session_state.theme = "Dark"

# -------------------------------
# SIDEBAR SETTINGS
# -------------------------------
with st.sidebar:
    st.title("Settings")

    theme = st.selectbox("Theme", ["Dark", "Light"])
    currency = st.selectbox("Currency", ["USD", "EUR", "GBP", "JPY", "CAD"])

    st.session_state.theme = theme

# -------------------------------
# CURRENCY
# -------------------------------
currency_symbols = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CAD": "C$"
}

rates = {
    "USD": 1,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 155,
    "CAD": 1.36
}

symbol = currency_symbols[currency]
rate = rates[currency]

# -------------------------------
# THEME (GRAY DARK MODE)
# -------------------------------
if theme == "Dark":
    bg_color = "#181A20"
    text_color = "#EDEDED"
    sidebar_color = "#22252B"
    card_color = "#2D3138"
else:
    bg_color = "#ffffff"
    text_color = "#000000"
    sidebar_color = "#f3f3f3"
    card_color = "#e9e9e9"

st.markdown(f"""
<style>
.stApp {{
    background-color: {bg_color};
    color: {text_color};
    font-family: -apple-system;
}}

.stButton>button {{
    width: 100%;
    border-radius: 10px;
    background-color: {card_color};
    color: {text_color};
}}

[data-testid="stSidebar"] {{
    background-color: {sidebar_color};
}}

</style>
""", unsafe_allow_html=True)

# -------------------------------
# SIDEBAR INPUT
# -------------------------------
with st.sidebar:

    st.subheader("Add Asset")

    ticker = st.text_input("Ticker").upper().strip()
    shares = st.number_input("Shares", min_value=0.0, step=0.1)
    cost = st.number_input("Avg Cost", min_value=0.0, step=0.1)

    if st.button("Add") and ticker:

        st.session_state.assets = [
            a for a in st.session_state.assets
            if a["ticker"] != ticker
        ]

        st.session_state.assets.append({
            "ticker": ticker,
            "shares": shares,
            "cost": cost
        })

        st.rerun()

# -------------------------------
# EMPTY STATE
# -------------------------------
if len(st.session_state.assets) == 0:
    st.title("Portfolio Tracker")
    st.write("Add stocks in the sidebar.")
    st.stop()

# -------------------------------
# DATA FETCH
# -------------------------------
series_list = []
metrics = []

for asset in st.session_state.assets:

    try:
        tkr = yf.Ticker(asset["ticker"])
        hist = tkr.history(period="1d", interval="1m")

        if hist.empty:
            continue

        values = hist["Close"] * asset["shares"]
        series_list.append(values)

        current_price = hist["Close"].iloc[-1]

        value = current_price * asset["shares"]
        cost_val = asset["cost"] * asset["shares"]

        metrics.append({
            "ticker": asset["ticker"],
            "value": value,
            "return": value - cost_val,
            "shares": asset["shares"]
        })

    except:
        continue

# -------------------------------
# PORTFOLIO CALC
# -------------------------------
df = pd.concat(series_list, axis=1)
df = df.ffill().bfill()
df["Total"] = df.sum(axis=1)

current = df["Total"].iloc[-1] * rate
start = df["Total"].iloc[0] * rate

change = current - start
pct = (change / start) * 100 if start else 0

color = "#00C805" if change >= 0 else "#FF4D4D"

# -------------------------------
# HEADER
# -------------------------------
st.title(f"{symbol}{current:,.2f}")

st.markdown(
    f"<h4 style='color:{color}'>{symbol}{change:,.2f} ({pct:.2f}%) Today</h4>",
    unsafe_allow_html=True
)

# -------------------------------
# CHART
# -------------------------------
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df.index,
    y=df["Total"] * rate,
    mode="lines",
    line=dict(color=color, width=2),
    fill="tozeroy",
    fillcolor="rgba(0,200,5,0.1)" if change >= 0 else "rgba(255,0,0,0.1)"
))

fig.update_layout(
    height=350,
    margin=dict(l=0, r=0, t=0, b=0),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(showgrid=False, showticklabels=False),
    yaxis=dict(showgrid=False, showticklabels=False)
)

st.plotly_chart(fig, use_container_width=True)

# -------------------------------
# POSITIONS
# -------------------------------
st.subheader("Positions")

for m in metrics:

    col1, col2, col3 = st.columns([3, 2, 1])

    with col1:
        st.write(m["ticker"])

    with col2:
        st.write(f"{symbol}{m['value']*rate:,.2f}")

    with col3:
        if st.button("❌", key=m["ticker"]):
            st.session_state.assets = [
                a for a in st.session_state.assets
                if a["ticker"] != m["ticker"]
            ]
            st.rerun()
