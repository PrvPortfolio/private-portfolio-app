import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json
import base64
import time
from streamlit_autorefresh import st_autorefresh

# -----------------------------------
# PAGE CONFIG
# -----------------------------------

st.set_page_config(
    page_title="Portfolio Tracker",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Auto refresh every 60 seconds
st_autorefresh(interval=60000, key="portfolio_refresh")

# -----------------------------------
# SESSION STATE
# -----------------------------------

if "assets" not in st.session_state:
    st.session_state.assets = []

if "theme" not in st.session_state:
    st.session_state.theme = "Dark"

# -----------------------------------
# THEME SELECTOR
# -----------------------------------

with st.sidebar:
    st.markdown("## ⚙️ Settings")

    theme = st.selectbox(
        "🎨 Theme",
        ["Dark", "Light"],
        index=0 if st.session_state.theme == "Dark" else 1
    )

    st.session_state.theme = theme

    currency = st.selectbox(
        "💱 Currency",
        ["USD", "EUR", "GBP", "JPY", "CAD"]
    )

# -----------------------------------
# CURRENCY SYMBOLS
# -----------------------------------

currency_symbols = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CAD": "C$"
}

conversion_rates = {
    "USD": 1,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 155,
    "CAD": 1.36
}

symbol = currency_symbols[currency]
rate = conversion_rates[currency]

# -----------------------------------
# THEME COLORS
# -----------------------------------

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


# -----------------------------------
# CUSTOM CSS
# -----------------------------------

st.markdown(f"""
<style>

.stApp {{
    background-color: {bg_color};
    color: {text_color};
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}}

.main-price {{
    font-size: clamp(36px, 8vw, 64px);
    font-weight: 500;
    letter-spacing: -2px;
    margin-bottom: 0;
}}

.return-text {{
    font-size: 18px;
    font-weight: 500;
    margin-top: -10px;
}}

.rh-green {{
    color: #00C805;
}}

.rh-red {{
    color: #FF5000;
}}

.stButton > button {{
    width: 100%;
    border-radius: 20px;
    background-color: {card_color};
    color: {text_color};
    border: none;
    padding: 10px;
}}

.stButton > button:hover {{
    border: 1px solid #00C805;
    color: #00C805;
}}

[data-testid="stSidebar"] {{
    background-color: {sidebar_color};
}}

hr {{
    border-color: #1e2124;
}}

</style>
""", unsafe_allow_html=True)

# -----------------------------------
# URL SAVE / LOAD
# -----------------------------------

def encode_portfolio(assets):
    json_str = json.dumps(assets)
    return base64.b64encode(json_str.encode()).decode()

def decode_portfolio(encoded_str):
    try:
        json_str = base64.b64decode(encoded_str.encode()).decode()
        return json.loads(json_str)
    except:
        return []

if "p" in st.query_params and len(st.session_state.assets) == 0:
    st.session_state.assets = decode_portfolio(st.query_params["p"])

def sync_to_url():
    st.query_params["p"] = encode_portfolio(st.session_state.assets)

# -----------------------------------
# SIDEBAR
# -----------------------------------

with st.sidebar:

    st.markdown("---")
    st.markdown("## 💼 Manage Portfolio")

    ticker = st.text_input(
        "Ticker",
        placeholder="AAPL or BTC-USD",
        key="ticker_input"
    ).upper().strip()

    shares = st.number_input(
        "Shares / Amount",
        min_value=0.0,
        step=0.01,
        key="shares_input"
    )

    avg_cost = st.number_input(
        "Average Cost",
        min_value=0.0,
        step=0.01,
        key="cost_input"
    )

    if st.button("➕ Add to Portfolio"):

        if ticker and shares > 0:

            st.session_state.assets = [
                a for a in st.session_state.assets
                if a['ticker'] != ticker
            ]

            st.session_state.assets.append({
                "ticker": ticker,
                "shares": shares,
                "cost": avg_cost
            })

            sync_to_url()

            # CLEAR INPUTS
            st.session_state.ticker_input = ""
            st.session_state.shares_input = 0.0
            st.session_state.cost_input = 0.0

            st.rerun()

    # -----------------------------------
    # BACKUP & RESTORE
    # -----------------------------------

    st.markdown("---")
    st.markdown("## 💾 Backup & Restore")

    uploaded_file = st.file_uploader(
        "Upload Portfolio JSON",
        type=["json"]
    )

    if uploaded_file is not None:

        try:
            uploaded_assets = json.load(uploaded_file)

            valid = True

            for item in uploaded_assets:
                if not all(k in item for k in ("ticker", "shares", "cost")):
                    valid = False

            if valid:
                st.session_state.assets = uploaded_assets
                sync_to_url()
                st.success("Portfolio Restored!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Invalid Portfolio File")

        except:
            st.error("Invalid JSON File")

    if len(st.session_state.assets) > 0:

        backup_json = json.dumps(st.session_state.assets)

        st.download_button(
            label="⬇️ Download Backup",
            data=backup_json,
            file_name="portfolio_backup.json",
            mime="application/json"
        )

        if st.button("🚨 Clear Portfolio"):
            st.session_state.assets = []
            st.query_params.clear()
            st.rerun()

