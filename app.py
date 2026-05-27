import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json
import base64
import time

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

if "theme" not in st.session_state: st.session_state.theme = "Night Vision"
if "currency" not in st.session_state: st.session_state.currency = "USD"

def sync_to_url():
    st.query_params["p"] = base64.b64encode(json.dumps(st.session_state.assets).encode()).decode()

# --- THEME CSS INJECTION ---
bg_color = "#000000" if st.session_state.theme == "Night Vision" else "#ffffff"
text_color = "#ffffff" if st.session_state.theme == "Night Vision" else "#000000"
sidebar_bg = "#0e0f11" if st.session_state.theme == "Night Vision" else "#f7f7f8"
border_color = "#1e2124" if st.session_state.theme == "Night Vision" else "#e5e5ea"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}
    .main-price {{ font-size: 64px; font-weight: 500; letter-spacing: -2px; margin-bottom: 0px; padding-bottom: 0px; }}
    .return-text {{ font-size: 18px; font-weight: 500; margin-top: -15px; margin-bottom: 20px; }}
    .rh-green {{ color: #00C805; }}
    .rh-red {{ color: #FF5000; }}
    [data-testid="stSidebar"] {{ background-color: {sidebar_bg}; }}
    .asset-row {{ border-bottom: 1px solid {border_color}; padding: 10px 0; }}
    </style>
""", unsafe_allow_html=True)

# --- FX RATE CONVERTER ---
@st.cache_data(ttl=300)
def get_fx_rate(target_currency):
    if target_currency == "USD": return 1.0
    try:
        fx = yf.Ticker(f"USD{target_currency}=X").history(period="1d")
        return float(fx['Close'].iloc[-1])
    except:
        return 1.0

fx_rate = get_fx_rate(st.session_state.currency)
curr_sym = {"USD": "$", "EUR": "€", "GBP": "£"}[st.session_state.currency]

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    st.session_state.theme = st.radio("Display Theme", ["Night Vision", "Day Light"], horizontal=True)
    st.session_state.currency = st.selectbox("Currency Output", ["USD", "EUR", "GBP"])
    st.markdown("---")
    
    st.markdown("### ➕ Add Asset")
    # Using st.form automatically blanks the inputs when submitted
    with st.form("add_asset_form", clear_on_submit=True):
        ticker = st.text_input("Ticker (e.g. AAPL, VOO)").upper().strip()
        shares = st.number_input("Shares", min_value=0.0, step=0.01)
        avg_cost = st.number_input(f"Average Cost ({curr_sym})", min_value=0.0, step=0.01)
        submitted = st.form_submit_button("Add to Portfolio", use_container_width=True)
        
        if submitted and ticker and shares > 0:
            # Convert cost back to USD base for internal tracking if needed, or assume cost is in local
            base_cost = avg_cost / fx_rate 
            st.session_state.assets = [a for a in st.session_state.assets if a['ticker'] != ticker]
            st.session_state.assets.append({"ticker": ticker, "shares": shares, "cost": base_cost})
            sync_to_url()
            st.rerun()

    st.markdown("---")
    st.markdown("### 💼 Current Positions")
    if not st.session_state.assets:
        st.write("No assets yet.")
    else:
        for i, asset in enumerate(st.session_state.assets):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{asset['ticker']}** ({asset['shares']})")
            with col2:
                if st.button("✕", key=f"del_{i}"):
                    st.session_state.assets.pop(i)
                    sync_to_url()
                    st.rerun()
                    
    st.markdown("---")
    st.markdown("### 💾 Backup & Restore")
    uploaded_file = st.file_uploader("Restore from File", type=["json"], label_visibility="collapsed")
    if uploaded_file is not None:
        try:
            st.session_state.assets = json.load(uploaded_file)
            sync_to_url()
            st.success("Restored!")
            time.sleep(1)
            st.rerun()
        except:
            st.error("Invalid file.")

    if st.session_state.assets:
        st.download_button("⬇️ Download Backup", data=json.dumps(st.session_state.assets), file_name="portfolio_backup.json", mime="application/json", use_container_width=True)

# --- MAIN DASHBOARD: ROBINHOOD CLONE ---
if len(st.session_state.assets) == 0:
    st.markdown(f"<h1 style='text-align:center; margin-top:100px; color:{text_color};'>Welcome to Portfolio.</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#8a93a6;'>Use the sidebar to add your assets or upload a backup file.</p>", unsafe_allow_html=True)

else:
    intraday_series = []
    current_metrics = []
    total_cost_basis = 0.0

    for asset in st.session_state.assets:
        tkr = yf.Ticker(asset['ticker'])
        hist = tkr.history(period="1d", interval="1m")
        
        if not hist.empty:
            # FIX: Strip timezones so different stocks merge perfectly without creating a flatline
            hist.index = hist.index.tz_localize(None) 
            close_prices = hist['Close'] * asset['shares'] * fx_rate
            intraday_series.append(close_prices.rename(asset['ticker']))
            
            current_price = hist['Close'].iloc[-1] * fx_rate
        else:
            current_price = 0
            
        value = current_price * asset['shares']
        cost = asset['cost'] * asset['shares'] * fx_rate
        total_cost_basis += cost
        
        current_metrics.append({
            "ticker": asset['ticker'],
            "shares": asset['shares'],
            "value": value,
            "return": value - cost
        })

    # Compile the Master Curve
    if intraday_series:
        # FIX: Forward fill missing minutes so the line doesn't break
        portfolio_df = pd.concat(intraday_series, axis=1).ffill().bfill()
        portfolio_df['Total'] = portfolio_df.sum(axis=1)
        
        current_balance = portfolio_df['Total'].iloc[-1]
        start_balance = portfolio_df['Total'].iloc[0]
        
        daily_dollar_change = current_balance - start_balance
        daily_pct_change = (daily_dollar_change / start_balance) * 100 if start_balance > 0 else 0
        
        is_up_today = daily_dollar_change >= 0
        chart_color = "#00C805" if is_up_today else "#FF5000"
        sign = "+" if is_up_today else ""

        # Render Header
        st.markdown(f'<div class="main-price">{curr_sym}{current_balance:,.2f}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="return-text {"rh-green" if is_up_today else "rh-red"}">{sign}{curr_sym}{abs(daily_dollar_change):,.2f} ({sign}{daily_pct_change:.2f}%) Today</div>', unsafe_allow_html=True)
        
        # Render Robinhood Chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=portfolio_df.index, 
            y=portfolio_df['Total'],
            mode='lines',
            line=dict(color=chart_color, width=2.5),
            fill='tozeroy',
            fillcolor=f'rgba({0 if is_up_today else 255}, {200 if is_up_today else 80}, {5 if is_up_today else 0}, 0.1)',
            hoverinfo='y',
            hovertemplate=f'{curr_sym}%{{y:,.2f}}<extra></extra>'
        ))

        fig.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            height=320,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # Render Position List
        st.markdown(f"### Positions")
        for metric in current_metrics:
            is_pos_up = metric['return'] >= 0
            pos_color = "#00C805" if is_pos_up else "#FF5000"
            pos_sign = "+" if is_pos_up else ""
            
            st.markdown(f"""
            <div class="asset-row" style="display: flex; justify-content: space-between;">
                <div>
                    <strong>{metric['ticker']}</strong><br>
                    <span style='color:#8a93a6; font-size:14px;'>{metric['shares']} Shares</span>
                </div>
                <div style="text-align: right;">
                    <strong>{curr_sym}{metric['value']:,.2f}</strong><br>
                    <span style='color:{pos_color}; font-size:14px;'>{pos_sign}{curr_sym}{metric['return']:,.2f}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Force continuous refresh for live market data
    time.sleep(20)
    st.rerun()
