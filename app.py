import streamlit as st
import pandas as pd
import logging
import sys
import urllib.parse
import numpy as np

logging.basicConfig(
    stream=sys.stdout, level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s'
)

st.set_page_config(
    page_title="Portfolio Hub",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── GLOBAL STYLES ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

/* ── ROOT TOKENS ── */
:root {
  --ink:       #0a0b0f;
  --surface:   #111318;
  --card:      #16191f;
  --border:    #252830;
  --muted:     #3a3e4a;
  --dim:       #6b7080;
  --text:      #e8eaf0;
  --sub:       #9499a8;
  --gold:      #c9a84c;
  --gold-glow: rgba(201,168,76,0.18);
  --green:     #3ecf6e;
  --green-glow:rgba(62,207,110,0.15);
  --red:       #f05a5a;
  --red-glow:  rgba(240,90,90,0.15);
  --blue:      #5a9cf0;
  --accent:    #c9a84c;
}

/* ── GLOBAL RESET ── */
html, body, [data-testid="stAppViewContainer"] {
  background: var(--ink) !important;
  color: var(--text) !important;
  font-family: 'DM Mono', monospace !important;
}

[data-testid="stAppViewContainer"] { padding: 0 !important; }

/* Hide Streamlit chrome */
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"] { visibility: hidden !important; }

/* ── HERO BANNER ── */
.hero {
  background: linear-gradient(135deg, #0d0e12 0%, #12141a 60%, #0f1116 100%);
  border-bottom: 1px solid var(--border);
  padding: 2.2rem 2.8rem 1.6rem;
  position: relative;
  overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute; inset: 0;
  background: radial-gradient(ellipse 60% 80% at 80% 50%, rgba(201,168,76,0.06) 0%, transparent 70%);
  pointer-events: none;
}
.hero-label {
  font-family: 'DM Mono', monospace;
  font-size: 0.65rem;
  letter-spacing: 0.22em;
  color: var(--gold);
  text-transform: uppercase;
  margin-bottom: 0.4rem;
}
.hero-title {
  font-family: 'Syne', sans-serif;
  font-size: clamp(1.8rem, 3.5vw, 2.8rem);
  font-weight: 800;
  color: var(--text);
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin: 0 0 0.3rem;
}
.hero-title span { color: var(--gold); }
.hero-sub {
  font-size: 0.72rem;
  color: var(--dim);
  letter-spacing: 0.08em;
}

/* ── METRIC CARDS ── */
.metric-row { display: flex; gap: 1rem; padding: 1.4rem 2.8rem; flex-wrap: wrap; }
.m-card {
  flex: 1; min-width: 160px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.1rem 1.4rem;
  position: relative;
  overflow: hidden;
  transition: border-color 0.2s;
}
.m-card:hover { border-color: var(--muted); }
.m-card::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0;
  height: 2px;
}
.m-card.gold::before  { background: linear-gradient(90deg, transparent, var(--gold), transparent); }
.m-card.green::before { background: linear-gradient(90deg, transparent, var(--green), transparent); }
.m-card.red::before   { background: linear-gradient(90deg, transparent, var(--red), transparent); }
.m-card.blue::before  { background: linear-gradient(90deg, transparent, var(--blue), transparent); }

.m-label {
  font-size: 0.6rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--dim);
  margin-bottom: 0.5rem;
}
.m-value {
  font-family: 'Syne', sans-serif;
  font-size: 1.55rem;
  font-weight: 700;
  color: var(--text);
  line-height: 1;
}
.m-badge {
  display: inline-block;
  margin-top: 0.5rem;
  font-size: 0.65rem;
  font-family: 'DM Mono', monospace;
  padding: 2px 8px;
  border-radius: 20px;
}
.badge-green { background: var(--green-glow); color: var(--green); }
.badge-red   { background: var(--red-glow);   color: var(--red); }
.badge-gold  { background: var(--gold-glow);  color: var(--gold); }

