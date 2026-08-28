# tools.py — The Hands (Data Fetching & Actions)

This file defines **what tools Claude can use** (schemas) and **what happens when it calls them** (implementations). It's the bridge between Claude's decisions and real-world data.

---

## Architecture Diagram

```
  Claude says:                      tools.py
  "call get_stock_data              +---------------------------+
   with tickers=[BHP.AX]"          |                           |
         |                          |  TOOL_SCHEMAS
         |                          |  +-----------------------+|
         v                          |  | name: get_stock_data  ||
  +-------------+                   |  | description: "..."    ||
  | execute_tool|                   |  | input_schema: {       ||
  |             |                   |  |   tickers: [string]   ||
  +------+------+                   |  | }                     ||
         |                          |  +-----------------------+|
         | looks up in              |  | name: get_stock_news  ||
         | TOOL_DISPATCH            |  | name: get_price_      ||
         |                          |  | history               ||
         |                          |  | name: screen_stocks   ||
         |                          |  | name: compare_stocks  ||
         v                          |  | name: generate_report ||
         |                          |  | name: create_chart    ||
         |                          |  | name: create_plot     ||
         |                          |  | name: create_diagram  ||
  +----------------+                |  +-----------------------+|
  | TOOL_DISPATCH  |                |                           |
  |                |                |  TOOL_DISPATCH            |
  | {              |                |  Maps name -> function    |
  |  "get_stock_   |                |                           |
  |   data": fn,   |                +---------------------------+
  |  "screen_      |
  |   stocks": fn, |
  |  ...           |
  | }              |
  +-------+--------+
          |
          v
  +------------------+       +------------------+
  | tool_get_stock_  |       |  _fetch_single() |
  | data()           +------>|  (line 161)      |
  | (line 211)       |       |                  |
  +------------------+       |  yf.Ticker(t)    |
                             |  tk.info         |
                             |  tk.history("1y")|
                             +--------+---------+
                                      |
                                      v
                             +------------------+
                             |  Yahoo Finance   |
                             |  API (yfinance)  |
                             +------------------+
```

---

## Two Halves of Each Tool

Every tool has **two parts**:

### 1. Schema (what Claude sees)
Defined in `TOOL_SCHEMAS` — a list of JSON objects describing each tool's name, description, and parameters. This is sent to Claude's API so it knows what tools are available and how to call them.

### 2. Implementation (what actually runs)
Python functions that execute when Claude calls a tool. Connected via `TOOL_DISPATCH` dictionary.

---

## The Tools

### `get_stock_data` (line 211)
- **Purpose**: Fetch detailed fundamentals for specific tickers
- **Input**: `tickers` — list of ASX tickers like `["BHP.AX", "RIO.AX"]`
- **How it works**: Calls `_fetch_single()` for each ticker, which uses `yfinance` to pull price, P/E, ROE, margins, growth, beta, 52-week range, and trailing returns
- **Returns**: JSON array of stock data objects

### `get_stock_news` (line 221)
- **Purpose**: Get recent headlines for sentiment analysis
- **Input**: `tickers` — list of ASX tickers
- **How it works**: Uses `yfinance`'s `.news` property, parses title/publisher/date from each item
- **Returns**: JSON object mapping ticker -> array of up to 5 headlines

### `get_price_history`
- **Purpose**: Fetch historical or recent intraday price bars for time-series analysis and plotting
- **Input**: Up to five tickers, period, interval, adjustment/pre-market options, and a bounded point count
- **How it works**: Retrieves OHLCV bars through `yfinance`, evenly downsamples large results while retaining the latest bar, and attaches source/retrieval timestamps and exchange metadata
- **Returns**: Timestamped OHLCV points plus explicit freshness and non-real-time notices

### `screen_stocks` (line 242)
- **Purpose**: Filter the ASX universe by criteria
- **Input**: Optional filters — `min_market_cap_b`, `max_pe_ratio`, `min_dividend_yield`, `min_roe`, `sectors`, `exclude_sectors`
- **How it works**: Iterates through `ASX_UNIVERSE` (30 hardcoded top ASX tickers), fetches each one, applies filters
- **Returns**: JSON array of stocks that match all criteria

### `compare_stocks` (line 285)
- **Purpose**: Side-by-side comparison of 2-10 stocks
- **Input**: `tickers` — list of tickers to compare
- **How it works**: Fetches each ticker, formats key metrics (price, P/E, ROE, yield, growth, beta, 1Y return) into a comparison table
- **Returns**: JSON array of formatted comparison rows

### `generate_report` (line 310)
- **Purpose**: Create a PDF research report
- **Input**: `tickers`, optional `title` and `strategy` (growth/value/dividend/balanced)
- **How it works**: Fetches all data + news, builds a PDF using `reportlab` with title page, rankings table, individual stock profiles, and disclaimer
- **Returns**: JSON with `report_path` and `stocks_included` count

### `create_chart`
- **Purpose**: Turn data already fetched or computed by the agent into a visual chart
- **Input**: Title, chart type, labels, numeric series, optional axis labels and number format
- **Supported forms**: Bar, line, area, scatter, and pie
- **Returns**: Metadata and the path to a saved SVG; the web UI displays it inline

### `create_diagram`
- **Purpose**: Visualise a process, hierarchy, decision flow, or set of relationships
- **Input**: Nodes, directed edges, optional layers, shapes, groups, and layout direction
- **Returns**: Metadata and the path to a saved SVG; the web UI displays it inline

### `create_plot`
- **Purpose**: Natively plot raw numeric observations without a charting service or extra runtime dependency
- **Input**: Named datasets with numeric values, optional x-values, labels, formatting, and histogram bins
- **Supported forms**: Numeric line and scatter plots, histograms, and statistical box plots
- **Returns**: Metadata and the path to a saved SVG; the web UI displays it inline

---

## Key Helper: `_fetch_single()` (line 161)

This is the workhorse function that all tools rely on. For a single ticker it:

```
yf.Ticker("BHP.AX")
        |
        +---> .info     --> price, P/E, ROE, margins, beta, etc.
        |
        +---> .history  --> 1-year price data for return calculations
```

Returns a dictionary with ~25 fields covering fundamentals, valuation, growth, and performance.

---

## ASX Universe (line 149)

A hardcoded list of 30 top ASX stocks used by `screen_stocks`:
```
BHP, CBA, CSL, NAB, WBC, ANZ, FMG, WES, MQG, WOW,
TLS, RIO, WDS, ALL, GMG, TCL, STO, COL, REA, XRO,
JHX, SOL, ORG, SHL, QBE, MIN, CPU, NXT, PME, CAR
```

---

## Dispatch Pattern

The `TOOL_DISPATCH` dict (line 462) maps tool names to lambda wrappers:
```python
TOOL_DISPATCH = {
    "get_stock_data": lambda args: tool_get_stock_data(**args),
    ...
}
```

`execute_tool()` (line 471) simply looks up the name and calls the function. This design allows `agent.py` to monkey-patch the dispatch table for demo mode.
