# agent.py — The Brain (Agent Loop)

This is the **entry point** and **orchestrator** of the entire application. It implements an agentic AI loop where Claude autonomously decides which tools to call based on your natural language query.

---

## Architecture Diagram

```
                          +---------------------+
                          |     USER INPUT       |
                          |  (CLI or Interactive)|
                          +----------+----------+
                                     |
                                     v
                          +---------------------+
                          |   __main__ block     |
                          |   (argparse)         |
                          +----------+----------+
                                     |
                         +-----------+-----------+
                         |                       |
                         v                       v
                  +-------------+        +---------------+
                  | run_agent() |        | interactive() |
                  | (one-shot)  |        | (chat loop)   |
                  +------+------+        +-------+-------+
                         |                       |
                         |    calls run_agent()   |
                         |<----------------------+
                         |
                         v
              +---------------------+
              |  AGENT LOOP         |
              |  (up to 15 turns)   |
              +----------+----------+
                         |
            +------------+------------+
            |                         |
            v                         v
   +----------------+      +-------------------+
   | Claude API     |      | Tool Execution    |
   | (messages.     |      | (execute_tool()   |
   |  create())     |      |  from tools.py)   |
   +-------+--------+      +---------+---------+
           |                          |
           |   tool_use blocks        |  JSON results
           +--------->----------------+
           |                          |
           |   tool_result messages   |
           +----------<---------------+
           |
           v
   +----------------+
   | stop_reason =  |
   | "end_turn"     |-----> Final text response to user
   +----------------+
```

---

## How the Agent Loop Works

The core logic lives in `run_agent()` (line 65). Here's the step-by-step flow:

### 1. Initialisation
```python
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from .env
messages = [{"role": "user", "content": user_message}]
```
- Creates an Anthropic client (API key loaded via `dotenv`)
- Seeds the conversation with the user's query

### 2. The Loop (max 15 iterations)
Each iteration:

**a) Call Claude**
```python
response = client.messages.create(
    model=MODEL,              # claude-sonnet-4-20250514
    max_tokens=4096,
    system=SYSTEM_PROMPT,     # "You are an expert ASX analyst..."
    tools=TOOL_SCHEMAS,       # 5 tool definitions from tools.py
    messages=messages,        # full conversation so far
)
```

**b) Parse the response** — Claude's response contains a mix of:
- `text` blocks — analysis/explanation text printed to the user
- `tool_use` blocks — requests to call a specific tool with arguments

**c) Check if done** — If `stop_reason == "end_turn"` and no tool calls, return the final text.

**d) Execute tools** — For each `tool_use` block:
```python
result = execute_tool(tool_use.name, tool_use.input)
```
This calls into `tools.py` which runs the actual function (e.g. fetching from yfinance).

**e) Feed results back** — Tool results are appended as `tool_result` messages, and the loop continues.

### 3. Demo Mode
When `--demo` is passed, `_patch_demo_tools()` replaces the real tool dispatch table with functions that read from `sample_data.py` instead of hitting yfinance. This is done via monkey-patching `tools.TOOL_DISPATCH`.

---

## Key Configuration

| Constant | Value | Purpose |
|---|---|---|
| `MODEL` | `claude-sonnet-4-20250514` | Which Claude model to use |
| `MAX_TURNS` | `15` | Safety limit to prevent infinite loops |
| `SYSTEM_PROMPT` | (long string) | Instructs Claude on its role, tools, and behaviour |

---

## Two Run Modes

| Mode | Command | Description |
|---|---|---|
| **One-shot** | `python agent.py "query"` | Runs once, prints result, exits |
| **Interactive** | `python agent.py` | REPL-style chat loop until user types `quit` |

Both support `--demo` to use sample data.
