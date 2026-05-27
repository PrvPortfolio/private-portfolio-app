import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json
import base64
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Portfolio Tracker", layout="centered", initial_sidebar_state="expanded")

# --- ROBINHOOD THEME CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
    .main-price { font-size: 64px; font-weight: 500; letter-spacing: -2px; margin-bottom: 0px; padding-bottom: 0px; }
    .return-text { font-size: 18px; font-weight: 500; margin-top: -15px; margin-bottom: 20px;}
    .rh-green { color: #00C805; }
    .rh-red { color: #FF5000; }
    .stButton>button { width: 100%; border-radius: 20px; background-color: #1e2124; color: white; border: none; }
    .stButton>button:hover { border: 1px solid #00C805; color: #00C805; }
    .asset-row { border-bottom: 1px solid #1e2124; padding: 10px 0; }
    [data-testid="stSidebar"] { background-color: #0e0f11; }
    </style>
""", unsafe_allow_html=True)

# --- STATE MANAGEMENT (URL BOOKMARKING) ---
def encode_portfolio(assets):
    json_str = json.dumps(assets)
    return base64.b64encode(json_str.encode()).decode()

def decode_portfolio(encoded_str):
    try:
        json_str = base64.b64decode(encoded_str.encode()).decode()
        return json.loads(json_str)
    except:
        return []

if "assets" not in st.session_state:
    # Try to load from URL first
    if "p" in st.query_params:
        st.session_state.assets = decode_portfolio(st.query_params["p"])
    else:
        st.session_state.assets = []

def sync_to_url():
    st.query_params["p"] = encode_portfolio(st.session_state.assets)

# --- SIDEBAR: ASSET INTAKE & UPLOAD ---
with st.sidebar:
    st.markdown("### 💼 Manage Portfolio")
    
    with st.expander("➕ Add Asset", expanded=True):
        ticker = st.text_input("Ticker", placeholder="AAPL, BTC-USD").upper().strip()
        shares = st.number_input("Amount / Shares", min_value=0.0, step=0.01)
        avg_cost = st.number_input("Average Cost ($)", min_value=0.0, step=0.01)
        
        if st.button("Add to Portfolio"):
            if ticker and shares > 0:
                # Remove if exists to update
                st.session_state.assets = [a for a in st.session_state.assets if a['ticker'] != ticker]
                st.session_state.assets.append({"ticker": ticker, "shares": shares, "cost": avg_cost})
                sync_to_url()
                st.rerun()

    st.markdown("---")
    st.markdown("### 💾 Backup & Restore")
    st.write("Upload a previously saved `.json` file to restore your portfolio instantly.")
    
    uploaded_file = st.file_uploader("Upload Portfolio JSON", type=["json"], label_visibility="collapsed")
    if uploaded_file is not None:
        try:
            st.session_state.assets = json.load(uploaded_file)
            sync_to_url()
            st.success("Portfolio Restored!")
            time.sleep(1)
            st.rerun()
        except:
            st.error("Invalid file.")

    if len(st.session_state.assets) > 0:
        backup_json = json.dumps(st.session_state.assets)
        st.download_button(
            label="⬇️ Download Backup File",
            data=backup_json,
            file_name="my_portfolio_backup.json",
            mime="application/json"
        )
        
        if st.button("🚨 Clear Portfolio"):
            st.session_state.assets = []
            st.query_params.clear()
            st.rerun()

# --- MAIN DASHBOARD: THE ROBINHOOD CLONE ---
if len(st.session_state.assets) == 0:
    st.markdown("<h1 style='text-align:center; margin-top:100px; color:#4a4b50;'>Welcome to Portfolio.</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#8a93a6;'>Use the sidebar to add your assets or upload a backup file.</p>", unsafe_allow_html=True)

else:
    # 1. Fetch Intraday Data to build the daily curve
    intraday_series = []
    current_metrics = []
    total_cost_basis = 0.0

    for asset in st.session_state.assets:
        tkr = yf.Ticker(asset['ticker'])
        # Get minute-by-minute data for the day
        hist = tkr.history(period="1d", interval="1m")
        
        if not hist.empty:
            close_prices = hist['Close'] * asset['shares']
            intraday_series.append(close_prices)
            current_price = hist['Close'].iloc[-1]
            previous_close = hist['Close'].iloc[0] # Roughly today's open/previous close
        else:
            # Fallback for illiquid assets
            current_price = 0
            previous_close = 0
            
        value = current_price * asset['shares']
        cost = asset['cost'] * asset['shares']
        total_cost_basis += cost
        
        current_metrics.append({
            "ticker": asset['ticker'],
            "shares": asset['shares'],
            "price": current_price,
            "value": value,
            "return": value - cost
        })

    # 2. Compile the Portfolio Curve
    if intraday_series:
        # Align timestamps and sum
        portfolio_df = pd.concat(intraday_series, axis=1).ffill().bfill()
        portfolio_df['Total'] = portfolio_df.sum(axis=1)
        
        current_balance = portfolio_df['Total'].iloc[-1]
        start_balance = portfolio_df['Total'].iloc[0]
        
        daily_dollar_change = current_balance - start_balance
        daily_pct_change = (daily_dollar_change / start_balance) * 100 if start_balance > 0 else 0
        
        total_dollar_change = current_balance - total_cost_basis
        total_pct_change = (total_dollar_change / total_cost_basis) * 100 if total_cost_basis > 0 else 0
        
        # Determine Color (Robinhood Green vs Robinhood Red)
        is_up_today = daily_dollar_change >= 0
        chart_color = "#00C805" if is_up_today else "#FF5000"
        sign = "+" if is_up_today else ""

        # 3. Render the Header
        st.markdown(f'<div class="main-price">${current_balance:,.2f}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="return-text {"rh-green" if is_up_today else "rh-red"}">{sign}${abs(daily_dollar_change):,.2f} ({sign}{daily_pct_change:.2f}%) Today</div>', unsafe_allow_html=True)
        
        # 4. Render the Minimalist Plotly Chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=portfolio_df.index, 
            y=portfolio_df['Total'],
            mode='lines',
            line=dict(color=chart_color, width=2),
            fill='tozeroy',
            fillcolor=f'rgba({0 if is_up_today else 255}, {200 if is_up_today else 80}, {5 if is_up_today else 0}, 0.1)',
            hoverinfo='y',
            hovertemplate='$%{y:,.2f}<extra></extra>'
        ))

        fig.update_layout(
            margin=dict(l=0, r=0, t=20, b=0),
            height=300,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False, rangeslider=dict(visible=False)),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # 5. Render Positions List
        st.markdown("### Positions")
        for metric in current_metrics:
            is_pos_up = metric['return'] >= 0
            pos_color = "#00C805" if is_pos_up else "#FF5000"
            pos_sign = "+" if is_pos_up else ""
            
            col1, col2, col3 = st.columns([2, 2, 2])
            with col1:
                st.markdown(f"**{metric['ticker']}**<br><span style='color:#8a93a6; font-size:14px;'>{metric['shares']} Shares</span>", unsafe_allow_html=True)
            with col2:
                # Spacing
                pass
            with col3:
                st.markdown(f"<div style='text-align:right;'>**${metric['value']:,.2f}**<br><span style='color:{pos_color}; font-size:14px;'>{pos_sign}${metric['return']:,.2f}</span></div>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 0.5em 0; border-color: #1e2124;'>", unsafe_allow_html=True)

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.info("💡 **How to Auto-Remember:** Your portfolio is securely encoded in the URL address bar above. **Bookmark this page right now.** Whenever you click that bookmark, your portfolio loads instantly.")
