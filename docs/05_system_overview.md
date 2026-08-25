# System Overview — How Everything Works Together

This document shows how all files in the qFinance project connect to form an agentic AI system for ASX stock research.

---

## Complete System Diagram

```
 USER
  |
  |  "Find undervalued mining stocks with high dividends"
  |
  v
+================================================================+
|                        agent.py                                 |
|                     (The Orchestrator)                          |
|                                                                 |
|  +------------------+     +-------------------+                 |
|  | __main__         |     | interactive()     |                 |
|  | (argparse)       |     | (REPL chat loop)  |                 |
|  +--------+---------+     +--------+----------+                 |
|           |                        |                            |
|           +----------+-------------+                            |
|                      |                                          |
|                      v                                          |
|           +---------------------+                               |
|           |    run_agent()      |  <-- THE CORE LOOP            |
|           +----------+----------+                               |
|                      |                                          |
|        +-------------+---------------+                          |
|        |                             |                          |
|        v                             v                          |
|  +-----------+              +-----------------+                 |
|  | Anthropic |              | SYSTEM_PROMPT   |                 |
|  | API       |              | (role + tool    |                 |
|  | Client    |              |  instructions)  |                 |
|  +-----+-----+              +-----------------+                 |
|        |                                                        |
+========|========================================================+
         |
         |  sends: system prompt + tool schemas + messages
         |  receives: text blocks + tool_use blocks
         v
+================================================================+
|                    Claude API (Anthropic)                        |
|                                                                 |
|  Claude reads the system prompt and tool schemas.               |
|  Based on the user's question, it decides:                      |
|                                                                 |
|  Option A: Respond with text (done)                             |
|  Option B: Call one or more tools, then continue                |
|                                                                 |
|  Example reasoning:                                             |
|  "User wants undervalued mining stocks with dividends.          |
|   I should screen_stocks with:                                  |
|     sectors=['Basic Materials'], min_dividend_yield=0.04,       |
|     max_pe_ratio=15                                             |
|   Then get_stock_data on the results for deeper analysis."      |
|                                                                 |
+========|========================================================+
         |
         |  tool_use: screen_stocks({sectors: ["Basic Materials"],
         |            min_dividend_yield: 0.04, max_pe_ratio: 15})
         v
+================================================================+
|                        tools.py                                 |
|                    (The Tool Layer)                              |
|                                                                 |
|  execute_tool("screen_stocks", {...})                           |
|        |                                                        |
|        v                                                        |
|  TOOL_DISPATCH["screen_stocks"]                                 |
|        |                                                        |
|        v                                                        |
|  tool_screen_stocks()                                           |
|        |                                                        |
|        |  for each ticker in ASX_UNIVERSE (30 stocks):          |
|        |     _fetch_single(ticker)                              |
|        |        |                                               |
|        |        v                                               |
|        |  +------------------+                                  |
|        |  | yfinance API     |  (or sample_data.py in demo)    |
|        |  | yf.Ticker(t)    |                                  |
|        |  | .info / .history |                                  |
|        |  +------------------+                                  |
|        |                                                        |
|        |  Apply filters -> return matching stocks as JSON       |
|        v                                                        |
|  Returns: '[{"ticker":"BHP.AX","pe_ratio":11.2,...}, ...]'      |
|                                                                 |
+========|========================================================+
         |
         |  tool_result sent back to Claude
         v
+================================================================+
|                    Claude API (turn 2)                           |
|                                                                 |
|  Claude sees the screening results.                             |
|  Decides to call get_stock_data on matches for full analysis.   |
|  May also call get_stock_news for sentiment.                    |
|                                                                 |
+========|========================================================+
         |
         |  (more tool calls and results may follow...)
         v
+================================================================+
|                    Claude API (final turn)                       |
|                                                                 |
|  Claude has all the data it needs.                              |
|  Produces a final text response with:                           |
|  - Analysis of each stock                                       |
|  - Comparison of key metrics                                    |
|  - Investment thesis                                            |
|  - Risk factors                                                 |
|  - Disclaimer                                                   |
|                                                                 |
|  stop_reason: "end_turn"                                        |
+================================================================+
         |
         v
      Printed to user's terminal


+==========================+     +================================+
|      report.py           |     |        sample_data.py          |
|   (PDF Generation)       |     |      (Demo Data)               |
|                          |     |                                |
|  Called when Claude uses  |     |  20 hardcoded ASX stocks       |
|  the generate_report     |     |  with realistic financials     |
|  tool.                   |     |                                |
|                          |     |  10 stocks have custom         |
|  Produces a styled PDF:  |     |  news headlines                |
|  - Title page            |     |                                |
|  - Executive summary     |     |  Used when --demo flag is      |
|  - Rankings table        |     |  passed to agent.py            |
|  - Stock profiles        |     |                                |
|  - Disclaimer            |     |  Swapped in via monkey-        |
|                          |     |  patching TOOL_DISPATCH        |
+==========================+     +================================+
```

---

## Data Flow: A Complete Example

Here's exactly what happens when you run:
```bash
python agent.py "Compare BHP and RIO"
```

```
Step 1: agent.py parses args, calls run_agent("Compare BHP and RIO")

Step 2: run_agent() sends to Claude API:
        - System prompt (expert ASX analyst role)
        - Tool schemas (5 tools with their parameters)
        - Message: "Compare BHP and RIO"

Step 3: Claude responds with tool_use:
        get_stock_data(tickers=["BHP.AX", "RIO.AX"])
        compare_stocks(tickers=["BHP.AX", "RIO.AX"])

Step 4: agent.py calls execute_tool() for each:
        tools.py -> _fetch_single("BHP.AX") -> yfinance -> {price, PE, ROE...}
        tools.py -> _fetch_single("RIO.AX") -> yfinance -> {price, PE, ROE...}
        Returns JSON results

Step 5: Results sent back to Claude as tool_result messages

Step 6: Claude analyses both datasets, writes a comparison:
        - Valuation comparison
        - Profitability analysis
        - Growth metrics
        - Dividend analysis
        - Risk profile
        - Final recommendation
        stop_reason: "end_turn"

Step 7: agent.py prints Claude's final text to terminal
```

---

## File Dependency Map

```
agent.py
  |
  +---> tools.py          (TOOL_SCHEMAS, execute_tool)
  |       |
  |       +---> yfinance  (live stock data)
  |       +---> reportlab (PDF generation in generate_report tool)
  |
  +---> sample_data.py    (demo mode only)
  |
  +---> anthropic         (Claude API client)
  +---> dotenv            (.env file loading)

report.py                  (standalone pipeline, not used by agent)
  |
  +---> config.py          (PREFERENCES, REPORT_TOP_N, etc.)
  +---> reportlab          (PDF generation)
```

---

## Key Design Decisions

### 1. Agentic Loop Pattern
Claude decides what to do — the code just executes. This means the system can handle queries it's never seen before, because Claude reasons about what tools to call and in what order.

### 2. Tool Schemas Separate from Implementation
The schemas (what Claude sees) are decoupled from the implementations (what runs). This allows demo mode to swap implementations without changing what Claude thinks the tools do.

### 3. Monkey-Patching for Demo Mode
Rather than if/else branching in every tool function, demo mode replaces the entire `TOOL_DISPATCH` dictionary. Clean separation — the tool functions themselves don't know about demo mode.

### 4. Stateless Conversation
Each `run_agent()` call starts fresh. There's no memory between queries in interactive mode — each question gets a new conversation with Claude.

---

## Configuration Files

| File | Purpose |
|---|---|
| `.env` | `ANTHROPIC_API_KEY` — your Claude API key |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Excludes `.env` from version control |
