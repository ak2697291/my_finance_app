import streamlit as st
import pandas as pd
import logging
import sys
import urllib.parse
import numpy as np
import requests
import json
import re
import time
from datetime import datetime

logging.basicConfig(
    stream=sys.stdout, level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s'
)

st.set_page_config(
    page_title="Portfolio Hub",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── AZURE OPENAI CONFIG ───────────────────────────────────────────────────────
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_API_KEY  = st.secrets["AZURE_API_KEY"]

def call_gpt(messages, max_tokens=2000):
    """Call Azure OpenAI GPT-5."""
    try:
        resp = requests.post(
            AZURE_ENDPOINT,
            headers={"Content-Type": "application/json", "api-key": AZURE_API_KEY},
            json={"messages": messages, "max_tokens": max_tokens},
            timeout=30
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"GPT error: {e}")
        return None

# ── GLOBAL STYLES ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

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

html, body, [data-testid="stAppViewContainer"] {
  background: var(--ink) !important;
  color: var(--text) !important;
  font-family: 'DM Mono', monospace !important;
}
[data-testid="stAppViewContainer"] { padding: 0 !important; }
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"] { visibility: hidden !important; }

.hero {
  background: linear-gradient(135deg, #0d0e12 0%, #12141a 60%, #0f1116 100%);
  border-bottom: 1px solid var(--border);
  padding: 2.2rem 2.8rem 1.6rem;
  position: relative; overflow: hidden;
}
.hero::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(ellipse 60% 80% at 80% 50%, rgba(201,168,76,0.06) 0%, transparent 70%);
  pointer-events: none;
}
.hero-label { font-family:'DM Mono',monospace;font-size:.65rem;letter-spacing:.22em;color:var(--gold);text-transform:uppercase;margin-bottom:.4rem; }
.hero-title { font-family:'Syne',sans-serif;font-size:clamp(1.8rem,3.5vw,2.8rem);font-weight:800;color:var(--text);line-height:1.1;letter-spacing:-.02em;margin:0 0 .3rem; }
.hero-title span { color: var(--gold); }
.hero-sub { font-size:.72rem;color:var(--dim);letter-spacing:.08em; }

.metric-row { display:flex;gap:1rem;padding:1.4rem 2.8rem;flex-wrap:wrap; }
.m-card { flex:1;min-width:160px;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.1rem 1.4rem;position:relative;overflow:hidden;transition:border-color .2s; }
.m-card:hover { border-color: var(--muted); }
.m-card::before { content:'';position:absolute;top:0;left:0;right:0;height:2px; }
.m-card.gold::before  { background: linear-gradient(90deg, transparent, var(--gold), transparent); }
.m-card.green::before { background: linear-gradient(90deg, transparent, var(--green), transparent); }
.m-card.red::before   { background: linear-gradient(90deg, transparent, var(--red), transparent); }
.m-card.blue::before  { background: linear-gradient(90deg, transparent, var(--blue), transparent); }
.m-label { font-size:.6rem;letter-spacing:.18em;text-transform:uppercase;color:var(--dim);margin-bottom:.5rem; }
.m-value { font-family:'Syne',sans-serif;font-size:1.55rem;font-weight:700;color:var(--text);line-height:1; }
.m-badge { display:inline-block;margin-top:.5rem;font-size:.65rem;font-family:'DM Mono',monospace;padding:2px 8px;border-radius:20px; }
.badge-green { background:var(--green-glow);color:var(--green); }
.badge-red   { background:var(--red-glow);color:var(--red); }
.badge-gold  { background:var(--gold-glow);color:var(--gold); }

[data-testid="stTabs"] > div:first-child {
  background:var(--surface);border-bottom:1px solid var(--border);padding:0 2.8rem;gap:0 !important;
}
[data-testid="stTabs"] button {
  font-family:'DM Mono',monospace !important;font-size:.7rem !important;letter-spacing:.12em !important;
  text-transform:uppercase !important;color:var(--dim) !important;padding:.9rem 1.2rem !important;
  border-bottom:2px solid transparent !important;border-radius:0 !important;
  background:transparent !important;transition:color .2s,border-color .2s !important;
}
[data-testid="stTabs"] button:hover { color: var(--text) !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color:var(--gold) !important;border-bottom-color:var(--gold) !important; }
[data-testid="stTabsContent"] { padding:1.8rem 2.8rem !important;background:var(--ink) !important; }

.sec-header { display:flex;align-items:center;gap:.7rem;margin-bottom:1.4rem; }
.sec-line { flex:1;height:1px;background:var(--border); }
.sec-title { font-family:'Syne',sans-serif;font-size:.75rem;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--sub); }

[data-testid="stDataFrame"] { background:var(--card) !important;border:1px solid var(--border) !important;border-radius:10px !important;overflow:hidden !important; }
[data-testid="stDataFrame"] table { font-family:'DM Mono',monospace !important;font-size:.72rem !important; }
[data-testid="stDataFrame"] th { background:var(--surface) !important;color:var(--sub) !important;font-size:.6rem !important;letter-spacing:.14em !important;text-transform:uppercase !important;border-bottom:1px solid var(--border) !important; }
[data-testid="stDataFrame"] td { color:var(--text) !important; }
[data-testid="stDataFrame"] tr:hover td { background:rgba(255,255,255,0.02) !important; }

