import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json
import base64
import time
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Portfolio Tracker", layout="centered", initial_sidebar_state="expanded")

# --- INITIALIZE STATE ---
if "assets" not in st.session_state:
    if "p" in st.query_params:
        try:
            st.session_state.assets = json.loads(base64.b64decode(st.query_params["p"].encode()).decode())
        except:
            st.session_state.assets = []
    else:
        st.session_state.assets = []

if "currency" not in st.session_state: st.session_state.currency = "USD"
if "timeframe" not in st.session_state: st.session_state.timeframe = "1D"
if "timezone" not in st.session_state: st.session_state.timezone = "US/Central"

def sync_to_url():
    st.query_params["p"] = base64.b64encode(json.dumps(st.session_state.assets).encode()).decode()

# --- HARDENED LIGHT MODE ROOT INJECTION (CSS) ---
st.markdown("""
    <style>
    /* 1. HIJACK CORE THEME VARIABLES */
    :root, .stApp, [data-testid="stAppViewContainer"] {
        --background-color: #ffffff !important;
        --secondary-background-color: #f1f3f5 !important;
        --text-color: #000000 !important;
        --primary-color: #000000 !important;
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    
    /* 2. STABILIZE HEADER & LAYOUT SHIFTS DURING REFRESH */
    [data-testid="stHeader"] { background-color: transparent !important; }
    [data-testid="stHeader"] svg, #MainMenu svg, button[aria-label="User Menu"] svg { fill: #000000 !important; color: #000000 !important; }
    
    /* 3. FORCE GLOBAL TYPOGRAPHY */
    p, span, label, h3, h2, h1, div { color: #000000; }

    /* 4. EXPLICIT CONTRAST BUTTON SPECIFICITY RULES */
    button[data-testid="baseButton-secondary"] {
        background-color: #f1f3f5 !important;
        color: #000000 !important;
        border: 1px solid #cbd5e1 !important;
    }
    button[data-testid="baseButton-secondary"] span, button[data-testid="baseButton-secondary"] p {
        color: #000000 !important;
    }
    
    button[data-testid="baseButton-primary"] {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: 1px solid #000000 !important;
    }
    button[data-testid="baseButton-primary"] span, button[data-testid="baseButton-primary"] p {
        color: #ffffff !important;
    }

    /* 5. MAIN INTERFACE METRICS */
    .main-price { font-size: 64px; font-weight: 500; letter-spacing: -2px; margin-bottom: 0px; padding-bottom: 0px; color: #000000 !important; }
    .return-text { font-size: 18px; font-weight: 500; margin-top: -15px; margin-bottom: 20px; }
    .rh-green { color: #00C805 !important; }
    .rh-red { color: #FF5000 !important; }
    
    /* 6. SIDEBAR & MATRIX FORM HARDENING */
    [data-testid="stSidebar"] { background-color: #f8f9fa !important; border-right: 1px solid #e5e5ea !important; }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] h3 { color: #000000 !important; }
    .asset-row { border-bottom: 1px solid #e5e5ea; padding: 10px 0; color: #000000 !important; }
    
    div[data-testid="stForm"] { background-color: #ffffff !important; border: 1px solid #a1a1a6 !important; border-radius: 12px; padding: 15px; }
    div[data-testid="stForm"] input, 
    div[data-testid="stForm"] div[data-baseweb="select"] {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    div[data-testid="stForm"] div[data-baseweb="select"] span,
    div[data-testid="stForm"] div[data-baseweb="select"] div {
        color: #000000 !important;
    }
    
    div[data-baseweb="popover"] ul { background-color: #ffffff !important; }
    div[data-baseweb="popover"] li { color: #000000 !important; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

# --- FX RATE CONVERTER ---
@st.cache_data(ttl=60)
def get_fx_rate(target_currency):
    if target_currency == "USD": return 1.0
    try:
        fx = yf.Ticker(f"USD{target_currency}=X").history(period="1d")
        return float(fx['Close'].iloc[-1])
    except:
        return 1.0

fx_rate = get_fx_rate(st.session_state.currency)
curr_sym = {"USD": "$", "EUR": "€", "GBP": "£"}[st.session_state.currency]

# --- STOCK & CRYPTO SEARCH SUGGESTIONS LIBRARY ---
TICKER_SUGGESTIONS = [
    "--- Select a Suggestion Below ---",
    "AAPL (Apple)", "MSFT (Microsoft)", "NVDA (NVIDIA)", "TSLA (Tesla)", 
    "AMZN (Amazon)", "GOOGL (Alphabet)", "META (Meta Platforms)", "NFLX (Netflix)", 
    "AMD (Advanced Micro Devices)", "PLTR (Palantir)", "COIN (Coinbase)", "HOOD (Robinhood)",
    "VOO (S&P 500 ETF)", "SPY (S&P 500 ETF)", "QQQ (Nasdaq 100)", "IWM (Russell 2000)",
    "BTC-USD (Bitcoin)", "ETH-USD (Ethereum)", "SOL-USD (Solana)", "DOGE-USD (Dogecoin)",
    "XRP-USD (Ripple)", "ADA-USD (Cardano)"
]

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.markdown("### ⚙️ Global Controls")
    st.session_state.currency = st.selectbox("Base Currency", ["USD", "EUR", "GBP"])
    st.session_state.timezone = st.selectbox(
        "Application Timezone", 
        ["US/Central", "US/Eastern", "US/Mountain", "US/Pacific", "UTC", "Europe/London", "Europe/Berlin", "Asia/Tokyo"]
    )
    st.markdown("---")
    
    st.markdown("### ➕ Add Asset Intake")
    with st.form("add_asset_form", clear_on_submit=True):
        suggestion_select = st.selectbox("Search Suggestions", TICKER_SUGGESTIONS, index=0)
        autofill_value = suggestion_select.split(" ")[0] if suggestion_select != "--- Select a Suggestion Below ---" else ""
            
        ticker = st.text_input("Ticker Confirmation", value=autofill_value, placeholder="e.g. AAPL, VOO, BTC-USD").upper().strip()
        shares = st.number_input("Share Quantity", min_value=0.0, step=0.01)
        avg_cost = st.number_input(f"Average Cost ({curr_sym})", min_value=0.0, step=0.01)
        
        submitted = st.form_submit_button("Incorporate Asset", use_container_width=True)
        
        if submitted and ticker and shares > 0:
            base_cost = avg_cost / fx_rate 
            st.session_state.assets = [a for a in st.session_state.assets if a['ticker'] != ticker]
            st.session_state.assets.append({"ticker": ticker, "shares": shares, "cost": base_cost})
            sync_to_url()
            st.rerun()

    st.markdown("---")
    st.markdown("### 💼 Active Allocations")
    if len(st.session_state.assets) == 0:
        st.write("No active allocations found.")
    else:
        for i, asset in enumerate(st.session_state.assets):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{asset['ticker']}** ({asset['shares']} units)")
            with col2:
                if st.button("✕", key=f"del_{i}"):
                    st.session_state.assets.pop(i)
                    sync_to_url()
                    st.rerun()
                    
    st.markdown("---")
    st.markdown("### 💾 Core Backup Storage")
    uploaded_file = st.file_uploader("Upload JSON Manifest", type=["json"], label_visibility="collapsed")
    
    if uploaded_file is not None:
        try:
            data = json.load(uploaded_file)
            uploaded_assets = data["assets"] if (isinstance(data, dict) and "assets" in data) else data
                
            if uploaded_assets != st.session_state.assets:
                st.session_state.assets = uploaded_assets
                sync_to_url()
                st.success("State Restored Successfully!")
                time.sleep(0.5)
                st.rerun()
        except:
            st.error("Corrupted architecture file.")

    if len(st.session_state.assets) > 0:
        st.download_button("⬇️ Export Structural Backup", data=json.dumps(st.session_state.assets), file_name="portfolio_backup.json", mime="application/json", use_container_width=True)

# --- MASTER LAYOUT FLAG ASSIGNMENT ---
is_portfolio_empty = len(st.session_state.assets) == 0

# --- MAIN SYSTEM INTERFACE ---
if is_portfolio_empty:
    st.markdown("<h1 style='text-align:center; margin-top:100px; color:#1a1a1a;'>Asset Tracking Terminal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#6c757d;'>Engine idle. Use the configuration matrix in the sidebar to seed asset layers.</p>", unsafe_allow_html=True)

else:
    # Fetch safe historical boundaries to build clean timezone parsing slices
    tf_map = {
        "Live": ("2d", "1m"),
        "1D": ("2d", "2m"),
        "1W": ("5d", "15m"),
        "1M": ("1mo", "1d"),
        "5Y": ("5y", "1wk"),
        "ALL": ("max", "1mo")
    }
    
    t_cols = st.columns(6)
    for idx, tf_opt in enumerate(["Live", "1D", "1W", "1M", "5Y", "ALL"]):
        if t_cols[idx].button(tf_opt, use_container_width=True, type="primary" if st.session_state.timeframe == tf_opt else "secondary"):
            st.session_state.timeframe = tf_opt
            st.rerun()
            
    yf_period, yf_interval = tf_map[st.session_state.timeframe]

    intraday_series = []
    current_metrics = []
    total_cost_basis = 0.0

    for asset in st.session_state.assets:
        tkr = yf.Ticker(asset['ticker'])
        hist = tkr.history(period=yf_period, interval=yf_interval)
        
        if not hist.empty:
            if hist.index.tz is not None:
                hist.index = hist.index.tz_convert(st.session_state.timezone).tz_localize(None)
            else:
                hist.index = hist.index.tz_localize('UTC').tz_convert(st.session_state.timezone).tz_localize(None)
            
            close_prices = hist['Close'] * asset['shares'] * fx_rate
            intraday_series.append(close_prices.rename(asset['ticker']))
            current_price = hist['Close'].iloc[-1] * fx_rate
        else:
            current_price = 0.0
            
        value = current_price * asset['shares']
        cost = asset['cost'] * asset['shares'] * fx_rate
        total_cost_basis += cost
        
        current_metrics.append({
            "ticker": asset['ticker'],
            "shares": asset['shares'],
            "value": value,
            "return": value - cost
        })

    if intraday_series:
        portfolio_df = pd.concat(intraday_series, axis=1).ffill().bfill().sort_index()
        portfolio_df['Total'] = portfolio_df.sum(axis=1)
        
        # --- DATA-DRIVEN ANCHOR SYSTEM (Bypasses server clock drifts) ---
        latest_now = portfolio_df.index[-1]
        
        if st.session_state.timeframe == "Live":
            start_filter = latest_now - pd.Timedelta(hours=1)
            portfolio_df = portfolio_df[portfolio_df.index >= start_filter]
            xaxis_format = "%I:%M %p"  # Clean Time Display (e.g. 10:42 AM)
        elif st.session_state.timeframe == "1D":
            start_filter = latest_now.normalize()  # Drop everything before 12:00 AM today
            portfolio_df = portfolio_df[portfolio_df.index >= start_filter]
            xaxis_format = "%I:%M %p"  # Clean Time Display (e.g. 02:15 PM)
        elif st.session_state.timeframe in ["1W", "1M"]:
            xaxis_format = "%b %d"     # Macro Date Display (e.g. May 28)
        else:
            xaxis_format = "%Y-%m"    # Multi-Year Display (e.g. 2026-05)

        if portfolio_df.empty:
            st.info("No localized asset adjustments captured inside this time segment yet.")
        else:
            current_balance = portfolio_df['Total'].iloc[-1]
            start_balance = portfolio_df['Total'].iloc[0]
            
            delta_dollar_change = current_balance - start_balance
            delta_pct_change = (delta_dollar_change / start_balance) * 100 if start_balance > 0 else 0
            
            is_up_today = delta_dollar_change >= 0
            chart_color = "#00C805" if is_up_today else "#FF5000"
            sign = "+" if is_up_today else ""

            st.markdown(f'<div class="main-price">{curr_sym}{current_balance:,.2f}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="return-text {"rh-green" if is_up_today else "rh-red"}">{sign}{curr_sym}{abs(delta_dollar_change):,.2f} ({sign}{delta_pct_change:.2f}%) Tracking ({st.session_state.timeframe})</div>', unsafe_allow_html=True)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=portfolio_df.index, 
                y=portfolio_df['Total'],
                mode='lines',
                line=dict(color=chart_color, width=2.5),
                fill='tozeroy',
                fillcolor=f'rgba({0 if is_up_today else 255}, {200 if is_up_today else 80}, {5 if is_up_today else 0}, 0.04)',
                hoverinfo='y',
                hovertemplate=f'{curr_sym}%{{y:,.2f}}<extra></extra>'
            ))

            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                height=300,
                paper_bgcolor='rgba(255,255,255,0)', plot_bgcolor='rgba(255,255,255,0)',
                xaxis=dict(
                    showgrid=False, 
                    showticklabels=True, 
                    zeroline=False, 
                    tickfont=dict(color="#000000"),
                    tickformat=xaxis_format,       # STRIP DATES FROM BASE AXIS LABELS
                    hoverformat=xaxis_format       # STRIP DATES FROM HOVER POPUPS
                ),
                yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

            st.markdown(f"### Asset Holdings Breakdown")
            for metric in current_metrics:
                is_pos_up = metric['return'] >= 0
                pos_color = "#00C805" if is_pos_up else "#FF5000"
                pos_sign = "+" if is_pos_up else ""
                
                st.markdown(f"""
                <div class="asset-row" style="display: flex; justify-content: space-between;">
                    <div>
                        <strong>{metric['ticker']}</strong><br>
                        <span style='color:#6c757d; font-size:14px;'>{metric['shares']:,} units</span>
                    </div>
                    <div style="text-align: right;">
                        <strong>{curr_sym}{metric['value']:,.2f}</strong><br>
                        <span style='color:{pos_color}; font-size:14px;'>{pos_sign}{curr_sym}{metric['return']:,.2f}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # --- DATA ARCHIVING ARCHITECTURE ---
            st.markdown("<br>### 📥 Compliance Data Extraction Suite", unsafe_allow_html=True)
            st.write("Extract your portfolio history matrix compiled cleanly across target intervals.")
            
            csv_df = portfolio_df[['Total']].reset_index()
            csv_df.columns = ['Timestamp', f'Portfolio Value ({st.session_state.currency})']
            
            down_col1, down_col2, down_col3, down_col4 = st.columns(4)
            
            with down_col1:
                st.download_button(label="📅 Daily Ledger", data=csv_df.to_csv(index=False).encode('utf-8'), 
                                   file_name=f"daily_valuation_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
            with down_col2:
                st.download_button(label="📊 Weekly Audit", data=csv_df.iloc[::5 if len(csv_df) > 5 else 1].to_csv(index=False).encode('utf-8'), 
                                   file_name="weekly_valuation_report.csv", mime="text/csv", use_container_width=True)
            with down_col3:
                st.download_button(label="📈 Monthly Ledger", data=csv_df.iloc[::20 if len(csv_df) > 20 else 1].to_csv(index=False).encode('utf-8'), 
                                   file_name="monthly_valuation_report.csv", mime="text/csv", use_container_width=True)
            with down_col4:
                st.download_button(label="🏛️ Annual Yield", data=csv_df.iloc[::250 if len(csv_df) > 250 else 1].to_csv(index=False).encode('utf-8'), 
                                   file_name="annual_valuation_report.csv", mime="text/csv", use_container_width=True)

    # 3-Second Smooth Interface Rerun Cycle
    time.sleep(3)
    st.rerun()