# -----------------------------------
# EMPTY STATE
# -----------------------------------

if len(st.session_state.assets) == 0:

    st.markdown(
        "<h1 style='text-align:center; margin-top:120px;'>Welcome to Portfolio</h1>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<p style='text-align:center; color:gray;'>Add assets using the sidebar.</p>",
        unsafe_allow_html=True
    )

# -----------------------------------
# MAIN DASHBOARD
# -----------------------------------

else:

    intraday_series = []
    current_metrics = []
    total_cost_basis = 0

    for asset in st.session_state.assets:

        try:

            tkr = yf.Ticker(asset['ticker'])

            hist = tkr.history(
                period="1d",
                interval="1m",
                auto_adjust=True
            )

            if hist.empty:
                st.warning(f"{asset['ticker']} data unavailable.")
                continue

            close_prices = (
                hist['Close']
                .astype(float)
                * float(asset['shares'])
            )

            close_prices = (
                close_prices
                .resample("1min")
                .last()
                .ffill()
            )

            intraday_series.append(close_prices)

            current_price = hist['Close'].iloc[-1]

            value = current_price * asset['shares']
            cost = asset['cost'] * asset['shares']

            total_cost_basis += cost

            current_metrics.append({
                "ticker": asset['ticker'],
                "shares": asset['shares'],
                "value": value,
                "return": value - cost
            })

        except:
            st.warning(f"Could not load {asset['ticker']}")

    # -----------------------------------
    # BUILD PORTFOLIO CURVE
    # -----------------------------------

    if intraday_series:

        portfolio_df = pd.concat(intraday_series, axis=1)

        portfolio_df = (
            portfolio_df
            .resample("1min")
            .last()
            .ffill()
            .bfill()
        )

        portfolio_df['Total'] = portfolio_df.sum(axis=1)

        current_balance = portfolio_df['Total'].iloc[-1]
        start_balance = portfolio_df['Total'].iloc[0]

        daily_change = current_balance - start_balance
        daily_pct = (
            daily_change / start_balance * 100
            if start_balance > 0 else 0
        )

        total_return = current_balance - total_cost_basis

        # Currency conversion
        current_balance *= rate
        daily_change *= rate
        total_return *= rate

        is_up = daily_change >= 0

        chart_color = "#00C805" if is_up else "#FF5000"
        sign = "+" if is_up else ""

        # -----------------------------------
        # HEADER
        # -----------------------------------

        st.markdown(
            f"<div class='main-price'>{symbol}{current_balance:,.2f}</div>",
            unsafe_allow_html=True
        )

        st.markdown(
            f"<div class='return-text {'rh-green' if is_up else 'rh-red'}'>"
            f"{sign}{symbol}{abs(daily_change):,.2f} "
            f"({sign}{daily_pct:.2f}%) Today"
            f"</div>",
            unsafe_allow_html=True
        )

        # -----------------------------------
        # CHART
        # -----------------------------------

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=portfolio_df.index,
            y=portfolio_df['Total'] * rate,
            mode='lines',
            line=dict(
                color=chart_color,
                width=3,
                shape='spline'
            ),
            fill='tozeroy',
            fillcolor='rgba(0,200,5,0.08)' if is_up else 'rgba(255,80,0,0.08)',
            hovertemplate=f'{symbol}%{{y:,.2f}}<extra></extra>'
        ))

        fig.update_layout(
            margin=dict(l=0, r=0, t=20, b=0),
            height=350,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                showgrid=False,
                showticklabels=False,
                zeroline=False
            ),
            yaxis=dict(
                showgrid=False,
                showticklabels=False,
                zeroline=False
            ),
            hovermode="x unified"
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={'displayModeBar': False}
        )

        # -----------------------------------
        # POSITIONS
        # -----------------------------------

        st.markdown("## Positions")

        for metric in current_metrics:

            pos_up = metric['return'] >= 0

            pos_color = "#00C805" if pos_up else "#FF5000"

            pos_sign = "+" if pos_up else ""

            value_converted = metric['value'] * rate
            return_converted = metric['return'] * rate

            col1, col2, col3, col4 = st.columns([2,2,2,1])

            with col1:

                st.markdown(
                    f"""
                    **{metric['ticker']}**
                    <br>
                    <span style='color:gray; font-size:14px;'>
                    {metric['shares']} Shares
                    </span>
                    """,
                    unsafe_allow_html=True
                )

            with col2:
                pass

            with col3:

                st.markdown(
                    f"""
                    <div style='text-align:right;'>

                    **{symbol}{value_converted:,.2f}**

                    <br>

                    <span style='color:{pos_color}; font-size:14px;'>

                    {pos_sign}{symbol}{abs(return_converted):,.2f}

                    </span>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with col4:

                if st.button("❌", key=f"delete_{metric['ticker']}"):

                    st.session_state.assets = [
                        a for a in st.session_state.assets
                        if a['ticker'] != metric['ticker']
                    ]

                    sync_to_url()
                    st.rerun()

            st.markdown("<hr>", unsafe_allow_html=True)

        st.info(
            "💡 Bookmark this page to auto-remember your portfolio."
        )
