#!/usr/bin/env python3
"""
CFO Silvia Automated Content Pipeline
=======================================
Fully automated: scrape data -> Claude generates post -> render card -> review -> post to X.

Modes:
    python silvia_auto.py earnings NVDA       # Earnings post for a specific ticker
    python silvia_auto.py macro CPI           # Economic data post (CPI, JOBS, GDP, PCE, FED)
    python silvia_auto.py daily               # Daily wrap (run after market close)
    python silvia_auto.py cron                # Daemon mode: runs daily wrap at 4:30 PM EST,
                                              #   watches for earnings, fires on macro events

Setup:
    pip install requests beautifulsoup4 playwright
    playwright install chromium

    Copy .env.example to .env and fill in what you actually use. ALL KEYS
    ARE OPTIONAL. The pipeline detects what is available and falls back
    accordingly:

        ANTHROPIC_API_KEY=sk-ant-...  (optional; if missing, use Claude Code)
        TWITTER_API_KEY=...           (optional; if missing, manual post)
        TWITTER_API_SECRET=...
        TWITTER_ACCESS_TOKEN=...
        TWITTER_ACCESS_SECRET=...
        TWITTER_BEARER_TOKEN=...

    Optional:
        AUTO_POST=false          # Set to 'true' to skip human confirmation
        LOG_DIR=./silvia_logs    # Where to write logs
        CARD_TEMPLATE=./card.html  # Custom card template path

Claude Code mode:
    If you do not have an ANTHROPIC_API_KEY, use Claude Code (claude.ai/code)
    to run the agents by hand. The prompts in triplex/prompts/*.txt are
    designed to work either way.

Manual X posting:
    If you do not have Twitter API keys, the pipeline will still render
    the card image and the post text to silvia_logs/. Post manually by
    copying the post_*.txt content into an X compose box and attaching
    the card PNG.
"""

import os
import re
import sys
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from textwrap import dedent

# ─── CONFIG ──────────────────────────────────────────────────────

