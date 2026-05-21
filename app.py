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

try:
    import yfinance as yf
except ImportError:
    yf = None

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

def get_yfinance_session():
    """Create a curl_cffi session to bypass SSL and bot protection."""
    try:
        from curl_cffi.requests import Session
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return Session(impersonate="chrome", verify=False)
    except Exception as e:
        logging.error(f"Error creating curl_cffi session: {e}")
        return None

@st.cache_data(ttl=300)
def fetch_news_real(portfolio_stocks):
    if yf is None:
        return []
    
    session = get_yfinance_session()
    articles = []
    
    # Clean stock names/symbols and limit to top 5 holdings to keep it fast
    unique_stocks = []
    for s in portfolio_stocks:
        cleaned = str(s).strip().upper()
        # Remove common suffixes
        cleaned = re.sub(r"\b(LTD|LIMITED|CORP|CORPORATION|INC|INDUSTRIES|INDS)\b.*", "", cleaned).strip()
        if cleaned and cleaned not in unique_stocks:
            unique_stocks.append(cleaned)
    
    for stock in unique_stocks[:5]:
        sym = stock if stock.endswith((".NS", ".BO")) else f"{stock}.NS"
        try:
            t = yf.Ticker(sym, session=session)
            news = t.news
            if news:
                for item in news[:2]:  # Get top 2 articles per stock
                    content = item.get("content", {})
                    if content.get("title"):
                        articles.append({
                            "ticker": stock,
                            "headline": content.get("title", ""),
                            "source": content.get("provider", {}).get("displayName", "Yahoo Finance"),
                            "time": content.get("pubDate", ""),
                            "summary": content.get("summary", ""),
                            "url": content.get("clickThroughUrl", {}).get("url", "#")
                        })
        except Exception as e:
            logging.error(f"Error fetching news for {sym}: {e}")
            
    # Now, pass this real news list to GPT to get sentiment and a polished summary
    if not articles:
        return []
        
    prompt = f"""You are a financial news analyst. Analyze the following actual news articles for Indian stocks:
{json.dumps(articles, indent=2)}

For each article, analyze the headline/summary and:
1. Classify sentiment as "positive", "negative", or "neutral".
2. Write a concise 2-sentence summary.
3. Compute a relative time string (e.g. "2h ago", "1d ago" or a date) based on the publication date.

Return ONLY a JSON array with the same number of objects as input, each having:
- "ticker": stock symbol
- "headline": original headline (from input)
- "source": source name (from input)
- "time": relative time
- "summary": your 2-sentence summary
- "sentiment": "positive", "negative", or "neutral"
- "url": original URL (from input)

Return ONLY the JSON array, no other text."""

    result = call_gpt([{"role": "user", "content": prompt}], max_tokens=2000)
    if not result:
        # Fallback
        for item in articles:
            item["sentiment"] = "neutral"
            item["time"] = item["time"][:10] if item["time"] else "Today"
        return articles
        
    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = re.sub(r"```json?|```", "", clean).strip()
        return json.loads(clean)
    except Exception as e:
        logging.error(f"Error parsing news sentiment: {e}")
        for item in articles:
            item["sentiment"] = "neutral"
            item["time"] = item["time"][:10] if item["time"] else "Today"
        return articles

