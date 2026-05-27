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

def sync_to_url():
    st.query_params["p"] = base64.b64encode(json.dumps(st.session_state.assets).encode()).decode()

# --- LOCKED DAY MODE THEMING (CSS) ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #000000; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
    .main-price { font-size: 64px; font-weight: 500; letter-spacing: -2px; margin-bottom: 0px; padding-bottom: 0px; color: #000000; }
    .return-text { font-size: 18px; font-weight: 500; margin-top: -15px; margin-bottom: 20px; }
    .rh-green { color: #00C805; }
    .rh-red { color: #FF5000; }
    [data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #e5e5ea; }
    .asset-row { border-bottom: 1px solid #e5e5ea; padding: 10px 0; color: #000000; }
    div[data-testid="stForm"] { background-color: #ffffff; border: 1px solid #e5e5ea; border-radius: 12px; }
    p, span, label, h3 { color: #000000 !important; }
    /* Horizontal selector styling */
    div['data-testid="stHorizontalBlock"'] button { background-color: #f1f3f5 !important; color: #000000 !important; }
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

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.markdown("### ⚙️ Global Controls")
    st.session_state.currency = st.selectbox("Base Currency", ["USD", "EUR", "GBP"])
    st.markdown("---")
    
    st.markdown("### ➕ Add Asset Intake")
    with st.form("add_asset_form", clear_on_submit=True):
        ticker = st.text_input("Ticker Symbol (e.g. NVDA, VOO)").upper().strip()
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
    if Pis_empty := (len(st.session_state.assets) == 0):
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
            st.session_state.assets = json.load(uploaded_file)
            sync_to_url()
            st.success("State Restored Successfully!")
            time.sleep(0.5)
            st.rerun()
        except:
            st.error("Corrupted architecture file.")

    if not Pis_empty:
        st.download_button("⬇️ Export Structural Backup", data=json.dumps(st.session_state.assets), file_name="portfolio_backup.json", mime="application/json", use_container_width=True)

# --- MAIN SYSTEM INTERFACE ---
if Pis_empty:
    st.markdown("<h1 style='text-align:center; margin-top:100px; color:#1a1a1a;'>Asset Tracking Terminal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#6c757d;'>Engine idle. Use the configuration matrix in the sidebar to seed asset layers.</p>", unsafe_allow_html=True)

else:
    # Timeframe Config Matrix Map
    # Map selection to (yfinance_period, yfinance_interval)
    tf_map = {
        "Live": ("1d", "1m"),
        "1D": ("1d", "2m"),
        "1W": ("5d", "15m"),
        "1M": ("1mo", "1d"),
        "5Y": ("5y", "1wk"),
        "ALL": ("max", "1mo")
    }
    
    # Render Timeframe Toolbar Component
    t_cols = st.columns(6)
    for idx, tf_opt in enumerate(["Live", "1D", "1W", "1M", "5Y", "ALL"]):
        if t_cols[idx].button(tf_opt, use_container_width=True, type="primary" if st.session_state.timeframe == tf_opt else "secondary"):
            st.session_state.timeframe = tf_opt
            st.rerun()
            
    yf_period, yf_interval = tf_map[st.session_state.timeframe]

    intraday_series = []
    current_metrics = []
    total_cost_basis = 0.0

    # Data Fetching Routine
    for asset in st.session_state.assets:
        tkr = yf.Ticker(asset['ticker'])
        hist = tkr.history(period=yf_period, interval=yf_interval)
        
        if not hist.empty:
            hist.index = hist.index.tz_localize(None) 
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
        portfolio_df = pd.concat(intraday_series, axis=1).ffill().bfill()
        portfolio_df['Total'] = portfolio_df.sum(axis=1)
        
        current_balance = portfolio_df['Total'].iloc[-1]
        start_balance = portfolio_df['Total'].iloc[0]
        
        delta_dollar_change = current_balance - start_balance
        delta_pct_change = (delta_dollar_change / start_balance) * 100 if start_balance > 0 else 0
        
        is_up_today = delta_dollar_change >= 0
        chart_color = "#00C805" if is_up_today else "#FF5000"
        sign = "+" if is_up_today else ""

        # Main Header Numbers
        st.markdown(f'<div class="main-price">{curr_sym}{current_balance:,.2f}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="return-text {"rh-green" if is_up_today else "rh-red"}">{sign}{curr_sym}{abs(delta_dollar_change):,.2f} ({sign}{delta_pct_change:.2f}%) Space ({st.session_state.timeframe})</div>', unsafe_allow_html=True)
        
        # High-Fidelity Chart Generation
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
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # Asset Manifest Output List
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

        # --- DATA ARCHIVING AND COMPILATION COMPONENT ---
        st.markdown("<br>### 📥 Compliance Data Extraction Suite", unsafe_allow_html=True)
        st.write("Extract your portfolio pricing matrix history compiled cleanly across target structural milestones.")
        
        # Generation of target historical windows for csv serialization
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

    # 1-Second Execution Loop Refresh Trigger
    time.sleep(1)
    st.rerun()
