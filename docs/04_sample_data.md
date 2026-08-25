# sample_data.py — The Stunt Double (Demo/Test Data)

This file provides **hardcoded fake ASX stock data** so the agent can run without hitting the Yahoo Finance API. Used when `--demo` flag is passed.

---

## Architecture Diagram

```
  --demo flag
       |
       v
  agent.py: _patch_demo_tools()
       |
       +---> from sample_data import get_sample_dataframe, get_sample_news
       |
       v
  sample_data.py
  +------------------------------------------+
  |                                          |
  |  SAMPLE_STOCKS (list of 20 dicts)        |
  |  +------------------------------------+  |
  |  | BHP.AX  - Basic Materials - $228B  |  |
  |  | CBA.AX  - Financial Svcs  - $215B  |  |
  |  | CSL.AX  - Healthcare      - $135B  |  |
  |  | NAB.AX  - Financial Svcs  - $108B  |  |
  |  | WBC.AX  - Financial Svcs  -  $95B  |  |
  |  | ANZ.AX  - Financial Svcs  -  $88B  |  |
  |  | FMG.AX  - Basic Materials -  $72B  |  |
  |  | WES.AX  - Consumer Cycl.  -  $82B  |  |
  |  | MQG.AX  - Financial Svcs  -  $78B  |  |
  |  | WOW.AX  - Consumer Def.   -  $42B  |  |
  |  | TLS.AX  - Communication   -  $48B  |  |
  |  | RIO.AX  - Basic Materials -  $42B  |  |
  |  | GMG.AX  - Real Estate     -  $65B  |  |
  |  | XRO.AX  - Technology      -  $25B  |  |
  |  | REA.AX  - Technology      -  $28B  |  |
  |  | PME.AX  - Healthcare      -  $22B  |  |
  |  | TCL.AX  - Industrials     -  $45B  |  |
  |  | STO.AX  - Energy          -  $22B  |  |
  |  | COL.AX  - Consumer Def.   -  $25B  |  |
  |  | QBE.AX  - Financial Svcs  -  $24B  |  |
  |  +------------------------------------+  |
  |                                          |
  |  SAMPLE_NEWS (dict of headlines)         |
  |  +------------------------------------+  |
  |  | BHP.AX: 2 headlines                |  |
  |  | CBA.AX: 2 headlines                |  |
  |  | CSL.AX: 2 headlines                |  |
  |  | FMG.AX: 2 headlines                |  |
  |  | GMG.AX: 2 headlines                |  |
  |  | XRO.AX: 2 headlines                |  |
  |  | PME.AX: 2 headlines                |  |
  |  | QBE.AX: 2 headlines                |  |
  |  | STO.AX: 2 headlines                |  |
  |  | REA.AX: 1 headline                 |  |
  |  | (others): auto-generated neutral   |  |
  |  +------------------------------------+  |
  |                                          |
  |  get_sample_dataframe() -> pd.DataFrame  |
  |  get_sample_news()      -> dict          |
  |                                          |
  +------------------------------------------+
```

---

## What's In Each Stock Record

Every stock in `SAMPLE_STOCKS` has the same fields as what `_fetch_single()` returns from yfinance:

| Field | Example (BHP) | Description |
|---|---|---|
| `ticker` | `"BHP.AX"` | ASX ticker symbol |
| `name` | `"BHP Group Limited"` | Company name |
| `sector` | `"Basic Materials"` | GICS sector |
| `industry` | `"Mining"` | Sub-industry |
| `market_cap` | `228e9` | Market cap in AUD |
| `current_price` | `43.50` | Current share price |
| `pe_ratio` | `11.2` | Trailing P/E |
| `forward_pe` | `10.5` | Forward P/E |
| `dividend_yield` | `0.052` | 5.2% yield |
| `roe` | `0.31` | Return on equity |
| `revenue_growth` | `0.08` | 8% revenue growth |
| `earnings_growth` | `0.12` | 12% earnings growth |
| `beta` | `1.1` | Volatility measure |
| ... | ... | + 10 more fields |

---

## News Data

`SAMPLE_NEWS` maps tickers to headline arrays. 10 stocks have hand-written headlines (mix of positive, negative, and neutral). Stocks without custom headlines get an auto-generated neutral one:

```python
for s in SAMPLE_STOCKS:
    if s["ticker"] not in SAMPLE_NEWS:
        SAMPLE_NEWS[s["ticker"]] = [
            {"title": f"{s['name']} delivers steady quarterly results", ...}
        ]
```

---

## How Demo Mode Patches In

In `agent.py`, `_patch_demo_tools()` replaces the real `tools.TOOL_DISPATCH` with demo functions that query these data structures using pandas filtering instead of calling yfinance. The schema stays the same — Claude doesn't know it's using fake data.