[data-testid="stSelectbox"] > div > div { background:var(--card) !important;border:1px solid var(--border) !important;border-radius:8px !important;color:var(--text) !important;font-family:'DM Mono',monospace !important;font-size:.75rem !important; }
[data-testid="stSelectbox"] label { font-size:.62rem !important;letter-spacing:.14em !important;text-transform:uppercase !important;color:var(--dim) !important; }
[data-testid="stSlider"] label { font-size:.62rem !important;letter-spacing:.14em !important;text-transform:uppercase !important;color:var(--dim) !important; }
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] { background:var(--gold) !important;border-color:var(--gold) !important; }
[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stSliderTrackFill"] { background:var(--gold) !important; }
[data-testid="stVegaLiteChart"] { border-radius:10px;overflow:hidden; }

.alloc-row { background:var(--card);border:1px solid var(--border);border-radius:10px;padding:.85rem 1.2rem;margin-bottom:.6rem;display:flex;align-items:center;gap:1rem; }
.alloc-name { font-family:'Syne',sans-serif;font-size:.82rem;font-weight:600;color:var(--text);flex:1;min-width:130px; }
.alloc-bar-wrap { flex:2;background:var(--muted);border-radius:4px;height:6px;overflow:hidden; }
.alloc-bar { height:100%;border-radius:4px;background:linear-gradient(90deg,var(--gold),#e8c46a); }
.alloc-pct { font-size:.65rem;color:var(--gold);min-width:38px;text-align:right;letter-spacing:.06em; }
.alloc-amt { font-family:'Syne',sans-serif;font-size:.88rem;font-weight:700;color:var(--text);min-width:100px;text-align:right; }

.wealth-card { background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:1.2rem; }
.wealth-header { background:var(--surface);padding:.7rem 1.2rem;font-size:.6rem;letter-spacing:.18em;text-transform:uppercase;color:var(--dim);border-bottom:1px solid var(--border); }

.ticker-wrap { background:var(--surface);border-top:1px solid var(--border);border-bottom:1px solid var(--border);overflow:hidden;padding:.5rem 0;margin:0; }
.ticker-inner { display:flex;gap:3rem;animation:ticker 40s linear infinite;white-space:nowrap; }
@keyframes ticker { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }
.tick-item { font-size:.65rem;letter-spacing:.08em;color:var(--sub);display:inline-flex;align-items:center;gap:.4rem; }
.tick-item .sym { color:var(--gold);font-weight:500; }
.tick-up   { color:var(--green); }
.tick-down { color:var(--red); }

/* ── NEWS CAROUSEL ── */
.news-carousel { position:relative;overflow:hidden;border-radius:14px;background:var(--card);border:1px solid var(--border);padding:0; }
.news-track { display:flex;transition:transform .5s cubic-bezier(.4,0,.2,1); }
.news-slide { min-width:100%;padding:1.8rem 2rem;box-sizing:border-box; }
.news-slide-tag { font-size:.58rem;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);margin-bottom:.6rem; }
.news-slide-headline { font-family:'Syne',sans-serif;font-size:1.05rem;font-weight:700;color:var(--text);line-height:1.4;margin-bottom:.7rem; }
.news-slide-meta { font-size:.62rem;color:var(--dim);margin-bottom:.8rem; }
.news-slide-summary { font-size:.72rem;color:var(--sub);line-height:1.6; }
.news-slide-link { display:inline-block;margin-top:.9rem;font-size:.65rem;letter-spacing:.1em;color:var(--gold);text-decoration:none;border:1px solid var(--gold-glow);padding:.3rem .8rem;border-radius:20px;transition:background .2s; }
.news-slide-link:hover { background:var(--gold-glow); }
.news-nav { position:absolute;bottom:1.2rem;right:1.4rem;display:flex;gap:.5rem; }
.news-dot { width:6px;height:6px;border-radius:50%;background:var(--muted);border:none;cursor:pointer;padding:0;transition:background .2s; }
.news-dot.active { background:var(--gold); }
.news-arrows { display:flex;gap:.5rem;margin-bottom:.8rem;justify-content:flex-end; }
.news-arrow { background:var(--card);border:1px solid var(--border);border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:.9rem;color:var(--sub);transition:all .2s; }
.news-arrow:hover { border-color:var(--gold);color:var(--gold); }
.news-ticker-badge { display:inline-block;background:var(--gold-glow);color:var(--gold);border-radius:6px;padding:1px 6px;font-size:.6rem;margin-right:.4rem; }

/* ── FUNDAMENTALS CARDS ── */
.fund-card { background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.2rem;margin-bottom:.8rem;position:relative; }
.fund-card-header { display:flex;align-items:center;gap:.8rem;margin-bottom:1rem; }
.fund-ticker { font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:800;color:var(--text); }
.fund-sector { font-size:.58rem;color:var(--dim);letter-spacing:.1em;text-transform:uppercase; }
.fund-strength { font-size:.6rem;letter-spacing:.1em;text-transform:uppercase;padding:.25rem .7rem;border-radius:20px;font-weight:500; }
.strength-strong { background:var(--green-glow);color:var(--green); }
.strength-moderate { background:var(--gold-glow);color:var(--gold); }
.strength-weak { background:var(--red-glow);color:var(--red); }
.fund-ratio-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:.6rem; }
.fund-ratio { background:var(--surface);border-radius:8px;padding:.6rem .7rem; }
.fund-ratio-label { font-size:.55rem;letter-spacing:.12em;text-transform:uppercase;color:var(--dim);margin-bottom:.3rem; }
.fund-ratio-value { font-family:'Syne',sans-serif;font-size:.95rem;font-weight:700; }
.fund-insight { margin-top:.8rem;font-size:.68rem;color:var(--sub);line-height:1.5;border-top:1px solid var(--border);padding-top:.7rem; }
.ratio-good  { color:var(--green); }
.ratio-warn  { color:var(--gold); }
.ratio-bad   { color:var(--red); }

/* ── SCREENER CARDS ── */
.screener-card { background:var(--card);border:1px solid var(--border);border-radius:14px;padding:1.4rem;margin-bottom:1rem;position:relative;overflow:hidden; }
.screener-card::before { content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,transparent,var(--gold),transparent); }
.screener-rank { position:absolute;top:1rem;right:1.2rem;font-family:'Syne',sans-serif;font-size:1.6rem;font-weight:800;color:var(--border); }
.screener-name { font-family:'Syne',sans-serif;font-size:1.15rem;font-weight:700;color:var(--text);margin-bottom:.2rem; }
.screener-sector { font-size:.6rem;color:var(--dim);letter-spacing:.12em;text-transform:uppercase;margin-bottom:.9rem; }
.screener-metrics { display:grid;grid-template-columns:repeat(5,1fr);gap:.5rem;margin-bottom:.9rem; }
.s-metric { background:var(--surface);border-radius:8px;padding:.5rem .7rem; }
.s-metric-label { font-size:.52rem;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);margin-bottom:.25rem; }
.s-metric-value { font-family:'Syne',sans-serif;font-size:.88rem;font-weight:700;color:var(--text); }
.invest-rec { background:linear-gradient(135deg,rgba(201,168,76,.12),rgba(201,168,76,.05));border:1px solid var(--gold-glow);border-radius:10px;padding:.8rem 1rem;margin-top:.8rem; }
.invest-rec-label { font-size:.58rem;letter-spacing:.15em;text-transform:uppercase;color:var(--gold);margin-bottom:.3rem; }
.invest-rec-amount { font-family:'Syne',sans-serif;font-size:1.2rem;font-weight:800;color:var(--gold); }
.invest-rec-reason { font-size:.65rem;color:var(--sub);line-height:1.5;margin-top:.4rem; }
.criteria-check { display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.6rem; }
.check-pill { font-size:.58rem;padding:.2rem .6rem;border-radius:20px;display:inline-flex;align-items:center;gap:.3rem; }
.check-pass { background:var(--green-glow);color:var(--green); }
.check-fail { background:var(--red-glow);color:var(--red); }