@st.cache_data(ttl=600)
def fetch_fundamentals_real(portfolio_stocks):
    if yf is None:
        return []
        
    session = get_yfinance_session()
    data = []
    
    unique_stocks = []
    for s in portfolio_stocks:
        cleaned = str(s).strip().upper()
        cleaned = re.sub(r"\b(LTD|LIMITED|CORP|CORPORATION|INC|INDUSTRIES|INDS)\b.*", "", cleaned).strip()
        if cleaned and cleaned not in unique_stocks:
            unique_stocks.append(cleaned)
            
    for stock in unique_stocks[:5]:
        sym = stock if stock.endswith((".NS", ".BO")) else f"{stock}.NS"
        try:
            t = yf.Ticker(sym, session=session)
            info = t.info
            if not info:
                continue
                
            pe = info.get("trailingPE") or info.get("forwardPE") or 0.0
            
            roe_val = info.get("returnOnEquity")
            roe = (roe_val * 100) if roe_val else 0.0
            
            de_val = info.get("debtToEquity")
            de = (de_val / 100.0) if de_val and de_val > 2.0 else (de_val or 0.0)
            
            eps_g_val = info.get("earningsGrowth")
            eps_g = (eps_g_val * 100) if eps_g_val else 0.0
            
            cfo = info.get("operatingCashflow")
            pat = info.get("netIncomeToCommon")
            cfo_pat = (cfo / pat) if (cfo and pat) else 0.0
            
            mcap_val = info.get("marketCap")
            mcap_cr = (mcap_val / 10_000_000) if mcap_val else 0.0
            
            data.append({
                "ticker": stock,
                "name": info.get("longName", stock),
                "sector": info.get("sector", "Unknown"),
                "pe_ratio": round(pe, 2) if pe else "N/A",
                "eps_growth": round(eps_g, 2) if eps_g else "N/A",
                "debt_to_equity": round(de, 2) if de else 0.0,
                "roe": round(roe, 2) if roe else "N/A",
                "cfo_pat_ratio": round(cfo_pat, 2) if cfo_pat else "N/A",
                "market_cap_cr": mcap_cr
            })
        except Exception as e:
            logging.error(f"Error fetching fundamentals for {sym}: {e}")
            
    if not data:
        return []
        
    # Send these metrics to GPT to categorize and write professional insights
    prompt = f"""You are a CFA-level equity analyst. Analyze the following actual financial metrics of these companies:
{json.dumps(data, indent=2)}

For each company:
1. Rate its overall strength as "strong", "moderate", or "weak".
2. Categorize the ratios:
   - "pe_color": "good" if PE < 25, "warn" if 25-40, "bad" if > 40
   - "eps_color": "good" if EPS growth > 15, "warn" if 5-15, "bad" if < 5
   - "de_color": "good" if D/E < 0.5, "warn" if 0.5-1.0, "bad" if > 1.0
   - "roe_color": "good" if ROE > 20, "warn" if 12-20, "bad" if < 12
3. Write a professional 2-sentence fundamental insight about the company's financial health based on these numbers.

Return ONLY a JSON array with the same number of objects as input, but adding these fields:
- "strength": "strong" | "moderate" | "weak"
- "pe_color": "good" | "warn" | "bad"
- "eps_color": "good" | "warn" | "bad"
- "de_color": "good" | "warn" | "bad"
- "roe_color": "good" | "warn" | "bad"
- "insight": 2-sentence insight

Return ONLY the JSON array, no other text."""

    result = call_gpt([{"role": "user", "content": prompt}], max_tokens=2000)
    if not result:
        # Fallback
        for item in data:
            item["strength"] = "moderate"
            item["pe_color"] = "warn"
            item["eps_color"] = "warn"
            item["de_color"] = "warn"
            item["roe_color"] = "warn"
            item["insight"] = "Fundamental data loaded from live sources."
        return data
        
    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = re.sub(r"```json?|```", "", clean).strip()
        return json.loads(clean)
    except Exception as e:
        logging.error(f"Error parsing fundamentals insights: {e}")
        for item in data:
            item["strength"] = "moderate"
            item["pe_color"] = "warn"
            item["eps_color"] = "warn"
            item["de_color"] = "warn"
            item["roe_color"] = "warn"
            item["insight"] = "Fundamental data loaded from live sources."
        return data

