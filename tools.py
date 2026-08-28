"""
Tool definitions for the ASX Research Agent.
Each tool is a function the LLM can call via tool_use, plus the schema it sees.
"""

import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qs, urlparse

import yfinance as yf

from config import REPORT_OUTPUT_DIR
from visualizations import (
    create_chart as _create_chart,
    create_diagram as _create_diagram,
    create_plot as _create_plot,
)

# yfinance issues one HTTP request per ticker, so screening the universe
# serially takes ~a minute. Fetch in parallel instead.
MAX_FETCH_WORKERS = 8


# ── Tool Schemas (sent to Claude) ────────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "get_stock_data",
        "description": (
            "Fetch fundamental data and price metrics for one or more ASX-listed stocks. "
            "Returns key financials: price, P/E, ROE, dividend yield, revenue growth, "
            "earnings growth, debt/equity, market cap, beta, margins, 52-week range, "
            "trailing returns, and source/retrieval timestamps. Use the .AX suffix for "
            "ASX tickers (e.g. BHP.AX). Yahoo/yfinance is not guaranteed real-time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ASX ticker symbols with .AX suffix, e.g. ['BHP.AX', 'CBA.AX']",
                }
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "get_stock_news",
        "description": (
            "Fetch recent news headlines for one or more ASX stocks. "
            "Returns up to 5 headlines per stock with title, publisher, and date. "
            "Useful for gauging market sentiment and recent developments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ASX ticker symbols with .AX suffix",
                }
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "get_price_history",
        "description": (
            "Fetch timestamped historical OHLCV market data from Yahoo Finance for up to "
            "five ASX tickers or indices. Use this before price-over-time charts, return or "
            "volatility analysis, drawdowns, or correlations. The latest available bar is "
            "always retained and each result reports its data timestamp, retrieval timestamp, "
            "exchange timezone, and whether rows were downsampled. Intraday data is limited by "
            "Yahoo/yfinance availability and is not guaranteed to be real-time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 5,
                    "description": "ASX tickers such as BHP.AX, or indices such as ^AXJO",
                },
                "period": {
                    "type": "string",
                    "enum": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"],
                    "description": "History window; default 1y",
                },
                "interval": {
                    "type": "string",
                    "enum": ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"],
                    "description": "Bar interval; default 1d. Intraday intervals cannot extend beyond the latest 60 days.",
                },
                "auto_adjust": {
                    "type": "boolean",
                    "description": "Adjust OHLC for splits and dividends; default true",
                },
                "prepost": {
                    "type": "boolean",
                    "description": "Include pre/post-market bars when Yahoo supplies them; default false",
                },
                "max_points": {
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 500,
                    "description": "Maximum returned bars per ticker; default 120. Data is evenly sampled with the latest bar retained.",
                },
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "web_search_news",
        "description": (
            "Search the web for the latest news about a specific ASX stock or market topic. "
            "Use this when a stock price has moved significantly and you need to find out why, "
            "or when you need more recent/detailed news than get_stock_news provides. "
            "Returns headlines, snippets, and source URLs from the past week."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query, e.g. 'BHP ASX news today' or 'CSL share price drop reason'",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5, max: 10)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "screen_stocks",
        "description": (
            "Screen the ASX for stocks matching specific criteria. "
            "Searches a predefined universe of top ASX stocks and filters by "
            "market cap, P/E ratio, dividend yield, ROE, sector, and more. "
            "Returns a filtered list of tickers that match."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_market_cap_b": {
                    "type": "number",
                    "description": "Minimum market cap in AUD billions (default: 0)",
                },
                "max_pe_ratio": {
                    "type": "number",
                    "description": "Maximum trailing P/E ratio (default: no limit)",
                },
                "min_dividend_yield": {
                    "type": "number",
                    "description": "Minimum dividend yield as decimal, e.g. 0.04 for 4% (default: 0)",
                },
                "min_roe": {
                    "type": "number",
                    "description": "Minimum return on equity as decimal, e.g. 0.15 for 15% (default: 0)",
                },
                "sectors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter to specific sectors, e.g. ['Basic Materials', 'Healthcare']. Empty = all sectors.",
                },
                "exclude_sectors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Sectors to exclude",
                },
            },
            "required": [],
        },
    },
    {
        "name": "compare_stocks",
        "description": (
            "Compare multiple stocks side-by-side on key metrics. "
            "Produces a comparison table with price, valuation, growth, profitability, "
            "and risk metrics. Good for narrowing down a shortlist."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ASX ticker symbols to compare (2-10 stocks)",
                }
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "generate_report",
        "description": (
            "Generate a PDF research report for a list of stocks. "
            "The report includes an executive summary, rankings table, "
            "individual stock profiles with key metrics, and recent news. "
            "Returns the file path of the generated PDF."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ASX ticker symbols to include in the report",
                },
                "title": {
                    "type": "string",
                    "description": "Custom title for the report (default: 'ASX Investment Research Report')",
                },
                "strategy": {
                    "type": "string",
                    "enum": ["growth", "value", "dividend", "balanced"],
                    "description": "Investment strategy context for the report (default: 'balanced')",
                },
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "create_chart",
        "description": (
            "Create a chart from numeric data that has already been computed or fetched. "
            "Use this for categorical charts, labelled trends, or visual comparisons. "
            "Supports bar, line, area, scatter, and pie charts and returns a saved SVG path."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Clear, specific chart title"},
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "area", "scatter", "pie"],
                    "description": "Chart form best suited to the data",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Category or point labels, in display order",
                },
                "series": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "values": {"type": "array", "items": {"type": "number"}},
                            "x_values": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "Required only for scatter charts",
                            },
                        },
                        "required": ["name", "values"],
                    },
                    "description": "One or more numeric series; pie charts accept exactly one",
                },
                "x_axis_label": {"type": "string"},
                "y_axis_label": {"type": "string"},
                "value_format": {
                    "type": "string",
                    "enum": ["number", "currency", "percent"],
                    "description": "Use percent for decimal fractions such as 0.052 = 5.2%",
                },
            },
            "required": ["title", "chart_type", "labels", "series"],
        },
    },
    {
        "name": "create_diagram",
        "description": (
            "Create a flowchart or relationship diagram from named nodes and directed edges. "
            "Use this when the user asks for a diagram, process flow, decision flow, hierarchy, "
            "or visual map of concepts. Returns a saved SVG path."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Clear diagram title"},
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Unique stable identifier"},
                            "label": {"type": "string", "description": "Text displayed in the node"},
                            "shape": {"type": "string", "enum": ["box", "rounded", "circle", "diamond"]},
                            "group": {"type": "string", "description": "Optional category used for node colour"},
                            "layer": {"type": "integer", "minimum": 0, "maximum": 20},
                        },
                        "required": ["id", "label"],
                    },
                },
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                            "label": {"type": "string"},
                        },
                        "required": ["from", "to"],
                    },
                },
                "direction": {"type": "string", "enum": ["top_down", "left_right"]},
            },
            "required": ["title", "nodes", "edges"],
        },
    },
    {
        "name": "create_plot",
        "description": (
            "Create a native numeric plot directly from raw computed observations. "
            "Use line or scatter for numeric x/y data, histogram for distributions, "
            "and box for statistical summaries. Rendering is dependency-free SVG and "
            "returns a saved artifact path. Use create_chart instead for categorical "
            "bar/area/pie charts with display labels."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Clear, specific plot title"},
                "plot_type": {
                    "type": "string",
                    "enum": ["line", "scatter", "histogram", "box"],
                },
                "datasets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "values": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "Raw y-values or observations",
                            },
                            "x_values": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "Optional numeric x-values for line/scatter; defaults to 1..N",
                            },
                        },
                        "required": ["name", "values"],
                    },
                },
                "x_axis_label": {"type": "string"},
                "y_axis_label": {"type": "string"},
                "value_format": {
                    "type": "string",
                    "enum": ["number", "currency", "percent"],
                    "description": "Use percent for decimal fractions such as 0.052 = 5.2%",
                },
                "bins": {
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 30,
                    "description": "Histogram bin count; ignored for other plot types",
                },
            },
            "required": ["title", "plot_type", "datasets"],
        },
    },
]


