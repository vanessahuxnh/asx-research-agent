import json
import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

import requests

import agent
import server
import tools
from source_utils import append_sources, collect_sources


class SourceTests(unittest.TestCase):
    def test_collect_and_append_sources_deduplicates_safe_urls(self):
        payload = {
            "ticker": "BHP.AX",
            "source_title": "BHP market data",
            "source_url": "https://finance.yahoo.com/quote/BHP.AX/",
            "results": [
                {"title": "BHP release", "url": "https://www.bhp.com/news/example"},
                {"title": "Duplicate", "url": "https://www.bhp.com/news/example"},
                {"title": "Unsafe", "url": "javascript:alert(1)"},
            ],
        }
        sources = collect_sources(payload)
        self.assertEqual(len(sources), 2)
        answer = append_sources("Analysis", sources)
        self.assertIn("## Sources", answer)
        self.assertIn("https://www.bhp.com/news/example", answer)
        self.assertNotIn("javascript:", answer)

    def test_no_external_sources_is_explicit(self):
        self.assertIn("No external sources were used", append_sources("Answer", []))

    def test_web_search_preserves_destination_urls_and_filters(self):
        html = '''<div class="result">
          <a class="result__a" href="https://www.asx.com.au/example">ASX release</a>
          <div class="result__snippet">Official announcement</div>
        </div>'''
        response = SimpleNamespace(text=html, raise_for_status=lambda: None)
        captured = {}

        def fake_post(_url, data, headers, timeout):
            captured.update(data)
            return response

        with patch.object(requests, "post", side_effect=fake_post):
            result = json.loads(tools.tool_web_search(
                "BHP announcement",
                recency="month",
                domains=["asx.com.au"],
            ))
        self.assertEqual(result["results"][0]["url"], "https://www.asx.com.au/example")
        self.assertEqual(captured["df"], "m")
        self.assertIn("site:asx.com.au", captured["q"])

    def test_web_search_reports_human_verification(self):
        response = SimpleNamespace(
            text="<html><body>Bots use DuckDuckGo too. Complete the following challenge.</body></html>",
            raise_for_status=lambda: None,
        )
        with patch.object(requests, "post", return_value=response):
            result = json.loads(tools.tool_web_search("BHP results"))
        self.assertIn("human-verification", result["error"])

    def test_fetch_web_page_extracts_text_and_source(self):
        html = b'''<html><head><title>BHP Results</title>
          <meta property="article:published_time" content="2026-08-18T00:00:00Z">
          <script>ignore me</script></head><body><h1>Annual results</h1><p>Revenue increased.</p></body></html>'''

        class FakeResponse:
            status_code = 200
            headers = {"Content-Type": "text/html; charset=utf-8"}
            encoding = "utf-8"

            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size):
                yield html

            def close(self):
                return None

        with patch.object(tools, "_validate_public_url", return_value="https://www.bhp.com/results"), patch.object(
            requests, "get", return_value=FakeResponse()
        ):
            result = json.loads(tools.tool_fetch_web_page("https://www.bhp.com/results"))
        self.assertEqual(result["source_title"], "BHP Results")
        self.assertEqual(result["source_url"], "https://www.bhp.com/results")
        self.assertEqual(result["published_at"], "2026-08-18T00:00:00Z")
        self.assertIn("Revenue increased", result["text"])
        self.assertNotIn("ignore me", result["text"])

    def test_fetch_web_page_rejects_local_destination(self):
        result = json.loads(tools.tool_fetch_web_page("http://127.0.0.1:5001/"))
        self.assertIn("not allowed", result["error"])

    def test_yahoo_news_preserves_canonical_article_url(self):
        ticker = SimpleNamespace(news=[{
            "content": {
                "title": "Market update",
                "pubDate": "2026-08-28T00:00:00Z",
                "provider": {"displayName": "Reuters"},
                "canonicalUrl": {"url": "https://finance.yahoo.com/news/market-update.html"},
            },
        }])
        with patch.object(tools.yf, "Ticker", return_value=ticker):
            news = tools._fetch_news_single("BHP.AX", 1)
        self.assertEqual(news[0]["url"], "https://finance.yahoo.com/news/market-update.html")

    def test_server_enforces_sources_section(self):
        tool_use = SimpleNamespace(
            type="tool_use", name="get_stock_data", id="tool-1", input={"tickers": ["BHP.AX"]}
        )
        responses = iter([
            SimpleNamespace(content=[tool_use], stop_reason="tool_use"),
            SimpleNamespace(content=[SimpleNamespace(type="text", text="BHP summary")], stop_reason="end_turn"),
        ])
        fake_client = SimpleNamespace(
            messages=SimpleNamespace(create=lambda **_kwargs: next(responses))
        )
        tool_result = json.dumps([{
            "ticker": "BHP.AX",
            "source_title": "BHP market data",
            "source_url": "https://finance.yahoo.com/quote/BHP.AX/",
        }])
        with patch.object(server.anthropic, "Anthropic", return_value=fake_client), patch.object(
            server, "execute_tool", return_value=tool_result
        ):
            events = "".join(server.stream_agent("Tell me about BHP"))
        self.assertIn("## Sources", events)
        self.assertIn("https://finance.yahoo.com/quote/BHP.AX/", events)

    def test_cli_prints_sources_section(self):
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Local explanation")],
            stop_reason="end_turn",
        )
        fake_client = SimpleNamespace(
            messages=SimpleNamespace(create=lambda **_kwargs: response)
        )
        output = io.StringIO()
        with patch.object(agent.anthropic, "Anthropic", return_value=fake_client), redirect_stdout(output):
            answer = agent.run_agent("Explain the agent")
        self.assertIn("## Sources", answer)
        self.assertIn("No external sources were used", output.getvalue())


if __name__ == "__main__":
    unittest.main()
