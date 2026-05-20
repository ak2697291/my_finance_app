import streamlit as st
import pandas as pd
import logging
import sys
import urllib.parse
import numpy as np

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
    encoded_tab = urllib.parse.quote(tab_name)
    # We load without headers (header=None) for the strategy tab to handle multiple tables safely
    if tab_name == "investmentStrategy":
        export_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={encoded_tab}"
        return pd.read_csv(export_url, header=None)
    else:
        export_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={encoded_tab}"
        return pd.read_csv(export_url)

# 3. Synchronous Loading Phase
try:
    df_invested = load_sheet_tab("invested")
    df_summary = load_sheet_tab("StockMarketPortfolioSummary")
    df_strategy_raw = load_sheet_tab("investmentStrategy")
    df_wealth = load_sheet_tab("TotalWealth")
    
    # Standard data cleanup for clean tabs
    df_invested = df_invested.dropna(subset=[df_invested.columns[0]])
    df_summary = df_summary.dropna(subset=[df_summary.columns[0]])
    df_wealth = df_wealth.dropna(subset=[df_wealth.columns[0]])
except Exception as err:
    logging.error(f"Data stream crash: {str(err)}")
    st.error("❌ Link Resolution Error")
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
except Exception as map_err:
    st.warning("📊 Summary metrics loading frame error.")

# 5. Mobile Layout Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📈 Holdings", "📊 Assets", "🎯 Strategy", "💰 Net Worth"])

with tab1:
    st.subheader("Asset Performance Matrix")
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
    
    try:
        # --- PARSE INCOME ---
        # Find row containing "Salary" across the raw matrix data string representations
        raw_strings = df_strategy_raw.astype(str)
        salary_idx = raw_strings[raw_strings.iloc[:, 0].str.contains('Salary', case=False, na=False)].index
        
        base_salary = 130000 # Sensible fall back
        if not salary_idx.empty:
            # Salary value sits on column 1 (B) of that row
            raw_sal_val = df_strategy_raw.iloc[salary_idx[0], 1]
            if isinstance(raw_sal_val, str):
                raw_sal_val = raw_sal_val.replace('₹', '').replace(',', '').strip()
            base_salary = pd.to_numeric(raw_sal_val, errors='coerce') or 130000

        # --- PARSE INVESTMENT BUDGET ---
        invest_target_row = raw_strings[raw_strings.iloc[:, 0].str.contains('Total Amount To Invest', case=False, na=False)]
        default_target = int(base_salary * 0.6154) # Fallback to 80000 based on your sheet profile
        if not invest_target_row.empty:
            raw_target_val = df_strategy_raw.iloc[invest_target_row.index[0], 1]
            if isinstance(raw_target_val, str):
                raw_target_val = raw_target_val.replace('₹', '').replace(',', '').strip()
            default_target = int(pd.to_numeric(raw_target_val, errors='coerce') or default_target)

        # Interactive slider calibrated up to your dynamic salary cap
        target_invest = st.slider(
            "Modify Monthly Target (₹)", 
            min_value=10000, 
            max_value=int(base_salary), 
            value=int(default_target), 
            step=2000
        )
        st.markdown(f"### Target Breakdown for ₹{target_invest:,}:")

        # --- EXTRACT THE INVESTMENT STRATEGY SUB-TABLE ---
        # Find where "INVESTMENT STRATEGY" title block drops down
        section_idx = raw_strings[raw_strings.iloc[:, 0].str.contains('INVESTMENT STRATEGY', case=False, na=False)].index
        
        if not section_idx.empty:
            start_row = section_idx[0] + 2 # Skip section header row and column definitions row
            
            # Extract everything under that section boundary box
            df_strat_block = df_strategy_raw.iloc[start_row:].copy()
            df_strat_block = df_strat_block.dropna(subset=[df_strat_block.columns[0]])
            
            # Map dynamic sub-block rows out cleanly
            for _, row in df_strat_block.iterrows():
                cat_name = str(row[0]).strip()
                raw_pct = row[1]
                
                if not cat_name or cat_name == 'nan' or 'disclaimer' in cat_name.lower():
                    continue
                    
                # Clean percentage format parsing engine ("35%" vs 0.35)
                if isinstance(raw_pct, str):
                    pct_val = float(raw_pct.replace('%', '').strip()) / 100 if '%' in raw_pct else float(raw_pct)
                else:
                    pct_val = float(raw_pct) if float(raw_pct) <= 1 else float(raw_pct) / 100
                    
                if pct_val <= 0 or pct_val > 1:
                    continue
                    
                calculated_allocation = target_invest * pct_val
                st.write(f"▪️ **{cat_name} ({pct_val*100:.1f}%):** ₹{calculated_allocation:,.2f}")
        else:
            st.info("Strategy parsing signature tracking blocks. Raw layout format mapped below:")
            st.dataframe(df_strategy_raw)
            
    except Exception as strategy_err:
        st.error(f"Strategy view building matrix exception: {str(strategy_err)}")
        st.dataframe(df_strategy_raw)

with tab4:
    st.subheader("Aggregated Financial Footprint")
    w_cat = df_wealth.columns[0]
    st.dataframe(df_wealth.set_index(w_cat), use_container_width=True)
    st.caption("🔄 Live sync secure framework tracking complete portfolio.")
