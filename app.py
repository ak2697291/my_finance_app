import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Page Configuration for Mobile viewports
st.set_page_config(
    page_title="Finance Management",
    page_icon="📊",
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# Deep-clean UI canvas to present a native fullscreen app wrapper on Android
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div.block-container{padding-top:1.5rem; padding-bottom:1.5rem;}
    [data-testid="stMetricValue"] {font-size: 1.8rem; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

# 2. Establish Secure Connection via Cloud Secrets Environment
# It dynamically reads from your environment configuration without revealing your link to GitHub
try:
    SPREADSHEET_URL = st.secrets["SPREADSHEET_URL"]
except KeyError:
    st.error("Missing Environment Secret: Please add 'SPREADSHEET_URL' to your Streamlit dashboard secrets dashboard.")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=30) # Dynamic cache refreshing every 30 seconds for live updates
def load_sheet_data(worksheet_name):
    return conn.read(spreadsheet=SPREADSHEET_URL, worksheet=worksheet_name)

# Safe Data Extraction Phase
try:
    df_invested = load_sheet_data("invested")
    df_summary = load_sheet_data("StockMarketPortfolioSummary")
    df_strategy = load_sheet_data("investmentStrategy")
    df_wealth = load_sheet_data("TotalWealth")
except Exception as e:
    st.error("Error linking to live sheet. Confirm your spreadsheet key and dashboard permission settings.")
    st.stop()

# Clean up structural trailing spacing in dataframes
df_invested = df_invested.dropna(subset=[df_invested.columns[0]])
df_summary = df_summary.dropna(subset=[df_summary.columns[0]])
df_strategy = df_strategy.dropna(subset=[df_strategy.columns[0]])
df_wealth = df_wealth.dropna(subset=[df_wealth.columns[0]])

# 3. Dynamic Global Metric Engine
st.title("📱 Live Portfolio Hub")

# Locate current value totals dynamically from the column structures
val_col = [c for c in df_summary.columns if 'value' in c.lower() or 'allocation' in c.lower()][0]
inv_col = [c for c in df_invested.columns if 'invested' in c.lower()][0]
cur_col = [c for c in df_invested.columns if 'current' in c.lower() and 'value' in c.lower()][0]

total_invested_calc = pd.to_numeric(df_invested[inv_col], errors='coerce').sum()
total_current_calc = pd.to_numeric(df_invested[cur_col], errors='coerce').sum()
net_pl_calc = total_current_calc - total_invested_calc
pl_pct_calc = (net_pl_calc / total_invested_calc) * 100 if total_invested_calc > 0 else 0

col1, col2 = st.columns(2)
col1.metric("Live Market Value", f"₹{total_current_calc:,.2f}", f"+{pl_pct_calc:.2f}%")
col2.metric("Absolute P&L", f"₹{net_pl_calc:,.2f}")

# 4. Mobile Bottom Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📈 Holdings", "📊 Assets", "🎯 Strategy", "💰 Net Worth"])

# --- TAB 1: HOLDINGS TRACKER ---
with tab1:
    st.subheader("Asset Performance Matrix")
    status_col = [c for c in df_invested.columns if 'status' in c.lower()][0]
    unique_statuses = ["ALL"] + list(df_invested[status_col].dropna().unique())
    status_filter = st.selectbox("Filter Position Status", unique_statuses)
    
    df_filtered = df_invested.copy()
    if status_filter != "ALL":
        df_filtered = df_filtered[df_filtered[status_col] == status_filter]
        
    st.dataframe(df_filtered.set_index(df_filtered.columns[0]), use_container_width=True)

# --- TAB 2: PORTFOLIO BREAKDOWNS ---
with tab2:
    st.subheader("Live Allocation Spread")
    label_col = df_summary.columns[0]
    st.bar_chart(data=df_summary, x=label_col, y=val_col)
    st.dataframe(df_summary.set_index(label_col), use_container_width=True)

# --- TAB 3: DYNAMIC INVESTMENT STRATEGY ---
with tab3:
    st.subheader("Rules-Based Target Planner")
    pct_col = [c for c in df_strategy.columns if '%' in c or 'target' in c.lower() or 'allocation' in c.lower()][0]
    cat_col = df_strategy.columns[0]
    
    salary_row = df_strategy[df_strategy[cat_col].str.contains('Salary|Income', case=False, na=False)]
    base_salary = 130000 
    if not salary_row.empty:
        val_idx = [c for c in df_strategy.columns if c != cat_col and c != pct_col][0]
        base_salary = pd.to_numeric(salary_row.iloc[0][val_idx], errors='coerce') or 130000

    target_invest = st.slider("Modify Monthly Target (₹)", int(base_salary*0.1), int(base_salary*0.9), int(base_salary*0.6), step=2000)
    st.markdown(f"**Target Breakdown for ₹{target_invest:,}:**")
    
    strategy_rows = df_strategy[~df_strategy[cat_col].str.contains('Salary|Expense|Total|Cash', case=False, na=False)]
    for _, row in strategy_rows.iterrows():
        raw_pct = row[pct_col]
        if isinstance(raw_pct, str):
            pct_val = float(raw_pct.replace('%', '')) / 100 if '%' in raw_pct else float(raw_pct)
        else:
            pct_val = float(raw_pct) if float(raw_pct) <= 1 else float(raw_pct) / 100
            
        calculated_allocation = target_invest * pct_val
        st.write(f"▪️ **{row[cat_col]} ({pct_val*100:.1f}%):** ₹{calculated_allocation:,.2f}")

# --- TAB 4: COMPLETE NET WORTH MONITOR ---
with tab4:
    st.subheader("Aggregated Financial Footprint")
    w_cat = df_wealth.columns[0]
    w_val = [c for c in df_wealth.columns if 'value' in c.lower() or 'amount' in c.lower() or 'total' in c.lower()][0]
    
    st.dataframe(df_wealth.set_index(w_cat), use_container_width=True)
    st.caption("🔄 Live sync secure operational framework.")