/* ── TABS ── */
[data-testid="stTabs"] > div:first-child {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 2.8rem;
  gap: 0 !important;
}
[data-testid="stTabs"] button {
  font-family: 'DM Mono', monospace !important;
  font-size: 0.7rem !important;
  letter-spacing: 0.12em !important;
  text-transform: uppercase !important;
  color: var(--dim) !important;
  padding: 0.9rem 1.2rem !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  background: transparent !important;
  transition: color 0.2s, border-color 0.2s !important;
}
[data-testid="stTabs"] button:hover { color: var(--text) !important; }
[data-testid="stTabs"] button[aria-selected="true"] {
  color: var(--gold) !important;
  border-bottom-color: var(--gold) !important;
}
[data-testid="stTabsContent"] {
  padding: 1.8rem 2.8rem !important;
  background: var(--ink) !important;
}

/* ── SECTION HEADERS ── */
.sec-header {
  display: flex; align-items: center; gap: 0.7rem;
  margin-bottom: 1.4rem;
}
.sec-line { flex: 1; height: 1px; background: var(--border); }
.sec-title {
  font-family: 'Syne', sans-serif;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--sub);
}

/* ── DATAFRAME OVERRIDES ── */
[data-testid="stDataFrame"] {
  background: var(--card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  overflow: hidden !important;
}
[data-testid="stDataFrame"] table {
  font-family: 'DM Mono', monospace !important;
  font-size: 0.72rem !important;
}
[data-testid="stDataFrame"] th {
  background: var(--surface) !important;
  color: var(--sub) !important;
  font-size: 0.6rem !important;
  letter-spacing: 0.14em !important;
  text-transform: uppercase !important;
  border-bottom: 1px solid var(--border) !important;
}
[data-testid="stDataFrame"] td { color: var(--text) !important; }
[data-testid="stDataFrame"] tr:hover td { background: rgba(255,255,255,0.02) !important; }

/* ── SELECT BOX ── */
[data-testid="stSelectbox"] > div > div {
  background: var(--card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  color: var(--text) !important;
  font-family: 'DM Mono', monospace !important;
  font-size: 0.75rem !important;
}
[data-testid="stSelectbox"] label {
  font-size: 0.62rem !important;
  letter-spacing: 0.14em !important;
  text-transform: uppercase !important;
  color: var(--dim) !important;
}

/* ── SLIDER ── */
[data-testid="stSlider"] label {
  font-size: 0.62rem !important;
  letter-spacing: 0.14em !important;
  text-transform: uppercase !important;
  color: var(--dim) !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
  background: var(--gold) !important;
  border-color: var(--gold) !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stSliderTrackFill"] {
  background: var(--gold) !important;
}

/* ── BAR CHART ── */
[data-testid="stVegaLiteChart"] { border-radius: 10px; overflow: hidden; }

/* ── STRATEGY ALLOCATION ROW ── */
.alloc-row {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.85rem 1.2rem;
  margin-bottom: 0.6rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}
.alloc-name {
  font-family: 'Syne', sans-serif;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text);
  flex: 1;
  min-width: 130px;
}
.alloc-bar-wrap { flex: 2; background: var(--muted); border-radius: 4px; height: 6px; overflow: hidden; }
.alloc-bar { height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--gold), #e8c46a); }
.alloc-pct {
  font-size: 0.65rem;
  color: var(--gold);
  min-width: 38px;
  text-align: right;
  letter-spacing: 0.06em;
}
.alloc-amt {
  font-family: 'Syne', sans-serif;
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--text);
  min-width: 100px;
  text-align: right;
}

/* ── WEALTH TABLE CARD ── */
.wealth-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 1.2rem;
}
.wealth-header {
  background: var(--surface);
  padding: 0.7rem 1.2rem;
  font-size: 0.6rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--dim);
  border-bottom: 1px solid var(--border);
}

/* ── TICKER TAPE ── */
.ticker-wrap {
  background: var(--surface);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  overflow: hidden;
  padding: 0.5rem 0;
  margin: 0;
}
.ticker-inner {
  display: flex;
  gap: 3rem;
  animation: ticker 40s linear infinite;
  white-space: nowrap;
}
@keyframes ticker {
  0%   { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}
.tick-item {
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  color: var(--sub);
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.tick-item .sym { color: var(--gold); font-weight: 500; }
.tick-up   { color: var(--green); }
.tick-down { color: var(--red); }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--ink); }
::-webkit-scrollbar-thumb { background: var(--muted); border-radius: 4px; }