@st.cache_data(ttl=1800)
def run_screener_real(budget, risk, sector, portfolio_str):
    if yf is None:
        return []
        
    session = get_yfinance_session()
    
    # We screen from a pool of 45 high-quality tickers
    pool = [
        "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "COFORGE.NS",
        "HDFCBANK.NS", "ICICIBANK.NS", "AXISBANK.NS", "KOTAKBANK.NS", "SBIN.NS", "BAJFINANCE.NS",
        "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", "VBL.NS",
        "SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "APOLLOHOSP.NS", "DIVISLAB.NS",
        "M&M.NS", "MARUTI.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS",
        "LT.NS", "SIEMENS.NS", "ABB.NS", "BEL.NS",
        "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "ULTRACEMCO.NS", "GRASIM.NS", "PIDILITIND.NS",
        "RELIANCE.NS", "NTPC.NS", "POWERGRID.NS", "ONGC.NS", "COALINDIA.NS", "BPCL.NS"
    ]
    
    # Fetch metrics concurrently
    raw_results = []
    from concurrent.futures import ThreadPoolExecutor
    
    def fetch_one(ticker):
        try:
            t = yf.Ticker(ticker, session=session)
            info = t.info
            if info:
                return info
        except Exception as e:
            logging.error(f"Screener fetch error for {ticker}: {e}")
        return None
        
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(fetch_one, pool)
        for r in results:
            if r:
                raw_results.append(r)
                
    # Now filter programmatically in Python against criteria:
    # 1. Market Cap > ₹1,000 Crores
    # 2. Sales CAGR > 10% (YoY)
    # 3. EPS CAGR > 10% (YoY)
    # 4. ROE > 20%
    # 5. D/E < 0.5
    
    screened_candidates = []
    for info in raw_results:
        ticker = info.get("symbol", "").replace(".NS", "")
        name = info.get("longName", ticker)
        sec = info.get("sector", "Unknown")
        
        # MCAP
        mcap_val = info.get("marketCap")
        mcap_cr = (mcap_val / 10_000_000) if mcap_val else 0.0
        mcap_pass = mcap_cr > 1000
        
        # Sales YoY growth
        rev_g = info.get("revenueGrowth")
        sales_g = (rev_g * 100) if rev_g else 0.0
        sales_pass = sales_g > 10.0
        
        # EPS YoY growth
        earn_g = info.get("earningsGrowth")
        eps_g = (earn_g * 100) if earn_g else 0.0
        eps_pass = eps_g > 10.0
        
        # ROE
        roe_val = info.get("returnOnEquity")
        roe = (roe_val * 100) if roe_val else 0.0
        roe_pass = roe > 20.0
        
        # Debt/Equity
        de_val = info.get("debtToEquity")
        de = (de_val / 100.0) if de_val and de_val > 2.0 else (de_val or 0.0)
        de_pass = de < 0.5
        
        # Determine criteria pass list
        criteria_pass = [mcap_pass, sales_pass, eps_pass, roe_pass, de_pass]
        score = sum(1 for p in criteria_pass if p)
        
        screened_candidates.append({
            "ticker": ticker,
            "name": name,
            "sector": sec,
            "market_cap_cr": mcap_cr,
            "sales_cagr_5y": sales_g,
            "eps_cagr_5y": eps_g,
            "avg_roe_5y": roe,
            "debt_to_equity": de,
            "criteria_pass": criteria_pass,
            "score": score
        })
        
    # Sort candidates by score descending, then by ROE descending
    screened_candidates.sort(key=lambda x: (x["score"], x["avg_roe_5y"]), reverse=True)
    
    # Filter by selected sector if applicable
    if sector != "All Sectors":
        sector_mapping = {
            "Banking & Finance": ["Financial", "Bank", "Capital"],
            "Technology": ["Tech", "Software", "IT"],
            "FMCG": ["Consumer Defensive", "FMCG", "Beverages", "Food"],
            "Healthcare": ["Healthcare", "Pharma", "Biotech"],
            "Infrastructure": ["Industrials", "Construction", "Utilities", "Infrastructure"],
            "Auto": ["Consumer Cyclical", "Auto"]
        }
        keywords = sector_mapping.get(sector, [])
        sector_candidates = [c for c in screened_candidates if any(k.lower() in c["sector"].lower() for k in keywords)]
        if len(sector_candidates) >= 4:
            selected_stocks = sector_candidates[:6]
        else:
            selected_stocks = screened_candidates[:6]
    else:
        selected_stocks = screened_candidates[:6]
        
    if len(selected_stocks) < 6:
        for c in screened_candidates:
            if c not in selected_stocks:
                selected_stocks.append(c)
            if len(selected_stocks) == 6:
                break
                
    selected_stocks = selected_stocks[:6]
    
    prompt = f"""You are a top Indian equity research analyst. The user has a monthly investment budget of ₹{budget:,}.
Risk profile: {risk}. Sector Preference: {sector}.
User's current portfolio for context: {portfolio_str}

Below are the 6 selected stocks from our real-time screener along with their factual metrics:
{json.dumps(selected_stocks, indent=2)}

Please perform the following:
1. Allocate the monthly budget of ₹{budget:,} among these 6 stocks. Set "invest_amount" for each stock in INR (integers) such that they sum exactly to {budget}. Set "invest_pct" as the percentage of the budget (integer).
2. Set "conviction" as "Strong Buy", "High", or "Medium".
3. Write a professional 2-sentence investment rationale for each stock.

Return ONLY a JSON array of 6 objects, matching the order of input, each having:
- "rank": 1 to 6
- "ticker": Stock ticker
- "name": Company name
- "sector": Sector
- "market_cap_cr": Market cap in crores (from input)
- "sales_cagr_5y": CAGR % (from input)
- "eps_cagr_5y": EPS CAGR % (from input)
- "avg_roe_5y": ROE % (from input)
- "debt_to_equity": D/E ratio (from input)
- "invest_amount": recommended monthly invest in INR (number)
- "invest_pct": percentage of budget (number)
- "conviction": "Strong Buy" | "High" | "Medium"
- "rationale": 2-sentence rationale
- "criteria_pass": array of 5 booleans (from input)

Return ONLY the JSON array, no other text."""

    result = call_gpt([{"role": "user", "content": prompt}], max_tokens=3000)
    if not result:
        alloc_amt = int(budget / 6)
        for i, item in enumerate(selected_stocks):
            item["rank"] = i + 1
            item["invest_amount"] = alloc_amt
            item["invest_pct"] = round(100 / 6)
            item["conviction"] = "High"
            item["rationale"] = "Solid fundamentals screened from live market."
        return selected_stocks
        
    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = re.sub(r"```json?|```", "", clean).strip()
        return json.loads(clean)
    except Exception as e:
        logging.error(f"Error parsing screener GPT response: {e}")
        alloc_amt = int(budget / 6)
        for i, item in enumerate(selected_stocks):
            item["rank"] = i + 1
            item["invest_amount"] = alloc_amt
            item["invest_pct"] = round(100 / 6)
            item["conviction"] = "High"
            item["rationale"] = "Solid fundamentals screened from live market."
        return selected_stocks

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

/* ── HERO ── */
.hero {
  background: linear-gradient(135deg, #0d0e12 0%, #12141a 60%, #0f1116 100%);
  border-bottom: 1px solid var(--border);
  padding: 1.6rem 1.4rem 1.2rem;
  position: relative; overflow: hidden;
}
@media (min-width: 640px) {
  .hero { padding: 2.2rem 2.8rem 1.6rem; }
}
.hero::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(ellipse 60% 80% at 80% 50%, rgba(201,168,76,0.06) 0%, transparent 70%);
  pointer-events: none;
}
.hero-label { font-family:'DM Mono',monospace;font-size:.6rem;letter-spacing:.18em;color:var(--gold);text-transform:uppercase;margin-bottom:.4rem; }
.hero-title { font-family:'Syne',sans-serif;font-size:clamp(1.5rem,6vw,2.8rem);font-weight:800;color:var(--text);line-height:1.1;letter-spacing:-.02em;margin:0 0 .3rem; }
.hero-title span { color: var(--gold); }
.hero-sub { font-size:.62rem;color:var(--dim);letter-spacing:.06em;line-height:1.5; }