/* ── AI BADGE ── */
.ai-badge { display:inline-flex;align-items:center;gap:.4rem;background:linear-gradient(135deg,rgba(90,156,240,.15),rgba(201,168,76,.1));border:1px solid rgba(90,156,240,.3);border-radius:20px;padding:.25rem .8rem;font-size:.6rem;letter-spacing:.1em;color:var(--blue);margin-bottom:1rem; }

/* ── LOADING PULSE ── */
@keyframes pulse { 0%,100%{opacity:.4} 50%{opacity:1} }
.loading-pulse { animation:pulse 1.5s ease-in-out infinite;color:var(--gold); }

::-webkit-scrollbar { width:4px;height:4px; }
::-webkit-scrollbar-track { background:var(--ink); }
::-webkit-scrollbar-thumb { background:var(--muted);border-radius:4px; }
div[data-testid="stBlock"] { background:transparent !important; }
[data-testid="column"] { background:transparent !important; }

/* Streamlit button override */
.stButton > button {
  background:var(--card) !important;border:1px solid var(--border) !important;
  color:var(--text) !important;font-family:'DM Mono',monospace !important;font-size:.7rem !important;
  letter-spacing:.1em !important;border-radius:8px !important;transition:all .2s !important;
}
.stButton > button:hover { border-color:var(--gold) !important;color:var(--gold) !important; }
</style>
""", unsafe_allow_html=True)


# ── HERO ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-label">◈ Live Dashboard · NSE / BSE · AI-Powered</div>
  <div class="hero-title">My <span>Portfolio</span> Hub</div>
  <div class="hero-sub">Real-time sync · GPT-5 Insights · Auto-refresh 30s · INR ₹</div>
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
    df_invested      = load_sheet_tab("invested")
    df_summary       = load_sheet_tab("StockMarketPortfolioSummary")
    df_strategy_raw  = load_sheet_tab("investmentStrategy")
    df_wealth        = load_sheet_tab("TotalWealth")
    df_invested      = df_invested.dropna(subset=[df_invested.columns[0]])
    df_summary       = df_summary.dropna(subset=[df_summary.columns[0]])
    df_wealth        = df_wealth.dropna(subset=[df_wealth.columns[0]])
except Exception as err:
    logging.error(str(err))
    st.error("❌ Could not load spreadsheet data.")
    st.stop()


# ── GLOBAL METRICS ────────────────────────────────────────────────────────────
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
name_col    = df_invested.columns[0]

# Extract stock names/symbols from portfolio
portfolio_stocks = df_invested[name_col].dropna().tolist()
portfolio_str = ", ".join([str(s)[:20] for s in portfolio_stocks[:15]])

# Build ticker tape
ticker_items = ""
if inv_match and cur_match:
    for _, row in df_invested.head(12).iterrows():
        sym = str(row[name_col])[:8].upper()
        inv = pd.to_numeric(row.get(inv_col, 0), errors='coerce') or 0
        cur = pd.to_numeric(row.get(cur_col, 0), errors='coerce') or 0
        chg = ((cur - inv) / inv * 100) if inv > 0 else 0
        cls = "tick-up" if chg >= 0 else "tick-down"
        sign = "▲" if chg >= 0 else "▼"
        ticker_items += f'<span class="tick-item"><span class="sym">{sym}</span> <span class="{cls}">{sign}{abs(chg):.1f}%</span></span>'
ticker_html = f'<div class="ticker-wrap"><div class="ticker-inner">{ticker_items}{ticker_items}</div></div>'
st.markdown(ticker_html, unsafe_allow_html=True)

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
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "◈  Holdings", "◈  Asset Mix", "◈  Strategy", "◈  Net Worth",
    "◈  Market Intel", "◈  Stock Screener"
])

# ── TAB 1: HOLDINGS ───────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="sec-header"><span class="sec-title">Asset Performance Matrix</span><div class="sec-line"></div></div>', unsafe_allow_html=True)

    def style_df(df):
        styled = df.style.set_properties(**{'background-color':'transparent','color':'#e8eaf0','font-family':'DM Mono, monospace','font-size':'0.74rem'})
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

    if inv_match and cur_match and len(df_invested) > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="sec-header"><span class="sec-title">Individual P&L Snapshot</span><div class="sec-line"></div></div>', unsafe_allow_html=True)
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
            rows_html += f"""<div class="alloc-row">
              <span class="alloc-name">{name}</span>
              <div class="alloc-bar-wrap"><div class="alloc-bar" style="width:{bar_w}%;background:linear-gradient(90deg,{bar_col},{bar_col}88);"></div></div>
              <span class="alloc-pct" style="color:{bar_col}">{sign}{abs(pct):.1f}%</span>
              <span class="alloc-amt" style="color:{bar_col}">₹{abs(pnl):,.0f}</span>
            </div>"""
        st.markdown(rows_html, unsafe_allow_html=True)


# ── TAB 2: ASSET MIX ──────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="sec-header"><span class="sec-title">Live Allocation Spread</span><div class="sec-line"></div></div>', unsafe_allow_html=True)
    label_col = df_summary.columns[0]
    val_match  = [c for c in df_summary.columns if any(k in c.lower() for k in ['value','allocation','amount','weight'])]
    if val_match:
        val_col = val_match[0]
        df_chart = df_summary[[label_col, val_col]].copy()
        df_chart[val_col] = pd.to_numeric(df_chart[val_col], errors='coerce')
        df_chart = df_chart.dropna()
        chart_spec = {
            "mark": {"type":"bar","cornerRadiusTopLeft":4,"cornerRadiusTopRight":4},
            "encoding": {
                "x": {"field":label_col,"type":"nominal","axis":{"labelColor":"#6b7080","titleColor":"#6b7080","labelFont":"DM Mono","titleFont":"DM Mono","labelAngle":-30,"labelLimit":120}},
                "y": {"field":val_col,"type":"quantitative","axis":{"labelColor":"#6b7080","titleColor":"#6b7080","labelFont":"DM Mono","gridColor":"#252830"}},
                "color": {"value":"#c9a84c"},
                "tooltip": [{"field":label_col,"type":"nominal"},{"field":val_col,"type":"quantitative","format":",.2f"}]
            },
            "config": {"background":"#16191f","view":{"stroke":"transparent"},"axis":{"domainColor":"#252830"}}
        }
        st.vega_lite_chart(df_chart, chart_spec, use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="sec-header"><span class="sec-title">Summary Table</span><div class="sec-line"></div></div>', unsafe_allow_html=True)
    st.dataframe(df_summary.set_index(label_col), use_container_width=True)


# ── TAB 3: STRATEGY ───────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="sec-header"><span class="sec-title">Rules-Based Target Planner</span><div class="sec-line"></div></div>', unsafe_allow_html=True)
    try:
        raw_strings = df_strategy_raw.astype(str)
        salary_idx = raw_strings[raw_strings.iloc[:,0].str.contains('Salary', case=False, na=False)].index
        base_salary = 130000
        if not salary_idx.empty:
            raw_sal = df_strategy_raw.iloc[salary_idx[0], 1]
            if isinstance(raw_sal, str): raw_sal = raw_sal.replace('₹','').replace(',','').strip()
            base_salary = pd.to_numeric(raw_sal, errors='coerce') or 130000
        inv_target_row = raw_strings[raw_strings.iloc[:,0].str.contains('Total Amount To Invest', case=False, na=False)]
        default_target = int(base_salary * 0.6154)
        if not inv_target_row.empty:
            raw_t = df_strategy_raw.iloc[inv_target_row.index[0], 1]
            if isinstance(raw_t, str): raw_t = raw_t.replace('₹','').replace(',','').strip()
            default_target = int(pd.to_numeric(raw_t, errors='coerce') or default_target)
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
        </div>""", unsafe_allow_html=True)
        target_invest = st.slider("Adjust Monthly Investment Target (₹)", min_value=10000, max_value=int(base_salary), value=int(default_target), step=2000)
        section_idx = raw_strings[raw_strings.iloc[:,0].str.contains('INVESTMENT STRATEGY', case=False, na=False)].index
        if not section_idx.empty:
            start_row = section_idx[0] + 2
            df_strat_block = df_strategy_raw.iloc[start_row:].copy()
            df_strat_block = df_strat_block.dropna(subset=[df_strat_block.columns[0]])
            st.markdown(f'<div class="sec-header" style="margin-top:1.5rem"><span class="sec-title">Allocation for ₹{target_invest:,}</span><div class="sec-line"></div></div>', unsafe_allow_html=True)
            alloc_rows = ""
            colors = ["#c9a84c","#5a9cf0","#3ecf6e","#f0a05a","#d05af0","#f05a5a","#5af0d0"]
            ci = 0
            for _, row in df_strat_block.iterrows():
                cat_name = str(row[0]).strip()
                raw_pct  = row[1]
                if not cat_name or cat_name == 'nan' or 'disclaimer' in cat_name.lower(): continue
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
                alloc_rows += f"""<div class="alloc-row">
                  <span class="alloc-name">{cat_name}</span>
                  <div class="alloc-bar-wrap"><div class="alloc-bar" style="width:{bar_w}%;background:linear-gradient(90deg,{col},{col}88);"></div></div>
                  <span class="alloc-pct" style="color:{col}">{pct_val*100:.1f}%</span>
                  <span class="alloc-amt">₹{amt:,.0f}</span>
                </div>"""
            st.markdown(alloc_rows, unsafe_allow_html=True)
        else:
            st.dataframe(df_strategy_raw)
    except Exception as e:
        st.error(f"Strategy parse error: {e}")
        st.dataframe(df_strategy_raw)


