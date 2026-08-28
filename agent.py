"""
ASX Investment Research Agent
==============================
An agentic AI system powered by Claude that uses natural language
to research, analyse, and report on ASX equities.

The agent has access to tools for:
  - Fetching stock fundamentals & prices
  - Fetching timestamped historical and recent intraday OHLCV bars
  - Getting recent news headlines
  - Screening stocks by criteria
  - Comparing stocks side-by-side
  - Generating PDF research reports
  - Creating native charts, numeric plots, and flow/relationship diagrams from computed data

Usage:
    python agent.py                          # interactive mode
    python agent.py "find undervalued mining stocks with high dividends"
    python agent.py --demo "compare BHP and RIO"   # use sample data
"""

import json
from typing import Optional

import anthropic
from dotenv import load_dotenv

from config import MAX_TOKENS, MAX_TURNS, MODEL, SYSTEM_PROMPT
from tools import TOOL_SCHEMAS, execute_tool

load_dotenv()


def run_agent(user_message: str, demo: bool = False) -> str:
    """
    Run the agent loop:
    1. Send user message + tools to Claude
    2. If Claude wants to use tools, execute them and send results back
    3. Repeat until Claude gives a final text response
    """
    # Swap tool implementations to demo mode if needed
    if demo:
        _patch_demo_tools()

    client = anthropic.Anthropic()

    messages = [{"role": "user", "content": user_message}]

    print(f"\n{'─' * 60}")
    print(f"🤖 Agent processing: \"{user_message}\"")
    print(f"{'─' * 60}\n")

    for turn in range(MAX_TURNS):
        # Call Claude
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # Process response blocks (thinking blocks are kept in the history but
        # not printed — they must be echoed back to the API unchanged)
        assistant_content = response.content
        text_parts = []
        tool_uses = []

        for block in assistant_content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # If there are text parts, print them
        if text_parts:
            for t in text_parts:
                print(t)

        if response.stop_reason == "refusal":
            return "⚠️ Claude declined to answer this request."

        if response.stop_reason == "max_tokens":
            print("\n⚠️ Response hit the token limit and may be incomplete.")
            return "\n".join(text_parts)

        # If no tool calls, we're done
        if not tool_uses:
            return "\n".join(text_parts)

        # Execute tool calls and build the next message
        messages.append({"role": "assistant", "content": assistant_content})

        tool_results = []
        for tool_use in tool_uses:
            print(f"  🔧 Calling tool: {tool_use.name}({json.dumps(tool_use.input, indent=None)[:120]}...)")

            result = execute_tool(tool_use.name, tool_use.input)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    return "⚠️ Agent reached maximum turns without completing. Try a more specific query."