/* ── STALE CONTENT OVERRIDE ── */
div[data-testid="stBlock"] { background: transparent !important; }
[data-testid="column"] { background: transparent !important; }
</style>
""", unsafe_allow_html=True)


# ── HERO ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-label">◈ Live Dashboard · NSE / BSE</div>
  <div class="hero-title">My <span>Portfolio</span> Hub</div>
  <div class="hero-sub">Real-time sync · Auto-refresh 30s · INR ₹</div>
</div>
""", unsafe_allow_html=True)


# ── SECRETS ───────────────────────────────────────────────────────────────────
try:
    base_url = st.secrets["SPREADSHEET_URL"]
    if base_url.endswith("/edit"): base_url = base_url[:-5]
    if base_url.endswith("/"):     base_url = base_url[:-1]
except KeyError:
    st.error("⚠️  Missing Secret: add `SPREADSHEET_URL` to your Streamlit Secrets dashboard.")
    st.stop()


# ── DATA LOADING ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_sheet_tab(tab_name):
    logging.info(f"Loading tab: {tab_name}")
    encoded_tab = urllib.parse.quote(tab_name)
    url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={encoded_tab}"
    hdr = None if tab_name == "investmentStrategy" else 0
    return pd.read_csv(url, header=hdr)

try:
    df_invested  = load_sheet_tab("invested")
    df_summary   = load_sheet_tab("StockMarketPortfolioSummary")
    df_strategy_raw = load_sheet_tab("investmentStrategy")
    df_wealth    = load_sheet_tab("TotalWealth")

    df_invested  = df_invested.dropna(subset=[df_invested.columns[0]])
    df_summary   = df_summary.dropna(subset=[df_summary.columns[0]])
    df_wealth    = df_wealth.dropna(subset=[df_wealth.columns[0]])
except Exception as err:
    logging.error(str(err))
    st.error("❌ Could not load spreadsheet data. Check your SPREADSHEET_URL and sheet tab names.")
    st.stop()


# ── GLOBAL METRICS ─────────────────────────────────────────────────────────────
inv_match = [c for c in df_invested.columns if 'invested' in c.lower()]
cur_match = [c for c in df_invested.columns if 'current' in c.lower() and 'value' in c.lower()]

total_invested_calc = total_current_calc = net_pl_calc = pl_pct_calc = 0
if inv_match and cur_match:
    inv_col = inv_match[0]; cur_col = cur_match[0]
    total_invested_calc = pd.to_numeric(df_invested[inv_col], errors='coerce').sum()
    total_current_calc  = pd.to_numeric(df_invested[cur_col], errors='coerce').sum()
    net_pl_calc  = total_current_calc - total_invested_calc
    pl_pct_calc  = (net_pl_calc / total_invested_calc * 100) if total_invested_calc > 0 else 0

badge_color = "green" if net_pl_calc >= 0 else "red"
pl_sign     = "▲" if net_pl_calc >= 0 else "▼"
n_holdings  = len(df_invested)

# Build ticker tape from holdings
ticker_items = ""
name_col = df_invested.columns[0]
if inv_match and cur_match:
    for _, row in df_invested.head(12).iterrows():
        sym = str(row[name_col])[:8].upper()
        inv = pd.to_numeric(row.get(inv_col, 0), errors='coerce') or 0
        cur = pd.to_numeric(row.get(cur_col, 0), errors='coerce') or 0
        chg = ((cur - inv) / inv * 100) if inv > 0 else 0
        cls = "tick-up" if chg >= 0 else "tick-down"
        sign = "▲" if chg >= 0 else "▼"
        ticker_items += f'<span class="tick-item"><span class="sym">{sym}</span> <span class="{cls}">{sign}{abs(chg):.1f}%</span></span>'
# Duplicate for seamless loop
ticker_html = f'<div class="ticker-wrap"><div class="ticker-inner">{ticker_items}{ticker_items}</div></div>'

st.markdown(ticker_html, unsafe_allow_html=True)