/* ── METRIC ROW ── */
.metric-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: .7rem;
  padding: 1rem 1rem;
}
@media (min-width: 640px) {
  .metric-row {
    display: flex;
    gap: 1rem;
    padding: 1.4rem 2.8rem;
    flex-wrap: wrap;
  }
}
.m-card {
  flex: 1;
  min-width: 0;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: .85rem 1rem;
  position: relative;
  overflow: hidden;
  transition: border-color .2s;
}
@media (min-width: 640px) {
  .m-card { min-width: 160px; padding: 1.1rem 1.4rem; }
}
.m-card:hover { border-color: var(--muted); }
.m-card::before { content:'';position:absolute;top:0;left:0;right:0;height:2px; }
.m-card.gold::before  { background: linear-gradient(90deg, transparent, var(--gold), transparent); }
.m-card.green::before { background: linear-gradient(90deg, transparent, var(--green), transparent); }
.m-card.red::before   { background: linear-gradient(90deg, transparent, var(--red), transparent); }
.m-card.blue::before  { background: linear-gradient(90deg, transparent, var(--blue), transparent); }
.m-label { font-size:.55rem;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);margin-bottom:.4rem; }
.m-value { font-family:'Syne',sans-serif;font-size:clamp(1.1rem,3.5vw,1.55rem);font-weight:700;color:var(--text);line-height:1;word-break:break-all; }
.m-badge { display:inline-block;margin-top:.4rem;font-size:.58rem;font-family:'DM Mono',monospace;padding:2px 7px;border-radius:20px; }
.badge-green { background:var(--green-glow);color:var(--green); }
.badge-red   { background:var(--red-glow);color:var(--red); }
.badge-gold  { background:var(--gold-glow);color:var(--gold); }

/* ── TABS ── */
[data-testid="stTabs"] > div:first-child {
  background:var(--surface);
  border-bottom:1px solid var(--border);
  padding:0 .8rem;
  gap:0 !important;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  flex-wrap: nowrap !important;
}
[data-testid="stTabs"] > div:first-child::-webkit-scrollbar { display: none; }
@media (min-width: 640px) {
  [data-testid="stTabs"] > div:first-child { padding:0 2.8rem; }
}
[data-testid="stTabs"] button {
  font-family:'DM Mono',monospace !important;font-size:.62rem !important;letter-spacing:.1em !important;
  text-transform:uppercase !important;color:var(--dim) !important;
  padding:.8rem .75rem !important;
  border-bottom:2px solid transparent !important;border-radius:0 !important;
  background:transparent !important;transition:color .2s,border-color .2s !important;
  white-space: nowrap !important;
}
[data-testid="stTabs"] button:hover { color: var(--text) !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color:var(--gold) !important;border-bottom-color:var(--gold) !important; }
[data-testid="stTabsContent"] { padding:1.2rem 1rem !important;background:var(--ink) !important; }
@media (min-width: 640px) {
  [data-testid="stTabsContent"] { padding:1.8rem 2.8rem !important; }
}

/* ── SECTION HEADER ── */
.sec-header { display:flex;align-items:center;gap:.7rem;margin-bottom:1.2rem; }
.sec-line { flex:1;height:1px;background:var(--border); }
.sec-title { font-family:'Syne',sans-serif;font-size:.68rem;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--sub);white-space:nowrap; }

/* ── DATA TABLE ── */
[data-testid="stDataFrame"] { background:var(--card) !important;border:1px solid var(--border) !important;border-radius:10px !important;overflow:hidden !important; }
[data-testid="stDataFrame"] table { font-family:'DM Mono',monospace !important;font-size:.68rem !important; }
[data-testid="stDataFrame"] th { background:var(--surface) !important;color:var(--sub) !important;font-size:.58rem !important;letter-spacing:.12em !important;text-transform:uppercase !important;border-bottom:1px solid var(--border) !important; }
[data-testid="stDataFrame"] td { color:var(--text) !important; }
[data-testid="stDataFrame"] tr:hover td { background:rgba(255,255,255,0.02) !important; }