def _patch_demo_tools():
    """Replace yfinance-based tools with sample data for demo mode."""
    from sample_data import get_sample_dataframe, get_sample_news
    import tools

    sample_df = get_sample_dataframe()
    sample_news = get_sample_news()

    def _lookup(ticker: str) -> Optional[dict]:
        rows = sample_df[sample_df["ticker"] == ticker]
        if len(rows) == 0:
            return None
        row = rows.iloc[0].to_dict()
        # Add display field
        mc = row.get("market_cap", 0) or 0
        row["market_cap_display"] = f"${mc/1e9:.1f}B" if mc >= 1e9 else f"${mc/1e6:.0f}M"
        return row

    def demo_get_stock_data(tickers):
        results = [_lookup(t) for t in tickers]
        return json.dumps([r for r in results if r], indent=2, default=str)

    def demo_get_stock_news(tickers):
        result = {t: sample_news.get(t, []) for t in tickers}
        return json.dumps(result, indent=2, default=str)

    def demo_get_price_history(tickers, **_kwargs):
        return json.dumps({
            "error": "Historical price data is unavailable in offline demo mode. Use live mode for current Yahoo Finance history.",
            "tickers": tickers,
            "results": [],
        })

    def demo_screen_stocks(min_market_cap_b=0, max_pe_ratio=None, min_dividend_yield=0,
                           min_roe=0, sectors=None, exclude_sectors=None):
        df = sample_df.copy()
        if min_market_cap_b > 0:
            df = df[df["market_cap"].fillna(0) >= min_market_cap_b * 1e9]
        if max_pe_ratio is not None:
            df = df[(df["pe_ratio"].isna()) | (df["pe_ratio"] <= max_pe_ratio)]
        if min_dividend_yield > 0:
            df = df[df["dividend_yield"].fillna(0) >= min_dividend_yield]
        if min_roe > 0:
            df = df[df["roe"].fillna(0) >= min_roe]
        if sectors:
            df = df[df["sector"].isin(sectors)]
        if exclude_sectors:
            df = df[~df["sector"].isin(exclude_sectors)]

        results = df.to_dict(orient="records")
        for r in results:
            mc = r.get("market_cap", 0) or 0
            r["market_cap_display"] = f"${mc/1e9:.1f}B" if mc >= 1e9 else f"${mc/1e6:.0f}M"
        return json.dumps(results, indent=2, default=str)

    def demo_compare_stocks(tickers):
        rows = []
        for t in tickers:
            data = _lookup(t)
            if data:
                rows.append({
                    "ticker": data["ticker"],
                    "name": data["name"],
                    "sector": data["sector"],
                    "price": data["current_price"],
                    "market_cap": data["market_cap_display"],
                    "pe_ratio": data["pe_ratio"],
                    "roe": f"{data['roe']:.1%}" if data.get("roe") else "N/A",
                    "dividend_yield": f"{data['dividend_yield']:.1%}" if data.get("dividend_yield") else "N/A",
                    "revenue_growth": f"{data['revenue_growth']:.1%}" if data.get("revenue_growth") else "N/A",
                    "earnings_growth": f"{data['earnings_growth']:.1%}" if data.get("earnings_growth") else "N/A",
                    "debt_to_equity": data["debt_to_equity"],
                    "beta": data["beta"],
                })
        return json.dumps(rows, indent=2, default=str)

    def demo_generate_report(tickers, title=None, strategy="balanced"):
        stocks = [_lookup(t) for t in tickers]
        stocks = [s for s in stocks if s]
        if not stocks:
            return json.dumps({"error": "No matching stocks found in sample data"})

        # Use the existing report generator
        from report import generate_report as gen
        import pandas as pd
        df = pd.DataFrame(stocks)
        df["news_sentiment"] = 0.5
        df["composite_score"] = 0.5
        df["rank"] = range(1, len(df) + 1)
        news = {t: sample_news.get(t, []) for t in tickers}
        path = gen(df, news)
        html = tools._build_html_report(
            stocks, news, title or "ASX Investment Research Report", strategy or "balanced"
        )
        return json.dumps({
            "report_path": path,
            "stocks_included": len(stocks),
            "html_report": html,
        })

    # Patch the dispatch table. web_search_news is left on the live
    # implementation — there is no sample data for it.
    tools.TOOL_DISPATCH = {
        **tools.TOOL_DISPATCH,
        "get_stock_data": lambda args: demo_get_stock_data(**args),
        "get_stock_news": lambda args: demo_get_stock_news(**args),
        "get_price_history": lambda args: demo_get_price_history(**args),
        "screen_stocks": lambda args: demo_screen_stocks(**args),
        "compare_stocks": lambda args: demo_compare_stocks(**args),
        "generate_report": lambda args: demo_generate_report(**args),
    }


# ── Interactive Mode ─────────────────────────────────────────────────────────

def interactive(demo=False):
    """Run the agent in interactive chat mode."""
    width = 62

    def line(text=""):
        print("║" + f"  {text}".ljust(width) + "║")

    print()
    print("╔" + "═" * width + "╗")
    print("║" + "ASX Investment Research Agent (powered by Claude)".center(width) + "║")
    print("╠" + "═" * width + "╣")
    line("Ask me anything about ASX stocks in natural language.")
    line("Examples:")
    line('• "Find undervalued mining stocks with high dividends"')
    line('• "Compare BHP, RIO, and FMG"')
    line('• "Generate a report on the top ASX tech stocks"')
    line('• "Graph the dividend yields of BHP, RIO and FMG"')
    line('• "Which bank has the best ROE?"')
    line()
    line(f"Mode: {'DEMO (sample data)' if demo else 'LIVE (yfinance)'}")
    line("Type 'quit' to exit.")
    print("╚" + "═" * width + "╝")
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        try:
            run_agent(user_input, demo=demo)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Try again or check your ANTHROPIC_API_KEY.\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ASX Investment Research Agent")
    parser.add_argument("query", nargs="?", help="One-shot query (otherwise enters interactive mode)")
    parser.add_argument("--demo", action="store_true", help="Use sample data instead of yfinance")
    args = parser.parse_args()

    if args.query:
        run_agent(args.query, demo=args.demo)
    else:
        interactive(demo=args.demo)