# Metric cards
st.markdown(f"""
<div class="metric-row">
  <div class="m-card gold">
    <div class="m-label">Live Market Value</div>
    <div class="m-value">₹{total_current_calc:,.0f}</div>
    <span class="m-badge badge-gold">CURRENT NAV</span>
  </div>
  <div class="m-card {'green' if net_pl_calc>=0 else 'red'}">
    <div class="m-label">Absolute P&amp;L</div>
    <div class="m-value">₹{abs(net_pl_calc):,.0f}</div>
    <span class="m-badge badge-{'green' if net_pl_calc>=0 else 'red'}">{pl_sign} {abs(pl_pct_calc):.2f}%</span>
  </div>
  <div class="m-card blue">
    <div class="m-label">Total Invested</div>
    <div class="m-value">₹{total_invested_calc:,.0f}</div>
    <span class="m-badge badge-gold">COST BASIS</span>
  </div>
  <div class="m-card gold">
    <div class="m-label">Holdings</div>
    <div class="m-value">{n_holdings}</div>
    <span class="m-badge badge-gold">POSITIONS</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ── TABS ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["◈  Holdings", "◈  Asset Mix", "◈  Strategy", "◈  Net Worth"])

# ── TAB 1: HOLDINGS ───────────────────────────────────────────────────────────
with tab1:
    st.markdown("""
    <div class="sec-header">
      <span class="sec-title">Asset Performance Matrix</span>
      <div class="sec-line"></div>
    </div>
    """, unsafe_allow_html=True)

    # Color P&L column if present
    def style_df(df):
        styled = df.style.set_properties(**{
            'background-color': 'transparent',
            'color': '#e8eaf0',
            'font-family': 'DM Mono, monospace',
            'font-size': '0.74rem',
        })
        for c in df.columns:
            if 'p&l' in c.lower() or 'gain' in c.lower() or 'profit' in c.lower() or 'return' in c.lower():
                def color_pnl(val):
                    try:
                        v = float(str(val).replace('₹','').replace(',','').replace('%',''))
                        return f'color: {"#3ecf6e" if v >= 0 else "#f05a5a"}'
                    except: return ''
                styled = styled.applymap(color_pnl, subset=[c])
        return styled

    status_match = [c for c in df_invested.columns if any(k in c.lower() for k in ['status','state','type','sector','category'])]
    if status_match:
        status_col = status_match[0]
        opts = ["ALL"] + sorted(df_invested[status_col].dropna().unique().tolist())
        col_f, col_spacer = st.columns([1, 3])
        with col_f:
            status_filter = st.selectbox("Filter by", opts, key="holdings_filter")
        df_show = df_invested.copy()
        if status_filter != "ALL":
            df_show = df_show[df_show[status_col] == status_filter]
    else:
        df_show = df_invested.copy()

    idx_col = df_show.columns[0]
    try:
        st.dataframe(style_df(df_show.set_index(idx_col)), use_container_width=True, height=400)
    except:
        st.dataframe(df_show.set_index(idx_col), use_container_width=True, height=400)

    # Mini P&L sparkline table
    if inv_match and cur_match and len(df_invested) > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="sec-header">
          <span class="sec-title">Individual P&L Snapshot</span>
          <div class="sec-line"></div>
        </div>""", unsafe_allow_html=True)

        rows_html = ""
        for _, row in df_invested.head(15).iterrows():
            name = str(row[name_col])[:22]
            inv_v = pd.to_numeric(row.get(inv_col, 0), errors='coerce') or 0
            cur_v = pd.to_numeric(row.get(cur_col, 0), errors='coerce') or 0
            pnl   = cur_v - inv_v
            pct   = (pnl / inv_v * 100) if inv_v > 0 else 0
            bar_w = min(abs(pct) * 1.2, 100)
            bar_col = "#3ecf6e" if pnl >= 0 else "#f05a5a"
            sign = "▲" if pnl >= 0 else "▼"
            rows_html += f"""
            <div class="alloc-row">
              <span class="alloc-name">{name}</span>
              <div class="alloc-bar-wrap">
                <div class="alloc-bar" style="width:{bar_w}%;background:linear-gradient(90deg,{bar_col},{bar_col}88);"></div>
              </div>
              <span class="alloc-pct" style="color:{bar_col}">{sign}{abs(pct):.1f}%</span>
              <span class="alloc-amt" style="color:{bar_col}">₹{abs(pnl):,.0f}</span>
            </div>"""
        st.markdown(rows_html, unsafe_allow_html=True)


