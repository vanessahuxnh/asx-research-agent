"""
Flask API server for the ASX Research Agent.
Streams agent responses via Server-Sent Events (SSE).
"""

import json
import os
import traceback

import anthropic
from dotenv import load_dotenv
from flask import Flask, Response, request
from flask_cors import CORS

from config import MAX_TOKENS, MAX_TURNS, MODEL, SYSTEM_PROMPT, VISUALIZATION_OUTPUT_DIR
from tools import TOOL_SCHEMAS, execute_tool

load_dotenv()

# static_folder must be set at construction — setting it inside the __main__
# block leaves "/" broken under gunicorn / `flask run`.
app = Flask(__name__, static_folder=os.path.dirname(os.path.abspath(__file__)))
CORS(app)


def _sse(payload: dict) -> str:
    """Encode one Server-Sent Event."""
    return f"data: {json.dumps(payload)}\n\n"


def _read_visualization(path: str):
    """Read only SVGs created inside the configured visualization directory."""
    if not isinstance(path, str) or not path.lower().endswith(".svg"):
        return None
    resolved = os.path.realpath(path)
    allowed = os.path.realpath(VISUALIZATION_OUTPUT_DIR)
    try:
        if os.path.commonpath([resolved, allowed]) != allowed:
            return None
        with open(resolved, "r", encoding="utf-8") as source:
            return source.read()
    except (OSError, ValueError):
        return None


def stream_agent(user_message: str):
    """Generator that yields SSE events as the agent processes."""
    try:
        client = anthropic.Anthropic()
    except Exception as e:
        yield _sse({"type": "error", "content": f"Could not initialise Claude client: {e}"})
        yield _sse({"type": "done"})
        return

    messages = [{"role": "user", "content": user_message}]

    try:
        for _turn in range(MAX_TURNS):
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                thinking={"type": "adaptive"},
                tools=TOOL_SCHEMAS,
                messages=messages,
            )

            assistant_content = response.content
            text_parts = []
            tool_uses = []

            for block in assistant_content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            answer = "\n".join(text_parts)

            if response.stop_reason == "refusal":
                yield _sse({"type": "error", "content": "Claude declined to answer this request."})
                yield _sse({"type": "done"})
                return

            # No tool calls (or truncated output) — send the final text and finish
            if not tool_uses or response.stop_reason == "max_tokens":
                if response.stop_reason == "max_tokens":
                    answer += "\n\n_(Response hit the token limit and may be incomplete.)_"
                yield _sse({"type": "answer", "content": answer})
                yield _sse({"type": "done"})
                return

            # Send any intermediate text
            if answer:
                yield _sse({"type": "text", "content": answer})

            # Execute tool calls and stream each one
            messages.append({"role": "assistant", "content": assistant_content})
            tool_results = []

            for tool_use in tool_uses:
                # Notify frontend that a tool is being called
                yield _sse({"type": "tool_call", "name": tool_use.name, "input": tool_use.input})

                result = execute_tool(tool_use.name, tool_use.input)

                # Send tool result data (parsed for the frontend to use)
                try:
                    parsed = json.loads(result)
                except (json.JSONDecodeError, TypeError):
                    parsed = result

                yield _sse({"type": "tool_result", "name": tool_use.name, "data": parsed})

                # If this was a report, send the HTML for inline rendering
                if tool_use.name == "generate_report" and isinstance(parsed, dict) and "html_report" in parsed:
                    yield _sse({"type": "html_report", "content": parsed["html_report"]})

                # Charts, plots, and diagrams are generated as escaped, dependency-free
                # SVG. Send the content inline while keeping the model-facing
                # tool result compact (path + metadata only).
                if tool_use.name in {"create_chart", "create_diagram", "create_plot"} and isinstance(parsed, dict):
                    svg = _read_visualization(parsed.get("visualization_path"))
                    if svg:
                        yield _sse({
                            "type": "visualization",
                            "content": svg,
                            "title": parsed.get("title", "Visualization"),
                        })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

        yield _sse({"type": "error", "content": "Agent reached maximum turns."})
        yield _sse({"type": "done"})

    except Exception as e:
        # An unhandled exception mid-generator would otherwise leave the client
        # hanging on a stream that just stops.
        traceback.print_exc()
        yield _sse({"type": "error", "content": f"{type(e).__name__}: {e}"})
        yield _sse({"type": "done"})


@app.route("/api/query", methods=["POST"])
def query():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("query") or "").strip()
    if not user_message:
        return {"error": "No query provided"}, 400

    return Response(
        stream_agent(user_message),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/")
def index():
    return app.send_static_file("asx_agent_ui.html")


if __name__ == "__main__":
    # Debug mode exposes the Werkzeug console — opt in explicitly, and only
    # bind beyond localhost when asked to.
    debug = os.getenv("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    host = os.getenv("ASX_HOST", "127.0.0.1")
    port = int(os.getenv("ASX_PORT", "5001"))

    print("\n  ASX Research Agent API")
    print(f"  http://{host}:{port}\n")
    app.run(host=host, port=port, debug=debug, threaded=True)