# ── ASX Universe ─────────────────────────────────────────────────────────────

ASX_UNIVERSE = [
    "BHP.AX", "CBA.AX", "CSL.AX", "NAB.AX", "WBC.AX",
    "ANZ.AX", "FMG.AX", "WES.AX", "MQG.AX", "WOW.AX",
    "TLS.AX", "RIO.AX", "WDS.AX", "ALL.AX", "GMG.AX",
    "TCL.AX", "STO.AX", "COL.AX", "REA.AX", "XRO.AX",
    "JHX.AX", "SOL.AX", "ORG.AX", "SHL.AX", "QBE.AX",
    "MIN.AX", "CPU.AX", "NXT.AX", "PME.AX", "CAR.AX",
]


# ── Tool Implementations ────────────────────────────────────────────────────

def _normalise_yield(val):
    """
    yfinance returns dividendYield as a percentage (5.2 for 5.2%) in current
    versions and as a decimal (0.052) in older ones. Everything downstream —
    screening filters, `:.1%` formatting — assumes a decimal, so normalise here.
    """
    if val is None:
        return None
    try:
        val = float(val)
    except (TypeError, ValueError):
        return None
    # No ASX stock yields over 100%, so anything above 1 is a percentage.
    return val / 100 if val > 1 else val


def _fetch_single(ticker_str: str) -> Optional[dict]:
    """Fetch data for a single ticker via yfinance."""
    try:
        fetched_at_time = datetime.now(timezone.utc)
        fetched_at = fetched_at_time.isoformat()
        tk = yf.Ticker(ticker_str)
        info = tk.info or {}
        hist = tk.history(period="1y")

        # Cast out of numpy scalars — json.dumps(..., default=str) would
        # otherwise emit them as quoted strings.
        def _num(val):
            return float(val) if val is not None else None

        price_now = _num(
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or (hist["Close"].iloc[-1] if len(hist) > 0 else None)
        )
        price_1y = _num(hist["Close"].iloc[0]) if len(hist) > 0 else None
        price_6m = _num(hist["Close"].iloc[len(hist) // 2]) if len(hist) > 10 else None

        return {
            "ticker": ticker_str,
            "name": info.get("shortName", ticker_str),
            "data_source": "Yahoo Finance via yfinance",
            "fetched_at_utc": fetched_at,
            "source_market_timestamp": _iso_timestamp(info.get("regularMarketTime")),
            "source_age_seconds_at_fetch": _timestamp_age_seconds(
                info.get("regularMarketTime"), fetched_at_time
            ),
            "fundamentals_most_recent_quarter": _iso_timestamp(info.get("mostRecentQuarter")),
            "last_fiscal_year_end": _iso_timestamp(info.get("lastFiscalYearEnd")),
            "earnings_timestamp": _iso_timestamp(info.get("earningsTimestamp")),
            "exchange_timezone": info.get("exchangeTimezoneName") or info.get("timeZoneFullName"),
            "market_state": info.get("marketState"),
            "is_guaranteed_realtime": False,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap"),
            "market_cap_display": _fmt_cap(info.get("marketCap")),
            "current_price": price_now,
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "dividend_yield": _normalise_yield(info.get("dividendYield")),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "return_1y": round((price_now / price_1y) - 1, 4) if (price_now and price_1y) else None,
            "return_6m": round((price_now / price_6m) - 1, 4) if (price_now and price_6m) else None,
        }
    except Exception as e:
        return {
            "ticker": ticker_str,
            "error": str(e),
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        }


def _fmt_cap(val):
    if not val:
        return "N/A"
    if val >= 1e9:
        return f"${val/1e9:.1f}B"
    return f"${val/1e6:.0f}M"


def _fetch_many(tickers: list[str]) -> list[dict]:
    """Fetch several tickers concurrently, preserving input order."""
    if not tickers:
        return []
    workers = min(MAX_FETCH_WORKERS, len(tickers))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return [d for d in pool.map(_fetch_single, tickers) if d]


def tool_get_stock_data(tickers: list[str]) -> str:
    """Execute get_stock_data tool."""
    return json.dumps(_fetch_many(tickers), indent=2, default=str)


VALID_HISTORY_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
VALID_HISTORY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"}


def _normalise_market_ticker(ticker: str) -> str:
    """Normalise plain ASX codes while preserving indices and explicit suffixes."""
    ticker = str(ticker or "").strip().upper()
    if not ticker:
        raise ValueError("ticker symbols cannot be empty")
    if ticker.startswith("^") or "." in ticker or "=" in ticker:
        return ticker
    return f"{ticker}.AX"


def _iso_timestamp(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _timestamp_age_seconds(value, fetched_at):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            source_seconds = float(value)
        elif hasattr(value, "timestamp"):
            source_seconds = float(value.timestamp())
        else:
            source_seconds = datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        return max(0, round(fetched_at.timestamp() - source_seconds))
    except (TypeError, ValueError, OverflowError):
        return None


def _json_number(value, integer=False):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(number) if integer else number


def _sample_history(history, max_points):
    """Evenly sample a frame while always retaining its first and latest rows."""
    if len(history) <= max_points:
        return history
    positions = {
        round(index * (len(history) - 1) / (max_points - 1))
        for index in range(max_points)
    }
    return history.iloc[sorted(positions)]


def _fetch_price_history_single(
    ticker_str: str,
    period: str,
    interval: str,
    auto_adjust: bool,
    prepost: bool,
    max_points: int,
) -> dict:
    """Fetch and serialise price history for one symbol."""
    fetched_at_time = datetime.now(timezone.utc)
    fetched_at = fetched_at_time.isoformat()
    try:
        ticker = yf.Ticker(ticker_str)
        history = ticker.history(
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            prepost=prepost,
            actions=False,
            repair=False,
            raise_errors=True,
        )
        if history is None or history.empty:
            return {
                "ticker": ticker_str,
                "error": "No price history was returned for this period and interval",
                "fetched_at_utc": fetched_at,
            }

        metadata = ticker.get_history_metadata() or {}
        available = len(history)
        sampled = _sample_history(history, max_points)
        points = []
        for timestamp, row in sampled.iterrows():
            points.append({
                "timestamp": _iso_timestamp(timestamp),
                "open": _json_number(row.get("Open")),
                "high": _json_number(row.get("High")),
                "low": _json_number(row.get("Low")),
                "close": _json_number(row.get("Close")),
                "volume": _json_number(row.get("Volume"), integer=True),
            })

        latest_timestamp = _iso_timestamp(history.index[-1])
        return {
            "ticker": ticker_str,
            "period": period,
            "interval": interval,
            "auto_adjusted": auto_adjust,
            "prepost_included": prepost,
            "currency": metadata.get("currency"),
            "exchange": metadata.get("exchangeName") or metadata.get("fullExchangeName"),
            "exchange_timezone": metadata.get("exchangeTimezoneName"),
            "instrument_type": metadata.get("instrumentType"),
            "latest_bar_timestamp": latest_timestamp,
            "source_market_timestamp": _iso_timestamp(metadata.get("regularMarketTime")),
            "source_age_seconds_at_fetch": _timestamp_age_seconds(
                metadata.get("regularMarketTime"), fetched_at_time
            ),
            "fetched_at_utc": fetched_at,
            "points_available": available,
            "points_returned": len(points),
            "downsampled": available > len(points),
            "points": points,
        }
    except Exception as error:
        return {
            "ticker": ticker_str,
            "error": str(error),
            "fetched_at_utc": fetched_at,
        }


def tool_get_price_history(
    tickers: list[str],
    period: str = "1y",
    interval: str = "1d",
    auto_adjust: bool = True,
    prepost: bool = False,
    max_points: int = 120,
) -> str:
    """Execute get_price_history with freshness metadata and bounded output."""
    if not isinstance(tickers, list) or not 1 <= len(tickers) <= 5:
        raise ValueError("tickers must contain between 1 and 5 symbols")
    if period not in VALID_HISTORY_PERIODS:
        raise ValueError(f"unsupported period: {period}")
    if interval not in VALID_HISTORY_INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")
    if isinstance(max_points, bool) or not isinstance(max_points, int) or not 2 <= max_points <= 500:
        raise ValueError("max_points must be an integer from 2 to 500")
    if not isinstance(auto_adjust, bool) or not isinstance(prepost, bool):
        raise ValueError("auto_adjust and prepost must be boolean values")

    normalised = [_normalise_market_ticker(ticker) for ticker in tickers]
    workers = min(MAX_FETCH_WORKERS, len(normalised))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(
            lambda ticker: _fetch_price_history_single(
                ticker, period, interval, auto_adjust, prepost, max_points
            ),
            normalised,
        ))
    return json.dumps({
        "source": "Yahoo Finance via yfinance",
        "is_guaranteed_realtime": False,
        "freshness_note": (
            "Use latest_bar_timestamp and source_market_timestamp as the data 'as of' values. "
            "Yahoo/yfinance availability and exchange delays apply; this is not a licensed real-time feed."
        ),
        "results": results,
    }, indent=2)


def _fetch_news_single(ticker_str: str, limit: int = 5) -> list[dict]:
    """Fetch up to `limit` recent headlines for one ticker."""
    try:
        items = yf.Ticker(ticker_str).news or []
    except Exception:
        return []

    parsed = []
    for item in items[:limit]:
        content = item.get("content") or {}
        provider = content.get("provider") or {}
        parsed.append({
            "title": content.get("title") or item.get("title") or "N/A",
            "publisher": provider.get("displayName", "N/A"),
            "date": content.get("pubDate", ""),
        })
    return parsed


def tool_get_stock_news(tickers: list[str]) -> str:
    """Execute get_stock_news tool."""
    if not tickers:
        return json.dumps({}, indent=2)
    with ThreadPoolExecutor(max_workers=min(MAX_FETCH_WORKERS, len(tickers))) as pool:
        results = pool.map(_fetch_news_single, tickers)
    return json.dumps(dict(zip(tickers, results)), indent=2, default=str)


def _unwrap_ddg_url(href: str) -> str:
    """DuckDuckGo wraps results in /l/?uddg=<encoded>; return the real target."""
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    try:
        parsed = urlparse(href)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            return target or href
    except ValueError:
        return href
    return href


def tool_web_search_news(query: str, num_results: int = 5) -> str:
    """Search DuckDuckGo for recent news headlines."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as e:
        return json.dumps({
            "error": f"Web search unavailable — missing dependency ({e.name}). "
                     f"Install it with: pip install -r requirements.txt",
            "results": [],
        })

    num_results = min(num_results or 5, 10)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    results = []
    try:
        url = "https://html.duckduckgo.com/html/"
        resp = requests.post(url, data={"q": query, "df": "w"}, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.select(".result, .web-result")[:num_results]:
            title_tag = item.select_one(".result__a, a.result__url")
            snippet_tag = item.select_one(".result__snippet")
            if title_tag:
                results.append({
                    "title": title_tag.get_text(strip=True),
                    "url": _unwrap_ddg_url(title_tag.get("href", "")),
                    "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
                })
    except Exception as e:
        return json.dumps({"error": f"Web search failed: {str(e)}", "results": []})

    return json.dumps({"query": query, "results": results}, indent=2)


def tool_screen_stocks(
    min_market_cap_b: float = 0,
    max_pe_ratio: float = None,
    min_dividend_yield: float = 0,
    min_roe: float = 0,
    sectors: list[str] = None,
    exclude_sectors: list[str] = None,
) -> str:
    """Execute screen_stocks tool — screens the full ASX universe."""
    results = []
    for data in _fetch_many(ASX_UNIVERSE):
        if "error" in data:
            continue

        # Apply filters
        mc = data.get("market_cap") or 0
        if min_market_cap_b > 0 and mc < min_market_cap_b * 1e9:
            continue

        pe = data.get("pe_ratio")
        if max_pe_ratio is not None and pe is not None and pe > max_pe_ratio:
            continue

        dy = data.get("dividend_yield") or 0
        if min_dividend_yield > 0 and dy < min_dividend_yield:
            continue

        roe = data.get("roe") or 0
        if min_roe > 0 and roe < min_roe:
            continue

        sector = data.get("sector", "N/A")
        if sectors and sector not in sectors:
            continue
        if exclude_sectors and sector in exclude_sectors:
            continue

        results.append(data)

    return json.dumps(results, indent=2, default=str)


def _pct(val) -> str:
    """Format a decimal as a percentage. 0 is a real value, not missing data."""
    return f"{val:.1%}" if isinstance(val, (int, float)) else "N/A"


def tool_compare_stocks(tickers: list[str]) -> str:
    """Execute compare_stocks tool."""
    rows = []
    for data in _fetch_many(tickers):
        if "error" in data:
            continue
        rows.append({
            "ticker": data["ticker"],
            "name": data["name"],
            "sector": data["sector"],
            "price": data["current_price"],
            "market_cap": data["market_cap_display"],
            "pe_ratio": data["pe_ratio"],
            "forward_pe": data["forward_pe"],
            "roe": _pct(data.get("roe")),
            "dividend_yield": _pct(data.get("dividend_yield")),
            "revenue_growth": _pct(data.get("revenue_growth")),
            "earnings_growth": _pct(data.get("earnings_growth")),
            "debt_to_equity": data["debt_to_equity"],
            "beta": data["beta"],
            "return_1y": _pct(data.get("return_1y")),
            "source_market_timestamp": data.get("source_market_timestamp"),
            "fundamentals_most_recent_quarter": data.get("fundamentals_most_recent_quarter"),
            "fetched_at_utc": data.get("fetched_at_utc"),
            "is_guaranteed_realtime": False,
        })
    return json.dumps(rows, indent=2, default=str)


def _build_html_report(stocks, news, title, strategy):
    """Build a styled HTML report string matching the dark theme UI."""
    from html import escape

    def _f(val, fmt):
        if val is None:
            return "N/A"
        if fmt == "pct":
            return f"{val:.1%}"
        if fmt == "price":
            return f"${val:,.2f}"
        if fmt == "ratio":
            return f"{val:.1f}"
        return str(val)

    rows_html = ""
    for i, s in enumerate(stocks, 1):
        eg = s.get("earnings_growth")
        eg_color = "#6ee7b7" if eg and eg >= 0 else "#f87171" if eg else "#565a6e"
        rows_html += f"""<tr style="border-bottom:1px solid #ffffff06">
            <td style="padding:8px 10px;text-align:center">{i}</td>
            <td style="padding:8px 10px;color:#6ee7b7;font-family:monospace;font-weight:600">{escape(str(s.get('ticker', '')).replace('.AX', ''))}</td>
            <td style="padding:8px 10px">{escape(str(s.get('name','N/A'))[:22])}</td>
            <td style="padding:8px 10px;text-align:right">{_f(s.get('current_price'),'price')}</td>
            <td style="padding:8px 10px;text-align:right">{_f(s.get('pe_ratio'),'ratio')}</td>
            <td style="padding:8px 10px;text-align:right">{_f(s.get('roe'),'pct')}</td>
            <td style="padding:8px 10px;text-align:right">{_f(s.get('dividend_yield'),'pct')}</td>
            <td style="padding:8px 10px;text-align:right;color:{eg_color}">{_f(eg,'pct')}</td>
        </tr>"""

    profiles_html = ""
    for i, s in enumerate(stocks, 1):
        stock_news = news.get(s.get("ticker"), [])
        news_html = ""
        if stock_news:
            hl = "; ".join([escape(n["title"][:60]) for n in stock_news[:3] if n.get("title")])
            if hl:
                news_html = f'<div style="font-size:12px;color:#8b8fa3;font-style:italic;margin-top:8px">Recent: {hl}</div>'

        profiles_html += f"""
        <div style="margin-bottom:12px;padding:14px 16px;background:#12141a;border-radius:10px;border:1px solid #ffffff0a">
            <div style="font-size:14px;font-weight:600;color:#e8e9ed;margin-bottom:10px">#{i} — {escape(str(s.get('name','N/A')))} ({escape(str(s.get('ticker', '')).replace('.AX', ''))})</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 24px;font-size:12px;color:#e8e9ed">
                <div><span style="color:#8b8fa3">Price</span> <strong>{_f(s.get('current_price'),'price')}</strong></div>
                <div><span style="color:#8b8fa3">Mkt Cap</span> <strong>{s.get('market_cap_display','N/A')}</strong></div>
                <div><span style="color:#8b8fa3">P/E</span> <strong>{_f(s.get('pe_ratio'),'ratio')}</strong></div>
                <div><span style="color:#8b8fa3">Fwd P/E</span> <strong>{_f(s.get('forward_pe'),'ratio')}</strong></div>
                <div><span style="color:#8b8fa3">ROE</span> <strong>{_f(s.get('roe'),'pct')}</strong></div>
                <div><span style="color:#8b8fa3">ROA</span> <strong>{_f(s.get('roa'),'pct')}</strong></div>
                <div><span style="color:#8b8fa3">Rev Growth</span> <strong>{_f(s.get('revenue_growth'),'pct')}</strong></div>
                <div><span style="color:#8b8fa3">Earn Growth</span> <strong>{_f(s.get('earnings_growth'),'pct')}</strong></div>
                <div><span style="color:#8b8fa3">Div Yield</span> <strong>{_f(s.get('dividend_yield'),'pct')}</strong></div>
                <div><span style="color:#8b8fa3">D/E</span> <strong>{_f(s.get('debt_to_equity'),'ratio')}</strong></div>
            </div>
            {news_html}
        </div>"""

    html = f"""<div style="font-family:'DM Sans',system-ui,sans-serif;color:#e8e9ed;max-width:100%">
    <div style="text-align:center;padding:16px 0 12px">
        <div style="font-size:20px;font-weight:600;letter-spacing:-0.02em">{escape(title)}</div>
        <div style="font-size:12px;color:#8b8fa3;margin-top:4px">Strategy: {escape(strategy.title())} | {datetime.now().strftime('%d %B %Y %H:%M')}</div>
    </div>
    <div style="height:1px;background:#ffffff0a;margin:0 0 16px"></div>
    <div style="font-size:14px;font-weight:500;margin-bottom:10px">Stock Rankings</div>
    <div style="overflow-x:auto;border-radius:10px;border:1px solid #ffffff0a;margin-bottom:20px">
        <table style="width:100%;border-collapse:collapse;font-size:12px">
            <thead><tr style="background:#181b23">
                <th style="padding:8px 10px;text-align:center;color:#8b8fa3;font-weight:400;font-size:11px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #ffffff0a">#</th>
                <th style="padding:8px 10px;text-align:left;color:#8b8fa3;font-weight:400;font-size:11px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #ffffff0a">Ticker</th>
                <th style="padding:8px 10px;text-align:left;color:#8b8fa3;font-weight:400;font-size:11px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #ffffff0a">Name</th>
                <th style="padding:8px 10px;text-align:right;color:#8b8fa3;font-weight:400;font-size:11px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #ffffff0a">Price</th>
                <th style="padding:8px 10px;text-align:right;color:#8b8fa3;font-weight:400;font-size:11px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #ffffff0a">P/E</th>
                <th style="padding:8px 10px;text-align:right;color:#8b8fa3;font-weight:400;font-size:11px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #ffffff0a">ROE</th>
                <th style="padding:8px 10px;text-align:right;color:#8b8fa3;font-weight:400;font-size:11px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #ffffff0a">Div Yld</th>
                <th style="padding:8px 10px;text-align:right;color:#8b8fa3;font-weight:400;font-size:11px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #ffffff0a">Earn Grw</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    <div style="font-size:14px;font-weight:500;margin-bottom:10px">Stock Profiles</div>
    {profiles_html}
    <div style="height:1px;background:#ffffff0a;margin:16px 0 8px"></div>
    <div style="font-size:10px;color:#565a6e;font-style:italic">
        Disclaimer: This report is for informational purposes only and does not constitute financial advice.
    </div>
</div>"""
    return html


def tool_generate_report(tickers: list[str], title: str = None, strategy: str = "balanced") -> str:
    """Execute generate_report tool — fetches data and generates PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER

    # Fetch data (prices and news in parallel — one HTTP round trip each)
    stocks = [d for d in _fetch_many(tickers) if "error" not in d]
    news = {}
    if tickers:
        with ThreadPoolExecutor(max_workers=min(MAX_FETCH_WORKERS, len(tickers))) as pool:
            news = dict(zip(tickers, pool.map(lambda t: _fetch_news_single(t, 3), tickers)))

    if not stocks:
        return json.dumps({"error": "No data could be fetched for the given tickers"})

    # Build PDF
    report_title = title or "ASX Investment Research Report"
    strategy = strategy or "balanced"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(REPORT_OUTPUT_DIR, f"asx_report_{timestamp}.pdf")

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("RTitle", parent=styles["Title"],
                              fontSize=22, textColor=colors.HexColor("#1a1a2e"), spaceAfter=6))
    styles.add(ParagraphStyle("RSub", parent=styles["Normal"],
                              fontSize=11, textColor=colors.HexColor("#666"), alignment=TA_CENTER, spaceAfter=20))
    styles.add(ParagraphStyle("SecH", parent=styles["Heading2"],
                              fontSize=14, textColor=colors.HexColor("#16213e"), spaceBefore=16, spaceAfter=8))
    styles.add(ParagraphStyle("StockH", parent=styles["Heading3"],
                              fontSize=12, textColor=colors.HexColor("#0f3460"), spaceBefore=12, spaceAfter=4))
    styles.add(ParagraphStyle("Body2", parent=styles["Normal"],
                              fontSize=9, leading=13, textColor=colors.HexColor("#333")))

    story = []
    story.append(Spacer(1, 40))
    story.append(Paragraph(report_title, styles["RTitle"]))
    story.append(Paragraph(
        f"Strategy: {strategy.title()} &nbsp;|&nbsp; {datetime.now().strftime('%d %B %Y %H:%M')}",
        styles["RSub"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#ccc")))
    story.append(Spacer(1, 12))

    # Rankings table
    story.append(Paragraph("Stock Rankings", styles["SecH"]))

    def _f(val, fmt):
        if val is None:
            return "N/A"
        if fmt == "pct":
            return f"{val:.1%}"
        if fmt == "price":
            return f"${val:,.2f}"
        if fmt == "ratio":
            return f"{val:.1f}"
        return str(val)

    tbl = [["#", "Ticker", "Name", "Price", "P/E", "ROE", "Div Yld", "Rev Grw"]]
    for i, s in enumerate(stocks, 1):
        tbl.append([
            str(i),
            s["ticker"].replace(".AX", ""),
            str(s["name"])[:22],
            _f(s.get("current_price"), "price"),
            _f(s.get("pe_ratio"), "ratio"),
            _f(s.get("roe"), "pct"),
            _f(s.get("dividend_yield"), "pct"),
            _f(s.get("revenue_growth"), "pct"),
        ])

    t = Table(tbl, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

    # Individual profiles
    story.append(Paragraph("Stock Profiles", styles["SecH"]))
    for i, s in enumerate(stocks, 1):
        story.append(Paragraph(f"#{i} — {s['name']} ({s['ticker'].replace('.AX', '')})", styles["StockH"]))
        metrics = [
            ["Price", _f(s.get("current_price"), "price"), "Mkt Cap", s.get("market_cap_display", "N/A")],
            ["P/E", _f(s.get("pe_ratio"), "ratio"), "Fwd P/E", _f(s.get("forward_pe"), "ratio")],
            ["ROE", _f(s.get("roe"), "pct"), "ROA", _f(s.get("roa"), "pct")],
            ["Rev Growth", _f(s.get("revenue_growth"), "pct"), "Earn Growth", _f(s.get("earnings_growth"), "pct")],
            ["Div Yield", _f(s.get("dividend_yield"), "pct"), "D/E", _f(s.get("debt_to_equity"), "ratio")],
        ]
        mt = Table(metrics, colWidths=[70, 80, 70, 80])
        mt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#888")),
            ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#888")),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(mt)

        stock_news = news.get(s["ticker"], [])
        if stock_news:
            hl = "; ".join([n["title"][:60] for n in stock_news[:3] if n.get("title")])
            if hl:
                story.append(Paragraph(f"<i>Recent: {hl}</i>", styles["Body2"]))
        story.append(Spacer(1, 8))

    # Disclaimer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#ccc")))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<i>Disclaimer: This report is for informational purposes only and does not constitute "
        "financial advice. Consult a qualified advisor before making investment decisions.</i>",
        ParagraphStyle("Disc", parent=styles["Normal"], fontSize=7, textColor=colors.grey)))

    doc.build(story)

    html_report = _build_html_report(stocks, news, report_title, strategy)
    return json.dumps({
        "report_path": output_path,
        "stocks_included": len(stocks),
        "html_report": html_report,
    })


# ── Tool Dispatcher ──────────────────────────────────────────────────────────

TOOL_DISPATCH = {
    "get_stock_data": lambda args: tool_get_stock_data(**args),
    "get_stock_news": lambda args: tool_get_stock_news(**args),
    "get_price_history": lambda args: tool_get_price_history(**args),
    "web_search_news": lambda args: tool_web_search_news(**args),
    "screen_stocks": lambda args: tool_screen_stocks(**args),
    "compare_stocks": lambda args: tool_compare_stocks(**args),
    "generate_report": lambda args: tool_generate_report(**args),
    "create_chart": lambda args: _create_chart(**args),
    "create_diagram": lambda args: _create_diagram(**args),
    "create_plot": lambda args: _create_plot(**args),
}


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Execute a tool by name and return the result as a string.

    Never raises: a failing tool is reported back to the model as an error
    result so it can recover, rather than tearing down the agent loop (or the
    SSE stream in server.py).
    """
    handler = TOOL_DISPATCH.get(tool_name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        return handler(tool_input or {})
    except TypeError as e:
        # Wrong / unexpected arguments from the model.
        return json.dumps({"error": f"Invalid arguments for {tool_name}: {e}"})
    except Exception as e:
        return json.dumps({"error": f"{tool_name} failed: {type(e).__name__}: {e}"})