# ── TAB 2: ASSET MIX ──────────────────────────────────────────────────────────
with tab2:
    st.markdown("""
    <div class="sec-header">
      <span class="sec-title">Live Allocation Spread</span>
      <div class="sec-line"></div>
    </div>
    """, unsafe_allow_html=True)

    label_col = df_summary.columns[0]
    val_match  = [c for c in df_summary.columns if any(k in c.lower() for k in ['value','allocation','amount','weight'])]

    if val_match:
        val_col = val_match[0]
        df_chart = df_summary[[label_col, val_col]].copy()
        df_chart[val_col] = pd.to_numeric(df_chart[val_col], errors='coerce')
        df_chart = df_chart.dropna()

        # Vega-Lite chart config for dark theme
        import json
        chart_spec = {
            "mark": {"type": "bar", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
            "encoding": {
                "x": {"field": label_col, "type": "nominal",
                      "axis": {"labelColor": "#6b7080", "titleColor": "#6b7080",
                               "labelFont": "DM Mono", "titleFont": "DM Mono",
                               "labelAngle": -30, "labelLimit": 120}},
                "y": {"field": val_col, "type": "quantitative",
                      "axis": {"labelColor": "#6b7080", "titleColor": "#6b7080",
                               "labelFont": "DM Mono", "gridColor": "#252830"}},
                "color": {"value": "#c9a84c"},
                "tooltip": [
                    {"field": label_col, "type": "nominal"},
                    {"field": val_col, "type": "quantitative", "format": ",.2f"}
                ]
            },
            "config": {
                "background": "#16191f",
                "view": {"stroke": "transparent"},
                "axis": {"domainColor": "#252830"}
            }
        }
        st.vega_lite_chart(df_chart, chart_spec, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="sec-header">
      <span class="sec-title">Summary Table</span>
      <div class="sec-line"></div>
    </div>""", unsafe_allow_html=True)
    st.dataframe(df_summary.set_index(label_col), use_container_width=True)


# ── TAB 3: STRATEGY ───────────────────────────────────────────────────────────
with tab3:
    st.markdown("""
    <div class="sec-header">
      <span class="sec-title">Rules-Based Target Planner</span>
      <div class="sec-line"></div>
    </div>
    """, unsafe_allow_html=True)

    try:
        raw_strings = df_strategy_raw.astype(str)

        # Parse salary
        salary_idx = raw_strings[raw_strings.iloc[:,0].str.contains('Salary', case=False, na=False)].index
        base_salary = 130000
        if not salary_idx.empty:
            raw_sal = df_strategy_raw.iloc[salary_idx[0], 1]
            if isinstance(raw_sal, str): raw_sal = raw_sal.replace('₹','').replace(',','').strip()
            base_salary = pd.to_numeric(raw_sal, errors='coerce') or 130000

        # Parse invest target
        inv_target_row = raw_strings[raw_strings.iloc[:,0].str.contains('Total Amount To Invest', case=False, na=False)]
        default_target = int(base_salary * 0.6154)
        if not inv_target_row.empty:
            raw_t = df_strategy_raw.iloc[inv_target_row.index[0], 1]
            if isinstance(raw_t, str): raw_t = raw_t.replace('₹','').replace(',','').strip()
            default_target = int(pd.to_numeric(raw_t, errors='coerce') or default_target)

        # Salary info bar
        st.markdown(f"""
        <div style="display:flex;gap:1rem;margin-bottom:1.2rem;flex-wrap:wrap;">
          <div class="m-card gold" style="flex:none;min-width:180px;">
            <div class="m-label">Monthly Income</div>
            <div class="m-value" style="font-size:1.2rem;">₹{int(base_salary):,}</div>
          </div>
          <div class="m-card blue" style="flex:none;min-width:180px;">
            <div class="m-label">Invest Ratio</div>
            <div class="m-value" style="font-size:1.2rem;">{default_target/base_salary*100:.1f}%</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        target_invest = st.slider(
            "Adjust Monthly Investment Target (₹)",
            min_value=10000, max_value=int(base_salary),
            value=int(default_target), step=2000
        )

        # Parse strategy block
        section_idx = raw_strings[raw_strings.iloc[:,0].str.contains('INVESTMENT STRATEGY', case=False, na=False)].index

        if not section_idx.empty:
            start_row = section_idx[0] + 2
            df_strat_block = df_strategy_raw.iloc[start_row:].copy()
            df_strat_block = df_strat_block.dropna(subset=[df_strat_block.columns[0]])

            st.markdown(f"""
            <div class="sec-header" style="margin-top:1.5rem">
              <span class="sec-title">Allocation for ₹{target_invest:,}</span>
              <div class="sec-line"></div>
            </div>""", unsafe_allow_html=True)

            alloc_rows = ""
            colors = ["#c9a84c","#5a9cf0","#3ecf6e","#f0a05a","#d05af0","#f05a5a","#5af0d0"]
            ci = 0
            for _, row in df_strat_block.iterrows():
                cat_name = str(row[0]).strip()
                raw_pct  = row[1]
                if not cat_name or cat_name == 'nan' or 'disclaimer' in cat_name.lower():
                    continue
                try:
                    if isinstance(raw_pct, str):
                        pct_val = float(raw_pct.replace('%','').strip()) / 100 if '%' in raw_pct else float(raw_pct)
                    else:
                        pct_val = float(raw_pct) if float(raw_pct) <= 1 else float(raw_pct) / 100
                    if pct_val <= 0 or pct_val > 1: continue
                except: continue

                amt = target_invest * pct_val
                bar_w = pct_val * 100
                col = colors[ci % len(colors)]
                ci += 1

                alloc_rows += f"""
                <div class="alloc-row">
                  <span class="alloc-name">{cat_name}</span>
                  <div class="alloc-bar-wrap">
                    <div class="alloc-bar" style="width:{bar_w}%;background:linear-gradient(90deg,{col},{col}88);"></div>
                  </div>
                  <span class="alloc-pct" style="color:{col}">{pct_val*100:.1f}%</span>
                  <span class="alloc-amt">₹{amt:,.0f}</span>
                </div>"""

            st.markdown(alloc_rows, unsafe_allow_html=True)
        else:
            st.info("Could not locate INVESTMENT STRATEGY block. Showing raw data.")
            st.dataframe(df_strategy_raw)

    except Exception as e:
        st.error(f"Strategy parse error: {e}")
        st.dataframe(df_strategy_raw)


# ── TAB 4: NET WORTH ──────────────────────────────────────────────────────────
with tab4:
    st.markdown("""
    <div class="sec-header">
      <span class="sec-title">Aggregated Financial Footprint</span>
      <div class="sec-line"></div>
    </div>
    """, unsafe_allow_html=True)

    w_cat = df_wealth.columns[0]

    # Try to show total wealth as a hero number
    val_cols_w = [c for c in df_wealth.columns if any(k in c.lower() for k in ['value','amount','total','balance','worth'])]
    if val_cols_w:
        vc = val_cols_w[0]
        total_w = pd.to_numeric(df_wealth[vc], errors='coerce').sum()
        st.markdown(f"""
        <div class="m-card gold" style="max-width:340px;margin-bottom:1.4rem;">
          <div class="m-label">Total Net Worth</div>
          <div class="m-value">₹{total_w:,.0f}</div>
          <span class="m-badge badge-gold">ALL ASSETS</span>
        </div>
        """, unsafe_allow_html=True)

    st.dataframe(df_wealth.set_index(w_cat), use_container_width=True, height=380)
    st.markdown("""
    <div style="margin-top:1rem;font-size:0.62rem;color:#3a3e4a;letter-spacing:0.1em;">
      ◈ LIVE SYNC · SECURE READ-ONLY · AUTO-REFRESH 30s
    </div>
    """, unsafe_allow_html=True)