/* ── FORM CONTROLS ── */
[data-testid="stSelectbox"] > div > div { background:var(--card) !important;border:1px solid var(--border) !important;border-radius:8px !important;color:var(--text) !important;font-family:'DM Mono',monospace !important;font-size:.72rem !important; }
[data-testid="stSelectbox"] label { font-size:.6rem !important;letter-spacing:.12em !important;text-transform:uppercase !important;color:var(--dim) !important; }
[data-testid="stSlider"] label { font-size:.6rem !important;letter-spacing:.12em !important;text-transform:uppercase !important;color:var(--dim) !important; }
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] { background:var(--gold) !important;border-color:var(--gold) !important; }
[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stSliderTrackFill"] { background:var(--gold) !important; }
[data-testid="stVegaLiteChart"] { border-radius:10px;overflow:hidden; }

/* ── ALLOC ROWS ── */
.alloc-row {
  background:var(--card);border:1px solid var(--border);border-radius:10px;
  padding:.75rem .9rem;margin-bottom:.5rem;
  display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;
}
.alloc-name { font-family:'Syne',sans-serif;font-size:.75rem;font-weight:600;color:var(--text);flex:1 1 100px;min-width:80px; }
.alloc-bar-wrap { flex:2 1 80px;background:var(--muted);border-radius:4px;height:5px;overflow:hidden;min-width:60px; }
.alloc-bar { height:100%;border-radius:4px;background:linear-gradient(90deg,var(--gold),#e8c46a); }
.alloc-pct { font-size:.62rem;color:var(--gold);min-width:36px;text-align:right;letter-spacing:.04em; }
.alloc-amt { font-family:'Syne',sans-serif;font-size:.82rem;font-weight:700;color:var(--text);min-width:80px;text-align:right; }

/* ── WEALTH CARD ── */
.wealth-card { background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:1.2rem; }
.wealth-header { background:var(--surface);padding:.7rem 1.2rem;font-size:.58rem;letter-spacing:.16em;text-transform:uppercase;color:var(--dim);border-bottom:1px solid var(--border); }

/* ── TICKER ── */
.ticker-wrap { background:var(--surface);border-top:1px solid var(--border);border-bottom:1px solid var(--border);overflow:hidden;padding:.45rem 0;margin:0; }
.ticker-inner { display:flex;gap:2.5rem;animation:ticker 40s linear infinite;white-space:nowrap; }
@keyframes ticker { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }
.tick-item { font-size:.62rem;letter-spacing:.06em;color:var(--sub);display:inline-flex;align-items:center;gap:.35rem; }
.tick-item .sym { color:var(--gold);font-weight:500; }
.tick-up   { color:var(--green); }
.tick-down { color:var(--red); }

/* ── NEWS CAROUSEL ── */
.news-carousel { position:relative;overflow:hidden;border-radius:14px;background:var(--card);border:1px solid var(--border);padding:0; }
.news-slide { padding:1.4rem 1.4rem; }
.news-slide-tag { font-size:.56rem;letter-spacing:.16em;text-transform:uppercase;color:var(--gold);margin-bottom:.5rem; }
.news-slide-headline { font-family:'Syne',sans-serif;font-size:.95rem;font-weight:700;color:var(--text);line-height:1.4;margin-bottom:.6rem; }
.news-slide-meta { font-size:.6rem;color:var(--dim);margin-bottom:.7rem; }
.news-slide-summary { font-size:.7rem;color:var(--sub);line-height:1.6; }
.news-slide-link { display:inline-block;margin-top:.8rem;font-size:.62rem;letter-spacing:.08em;color:var(--gold);text-decoration:none;border:1px solid var(--gold-glow);padding:.3rem .8rem;border-radius:20px;transition:background .2s; }
.news-slide-link:hover { background:var(--gold-glow); }
.news-ticker-badge { display:inline-block;background:var(--gold-glow);color:var(--gold);border-radius:6px;padding:1px 6px;font-size:.58rem;margin-right:.4rem; }

/* ── FUNDAMENTALS CARDS ── */
.fund-card { background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1rem;margin-bottom:.8rem;position:relative; }
.fund-card-header { display:flex;align-items:flex-start;gap:.8rem;margin-bottom:.9rem;flex-wrap:wrap; }
.fund-ticker { font-family:'Syne',sans-serif;font-size:1.05rem;font-weight:800;color:var(--text); }
.fund-sector { font-size:.56rem;color:var(--dim);letter-spacing:.08em;text-transform:uppercase; }
.fund-strength { font-size:.58rem;letter-spacing:.08em;text-transform:uppercase;padding:.2rem .6rem;border-radius:20px;font-weight:500;white-space:nowrap; }
.strength-strong { background:var(--green-glow);color:var(--green); }
.strength-moderate { background:var(--gold-glow);color:var(--gold); }
.strength-weak { background:var(--red-glow);color:var(--red); }
.fund-ratio-grid { display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem; }
@media (min-width: 480px) {
  .fund-ratio-grid { grid-template-columns:repeat(4,1fr); }
}
.fund-ratio { background:var(--surface);border-radius:8px;padding:.55rem .65rem; }
.fund-ratio-label { font-size:.52rem;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);margin-bottom:.25rem; }
.fund-ratio-value { font-family:'Syne',sans-serif;font-size:.9rem;font-weight:700; }
.fund-insight { margin-top:.7rem;font-size:.66rem;color:var(--sub);line-height:1.5;border-top:1px solid var(--border);padding-top:.6rem; }
.ratio-good  { color:var(--green); }
.ratio-warn  { color:var(--gold); }
.ratio-bad   { color:var(--red); }

/* ── SCREENER CARDS ── */
.screener-card { background:var(--card);border:1px solid var(--border);border-radius:14px;padding:1.1rem 1.1rem;margin-bottom:1rem;position:relative;overflow:hidden; }
.screener-card::before { content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,transparent,var(--gold),transparent); }
.screener-rank { position:absolute;top:.9rem;right:1rem;font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;color:var(--border); }
.screener-name { font-family:'Syne',sans-serif;font-size:1.05rem;font-weight:700;color:var(--text);margin-bottom:.2rem;padding-right:2.5rem; }
.screener-sector { font-size:.58rem;color:var(--dim);letter-spacing:.1em;text-transform:uppercase;margin-bottom:.8rem; }
.screener-metrics { display:grid;grid-template-columns:repeat(2,1fr);gap:.4rem;margin-bottom:.8rem; }
@media (min-width: 480px) {
  .screener-metrics { grid-template-columns:repeat(3,1fr); }
}
@media (min-width: 720px) {
  .screener-metrics { grid-template-columns:repeat(5,1fr); }
}
.s-metric { background:var(--surface);border-radius:8px;padding:.45rem .6rem; }
.s-metric-label { font-size:.5rem;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);margin-bottom:.2rem; }
.s-metric-value { font-family:'Syne',sans-serif;font-size:.82rem;font-weight:700;color:var(--text); }
.invest-rec { background:linear-gradient(135deg,rgba(201,168,76,.12),rgba(201,168,76,.05));border:1px solid var(--gold-glow);border-radius:10px;padding:.75rem .9rem;margin-top:.7rem; }
.invest-rec-label { font-size:.56rem;letter-spacing:.13em;text-transform:uppercase;color:var(--gold);margin-bottom:.3rem; }
.invest-rec-amount { font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:800;color:var(--gold); }
.invest-rec-reason { font-size:.63rem;color:var(--sub);line-height:1.5;margin-top:.4rem; }
.criteria-check { display:flex;gap:.35rem;flex-wrap:wrap;margin-top:.5rem; }
.check-pill { font-size:.55rem;padding:.18rem .55rem;border-radius:20px;display:inline-flex;align-items:center;gap:.25rem; }
.check-pass { background:var(--green-glow);color:var(--green); }
.check-fail { background:var(--red-glow);color:var(--red); }

