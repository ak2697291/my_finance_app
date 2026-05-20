import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import logging
import sys

# Configure standard logging to output straight to the Streamlit console logs
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

st.set_page_config(
    page_title="Finance Management Debug",
    page_icon="📊",
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# Deep-clean UI canvas for mobile viewports
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div.block-container{padding-top:1.5rem; padding-bottom:1.5rem;}
    </style>
""", unsafe_allow_html=True)

st.title("📱 Live Portfolio Hub")

# 1. Check Secrets Configuration
logging.info("--- STARTING WORKSHEET EXTRACTION PIPELINE ---")
try:
    SPREADSHEET_URL = st.secrets["SPREADSHEET_URL"]
    logging.info("SUCCESS: 'SPREADSHEET_URL' successfully retrieved from Secrets.")
except KeyError:
    logging.error("CRITICAL: 'SPREADSHEET_URL' key is completely missing from Secrets dashboard!")
    st.error("Missing Environment Secret: Please add 'SPREADSHEET_URL' to your Streamlit dashboard secrets.")
    st.stop()

# 2. Establish Connection Engine
logging.info("Initializing GSheetsConnection engine...")
conn = st.connection("gsheets", type=GSheetsConnection)

# Helper function to load and print sheet structures to logs
def debug_load_sheet(sheet_name):
    logging.info(f"Attempting live fetch for tab name: '{sheet_name}'")
    try:
        # Lowering cache TTL to 5 seconds during active debugging
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=sheet_name, ttl=5)
        logging.info(f"SUCCESS: Fetched '{sheet_name}'. Shape: {df.shape}. Columns found: {list(df.columns)}")
        return df
    except Exception as raw_error:
        logging.error(f"FAILURE: Could not read sheet '{sheet_name}'. Details: {str(raw_error)}")
        # Raise exception to catch globally inside app
        raise raw_error

# 3. Step-by-Step Data Extraction
data_loaded = True
error_diagnostics = {}

sheets_to_load = ["invested", "StockMarketPortfolioSummary", "investmentStrategy", "TotalWealth"]
loaded_dfs = {}

for sheet in sheets_to_load:
    try:
        loaded_dfs[sheet] = debug_load_sheet(sheet)
    except Exception as e:
        data_loaded = False
        error_diagnostics[sheet] = str(e)

# If any tab fails, present a rich error screen on your phone to pinpoint the exact failure point
if not data_loaded:
    st.error("❌ Connection Pipeline Blocked")
    st.markdown("### 🔍 Diagnostic Report")
    st.write("The connection engine reached Google, but failed to process individual tabs. Check the status matrix below:")
    
    for sheet in sheets_to_load:
        if sheet in loaded_dfs:
            st.success(f"**Tab '{sheet}':** Loaded perfectly ({len(loaded_dfs[sheet])} rows detected)")
        else:
            st.error(f"**Tab '{sheet}':** FAILED")
            st.code(f"Error Message: {error_diagnostics.get(sheet)}")
            
    st.info("💡 **Next Step:** Check the 'Manage app' console log pane in the bottom right corner of your Streamlit Cloud web dashboard to see the full system stack trace.")
    st.stop()

# Assign successfully loaded dataframes
df_invested = loaded_dfs["invested"]
df_summary = loaded_dfs["StockMarketPortfolioSummary"]
df_strategy = loaded_dfs["investmentStrategy"]
df_wealth = loaded_dfs["TotalWealth"]

# Clean up trailing structural padding rows
df_invested = df_invested.dropna(subset=[df_invested.columns[0]])
df_summary = df_summary.dropna(subset=[df_summary.columns[0]])
df_strategy = df_strategy.dropna(subset=[df_strategy.columns[0]])
df_wealth = df_wealth.dropna(subset=[df_wealth.columns[0]])

logging.info("All sheets successfully parsed and sanitized. Building layouts...")

# 4. Global Performance Cards Engine
try:
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
except Exception as layout_err:
    logging.error(f"CRITICAL: Structural mapping error while computing dashboard layout columns: {str(layout_err)}")
    st.error(f"Data mapping discrepancy: {str(layout_err)}")
    st.stop()

# 5. Mobile Tab Selection Elements
tab1, tab2, tab3, tab4 = st.tabs(["📈 Holdings", "📊 Assets", "🎯 Strategy", "💰 Net Worth"])

with tab1:
    st.subheader("Asset Performance Matrix")
    status_col = [c for c in df_invested.columns if 'status' in c.lower()][0]
    unique_statuses = ["ALL"] + list(df_invested[status_col].dropna().unique())
    status_filter = st.selectbox("Filter Position Status", unique_statuses)
    
    df_filtered = df_invested.copy()
    if status_filter != "ALL":
        df_filtered = df_filtered[df_filtered[status_col] == status_filter]
    st.dataframe(df_filtered.set_index(df_filtered.columns[0]), use_container_width=True)

with tab2:
    st.subheader("Live Allocation Spread")
    label_col = df_summary.columns[0]
    st.bar_chart(data=df_summary, x=label_col, y=val_col)
    st.dataframe(df_summary.set_index(label_col), use_container_width=True)

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

with tab4:
    st.subheader("Aggregated Financial Footprint")
    w_cat = df_wealth.columns[0]
    st.dataframe(df_wealth.set_index(w_cat), use_container_width=True)
    st.caption("🔄 Secure Diagnostic Build.")