def load_env():
    """Load .env file if present."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

LOG_DIR = Path(os.environ.get("LOG_DIR", "./silvia_logs"))
LOG_DIR.mkdir(exist_ok=True)
AUTO_POST = os.environ.get("AUTO_POST", "false").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "pipeline.log"),
    ],
)
log = logging.getLogger("silvia")


# ═══════════════════════════════════════════════════════════════════
#  PART 1: DATA SCRAPERS (free public sources, no APIs needed)
# ═══════════════════════════════════════════════════════════════════

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def scrape_earnings(ticker: str) -> dict:
    """
    Pull earnings data from Yahoo Finance.
    Returns: eps_actual, eps_est, rev_actual, rev_est, ah_move, quarter, company, guidance, news
    """
    log.info(f"Scraping earnings data for {ticker}...")
    ticker = ticker.upper()
    data = {"ticker": ticker}

    # Yahoo Finance API (public JSON endpoint)
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
    params = {"modules": "earnings,price,financialData,defaultKeyStatistics"}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        j = r.json()["quoteSummary"]["result"][0]

        price = j.get("price", {})
        data["company"] = price.get("shortName", ticker)
        data["market_price"] = price.get("regularMarketPrice", {}).get("raw", 0)
        pre_post = price.get("postMarketPrice", {}).get("raw") or price.get("preMarketPrice", {}).get("raw")
        if pre_post and data["market_price"]:
            ah_pct = ((pre_post - data["market_price"]) / data["market_price"]) * 100
            data["ah_move"] = f"{ah_pct:+.1f}%"
        else:
            data["ah_move"] = "N/A"

        earnings = j.get("earnings", {}).get("earningsChart", {})
        quarterly = earnings.get("quarterly", [])
        if quarterly:
            latest = quarterly[-1]
            data["eps_actual"] = f"${latest.get('actual', {}).get('raw', 'N/A')}"
            data["eps_est"] = f"${latest.get('estimate', {}).get('raw', 'N/A')}"
            data["quarter"] = latest.get("date", "N/A")

    except Exception as e:
        log.warning(f"Yahoo Finance API failed: {e}. Trying HTML scrape...")

    # Fallback: scrape Yahoo Finance earnings page
    if "eps_actual" not in data:
        try:
            url = f"https://finance.yahoo.com/quote/{ticker}/financials/"
            r = requests.get(url, headers=HEADERS, timeout=10)
            # Parse what we can from the page
            data.setdefault("eps_actual", "[MANUAL]")
            data.setdefault("eps_est", "[MANUAL]")
        except Exception as e:
            log.warning(f"Yahoo scrape also failed: {e}")
            data.setdefault("eps_actual", "[MANUAL]")
            data.setdefault("eps_est", "[MANUAL]")

    data.setdefault("rev_actual", "[MANUAL]")
    data.setdefault("rev_est", "[MANUAL]")
    data.setdefault("quarter", "Q? FY??")
    data.setdefault("company", ticker)
    data.setdefault("ah_move", "[MANUAL]")

    # News context via Google News RSS
    try:
        news_url = f"https://news.google.com/rss/search?q={ticker}+earnings&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(news_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "xml")
        items = soup.find_all("item", limit=3)
        data["news"] = "\n".join([f"- {item.find('title').text}" for item in items]) if items else "[No recent news found]"
    except Exception:
        data["news"] = "[News fetch failed - add manually]"

    data["guidance"] = "[Paste from press release or earnings call transcript]"

    log.info(f"Earnings data for {ticker}: EPS {data.get('eps_actual')} vs {data.get('eps_est')}")
    return data


def scrape_macro(indicator: str) -> dict:
    """
    Pull economic data. Indicator: CPI, JOBS, GDP, PCE, FED.
    Scrapes TradingEconomics for estimate, CNBC/Google News for context.
    """
    log.info(f"Scraping macro data for {indicator}...")
    indicator = indicator.upper()

    indicator_map = {
        "CPI": {"name": "Consumer Price Index (CPI)", "te_slug": "united-states/consumer-price-index-cpi"},
        "JOBS": {"name": "Non-Farm Payrolls", "te_slug": "united-states/non-farm-payrolls"},
        "GDP": {"name": "GDP Growth Rate", "te_slug": "united-states/gdp-growth"},
        "PCE": {"name": "PCE Price Index", "te_slug": "united-states/pce-price-index"},
        "FED": {"name": "Fed Funds Rate Decision", "te_slug": "united-states/interest-rate"},
    }

    info = indicator_map.get(indicator, {"name": indicator, "te_slug": ""})
    data = {
        "indicator": indicator,
        "full_name": info["name"],
        "headline": "[PASTE headline number from BLS.gov / CNBC]",
        "estimate": "[PASTE from TradingEconomics.com]",
        "breakdown": "[PASTE key components]",
        "sp_futures": "[CNBC pre-market]",
        "ten_year": "[Yahoo Finance ^TNX]",
        "dxy": "[Yahoo Finance DX-Y.NYB]",
        "context": "[Is Fed meeting soon? Is this confirming a trend?]",
    }

    # Try to get estimate from TradingEconomics
    if info.get("te_slug"):
        try:
            url = f"https://tradingeconomics.com/{info['te_slug']}"
            r = requests.get(url, headers={**HEADERS, "Accept": "text/html"}, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            # Look for the forecast/estimate value
            forecast_el = soup.find("td", {"id": "annotated-Forecast"})
            if forecast_el:
                data["estimate"] = forecast_el.text.strip()
            actual_el = soup.find("td", {"id": "annotated-Last"})
            if actual_el:
                data["headline"] = actual_el.text.strip()
        except Exception as e:
            log.warning(f"TradingEconomics scrape failed: {e}")

    # Market reaction from Yahoo Finance
    try:
        for sym, key in [("^TNX", "ten_year"), ("DX-Y.NYB", "dxy")]:
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules=price"
            r = requests.get(url, headers=HEADERS, timeout=10)
            j = r.json()["quoteSummary"]["result"][0]["price"]
            price = j.get("regularMarketPrice", {}).get("raw", "N/A")
            change = j.get("regularMarketChangePercent", {}).get("raw", 0)
            data[key] = f"{price} ({change:+.2f}%)"
    except Exception as e:
        log.warning(f"Market data fetch failed: {e}")

    # News context
    try:
        q = info["name"].replace(" ", "+")
        news_url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(news_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "xml")
        items = soup.find_all("item", limit=3)
        data["news"] = "\n".join([f"- {item.find('title').text}" for item in items]) if items else ""
    except Exception:
        data["news"] = ""

    return data


def scrape_daily() -> dict:
    """
    Pull end-of-day market data for the daily wrap.
    Sources: Yahoo Finance for indices/commodities, Google News for stories.
    """
    log.info("Scraping daily market data...")
    data = {"date": datetime.now().strftime("%B %d, %Y")}

    # Index data from Yahoo Finance (try JSON API, then yfinance, then manual)
    indices = {
        "sp": {"sym": "^GSPC", "name": "S&P 500"},
        "nq": {"sym": "^IXIC", "name": "Nasdaq"},
        "dow": {"sym": "^DJI", "name": "Dow"},
    }
    for key, info in indices.items():
        try:
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{info['sym']}?modules=price"
            r = requests.get(url, headers=HEADERS, timeout=10)
            j = r.json()["quoteSummary"]["result"][0]["price"]
            close = j.get("regularMarketPrice", {}).get("fmt", "N/A")
            change_pct = j.get("regularMarketChangePercent", {}).get("raw", 0)
            data[f"{key}_close"] = close
            data[f"{key}_pct"] = f"{change_pct:+.1f}%"
        except Exception:
            # Fallback: try yfinance package
            try:
                import yfinance as yf
                t = yf.Ticker(info["sym"])
                hist = t.history(period="1d")
                if not hist.empty:
                    close = hist["Close"].iloc[-1]
                    prev = t.history(period="2d")["Close"].iloc[0] if len(t.history(period="2d")) > 1 else close
                    pct = ((close - prev) / prev) * 100
                    data[f"{key}_close"] = f"{close:,.0f}"
                    data[f"{key}_pct"] = f"{pct:+.1f}%"
                else:
                    raise ValueError("Empty history")
            except Exception as e:
                log.warning(f"Failed to fetch {info['name']}: {e}")
                data[f"{key}_close"] = "[MANUAL]"
                data[f"{key}_pct"] = "[MANUAL]"

    # Other markets
    others = {
        "ten_year": "^TNX",
        "oil": "CL=F",
        "gold": "GC=F",
        "btc": "BTC-USD",
    }
    for key, sym in others.items():
        try:
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules=price"
            r = requests.get(url, headers=HEADERS, timeout=10)
            j = r.json()["quoteSummary"]["result"][0]["price"]
            price = j.get("regularMarketPrice", {}).get("fmt", "N/A")
            change = j.get("regularMarketChangePercent", {}).get("raw", 0)
            data[key] = f"{price} ({change:+.1f}%)"
        except Exception as e:
            log.warning(f"Failed to fetch {sym}: {e}")
            data[key] = "[MANUAL]"

    # Top market stories from Google News
    try:
        news_url = "https://news.google.com/rss/search?q=stock+market+today&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(news_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "xml")
        items = soup.find_all("item", limit=6)
        data["stories"] = "\n".join([f"- {item.find('title').text}" for item in items]) if items else "[Manual]"
    except Exception:
        data["stories"] = "[Add top stories manually]"

    # Earnings today (from Yahoo Finance calendar)
    data["earnings_today"] = "[Check Earnings Whispers or Yahoo Finance earnings calendar]"

    # Tomorrow's calendar
    data["tomorrow"] = "[Check MarketWatch Economic Calendar + Earnings Whispers]"

    log.info(f"Daily data: S&P {data.get('sp_close')} ({data.get('sp_pct')})")
    return data


# ═══════════════════════════════════════════════════════════════════
#  PART 2: CLAUDE API (generate post + card brief)
# ═══════════════════════════════════════════════════════════════════

class ClaudeCodeModeRequired(RuntimeError):
    """Raised when a direct Claude API call is requested but no API key is configured.

    The caller should either:
      1. Set ANTHROPIC_API_KEY in .env and install the anthropic package, OR
      2. Run the agent prompt by hand in Claude Code (claude.ai/code)
         using the prompt files in triplex/prompts/*.txt
    """


def call_claude(system_prompt: str, user_prompt: str) -> str:
    """Call Claude API and return the text response.

    If the anthropic package is not installed OR ANTHROPIC_API_KEY is not set,
    this raises ClaudeCodeModeRequired with a helpful message. The caller can
    catch it and fall back to Claude Code manual mode.
    """
    try:
        import anthropic
    except ImportError:
        raise ClaudeCodeModeRequired(
            "anthropic package not installed. Either run 'pip install anthropic' "
            "and set ANTHROPIC_API_KEY, or run the agent by hand in Claude Code "
            "using the prompt files in triplex/prompts/*.txt"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ClaudeCodeModeRequired(
            "ANTHROPIC_API_KEY not set. Either add it to .env, or run the agent "
            "by hand in Claude Code using the prompt files in triplex/prompts/*.txt"
        )

    client = anthropic.Anthropic(api_key=api_key)
    log.info("Calling Claude API...")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = response.content[0].text
    log.info(f"Claude response: {len(text)} chars, {len(text.split())} words")
    return text


# System prompts for each content type
SYSTEM_EARNINGS = dedent("""\
    You are Silvia, a personal CFO. You write earnings commentary for @CFOSilvia on X.

    CRITICAL: The first 280 characters appear above the "Show more" fold on X. Lead with ticker (Unicode bold), beat/miss verdict, EPS + Revenue numbers. Must work as a standalone hook.

    After the fold:
    - 3 things that mattered. Numbered 1, 2, 3 in natural prose. No bold headers, no colon lists. Each 1-2 sentences.
    - Forward guidance: 1-2 sentences.
    - "If you own [TICKER]:" with a specific assessment.
    - CTA: "Own [TICKER]? Silvia can break down what this means for your position. cfosilvia.com"

    200-300 words. Short paragraphs (1-2 sentences). Varied sentence rhythm. Have a take.
    No emojis, hashtags, em dashes, exclamation marks, bold except Unicode bold opener.
    No "it's worth noting," "the landscape," inflated language. No scene-setting opener. No summary at end.

    After the post, output a section labeled IMAGE_CARD_BRIEF with exactly:
    TICKER: [ticker]
    VERDICT: [BEAT or MISS]
    EPS_ACTUAL: [number]
    EPS_EST: [number]
    REV_ACTUAL: [number]
    REV_EST: [number]
    AH_MOVE: [percentage]
    QUARTER: [quarter]""")

SYSTEM_MACRO = dedent("""\
    You are Silvia, a personal CFO. You write economic data commentary for @CFOSilvia on X.

    CRITICAL: First 280 characters = hook above "Show more." Data name in Unicode bold, the number, vs estimate, verdict. Standalone.

    After: what drove it, portfolio impact (specific asset classes), market reaction with numbers, what to watch next with date.
    CTA: "What does this mean for your portfolio? Ask Silvia. cfosilvia.com"

    200-300 words. Short paragraphs. Varied rhythm. Have a take. No em dashes. No inflated language.

    After the post, output IMAGE_CARD_BRIEF with:
    DATA_NAME: [e.g. CPI]
    VERDICT: [HOT or COOL or IN LINE]
    HEADLINE_NUM: [the number]
    UNIT: [YoY or MoM]
    ESTIMATE: [est number]""")

SYSTEM_DAILY = dedent("""\
    You are Silvia, a personal CFO. Every market day after close, you write the daily wrap for @CFOSilvia on X.

    CRITICAL: First 280 chars = date in Unicode bold, one-line day verdict, S&P close + %. Must make someone tap.

    After: at least 5 news items (sometimes 7-8). Each its own short paragraph, 1-3 sentences. No bold headers, no numbered colon lists. Cover whatever mattered: earnings, company news, econ data, Fed, sectors, geopolitics, crypto, commodities, bonds.

    Each item: what happened + why an investor cares. Have opinions.
    After items: one paragraph on tomorrow (name, time, why).
    CTA: "What does this mean for your portfolio? Ask Silvia. cfosilvia.com"

    300-500 words. Short paragraphs. Varied rhythm. No em dashes. No inflated language. No summary.

    After the post, output IMAGE_CARD_BRIEF with:
    DATE: [date]
    SP_CLOSE: [number]
    SP_PCT: [percentage]
    HEADLINE: [10 words max summary]""")


def generate_earnings_post(data: dict) -> tuple[str, dict]:
    """Generate earnings post. Returns (post_text, card_brief)."""
    user_prompt = f"""Write the @CFOSilvia earnings post for:

TICKER: {data['ticker']}
COMPANY: {data['company']}
QUARTER: {data.get('quarter', 'Latest')}

EARNINGS DATA:
EPS Actual: {data['eps_actual']}
EPS Estimate: {data['eps_est']}
Revenue Actual: {data.get('rev_actual', '[not available]')}
Revenue Estimate: {data.get('rev_est', '[not available]')}

GUIDANCE:
{data.get('guidance', '[Not available]')}

NEWS CONTEXT:
{data.get('news', '[Not available]')}

AFTER-HOURS MOVE: {data.get('ah_move', 'N/A')}"""

    full = call_claude(SYSTEM_EARNINGS, user_prompt)
    return parse_response(full)


def generate_macro_post(data: dict) -> tuple[str, dict]:
    """Generate macro data post."""
    user_prompt = f"""Write the @CFOSilvia economic data post for:

DATA: {data['full_name']}
HEADLINE: {data['headline']}
ESTIMATE: {data['estimate']}

BREAKDOWN:
{data.get('breakdown', '[Not available]')}

MARKET REACTION:
10Y yield: {data.get('ten_year', 'N/A')}
DXY: {data.get('dxy', 'N/A')}
S&P futures: {data.get('sp_futures', 'N/A')}

NEWS CONTEXT:
{data.get('news', '')}

CONTEXT: {data.get('context', '')}"""

    full = call_claude(SYSTEM_MACRO, user_prompt)
    return parse_response(full)


def generate_daily_post(data: dict) -> tuple[str, dict]:
    """Generate daily wrap post."""
    user_prompt = f"""Write today's @CFOSilvia daily wrap.

DATE: {data['date']}

MARKET CLOSE:
S&P 500: {data.get('sp_close', 'N/A')} ({data.get('sp_pct', 'N/A')})
Nasdaq: {data.get('nq_close', 'N/A')} ({data.get('nq_pct', 'N/A')})
Dow: {data.get('dow_close', 'N/A')} ({data.get('dow_pct', 'N/A')})

TODAY'S EARNINGS:
{data.get('earnings_today', 'None reported')}

TODAY'S NEWS / STORIES:
{data.get('stories', 'N/A')}

OTHER MARKETS:
10Y yield: {data.get('ten_year', 'N/A')}
Oil: {data.get('oil', 'N/A')}
Gold: {data.get('gold', 'N/A')}
Bitcoin: {data.get('btc', 'N/A')}

TOMORROW:
{data.get('tomorrow', '[Check calendar]')}

Write the wrap. At least 5 items. More if busy."""

    full = call_claude(SYSTEM_DAILY, user_prompt)
    return parse_response(full)


def parse_response(full_text: str) -> tuple[str, dict]:
    """Split Claude's response into post text and card brief dict."""
    if "IMAGE_CARD_BRIEF" in full_text:
        parts = full_text.split("IMAGE_CARD_BRIEF")
        post_text = parts[0].strip()
        brief_text = parts[1].strip()
    else:
        post_text = full_text.strip()
        brief_text = ""

    # Parse brief into dict
    brief = {}
    for line in brief_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            brief[k.strip()] = v.strip()

    return post_text, brief


# ═══════════════════════════════════════════════════════════════════
#  PART 3: CARD IMAGE GENERATION (Playwright)
# ═══════════════════════════════════════════════════════════════════

CARD_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: transparent; }}
.card {{ width: 1200px; height: 675px; background: #0A0A0A; color: #fff;
  font-family: -apple-system, 'SF Pro Display', 'Helvetica Neue', sans-serif;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  position: relative; padding-bottom: 80px; }}
.quarter {{ position: absolute; top: 28px; right: 48px; color: #444; font-size: 15px; }}
.ticker {{ font-size: 120px; font-weight: 800; letter-spacing: -4px; line-height: 1; }}
.pill {{ padding: 10px 28px; border-radius: 6px; font-size: 24px; font-weight: 700; letter-spacing: 3px; }}
.pill-g {{ background: rgba(34,197,94,0.15); border: 2px solid #22C55E; color: #22C55E; }}
.pill-r {{ background: rgba(239,68,68,0.15); border: 2px solid #EF4444; color: #EF4444; }}
.nums {{ display: flex; gap: 80px; align-items: center; }}
.nl {{ font-size: 16px; color: #666; letter-spacing: 2px; margin-bottom: 10px; text-align: center; }}
.na {{ font-size: 52px; font-weight: 700; }}
.ne {{ font-size: 24px; color: #555; }}
.dv {{ width: 1px; height: 70px; background: #222; }}
.ah {{ margin-top: 28px; font-size: 22px; color: #888; }}
.green {{ color: #22C55E; }} .red {{ color: #EF4444; }}
.bar {{ position: absolute; bottom: 0; left: 0; right: 0; height: 80px; background: #111;
  border-top: 2px solid #C9A84C; display: flex; align-items: center; justify-content: center; gap: 16px; }}
.bar-b {{ color: #C9A84C; font-size: 15px; font-weight: 600; letter-spacing: 1.5px; position: absolute; left: 48px; }}
.bar-a {{ color: #888; font-size: 28px; }} .bar-t {{ color: #fff; font-size: 28px; font-weight: 700; }}
.big {{ font-size: 140px; font-weight: 800; letter-spacing: -6px; line-height: 1; margin-bottom: 16px; }}
.sub {{ font-size: 28px; color: #666; letter-spacing: 4px; font-weight: 500; margin-bottom: 8px; }}
.mp {{ padding: 8px 32px; border-radius: 6px; font-size: 20px; font-weight: 700; letter-spacing: 4px; margin-bottom: 32px; }}
.mnb {{ font-size: 64px; font-weight: 700; }}
.dd {{ font-size: 80px; font-weight: 800; letter-spacing: -3px; line-height: 1; margin-bottom: 44px; }}
.dsp {{ font-size: 56px; font-weight: 700; }}
.dspl {{ font-size: 20px; color: #666; letter-spacing: 2px; }}
.dspp {{ font-size: 32px; font-weight: 700; }}
.dh {{ margin-top: 24px; font-size: 22px; color: #999; text-align: center; max-width: 800px; line-height: 1.5; }}
</style></head><body>{content}</body></html>"""


def generate_card_html(post_type: str, brief: dict) -> str:
    """Generate the HTML for the image card."""
    if post_type == "earnings":
        verdict = brief.get("VERDICT", "BEAT")
        is_beat = verdict.upper() == "BEAT"
        color_class = "green" if is_beat else "red"
        pill_class = "pill-g" if is_beat else "pill-r"
        content = f"""
        <div class="card">
          <div class="quarter">{brief.get('QUARTER', '')} Earnings</div>
          <div style="display:flex;align-items:center;gap:24px;margin-bottom:44px">
            <span class="ticker">{brief.get('TICKER', '???')}</span>
            <div class="pill {pill_class}">{verdict}</div>
          </div>
          <div class="nums">
            <div><div class="nl">EPS</div><div style="display:flex;align-items:baseline;gap:14px">
              <span class="na {color_class}">{brief.get('EPS_ACTUAL', '?')}</span>
              <span class="ne">vs {brief.get('EPS_EST', '?')}</span></div></div>
            <div class="dv"></div>
            <div><div class="nl">REVENUE</div><div style="display:flex;align-items:baseline;gap:14px">
              <span class="na {color_class}">{brief.get('REV_ACTUAL', '?')}</span>
              <span class="ne">vs {brief.get('REV_EST', '?')}</span></div></div>
          </div>
          <div class="ah">After hours: <span class="{color_class}">{brief.get('AH_MOVE', 'N/A')}</span></div>
          <div class="bar"><span class="bar-b">@CFOSilvia</span><span class="bar-a">↑</span><span class="bar-t">Show more</span><span class="bar-a">↑</span></div>
        </div>"""

    elif post_type == "macro":
        verdict = brief.get("VERDICT", "HOT")
        is_hot = verdict.upper() == "HOT"
        pill_style = "background:rgba(239,68,68,0.12);border:2px solid #EF4444;color:#EF4444" if is_hot else "background:rgba(34,197,94,0.15);border:2px solid #22C55E;color:#22C55E"
        content = f"""
        <div class="card">
          <div class="quarter">{datetime.now().strftime('%B %d, %Y')}</div>
          <div class="big">{brief.get('DATA_NAME', '???')}</div>
          <div class="mp" style="{pill_style}">{verdict}</div>
          <div style="display:flex;align-items:baseline;gap:20px">
            <span class="mnb">{brief.get('HEADLINE_NUM', '?')}</span>
            <span style="font-size:20px;color:#666">{brief.get('UNIT', '')}</span>
            <span style="font-size:28px;color:#555;margin-left:16px">vs {brief.get('ESTIMATE', '?')} est</span>
          </div>
          <div class="bar"><span class="bar-b">@CFOSilvia</span><span class="bar-a">↑</span><span class="bar-t">Show more</span><span class="bar-a">↑</span></div>
        </div>"""

    elif post_type == "daily":
        pct = brief.get("SP_PCT", "+0.0%")
        is_green = not pct.startswith("-")
        color_class = "green" if is_green else "red"
        day_name = datetime.now().strftime("%A").upper()
        date_str = datetime.now().strftime("%B %d")
        content = f"""
        <div class="card">
          <div class="quarter">Daily Wrap</div>
          <div style="font-size:24px;color:#555;letter-spacing:3px;font-weight:500;margin-bottom:8px">{day_name}</div>
          <div class="dd">{date_str}</div>
          <div style="display:flex;align-items:baseline;gap:16px;margin-bottom:12px">
            <span class="dspl">S&P 500</span>
            <span class="dsp">{brief.get('SP_CLOSE', '???')}</span>
            <span class="dspp {color_class}">{pct}</span>
          </div>
          <div class="dh">{brief.get('HEADLINE', '')}</div>
          <div class="bar"><span class="bar-b">@CFOSilvia</span><span class="bar-a">↑</span><span class="bar-t">Show more</span><span class="bar-a">↑</span></div>
        </div>"""
    else:
        content = "<div class='card'><span class='ticker'>???</span></div>"

    return CARD_HTML_TEMPLATE.format(content=content)


def render_card(post_type: str, brief: dict, output_path: str = None) -> str:
    """Render the card HTML to a PNG image using Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(LOG_DIR / f"card_{post_type}_{timestamp}.png")

    html = generate_card_html(post_type, brief)
    html_path = str(LOG_DIR / "temp_card.html")
    Path(html_path).write_text(html)

    log.info("Rendering card image...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1300, "height": 800})
        page.goto(f"file://{os.path.abspath(html_path)}")
        page.wait_for_timeout(500)
        el = page.locator(".card")
        el.screenshot(path=output_path)
        browser.close()

    log.info(f"Card saved: {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════
#  PART 4: REVIEW ENGINE
# ═══════════════════════════════════════════════════════════════════

BANNED_WORDS = [
    "additionally", "bolstered", "comprehensive", "crucial", "delve", "elevate",
    "empower", "enduring", "enhance", "ensuring", "evolving landscape", "exemplifies",
    "facilitate", "fostering", "furthermore", "game-changer", "garner", "groundbreaking",
    "holistic", "in the realm of", "it's worth noting", "landscape", "leverage",
    "meticulous", "moreover", "multifaceted", "myriad", "navigate", "nestled",
    "paradigm", "pivotal", "plethora", "profound", "robust", "seamless", "showcasing",
    "spearhead", "streamline", "synergy", "tapestry", "testament", "transformative",
    "underscore", "utilize", "vibrant",
]

BANNED_OPENERS = [
    "furthermore", "moreover", "additionally", "in conclusion", "overall",
    "in summary", "to sum up", "firstly", "secondly", "lastly",
    "in today's", "in an era", "as we navigate",
]


def review_post(text: str, post_type: str = "earnings") -> dict:
    """Run QA checks. Returns {score, can_post, errors[], warnings[], passed[]}."""
    errors, warnings, passed = [], [], []
    words = text.split()
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    wc = len(words)

    # Word count
    if post_type in ("earnings", "macro"):
        (passed if 190 <= wc <= 350 else errors).append(f"Word count: {wc} (target 200-300)")
    else:
        (passed if 280 <= wc <= 550 else errors).append(f"Word count: {wc} (target 300-500)")

    # Em dashes
    if '\u2014' in text or '\u2013' in text:
        errors.append("Em/en dashes found")
    else:
        passed.append("No em dashes")

    # Exclamation marks
    if '!' in text:
        errors.append(f"{text.count('!')} exclamation mark(s)")
    else:
        passed.append("No exclamation marks")

    # Emojis
    if re.search(r'[\U0001F600-\U0001FAFF\U00002600-\U000027BF]', text):
        errors.append("Emojis found")
    else:
        passed.append("No emojis")

    # Banned words
    text_lower = text.lower()
    found = [w for w in BANNED_WORDS if w in text_lower]
    if found:
        errors.append(f"Banned words: {', '.join(found[:5])}")
    else:
        passed.append("No banned words")

    # Banned openers
    for para in paragraphs:
        first = para.lower()[:50]
        for opener in BANNED_OPENERS:
            if first.startswith(opener):
                errors.append(f"Banned opener: '{opener}...'")
                break

    # Hashtags
    if re.search(r'#\w+', text):
        errors.append("Hashtags found")
    else:
        passed.append("No hashtags")

    # CTA
    if 'cfosilvia.com' in text_lower:
        passed.append("CTA present")
    else:
        errors.append("Missing cfosilvia.com CTA")

    # Hedging
    hedges = ["it seems", "it appears", "it remains to be seen", "only time will tell"]
    found_h = [h for h in hedges if h in text_lower]
    if found_h:
        errors.append(f"Hedging: {', '.join(found_h)}")
    else:
        passed.append("No hedging")

    # Hook check (first 280 chars should have numbers)
    if len(text) > 280 and re.search(r'\$[\d,.]+|\d+\.?\d*%', text[:280]):
        passed.append("Hook has numbers")
    elif len(text) > 280:
        warnings.append("Hook (first 280 chars) lacks numbers")

    # Sentence variation
    sent_lens = [len(s.split()) for s in sentences if s.split()]
    if len(sent_lens) >= 5:
        avg = sum(sent_lens) / len(sent_lens)
        std = (sum((l - avg) ** 2 for l in sent_lens) / len(sent_lens)) ** 0.5
        if std > 3:
            passed.append(f"Sentence variation OK (std: {std:.1f})")
        else:
            warnings.append(f"Low sentence variation (std: {std:.1f})")

    # Type-specific
    if post_type == "earnings":
        if re.search(r'eps', text_lower):
            passed.append("EPS present")
        else:
            errors.append("Missing EPS")
        if "if you own" in text_lower:
            passed.append("Holder line present")
        else:
            warnings.append("Missing 'If you own' line")
    elif post_type == "daily":
        content_paras = [p for p in paragraphs if len(p.split()) > 10]
        if len(content_paras) >= 5:
            passed.append(f"{len(content_paras)} items (need 5+)")
        else:
            errors.append(f"Only {len(content_paras)} items (need 5+)")

    total = len(errors) + len(warnings) + len(passed)
    score = round(len(passed) / total * 100) if total else 100

    return {
        "score": score,
        "can_post": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "word_count": wc,
    }


def print_review(result: dict):
    """Print a formatted review report."""
    print("\n" + "=" * 56)
    print("  SILVIA REVIEW")
    print("=" * 56)
    if result["errors"]:
        print(f"\n  ERRORS ({len(result['errors'])})")
        for e in result["errors"]:
            print(f"    [X] {e}")
    if result["warnings"]:
        print(f"\n  WARNINGS ({len(result['warnings'])})")
        for w in result["warnings"]:
            print(f"    [!] {w}")
    print(f"\n  PASSED: {len(result['passed'])}  |  SCORE: {result['score']}/100")
    print(f"  STATUS: {'READY' if result['can_post'] else 'BLOCKED'}")
    print("=" * 56 + "\n")


# ═══════════════════════════════════════════════════════════════════
#  PART 5: TWITTER/X POSTING
# ═══════════════════════════════════════════════════════════════════

def _manual_post_instructions(text: str, image_path: str) -> None:
    """Print the manual posting instructions when Twitter keys are not configured."""
    print("\n" + "=" * 60)
    print("  MANUAL X POSTING — Twitter API keys not configured")
    print("=" * 60)
    print("\n  Steps:")
    print("   1. Copy the post text from the file below")
    print("   2. Open https://x.com/compose/post in a browser")
    print("   3. Paste the text into the compose box")
    print(f"   4. Attach this image: {image_path}")
    print("   5. Click Post")
    print(f"\n  Post text saved: see most recent post_*.txt in {LOG_DIR}")
    print(f"  Card image:      {image_path}")
    print("\n  To automate posting in the future, add TWITTER_* keys to .env")
    print("  and run `pip install tweepy`.")
    print("=" * 60 + "\n")


def post_to_x(text: str, image_path: str) -> str | None:
    """Post to X with image. Returns tweet URL or None.

    If tweepy is not installed OR any Twitter credential is missing, falls
    back to printing manual posting instructions and returns None. The
    caller should treat None as "manual mode, handle it yourself" rather
    than a hard error.
    """
    try:
        import tweepy
    except ImportError:
        log.info("tweepy not installed — falling back to manual posting mode")
        _manual_post_instructions(text, image_path)
        return None

    keys = {k: os.environ.get(k) for k in [
        "TWITTER_API_KEY", "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET", "TWITTER_BEARER_TOKEN",
    ]}
    if not all(keys.values()):
        missing = [k for k, v in keys.items() if not v]
        log.info(f"Missing Twitter credentials: {', '.join(missing)} — manual posting mode")
        _manual_post_instructions(text, image_path)
        return None

    # v1.1 for media upload
    auth = tweepy.OAuth1UserHandler(
        keys["TWITTER_API_KEY"], keys["TWITTER_API_SECRET"],
        keys["TWITTER_ACCESS_TOKEN"], keys["TWITTER_ACCESS_SECRET"],
    )
    api_v1 = tweepy.API(auth)

    # v2 for posting
    client = tweepy.Client(
        bearer_token=keys["TWITTER_BEARER_TOKEN"],
        consumer_key=keys["TWITTER_API_KEY"],
        consumer_secret=keys["TWITTER_API_SECRET"],
        access_token=keys["TWITTER_ACCESS_TOKEN"],
        access_token_secret=keys["TWITTER_ACCESS_SECRET"],
    )

    log.info(f"Uploading image: {image_path}")
    media = api_v1.media_upload(filename=image_path)

    log.info("Posting to X...")
    response = client.create_tweet(text=text, media_ids=[media.media_id])
    tweet_id = response.data["id"]
    url = f"https://x.com/CFOSilvia/status/{tweet_id}"
    log.info(f"LIVE: {url}")
    return url


# ═══════════════════════════════════════════════════════════════════
#  PART 6: ORCHESTRATOR (ties everything together)
# ═══════════════════════════════════════════════════════════════════

def run_pipeline(post_type: str, arg: str = None):
    """
    Full automated pipeline:
    1. Scrape data
    2. Call Claude to generate post + card brief
    3. Render card image
    4. Run review
    5. Post to X (with confirmation unless AUTO_POST=true)
    6. Log everything
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Step 1: Scrape
    log.info(f"{'='*50}")
    log.info(f"PIPELINE START: {post_type} {arg or ''}")
    log.info(f"{'='*50}")

    if post_type == "earnings":
        data = scrape_earnings(arg)
        # Check if we got real data or placeholders
        manual_fields = [k for k, v in data.items() if isinstance(v, str) and "[MANUAL]" in v]
        if manual_fields:
            log.warning(f"Fields need manual input: {', '.join(manual_fields)}")
            print(f"\n  Some data couldn't be scraped automatically: {', '.join(manual_fields)}")
            print("  The pipeline will continue but Claude may produce placeholder content.")
            print("  For best results, fill in these fields in the data dict.\n")

    elif post_type == "macro":
        data = scrape_macro(arg)
    elif post_type == "daily":
        data = scrape_daily()
    else:
        log.error(f"Unknown post type: {post_type}")
        return

    # Save raw data
    data_path = LOG_DIR / f"data_{post_type}_{timestamp}.json"
    data_path.write_text(json.dumps(data, indent=2, default=str))
    log.info(f"Raw data saved: {data_path}")

    # Step 2: Generate with Claude
    if post_type == "earnings":
        post_text, brief = generate_earnings_post(data)
    elif post_type == "macro":
        post_text, brief = generate_macro_post(data)
    else:
        post_text, brief = generate_daily_post(data)

    # Save post text
    post_path = LOG_DIR / f"post_{post_type}_{timestamp}.txt"
    post_path.write_text(post_text)
    log.info(f"Post text saved: {post_path}")

    # Step 3: Render card
    card_path = str(LOG_DIR / f"card_{post_type}_{timestamp}.png")
    render_card(post_type, brief, card_path)

    # Step 4: Review
    review = review_post(post_text, post_type)
    print_review(review)

    # Save review
    review_path = LOG_DIR / f"review_{post_type}_{timestamp}.json"
    review_path.write_text(json.dumps(review, indent=2))

    if not review["can_post"]:
        log.warning("REVIEW FAILED. Post blocked.")
        print("  Fix the errors above and re-run, or edit the post manually:")
        print(f"  {post_path}")
        return

    # Step 5: Post to X
    print(f"\n  POST PREVIEW ({review['word_count']} words)")
    print("  " + "-" * 50)
    for line in post_text.split("\n")[:6]:
        print(f"  {line}")
    if len(post_text.split("\n")) > 6:
        print(f"  ... ({len(post_text.split(chr(10)))} total lines)")
    print("  " + "-" * 50)
    print(f"  Card: {card_path}")
    print(f"  Score: {review['score']}/100\n")

    if AUTO_POST:
        log.info("AUTO_POST=true, posting without confirmation...")
        confirm = True
    else:
        answer = input("  Type 'POST' to publish to @CFOSilvia: ")
        confirm = answer.strip() == "POST"

    if not confirm:
        log.info("Cancelled by user.")
        print("  Saved locally. Files:")
        print(f"    Post: {post_path}")
        print(f"    Card: {card_path}")
        return

    url = post_to_x(post_text, card_path)

    # Step 6: Log
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "type": post_type,
        "ticker": arg,
        "url": url,
        "score": review["score"],
        "word_count": review["word_count"],
        "post_file": str(post_path),
        "card_file": card_path,
    }
    master_log = LOG_DIR / "post_history.json"
    history = json.loads(master_log.read_text()) if master_log.exists() else []
    history.append(log_entry)
    master_log.write_text(json.dumps(history, indent=2))

    if url:
        print(f"\n  LIVE: {url}")
    print(f"  Logged to: {master_log}")


def run_cron():
    """
    Daemon mode. Runs on a schedule:
    - Daily wrap at 4:30 PM EST (21:30 UTC)
    - Can be extended to watch for earnings releases
    """
    import sched
    import threading

    log.info("Starting cron daemon...")
    log.info("  Daily wrap: 4:30 PM EST (auto)")
    log.info("  Press Ctrl+C to stop\n")

    def daily_check():
        """Check if it's time for the daily wrap."""
        while True:
            now = datetime.now(timezone(timedelta(hours=-5)))  # EST
            if now.weekday() < 5:  # Mon-Fri
                target = now.replace(hour=16, minute=30, second=0, microsecond=0)
                if abs((now - target).total_seconds()) < 60:
                    log.info("Triggering daily wrap...")
                    try:
                        run_pipeline("daily")
                    except Exception as e:
                        log.error(f"Daily wrap failed: {e}")
            time.sleep(55)  # Check every ~minute

    thread = threading.Thread(target=daily_check, daemon=True)
    thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Cron stopped.")


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print(dedent("""
        CFO Silvia Automated Pipeline
        ================================
        python silvia_auto.py earnings NVDA     # Auto earnings post
        python silvia_auto.py macro CPI         # Auto macro data post
        python silvia_auto.py daily             # Auto daily wrap
        python silvia_auto.py cron              # Daemon: daily wrap at 4:30 PM EST

        Set AUTO_POST=true in .env to skip confirmation.
        """))
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "earnings":
        if len(sys.argv) < 3:
            print("Usage: python silvia_auto.py earnings <TICKER>")
            sys.exit(1)
        run_pipeline("earnings", sys.argv[2].upper())

    elif cmd == "macro":
        if len(sys.argv) < 3:
            print("Usage: python silvia_auto.py macro <CPI|JOBS|GDP|PCE|FED>")
            sys.exit(1)
        run_pipeline("macro", sys.argv[2].upper())

    elif cmd == "daily":
        run_pipeline("daily")

    elif cmd == "cron":
        run_cron()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
