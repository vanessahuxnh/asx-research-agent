import json
import unittest
from unittest.mock import patch

import pandas as pd

import tools


class FakeHistoryTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.history_calls = []

    def history(self, **kwargs):
        self.history_calls.append(kwargs)
        index = pd.date_range(
            "2026-08-28 10:00:00",
            periods=6,
            freq="5min",
            tz="Australia/Sydney",
        )
        return pd.DataFrame({
            "Open": [10, 11, 12, 13, 14, 15],
            "High": [11, 12, 13, 14, 15, 16],
            "Low": [9, 10, 11, 12, 13, 14],
            "Close": [10.5, 11.5, 12.5, 13.5, 14.5, 15.5],
            "Volume": [100, 200, 300, 400, 500, 600],
        }, index=index)

    def get_history_metadata(self):
        return {
            "currency": "AUD",
            "exchangeName": "ASX",
            "exchangeTimezoneName": "Australia/Sydney",
            "instrumentType": "EQUITY",
            "regularMarketTime": 1787880300,
        }


class FakeStockTicker:
    @property
    def info(self):
        return {
            "shortName": "Example Ltd",
            "currentPrice": 15.5,
            "regularMarketTime": 1787880300,
            "mostRecentQuarter": 1785456000,
            "lastFiscalYearEnd": 1753920000,
            "earningsTimestamp": 1786579200,
            "exchangeTimezoneName": "Australia/Sydney",
        }

    def history(self, **_kwargs):
        index = pd.date_range("2025-08-28", periods=2, freq="365D")
        return pd.DataFrame({"Close": [10.0, 15.5]}, index=index)


class PriceHistoryTests(unittest.TestCase):
    def test_history_is_timestamped_normalised_and_keeps_latest_bar(self):
        instances = []

        def make_ticker(symbol):
            ticker = FakeHistoryTicker(symbol)
            instances.append(ticker)
            return ticker

        with patch.object(tools.yf, "Ticker", side_effect=make_ticker):
            result = json.loads(tools.tool_get_price_history(
                tickers=["bhp"],
                period="5d",
                interval="5m",
                max_points=3,
            ))

        self.assertFalse(result["is_guaranteed_realtime"])
        history = result["results"][0]
        self.assertEqual(history["ticker"], "BHP.AX")
        self.assertEqual(history["currency"], "AUD")
        self.assertEqual(history["exchange_timezone"], "Australia/Sydney")
        self.assertIsInstance(history["source_age_seconds_at_fetch"], int)
        self.assertEqual(history["points_available"], 6)
        self.assertEqual(history["points_returned"], 3)
        self.assertTrue(history["downsampled"])
        self.assertEqual(history["points"][-1]["close"], 15.5)
        self.assertEqual(history["latest_bar_timestamp"], history["points"][-1]["timestamp"])
        self.assertEqual(instances[0].history_calls[0]["interval"], "5m")
        self.assertTrue(instances[0].history_calls[0]["auto_adjust"])

    def test_history_preserves_explicit_index_symbol(self):
        with patch.object(tools.yf, "Ticker", side_effect=FakeHistoryTicker):
            result = json.loads(tools.tool_get_price_history(["^axjo"], max_points=10))
        self.assertEqual(result["results"][0]["ticker"], "^AXJO")

    def test_history_rejects_unbounded_output(self):
        result = json.loads(tools.execute_tool("get_price_history", {
            "tickers": ["BHP.AX"],
            "max_points": 501,
        }))
        self.assertIn("max_points", result["error"])

    def test_history_tool_is_exposed_to_the_agent(self):
        names = [schema["name"] for schema in tools.TOOL_SCHEMAS]
        self.assertIn("get_price_history", names)

    def test_stock_data_separates_quote_and_fundamental_freshness(self):
        with patch.object(tools.yf, "Ticker", return_value=FakeStockTicker()):
            result = tools._fetch_single("EXM.AX")
        self.assertIn("T", result["source_market_timestamp"])
        self.assertIn("T", result["fundamentals_most_recent_quarter"])
        self.assertIn("T", result["last_fiscal_year_end"])
        self.assertFalse(result["is_guaranteed_realtime"])


if __name__ == "__main__":
    unittest.main()