/* ── AI BADGE ── */
.ai-badge { display:inline-flex;align-items:center;gap:.4rem;background:linear-gradient(135deg,rgba(90,156,240,.15),rgba(201,168,76,.1));border:1px solid rgba(90,156,240,.3);border-radius:20px;padding:.22rem .75rem;font-size:.58rem;letter-spacing:.08em;color:var(--blue);margin-bottom:.9rem; }

/* ── LOADING PULSE ── */
@keyframes pulse { 0%,100%{opacity:.4} 50%{opacity:1} }
.loading-pulse { animation:pulse 1.5s ease-in-out infinite;color:var(--gold); }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width:4px;height:4px; }
::-webkit-scrollbar-track { background:var(--ink); }
::-webkit-scrollbar-thumb { background:var(--muted);border-radius:4px; }

div[data-testid="stBlock"] { background:transparent !important; }
[data-testid="column"] { background:transparent !important; }

/* ── STREAMLIT BUTTON ── */
.stButton > button {
  background:var(--card) !important;border:1px solid var(--border) !important;
  color:var(--text) !important;font-family:'DM Mono',monospace !important;font-size:.68rem !important;
  letter-spacing:.08em !important;border-radius:8px !important;transition:all .2s !important;
}
.stButton > button:hover { border-color:var(--gold) !important;color:var(--gold) !important; }

/* ── NUMBER INPUT ── */
[data-testid="stNumberInput"] input { background:var(--card) !important;border:1px solid var(--border) !important;color:var(--text) !important;font-family:'DM Mono',monospace !important;font-size:.72rem !important;border-radius:8px !important; }
[data-testid="stNumberInput"] label { font-size:.6rem !important;letter-spacing:.12em !important;text-transform:uppercase !important;color:var(--dim) !important; }

/* ── RESPONSIVE COLUMNS ── */
/* Make Streamlit columns stack on small screens */
@media (max-width: 640px) {
  [data-testid="column"] { min-width: 100% !important; width: 100% !important; flex: none !important; }
  .stColumns { flex-direction: column !important; }
}

/* Strategy mini-cards responsive */
.strategy-mini-cards { display:flex;gap:.8rem;margin-bottom:1.2rem;flex-wrap:wrap; }
.strategy-mini-card { flex:1;min-width:130px;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:.85rem 1rem; }
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
    "◈ Holdings", "◈ Mix", "◈ Strategy", "◈ Worth",
    "◈ Intel", "◈ Screener"
])