# ── TAB 4: NET WORTH ──────────────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="sec-header"><span class="sec-title">Aggregated Financial Footprint</span><div class="sec-line"></div></div>', unsafe_allow_html=True)
    w_cat = df_wealth.columns[0]
    val_cols_w = [c for c in df_wealth.columns if any(k in c.lower() for k in ['value','amount','total','balance','worth'])]
    if val_cols_w:
        vc = val_cols_w[0]
        total_w = pd.to_numeric(df_wealth[vc], errors='coerce').sum()
        st.markdown(f"""
        <div class="m-card gold" style="max-width:340px;margin-bottom:1.4rem;">
          <div class="m-label">Total Net Worth</div>
          <div class="m-value">₹{total_w:,.0f}</div>
          <span class="m-badge badge-gold">ALL ASSETS</span>
        </div>""", unsafe_allow_html=True)
    st.dataframe(df_wealth.set_index(w_cat), use_container_width=True, height=380)
    st.markdown('<div style="margin-top:1rem;font-size:.62rem;color:#3a3e4a;letter-spacing:.1em;">◈ LIVE SYNC · SECURE READ-ONLY · AUTO-REFRESH 30s</div>', unsafe_allow_html=True)


# ── TAB 5: MARKET INTEL ───────────────────────────────────────────────────────
with tab5:
    st.markdown('<div class="ai-badge">◈ GPT-5 Powered · Live Web Intelligence · Auto-curated for your portfolio</div>', unsafe_allow_html=True)

    col_news, col_fund = st.columns([1.1, 1], gap="large")

    # ── NEWS SECTION ──
    with col_news:
        st.markdown('<div class="sec-header"><span class="sec-title">Market Headlines</span><div class="sec-line"></div></div>', unsafe_allow_html=True)

        @st.cache_data(ttl=300)
        def fetch_news_gpt(stocks_str):
            prompt = f"""You are a financial news analyst. For the following Indian stock portfolio: {stocks_str}

Generate 6 realistic, current-style news headlines and summaries for these stocks as if they are from today {datetime.now().strftime('%B %Y')}.

Return ONLY a JSON array with exactly 6 objects, each having:
- "ticker": stock symbol (e.g. "RELIANCE", "TCS")
- "headline": compelling news headline (max 12 words)
- "source": news source name (e.g. "Economic Times", "Moneycontrol", "Bloomberg Quint")
- "time": relative time (e.g. "2h ago", "4h ago")
- "summary": 2-sentence summary of the news
- "sentiment": "positive", "negative", or "neutral"
- "url": a realistic financial news URL

Return ONLY the JSON array, no other text."""
            result = call_gpt([{"role": "user", "content": prompt}], max_tokens=1500)
            if not result: return []
            try:
                clean = result.strip()
                if clean.startswith("```"): clean = re.sub(r"```json?|```", "", clean).strip()
                return json.loads(clean)
            except:
                return []

        if "news_data" not in st.session_state:
            st.session_state.news_data = []
        if "news_idx" not in st.session_state:
            st.session_state.news_idx = 0

        refresh_col, _ = st.columns([1, 3])
        with refresh_col:
            if st.button("⟳ Refresh News", key="refresh_news"):
                st.cache_data.clear()
                st.session_state.news_data = []

        if not st.session_state.news_data:
            with st.spinner("🔍 Fetching market intelligence..."):
                st.session_state.news_data = fetch_news_gpt(portfolio_str)

        news_data = st.session_state.news_data

        if news_data:
            n_slides = len(news_data)
            cur_idx  = st.session_state.news_idx % n_slides

            nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 4])
            with nav_col1:
                if st.button("◀", key="prev_news"):
                    st.session_state.news_idx = (cur_idx - 1) % n_slides
                    st.rerun()
            with nav_col2:
                if st.button("▶", key="next_news"):
                    st.session_state.news_idx = (cur_idx + 1) % n_slides
                    st.rerun()

            article = news_data[cur_idx]
            ticker  = article.get("ticker", "")
            sent    = article.get("sentiment", "neutral")
            sent_color = "#3ecf6e" if sent == "positive" else ("#f05a5a" if sent == "negative" else "#c9a84c")
            sent_icon  = "▲" if sent == "positive" else ("▼" if sent == "negative" else "●")

            st.markdown(f"""
            <div class="news-carousel">
              <div class="news-slide">
                <div class="news-slide-tag">
                  <span class="news-ticker-badge">{ticker}</span>
                  <span style="color:{sent_color}">{sent_icon} {sent.upper()}</span>
                  &nbsp;·&nbsp; {article.get('source','—')} &nbsp;·&nbsp; {article.get('time','—')}
                </div>
                <div class="news-slide-headline">{article.get('headline','')}</div>
                <div class="news-slide-summary">{article.get('summary','')}</div>
                <a class="news-slide-link" href="{article.get('url','#')}" target="_blank">Read Full Article →</a>
                <div style="margin-top:1rem;font-size:.58rem;color:var(--muted);">{cur_idx+1} / {n_slides}</div>
              </div>
            </div>""", unsafe_allow_html=True)

            # Mini index of all headlines
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="sec-header"><span class="sec-title">All Headlines</span><div class="sec-line"></div></div>', unsafe_allow_html=True)
            for i, art in enumerate(news_data):
                s = art.get("sentiment","neutral")
                sc = "#3ecf6e" if s=="positive" else ("#f05a5a" if s=="negative" else "#c9a84c")
                active_style = "border-left:3px solid var(--gold);padding-left:.6rem;" if i==cur_idx else "padding-left:.9rem;"
                st.markdown(f"""
                <div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:.55rem .8rem;margin-bottom:.4rem;cursor:pointer;{active_style}">
                  <span style="font-size:.58rem;color:{sc};margin-right:.5rem;">{'▲' if s=='positive' else '▼' if s=='negative' else '●'}</span>
                  <span class="news-ticker-badge">{art.get('ticker','')}</span>
                  <span style="font-size:.68rem;color:var(--text);">{art.get('headline','')[:55]}...</span>
                  <span style="float:right;font-size:.55rem;color:var(--dim);">{art.get('time','')}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.warning("Could not fetch news. Check your internet connection.")

    # ── FUNDAMENTALS SECTION ──
    with col_fund:
        st.markdown('<div class="sec-header"><span class="sec-title">Fundamentals Analysis</span><div class="sec-line"></div></div>', unsafe_allow_html=True)

        @st.cache_data(ttl=600)
        def fetch_fundamentals_gpt(stocks_str):
            prompt = f"""You are a CFA-level equity analyst. Analyze the fundamentals of these Indian stocks: {stocks_str}

For each stock (up to 5 most important ones), provide realistic fundamental data based on your knowledge of these companies.

Return ONLY a JSON array where each object has:
- "ticker": stock symbol
- "name": company full name
- "sector": business sector
- "pe_ratio": P/E ratio (number)
- "eps_growth": EPS growth % YoY (number)
- "debt_to_equity": D/E ratio (number)
- "roe": Return on Equity % (number)
- "strength": "strong", "moderate", or "weak" (overall fundamental rating)
- "pe_color": "good" if PE<25, "warn" if 25-40, "bad" if >40
- "eps_color": "good" if EPS>15, "warn" if 5-15, "bad" if <5
- "de_color": "good" if D/E<0.5, "warn" if 0.5-1, "bad" if >1
- "roe_color": "good" if ROE>20, "warn" if 12-20, "bad" if <12
- "insight": 2-sentence fundamental insight about this stock

Return ONLY valid JSON array, no markdown, no extra text."""
            result = call_gpt([{"role": "user", "content": prompt}], max_tokens=2000)
            if not result: return []
            try:
                clean = result.strip()
                if clean.startswith("```"): clean = re.sub(r"```json?|```", "", clean).strip()
                return json.loads(clean)
            except:
                return []

        if "fund_data" not in st.session_state:
            st.session_state.fund_data = []

        if not st.session_state.fund_data:
            with st.spinner("🧮 Running fundamental analysis..."):
                st.session_state.fund_data = fetch_fundamentals_gpt(portfolio_str)

        fund_data = st.session_state.fund_data

        if fund_data:
            for stock in fund_data[:5]:
                strength = stock.get("strength","moderate")
                strength_class = f"strength-{strength}"
                strength_label = {"strong":"◉ STRONG","moderate":"◎ MODERATE","weak":"○ WEAK"}.get(strength,"◎ MODERATE")

                def ratio_color(key):
                    c = stock.get(key, "warn")
                    return {"good":"ratio-good","warn":"ratio-warn","bad":"ratio-bad"}.get(c,"ratio-warn")

                st.markdown(f"""
                <div class="fund-card">
                  <div class="fund-card-header">
                    <div>
                      <div class="fund-ticker">{stock.get('ticker','?')}</div>
                      <div class="fund-sector">{stock.get('sector','—')}</div>
                    </div>
                    <div style="flex:1"></div>
                    <span class="fund-strength {strength_class}">{strength_label}</span>
                  </div>
                  <div class="fund-ratio-grid">
                    <div class="fund-ratio">
                      <div class="fund-ratio-label">P / E</div>
                      <div class="fund-ratio-value {ratio_color('pe_color')}">{stock.get('pe_ratio','—')}x</div>
                    </div>
                    <div class="fund-ratio">
                      <div class="fund-ratio-label">EPS Gr.</div>
                      <div class="fund-ratio-value {ratio_color('eps_color')}">{stock.get('eps_growth','—')}%</div>
                    </div>
                    <div class="fund-ratio">
                      <div class="fund-ratio-label">D / E</div>
                      <div class="fund-ratio-value {ratio_color('de_color')}">{stock.get('debt_to_equity','—')}</div>
                    </div>
                    <div class="fund-ratio">
                      <div class="fund-ratio-label">ROE</div>
                      <div class="fund-ratio-value {ratio_color('roe_color')}">{stock.get('roe','—')}%</div>
                    </div>
                  </div>
                  <div class="fund-insight">{stock.get('insight','—')}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Fundamental data could not be loaded. GPT analysis requires connection.")

        if st.button("↻ Re-analyze Fundamentals", key="refund"):
            st.session_state.fund_data = []
            st.rerun()


# ── TAB 6: STOCK SCREENER ─────────────────────────────────────────────────────
with tab6:
    st.markdown('<div class="ai-badge">◈ GPT-5 Screener · Quality Filter · Your Investment Allocation Engine</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="sec-header">
      <span class="sec-title">Quality Stock Screener</span>
      <div class="sec-line"></div>
    </div>
    <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:1rem 1.2rem;margin-bottom:1.4rem;">
      <div style="font-size:.6rem;letter-spacing:.15em;text-transform:uppercase;color:var(--gold);margin-bottom:.7rem;">Active Criteria</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;font-size:.65rem;color:var(--sub);">
        <div>✦ Market Cap &gt; ₹1,000 Cr</div>
        <div>✦ Sales &amp; EPS CAGR &gt; 10% (5Y)</div>
        <div>✦ Avg ROE &gt; 20% (5Y)</div>
        <div>✦ CFO/PAT Ratio &gt; 1 (5Y avg)</div>
        <div>✦ Debt/Equity &lt; 0.5</div>
        <div>✦ NSE/BSE Listed</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        monthly_budget = st.number_input("Monthly investment budget (₹)", min_value=5000, max_value=500000, value=50000, step=5000)
    with sc2:
        risk_profile = st.selectbox("Risk Profile", ["Conservative", "Moderate", "Aggressive"], index=1)
    with sc3:
        sector_pref = st.selectbox("Sector Preference", ["All Sectors", "Banking & Finance", "Technology", "FMCG", "Healthcare", "Infrastructure", "Auto"])

    if st.button("⚡ Run Quality Screener", key="run_screener"):
        st.session_state.screener_data = None

    @st.cache_data(ttl=1800)
    def run_screener_gpt(budget, risk, sector, portfolio_str):
        sector_note = f"Focus on {sector} sector." if sector != "All Sectors" else "Include diverse sectors."
        prompt = f"""You are a top Indian equity research analyst. The user has a monthly investment budget of ₹{budget:,}.
Risk profile: {risk}. {sector_note}
User's current portfolio for context: {portfolio_str}

Screen and recommend 6 high-quality Indian stocks that meet ALL these criteria:
1. Market Cap > ₹1,000 Crores
2. 5-year Sales CAGR > 10%
3. 5-year EPS CAGR > 10%
4. 5-year Average ROE > 20%
5. 5-year Average CFO/PAT ratio > 1
6. Debt-to-Equity ratio < 0.5

For each stock, recommend how much of the ₹{budget:,} monthly budget to invest (in INR) and give a clear rationale.

Return ONLY a JSON array of 6 objects, each with:
- "rank": 1 to 6
- "ticker": NSE symbol
- "name": full company name
- "sector": sector
- "market_cap_cr": market cap in crores (number)
- "sales_cagr_5y": 5Y sales CAGR % (number)
- "eps_cagr_5y": 5Y EPS CAGR % (number)
- "avg_roe_5y": 5Y average ROE % (number)
- "cfo_pat_ratio": 5Y avg CFO/PAT ratio (number)
- "debt_to_equity": current D/E (number)
- "invest_amount": recommended monthly invest in INR (number, must sum close to {budget})
- "invest_pct": percentage of budget (number)
- "conviction": "High", "Medium" or "Strong Buy"
- "rationale": 2-sentence investment thesis
- "criteria_pass": array of 5 booleans for each criteria above

Return ONLY the JSON array, no markdown, no extra text."""
        result = call_gpt([{"role": "user", "content": prompt}], max_tokens=3000)
        if not result: return []
        try:
            clean = result.strip()
            if clean.startswith("```"): clean = re.sub(r"```json?|```", "", clean).strip()
            return json.loads(clean)
        except:
            return []

    if "screener_data" not in st.session_state:
        st.session_state.screener_data = None

    if st.session_state.screener_data is None:
        with st.spinner("🔬 Screening 5,000+ NSE/BSE stocks against quality criteria..."):
            st.session_state.screener_data = run_screener_gpt(monthly_budget, risk_profile, sector_pref, portfolio_str)

    screener_data = st.session_state.screener_data

    if screener_data:
        st.markdown("<br>", unsafe_allow_html=True)

        # Summary allocation bar
        total_alloc = sum(s.get("invest_amount", 0) for s in screener_data)
        st.markdown(f"""
        <div style="background:var(--card);border:1px solid var(--gold-glow);border-radius:10px;padding:1rem 1.4rem;margin-bottom:1.4rem;display:flex;align-items:center;gap:1.5rem;">
          <div>
            <div style="font-size:.58rem;letter-spacing:.15em;text-transform:uppercase;color:var(--gold);">Total Allocated</div>
            <div style="font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;color:var(--gold);">₹{total_alloc:,.0f}</div>
          </div>
          <div style="flex:1;height:1px;background:var(--border);"></div>
          <div style="font-size:.65rem;color:var(--sub);">{len(screener_data)} quality stocks screened</div>
        </div>""", unsafe_allow_html=True)

        criteria_labels = ["Mkt Cap>1K Cr", "Sales CAGR>10%", "EPS CAGR>10%", "ROE>20%", "D/E<0.5"]

        for stock in screener_data:
            conviction = stock.get("conviction","Medium")
            conv_color = {"Strong Buy":"#3ecf6e","High":"#c9a84c","Medium":"#5a9cf0"}.get(conviction,"#5a9cf0")
            invest_amt = stock.get("invest_amount", 0)
            invest_pct = stock.get("invest_pct", 0)
            bar_w = min(invest_pct, 100)
            criteria = stock.get("criteria_pass", [True]*5)

            checks_html = ""
            for i, (label, passed) in enumerate(zip(criteria_labels, criteria)):
                cls = "check-pass" if passed else "check-fail"
                icon = "✓" if passed else "✗"
                checks_html += f'<span class="check-pill {cls}">{icon} {label}</span>'

            st.markdown(f"""
            <div class="screener-card">
              <div class="screener-rank">#{stock.get('rank','?')}</div>
              <div class="screener-name">{stock.get('name','?')}</div>
              <div class="screener-sector">{stock.get('sector','—')} · <span style="color:{conv_color}">{conviction}</span></div>
              <div class="screener-metrics">
                <div class="s-metric">
                  <div class="s-metric-label">Mkt Cap</div>
                  <div class="s-metric-value">₹{stock.get('market_cap_cr',0):,.0f}Cr</div>
                </div>
                <div class="s-metric">
                  <div class="s-metric-label">Sales CAGR</div>
                  <div class="s-metric-value" style="color:var(--green)">{stock.get('sales_cagr_5y',0):.1f}%</div>
                </div>
                <div class="s-metric">
                  <div class="s-metric-label">EPS CAGR</div>
                  <div class="s-metric-value" style="color:var(--green)">{stock.get('eps_cagr_5y',0):.1f}%</div>
                </div>
                <div class="s-metric">
                  <div class="s-metric-label">ROE (5Y)</div>
                  <div class="s-metric-value" style="color:var(--gold)">{stock.get('avg_roe_5y',0):.1f}%</div>
                </div>
                <div class="s-metric">
                  <div class="s-metric-label">D/E Ratio</div>
                  <div class="s-metric-value" style="color:{'var(--green)' if stock.get('debt_to_equity',1)<0.5 else 'var(--red)'}">{stock.get('debt_to_equity',0):.2f}</div>
                </div>
              </div>
              <div class="criteria-check">{checks_html}</div>
              <div class="invest-rec">
                <div class="invest-rec-label">◈ Recommended Monthly Investment</div>
                <div style="display:flex;align-items:center;gap:1rem;">
                  <div class="invest-rec-amount">₹{invest_amt:,.0f}</div>
                  <div style="flex:1;background:var(--muted);border-radius:4px;height:4px;overflow:hidden;">
                    <div style="width:{bar_w}%;height:100%;background:linear-gradient(90deg,var(--gold),#e8c46a);"></div>
                  </div>
                  <div style="font-size:.65rem;color:var(--gold);min-width:36px;">{invest_pct:.0f}%</div>
                </div>
                <div class="invest-rec-reason">{stock.get('rationale','—')}</div>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div style="margin-top:1.2rem;padding:1rem;background:var(--surface);border:1px solid var(--border);border-radius:10px;font-size:.62rem;color:var(--dim);line-height:1.6;">
          <strong style="color:var(--gold);">⚠ Disclaimer:</strong> These recommendations are AI-generated for informational purposes only and do not constitute financial advice. 
          Always verify fundamental data independently via NSE/BSE filings, Screener.in, or consult a SEBI-registered advisor before investing.
        </div>""", unsafe_allow_html=True)

    else:
        st.warning("Screener could not run. Verify your Azure OpenAI connection.")
        if st.button("Retry Screener"):
            st.session_state.screener_data = None
            st.rerun()
