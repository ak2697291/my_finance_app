import streamlit as st
import pandas as pd

# Set page configuration
st.set_page_config(page_title="Asset Management Dashboard", layout="wide")

# --- DATA LOADING ---
# Safely loading data from cache or state (assuming you use st.connection or similar)
@st.cache_data(ttl=600)
def load_sheet_data():
    try:
        # Utilizing your established worksheet connection for 'invested'
        # Replacing this placeholder with your actual gsheets/excel read logic if different
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="invested")
        return df
    except Exception as e:
        st.error(f"Error connecting to worksheet: {e}")
        return pd.DataFrame()

# Initialize dataframe
df_invested = load_sheet_data()

# --- MAIN UI ---
st.title("Financial & Asset Portfolio Analytics")

if df_invested.empty:
    st.error("The 'invested' worksheet appears to be empty or could not be loaded.")
    st.info("Please check your Google Sheets connection and ensure data exists.")
else:
    # Standardize column strings for cleaner debugging layout
    available_columns = list(df_invested.columns)

    # Tabs layout
    tab1, tab2, tab3 = st.tabs(["Performance Matrix", "Trend Analysis", "Raw Data Overview"])

    # ---------------------------------------------------------
    # TAB 1: PERFORMANCE MATRIX (Where the crash occurred)
    # ---------------------------------------------------------
    with tab1:
        st.subheader("Asset Performance Matrix")
        
        # Safe column parsing: look for any column containing 'status' case-insensitively
        status_cols = [c for c in available_columns if 'status' in c.lower()]
        
        # Defend against IndexError: list index out of range
        if status_cols:
            # Safely grab the first matching column name
            status_col = status_cols[0]
            
            # Extract unique values safely, eliminating NaN values
            unique_statuses = ["ALL"] + list(df_invested[status_col].dropna().unique())
            
            # Render the filter component
            status_filter = st.selectbox("Filter by Asset Status", unique_statuses)
            
            # Apply filter to data view
            if status_filter != "ALL":
                df_filtered = df_invested[df_invested[status_col] == status_filter]
            else:
                df_filtered = df_invested.copy()
                
            # Render KPI Blocks based on filtered data
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Assets Listed", len(df_filtered))
            with col2:
                # Fallback to standard indexing if specific numeric columns aren't found
                val_cols = [c for c in available_columns if 'value' in c.lower() or 'amount' in c.lower()]
                if val_cols:
                    st.metric("Total Portfolio Value", f"${df_filtered[val_cols[0]].sum():,.2f}")
                else:
                    st.metric("Total Portfolio Value", "N/A (Value column missing)")
            with col3:
                st.metric("Active Filter Type", status_filter)

            st.dataframe(df_filtered, use_container_width=True)
            
        else:
            # Graceful recovery UI block instead of a hard crash
            st.warning("⚠️ Column Error: Could not automatically detect a 'Status' column in this worksheet.")
            
            st.markdown(
                """
                ### Troubleshooting Next Steps:
                The application relies on finding a column with the keyword **'status'** in your header row. 
                Below you can inspect the exact layout of the data Streamlit is receiving:
                """
            )
            
            # Debug expanding tools for you to see what is missing
            with st.expander("🔍 Inspect Sheet Schema & Headers", expanded=True):
                st.write("**Detected Columns:**", available_columns)
                st.write("**Sample Row Snapshot:**")
                st.dataframe(df_invested.head(3), use_container_width=True)
                
            st.info("💡 Tip: Ensure your Google Sheet contains a header row at the very top (Row 1) containing a column explicitly named 'Status'.")

    # ---------------------------------------------------------
    # TAB 2: TREND ANALYSIS
    # ---------------------------------------------------------
    with tab2:
        st.subheader("Historical Trends")
        # Add tracking/charting configurations here
        st.info("Trend visualization is active based on loaded records.")
        st.line_chart(df_invested.select_dtypes(include=['number']))

    # ---------------------------------------------------------
    # TAB 3: RAW DATA OVERVIEW
    # ---------------------------------------------------------
    with tab3:
        st.subheader("Complete Sheet Audit Log")
        st.dataframe(df_invested, use_container_width=True)