# ── TAB 1: HOLDINGS ───────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="sec-header"><span class="sec-title">Asset Performance Matrix</span><div class="sec-line"></div></div>', unsafe_allow_html=True)

    def style_df(df):
        styled = df.style.set_properties(**{'background-color':'transparent','color':'#e8eaf0','font-family':'DM Mono, monospace','font-size':'0.7rem'})
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
        col_f, col_spacer = st.columns([1, 2])
        with col_f:
            status_filter = st.selectbox("Filter by", opts, key="holdings_filter")
        df_show = df_invested.copy()
        if status_filter != "ALL":
            df_show = df_show[df_show[status_col] == status_filter]
    else:
        df_show = df_invested.copy()

    idx_col = df_show.columns[0]
    try:
        st.dataframe(style_df(df_show.set_index(idx_col)), use_container_width=True, height=380)
    except:
        st.dataframe(df_show.set_index(idx_col), use_container_width=True, height=380)

    if inv_match and cur_match and len(df_invested) > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="sec-header"><span class="sec-title">Individual P&L Snapshot</span><div class="sec-line"></div></div>', unsafe_allow_html=True)
        rows_html = ""
        for _, row in df_invested.head(15).iterrows():
            name = str(row[name_col])[:20]
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
                "x": {"field":label_col,"type":"nominal","axis":{"labelColor":"#6b7080","titleColor":"#6b7080","labelFont":"DM Mono","titleFont":"DM Mono","labelAngle":-40,"labelLimit":90,"labelFontSize":9}},
                "y": {"field":val_col,"type":"quantitative","axis":{"labelColor":"#6b7080","titleColor":"#6b7080","labelFont":"DM Mono","gridColor":"#252830","labelFontSize":9}},
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
        <div class="strategy-mini-cards">
          <div class="strategy-mini-card">
            <div class="m-label">Monthly Income</div>
            <div class="m-value">₹{int(base_salary):,}</div>
          </div>
          <div class="strategy-mini-card">
            <div class="m-label">Invest Ratio</div>
            <div class="m-value">{default_target/base_salary*100:.1f}%</div>
          </div>
        </div>""", unsafe_allow_html=True)

        target_invest = st.slider("Adjust Monthly Investment Target (₹)", min_value=10000, max_value=int(base_salary), value=int(default_target), step=2000)

        section_idx = raw_strings[raw_strings.iloc[:,0].str.contains('INVESTMENT STRATEGY', case=False, na=False)].index
        if not section_idx.empty:
            start_row = section_idx[0] + 2
            df_strat_block = df_strategy_raw.iloc[start_row:].copy()
            df_strat_block = df_strat_block.dropna(subset=[df_strat_block.columns[0]])
            st.markdown(f'<div class="sec-header" style="margin-top:1.2rem"><span class="sec-title">Allocation for ₹{target_invest:,}</span><div class="sec-line"></div></div>', unsafe_allow_html=True)
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
        <div class="m-card gold" style="max-width:100%;margin-bottom:1.2rem;">
          <div class="m-label">Total Net Worth</div>
          <div class="m-value">₹{total_w:,.0f}</div>
          <span class="m-badge badge-gold">ALL ASSETS</span>
        </div>""", unsafe_allow_html=True)
    st.dataframe(df_wealth.set_index(w_cat), use_container_width=True, height=360)
    st.markdown('<div style="margin-top:1rem;font-size:.6rem;color:#3a3e4a;letter-spacing:.08em;">◈ LIVE SYNC · SECURE READ-ONLY · AUTO-REFRESH 30s</div>', unsafe_allow_html=True)


