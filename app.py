import streamlit as st
import pandas as pd
import logging
import sys
import urllib.parse

# Set up logging tracking
logging.basicConfig(
    stream=sys.stdout, level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s'
)

st.set_page_config(
    page_title="My Portfolio Hub",
    page_icon="📊",
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# Custom mobile interface adjustments
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div.block-container{padding-top:1.5rem; padding-bottom:1.5rem;}
    [data-testid="stMetricValue"] {font-size: 1.7rem; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

st.title("📱 Live Portfolio Hub")

# 1. Pull Base Link from Secrets Safely
try:
    base_url = st.secrets["SPREADSHEET_URL"]
    # Clean up trailing forward slashes or edits if any remain
    if base_url.endswith("/edit"):
        base_url = base_url[:-5]
    if base_url.endswith("/"):
        base_url = base_url[:-1]
except KeyError:
    st.error("Missing Environment Secret: Please add 'SPREADSHEET_URL' to your Secrets dashboard.")
    st.stop()

# 2. Resilient Direct CSV Streaming Engine
@st.cache_data(ttl=30)
def load_sheet_tab(tab_name):
    logging.info(f"Connecting to live worksheet tab: '{tab_name}'")
    # Encode tab name properly for URL requests
    encoded_tab = urllib.parse.quote(tab_name)
    export_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={encoded_tab}"
    
    df = pd.read_csv(export_url)
    if df.empty:
        raise ValueError(f"Tab '{tab_name}' returned an empty dataset structure.")
    return df

# 3. Synchronous Loading Phase
try:
    df_invested = load_sheet_tab("invested")
    df_summary = load_sheet_tab("StockMarketPortfolioSummary")
    df_strategy = load_sheet_tab("investmentStrategy")
    df_wealth = load_sheet_tab("TotalWealth")
    
    # Clean up any full blank padding rows
    df_invested = df_invested.dropna(subset=[df_invested.columns[0]])
    df_summary = df_summary.dropna(subset=[df_summary.columns[0]])
    df_strategy = df_strategy.dropna(subset=[df_strategy.columns[0]])
    df_wealth = df_wealth.dropna(subset=[df_wealth.columns[0]])
except Exception as err:
    logging.error(f"Data stream crash: {str(err)}")
    st.error("❌ Link Resolution Error")
    st.write("The app couldn't process the sheets cleanly. Double check that your tab names match perfectly:")
    st.code("invested\nStockMarketPortfolioSummary\ninvestmentStrategy\nTotalWealth")
    st.caption(f"System Message: {str(err)}")
    st.stop()

# 4. Live Global Metrics Calculation
try:
    inv_match = [c for c in df_invested.columns if 'invested' in c.lower()]
    cur_match = [c for c in df_invested.columns if 'current' in c.lower() and 'value' in c.lower()]

    if inv_match and cur_match:
        inv_col = inv_match[0]
        cur_col = cur_match[0]

        total_invested_calc = pd.to_numeric(df_invested[inv_col], errors='coerce').sum()
        total_current_calc = pd.to_numeric(df_invested[cur_col], errors='coerce').sum()
        net_pl_calc = total_current_calc - total_invested_calc
        pl_pct_calc = (net_pl_calc / total_invested_calc) * 100 if total_invested_calc > 0 else 0

        col1, col2 = st.columns(2)
        col1.metric("Live Market Value", f"₹{total_current_calc:,.2f}", f"+{pl_pct_calc:.2f}%")
        col2.metric("Absolute P&L", f"₹{net_pl_calc:,.2f}")
    else:
        st.info("📊 Add 'Invested' and 'Current Value' columns to compute summary cards.")
except Exception as map_err:
    st.warning("📊 Dashboard metrics displaying raw layout frame.")

# 5. Mobile Layout Views
tab1, tab2, tab3, tab4 = st.tabs(["📈 Holdings", "📊 Assets", "🎯 Strategy", "💰 Net Worth"])

with tab1:
    st.subheader("Asset Performance Matrix")
    
    # Safely scan for a status column to avoid IndexError
    status_match = [c for c in df_invested.columns if 'status' in c.lower() or 'state' in c.lower() or 'type' in c.lower()]
    
    if status_match:
        status_col = status_match[0]
        unique_statuses = ["ALL"] + list(df_invested[status_col].dropna().unique())
        status_filter = st.selectbox("Filter Status", unique_statuses)
        
        df_filtered = df_invested.copy()
        if status_filter != "ALL":
            df_filtered = df_filtered[df_filtered[status_col] == status_filter]
        st.dataframe(df_filtered.set_index(df_filtered.columns[0]), use_container_width=True)
    else:
        st.caption("💡 Tip: Add a 'Status' column to your Google Sheet to enable dynamic filtering.")
        st.dataframe(df_invested.set_index(df_invested.columns[0]), use_container_width=True)

with tab2:
    st.subheader("Live Allocation Spread")
    label_col = df_summary.columns[0]
    val_match = [c for c in df_summary.columns if 'value' in c.lower() or 'allocation' in c.lower() or 'amount' in c.lower()]
    
    if val_match:
        val_col = val_match[0]
        st.bar_chart(data=df_summary, x=label_col, y=val_col)
    st.dataframe(df_summary.set_index(label_col), use_container_width=True)

with tab3:
    st.subheader("Rules-Based Target Planner")
    
    pct_match = [c for c in df_strategy.columns if '%' in c or 'target' in c.lower() or 'allocation' in c.lower()]
    cat_col = df_strategy.columns[0]
    
    if pct_match:
        pct_col = pct_match[0]
        salary_row = df_strategy[df_strategy[cat_col].str.contains('Salary|Income', case=False, na=False)]
        base_salary = 130000 
        
        if not salary_row.empty:
            # Safely look for a column that isn't category or percentage to fetch salary
            val_indices = [c for c in df_strategy.columns if c != cat_col and c != pct_col]
            if val_indices:
                val_idx = val_indices[0]
                base_salary = pd.to_numeric(salary_row.iloc[0][val_idx], errors='coerce') or 130000

        target_invest = st.slider("Modify Monthly Target (₹)", int(base_salary*0.1), int(base_salary*0.9), int(base_salary*0.6), step=2000)
        st.markdown(f"**Target Breakdown for ₹{target_invest:,}:**")
        
        strategy_rows = df_strategy[~df_strategy[cat_col].str.contains('Salary|Expense|Total|Cash', case=False, na=False)]
        for _, row in strategy_rows.iterrows():
            raw_pct = row[pct_col]
            try:
                if isinstance(raw_pct, str):
                    pct_val = float(raw_pct.replace('%', '')) / 100 if '%' in raw_pct else float(raw_pct)
                else:
                    pct_val = float(raw_pct) if float(raw_pct) <= 1 else float(raw_pct) / 100
                    
                calculated_allocation = target_invest * pct_val
                st.write(f"▪️ **{row[cat_col]} ({pct_val*100:.1f}%):** ₹{calculated_allocation:,.2f}")
            except Exception:
                continue
    else:
        st.dataframe(df_strategy.set_index(cat_col), use_container_width=True)

with tab4:
    st.subheader("Aggregated Financial Footprint")
    w_cat = df_wealth.columns[0]
    st.dataframe(df_wealth.set_index(w_cat), use_container_width=True)
    st.caption("🔄 Secure Dynamic Sync Active.")