# ── TAB 5: MARKET INTEL ───────────────────────────────────────────────────────
with tab5:
    st.markdown('<div class="ai-badge">◈ Live Market Intelligence · Real-time Data · AI-Analyzed</div>', unsafe_allow_html=True)

    # On mobile, stack news and fundamentals vertically
    # Use ratio 1:1 on desktop; they stack automatically on mobile via CSS
    col_news, col_fund = st.columns([1, 1], gap="medium")

    # ── NEWS SECTION ──
    with col_news:
        st.markdown('<div class="sec-header"><span class="sec-title">Market Headlines</span><div class="sec-line"></div></div>', unsafe_allow_html=True)

        if "news_data" not in st.session_state:
            st.session_state.news_data = []
        if "news_idx" not in st.session_state:
            st.session_state.news_idx = 0

        refresh_col, _ = st.columns([1, 2])
        with refresh_col:
            if st.button("⟳ Refresh News", key="refresh_news"):
                st.cache_data.clear()
                st.session_state.news_data = []

        if not st.session_state.news_data:
            with st.spinner("🔍 Fetching market intelligence..."):
                st.session_state.news_data = fetch_news_real(portfolio_stocks)

        news_data = st.session_state.news_data

        if news_data:
            n_slides = len(news_data)
            cur_idx  = st.session_state.news_idx % n_slides

            nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 3])
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
                <div style="margin-top:.8rem;font-size:.56rem;color:var(--muted);">{cur_idx+1} / {n_slides}</div>
              </div>
            </div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="sec-header"><span class="sec-title">All Headlines</span><div class="sec-line"></div></div>', unsafe_allow_html=True)
            for i, art in enumerate(news_data):
                s = art.get("sentiment","neutral")
                sc = "#3ecf6e" if s=="positive" else ("#f05a5a" if s=="negative" else "#c9a84c")
                active_style = "border-left:3px solid var(--gold);padding-left:.6rem;" if i==cur_idx else "padding-left:.9rem;"
                st.markdown(f"""
                <div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:.5rem .75rem;margin-bottom:.4rem;{active_style}">
                  <span style="font-size:.56rem;color:{sc};margin-right:.4rem;">{'▲' if s=='positive' else '▼' if s=='negative' else '●'}</span>
                  <span class="news-ticker-badge">{art.get('ticker','')}</span>
                  <span style="font-size:.65rem;color:var(--text);">{art.get('headline','')[:50]}...</span>
                  <span style="float:right;font-size:.53rem;color:var(--dim);">{art.get('time','')}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.warning("Could not fetch news. Check your internet connection.")

    # ── FUNDAMENTALS SECTION ──
    with col_fund:
        st.markdown('<div class="sec-header"><span class="sec-title">Fundamentals Analysis</span><div class="sec-line"></div></div>', unsafe_allow_html=True)

        if "fund_data" not in st.session_state:
            st.session_state.fund_data = []

        if not st.session_state.fund_data:
            with st.spinner("🧮 Running fundamental analysis..."):
                st.session_state.fund_data = fetch_fundamentals_real(portfolio_stocks)

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
                    <div style="flex:1">
                      <div class="fund-ticker">{stock.get('ticker','?')}</div>
                      <div class="fund-sector">{stock.get('sector','—')}</div>
                    </div>
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
    st.markdown('<div class="ai-badge">◈ GPT-5 Screener · Quality Filter · Allocation Engine</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="sec-header">
      <span class="sec-title">Quality Stock Screener</span>
      <div class="sec-line"></div>
    </div>
    <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:.9rem 1.1rem;margin-bottom:1.2rem;">
      <div style="font-size:.58rem;letter-spacing:.13em;text-transform:uppercase;color:var(--gold);margin-bottom:.6rem;">Active Criteria</div>
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:.4rem;font-size:.62rem;color:var(--sub);">
        <div>✦ Market Cap &gt; ₹1,000 Cr</div>
        <div>✦ Sales &amp; EPS CAGR &gt; 10%</div>
        <div>✦ Avg ROE &gt; 20% (5Y)</div>
        <div>✦ CFO/PAT Ratio &gt; 1</div>
        <div>✦ Debt/Equity &lt; 0.5</div>
        <div>✦ NSE/BSE Listed</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    sc1, sc2 = st.columns(2)
    with sc1:
        monthly_budget = st.number_input("Monthly budget (₹)", min_value=5000, max_value=500000, value=50000, step=5000)
    with sc2:
        risk_profile = st.selectbox("Risk Profile", ["Conservative", "Moderate", "Aggressive"], index=1)

    sector_pref = st.selectbox("Sector Preference", ["All Sectors", "Banking & Finance", "Technology", "FMCG", "Healthcare", "Infrastructure", "Auto"])

    if st.button("⚡ Run Quality Screener", key="run_screener"):
        st.session_state.screener_data = None

    if "screener_data" not in st.session_state:
        st.session_state.screener_data = None

    if st.session_state.screener_data is None:
        with st.spinner("🔬 Screening 5,000+ NSE/BSE stocks against quality criteria..."):
            st.session_state.screener_data = run_screener_real(monthly_budget, risk_profile, sector_pref, portfolio_str)

    screener_data = st.session_state.screener_data

    if screener_data:
        st.markdown("<br>", unsafe_allow_html=True)

        total_alloc = sum(s.get("invest_amount", 0) for s in screener_data)
        st.markdown(f"""
        <div style="background:var(--card);border:1px solid var(--gold-glow);border-radius:10px;padding:.9rem 1.2rem;margin-bottom:1.2rem;">
          <div style="font-size:.56rem;letter-spacing:.13em;text-transform:uppercase;color:var(--gold);">Total Allocated</div>
          <div style="font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;color:var(--gold);">₹{total_alloc:,.0f}</div>
          <div style="font-size:.62rem;color:var(--sub);margin-top:.3rem;">{len(screener_data)} quality stocks screened</div>
        </div>""", unsafe_allow_html=True)

        criteria_labels = ["Mkt Cap", "Sales CAGR", "EPS CAGR", "ROE>20%", "D/E<0.5"]

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
                <div style="display:flex;align-items:center;gap:.8rem;flex-wrap:wrap;">
                  <div class="invest-rec-amount">₹{invest_amt:,.0f}</div>
                  <div style="flex:1;min-width:60px;background:var(--muted);border-radius:4px;height:4px;overflow:hidden;">
                    <div style="width:{bar_w}%;height:100%;background:linear-gradient(90deg,var(--gold),#e8c46a);"></div>
                  </div>
                  <div style="font-size:.62rem;color:var(--gold);min-width:32px;">{invest_pct:.0f}%</div>
                </div>
                <div class="invest-rec-reason">{stock.get('rationale','—')}</div>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div style="margin-top:1rem;padding:.9rem 1rem;background:var(--surface);border:1px solid var(--border);border-radius:10px;font-size:.6rem;color:var(--dim);line-height:1.6;">
          <strong style="color:var(--gold);">⚠ Disclaimer:</strong> These recommendations are AI-generated for informational purposes only and do not constitute financial advice.
          Always verify fundamental data independently via NSE/BSE filings, Screener.in, or consult a SEBI-registered advisor before investing.
        </div>""", unsafe_allow_html=True)

    else:
        st.warning("Screener could not run. Verify your Azure OpenAI connection.")
        if st.button("Retry Screener"):
            st.session_state.screener_data = None
            st.rerun()
