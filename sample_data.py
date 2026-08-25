"""
Sample ASX data for demo/testing when yfinance API is unavailable.
Replace with live data by running: python ingest.py
"""

import pandas as pd

SAMPLE_STOCKS = [
    {"ticker": "BHP.AX", "name": "BHP Group Limited", "sector": "Basic Materials", "industry": "Mining", "market_cap": 228e9, "current_price": 43.50, "pe_ratio": 11.2, "forward_pe": 10.5, "pb_ratio": 2.8, "dividend_yield": 0.052, "roe": 0.31, "roa": 0.14, "debt_to_equity": 42.5, "revenue": 53.8e9, "revenue_growth": 0.08, "earnings_growth": 0.12, "profit_margin": 0.27, "operating_margin": 0.35, "beta": 1.1, "52w_high": 48.2, "52w_low": 38.1, "avg_volume": 12500000, "return_1y": 0.09, "return_6m": 0.04},
    {"ticker": "CBA.AX", "name": "Commonwealth Bank", "sector": "Financial Services", "industry": "Banks", "market_cap": 215e9, "current_price": 128.50, "pe_ratio": 21.5, "forward_pe": 19.8, "pb_ratio": 3.1, "dividend_yield": 0.034, "roe": 0.14, "roa": 0.009, "debt_to_equity": 320.0, "revenue": 26.5e9, "revenue_growth": 0.05, "earnings_growth": 0.07, "profit_margin": 0.38, "operating_margin": 0.42, "beta": 0.85, "52w_high": 135.0, "52w_low": 98.0, "avg_volume": 3200000, "return_1y": 0.22, "return_6m": 0.11},
    {"ticker": "CSL.AX", "name": "CSL Limited", "sector": "Healthcare", "industry": "Biotechnology", "market_cap": 135e9, "current_price": 280.00, "pe_ratio": 35.2, "forward_pe": 28.5, "pb_ratio": 9.5, "dividend_yield": 0.011, "roe": 0.22, "roa": 0.08, "debt_to_equity": 85.0, "revenue": 14.8e9, "revenue_growth": 0.11, "earnings_growth": 0.18, "profit_margin": 0.22, "operating_margin": 0.28, "beta": 0.65, "52w_high": 310.0, "52w_low": 240.0, "avg_volume": 1500000, "return_1y": 0.15, "return_6m": 0.08},
    {"ticker": "NAB.AX", "name": "National Australia Bank", "sector": "Financial Services", "industry": "Banks", "market_cap": 108e9, "current_price": 38.20, "pe_ratio": 15.8, "forward_pe": 14.5, "pb_ratio": 1.9, "dividend_yield": 0.044, "roe": 0.12, "roa": 0.008, "debt_to_equity": 290.0, "revenue": 20.1e9, "revenue_growth": 0.03, "earnings_growth": 0.04, "profit_margin": 0.33, "operating_margin": 0.38, "beta": 0.95, "52w_high": 40.5, "52w_low": 28.0, "avg_volume": 8500000, "return_1y": 0.18, "return_6m": 0.06},
    {"ticker": "WBC.AX", "name": "Westpac Banking Corp", "sector": "Financial Services", "industry": "Banks", "market_cap": 95e9, "current_price": 28.50, "pe_ratio": 14.2, "forward_pe": 13.5, "pb_ratio": 1.7, "dividend_yield": 0.048, "roe": 0.11, "roa": 0.007, "debt_to_equity": 310.0, "revenue": 21.3e9, "revenue_growth": 0.04, "earnings_growth": 0.06, "profit_margin": 0.30, "operating_margin": 0.35, "beta": 1.0, "52w_high": 30.5, "52w_low": 21.0, "avg_volume": 9000000, "return_1y": 0.20, "return_6m": 0.07},
    {"ticker": "ANZ.AX", "name": "ANZ Group Holdings", "sector": "Financial Services", "industry": "Banks", "market_cap": 88e9, "current_price": 29.80, "pe_ratio": 13.5, "forward_pe": 12.8, "pb_ratio": 1.5, "dividend_yield": 0.052, "roe": 0.10, "roa": 0.006, "debt_to_equity": 340.0, "revenue": 19.2e9, "revenue_growth": 0.02, "earnings_growth": 0.03, "profit_margin": 0.28, "operating_margin": 0.33, "beta": 1.05, "52w_high": 31.0, "52w_low": 23.5, "avg_volume": 7800000, "return_1y": 0.15, "return_6m": 0.05},
    {"ticker": "FMG.AX", "name": "Fortescue Ltd", "sector": "Basic Materials", "industry": "Mining", "market_cap": 72e9, "current_price": 18.90, "pe_ratio": 8.5, "forward_pe": 9.2, "pb_ratio": 3.5, "dividend_yield": 0.082, "roe": 0.38, "roa": 0.22, "debt_to_equity": 55.0, "revenue": 18.2e9, "revenue_growth": 0.15, "earnings_growth": 0.22, "profit_margin": 0.32, "operating_margin": 0.45, "beta": 1.3, "52w_high": 25.0, "52w_low": 14.5, "avg_volume": 15000000, "return_1y": 0.05, "return_6m": -0.08},
    {"ticker": "WES.AX", "name": "Wesfarmers Limited", "sector": "Consumer Cyclical", "industry": "Retail", "market_cap": 82e9, "current_price": 72.30, "pe_ratio": 30.5, "forward_pe": 27.0, "pb_ratio": 7.2, "dividend_yield": 0.028, "roe": 0.25, "roa": 0.10, "debt_to_equity": 50.0, "revenue": 44.0e9, "revenue_growth": 0.06, "earnings_growth": 0.09, "profit_margin": 0.06, "operating_margin": 0.10, "beta": 0.75, "52w_high": 78.0, "52w_low": 55.0, "avg_volume": 2000000, "return_1y": 0.25, "return_6m": 0.12},
    {"ticker": "MQG.AX", "name": "Macquarie Group Ltd", "sector": "Financial Services", "industry": "Capital Markets", "market_cap": 78e9, "current_price": 205.00, "pe_ratio": 18.5, "forward_pe": 16.0, "pb_ratio": 2.5, "dividend_yield": 0.032, "roe": 0.15, "roa": 0.012, "debt_to_equity": 450.0, "revenue": 17.5e9, "revenue_growth": 0.12, "earnings_growth": 0.15, "profit_margin": 0.25, "operating_margin": 0.30, "beta": 1.15, "52w_high": 220.0, "52w_low": 160.0, "avg_volume": 900000, "return_1y": 0.18, "return_6m": 0.10},
    {"ticker": "WOW.AX", "name": "Woolworths Group Ltd", "sector": "Consumer Defensive", "industry": "Grocery Stores", "market_cap": 42e9, "current_price": 33.50, "pe_ratio": 25.0, "forward_pe": 22.0, "pb_ratio": 4.8, "dividend_yield": 0.030, "roe": 0.18, "roa": 0.05, "debt_to_equity": 120.0, "revenue": 65.0e9, "revenue_growth": 0.04, "earnings_growth": 0.05, "profit_margin": 0.025, "operating_margin": 0.04, "beta": 0.55, "52w_high": 38.0, "52w_low": 30.0, "avg_volume": 4500000, "return_1y": 0.08, "return_6m": 0.03},
    {"ticker": "TLS.AX", "name": "Telstra Group Ltd", "sector": "Communication Services", "industry": "Telecom", "market_cap": 48e9, "current_price": 4.05, "pe_ratio": 22.0, "forward_pe": 20.0, "pb_ratio": 3.0, "dividend_yield": 0.042, "roe": 0.13, "roa": 0.04, "debt_to_equity": 150.0, "revenue": 23.0e9, "revenue_growth": 0.03, "earnings_growth": 0.06, "profit_margin": 0.12, "operating_margin": 0.20, "beta": 0.45, "52w_high": 4.30, "52w_low": 3.50, "avg_volume": 20000000, "return_1y": 0.10, "return_6m": 0.04},
    {"ticker": "RIO.AX", "name": "Rio Tinto Limited", "sector": "Basic Materials", "industry": "Mining", "market_cap": 42e9, "current_price": 115.00, "pe_ratio": 9.8, "forward_pe": 10.2, "pb_ratio": 2.2, "dividend_yield": 0.058, "roe": 0.24, "roa": 0.12, "debt_to_equity": 40.0, "revenue": 54.0e9, "revenue_growth": 0.06, "earnings_growth": 0.10, "profit_margin": 0.22, "operating_margin": 0.32, "beta": 1.05, "52w_high": 130.0, "52w_low": 100.0, "avg_volume": 2500000, "return_1y": 0.07, "return_6m": 0.02},
    {"ticker": "GMG.AX", "name": "Goodman Group", "sector": "Real Estate", "industry": "REIT", "market_cap": 65e9, "current_price": 35.50, "pe_ratio": 38.0, "forward_pe": 30.0, "pb_ratio": 5.5, "dividend_yield": 0.010, "roe": 0.15, "roa": 0.06, "debt_to_equity": 25.0, "revenue": 2.8e9, "revenue_growth": 0.22, "earnings_growth": 0.28, "profit_margin": 0.55, "operating_margin": 0.60, "beta": 0.90, "52w_high": 38.0, "52w_low": 22.0, "avg_volume": 3500000, "return_1y": 0.45, "return_6m": 0.18},
    {"ticker": "XRO.AX", "name": "Xero Limited", "sector": "Technology", "industry": "Software", "market_cap": 25e9, "current_price": 165.00, "pe_ratio": 120.0, "forward_pe": 55.0, "pb_ratio": 18.0, "dividend_yield": 0.0, "roe": 0.08, "roa": 0.04, "debt_to_equity": 30.0, "revenue": 1.9e9, "revenue_growth": 0.25, "earnings_growth": 0.85, "profit_margin": 0.12, "operating_margin": 0.18, "beta": 1.4, "52w_high": 175.0, "52w_low": 95.0, "avg_volume": 800000, "return_1y": 0.55, "return_6m": 0.22},
    {"ticker": "REA.AX", "name": "REA Group Ltd", "sector": "Technology", "industry": "Internet Content", "market_cap": 28e9, "current_price": 210.00, "pe_ratio": 55.0, "forward_pe": 42.0, "pb_ratio": 15.0, "dividend_yield": 0.010, "roe": 0.28, "roa": 0.10, "debt_to_equity": 45.0, "revenue": 1.5e9, "revenue_growth": 0.18, "earnings_growth": 0.20, "profit_margin": 0.35, "operating_margin": 0.45, "beta": 1.1, "52w_high": 225.0, "52w_low": 155.0, "avg_volume": 500000, "return_1y": 0.30, "return_6m": 0.14},
    {"ticker": "PME.AX", "name": "Pro Medicus Limited", "sector": "Healthcare", "industry": "Health IT", "market_cap": 22e9, "current_price": 175.00, "pe_ratio": 160.0, "forward_pe": 100.0, "pb_ratio": 65.0, "dividend_yield": 0.003, "roe": 0.42, "roa": 0.35, "debt_to_equity": 5.0, "revenue": 0.18e9, "revenue_growth": 0.30, "earnings_growth": 0.35, "profit_margin": 0.55, "operating_margin": 0.62, "beta": 1.2, "52w_high": 190.0, "52w_low": 80.0, "avg_volume": 600000, "return_1y": 0.90, "return_6m": 0.30},
    {"ticker": "TCL.AX", "name": "Transurban Group", "sector": "Industrials", "industry": "Infrastructure", "market_cap": 45e9, "current_price": 13.20, "pe_ratio": 95.0, "forward_pe": 50.0, "pb_ratio": 3.8, "dividend_yield": 0.045, "roe": 0.04, "roa": 0.02, "debt_to_equity": 600.0, "revenue": 4.2e9, "revenue_growth": 0.07, "earnings_growth": 0.10, "profit_margin": 0.10, "operating_margin": 0.65, "beta": 0.50, "52w_high": 14.0, "52w_low": 11.5, "avg_volume": 6000000, "return_1y": 0.10, "return_6m": 0.05},
    {"ticker": "STO.AX", "name": "Santos Limited", "sector": "Energy", "industry": "Oil & Gas", "market_cap": 22e9, "current_price": 7.20, "pe_ratio": 12.5, "forward_pe": 11.0, "pb_ratio": 1.1, "dividend_yield": 0.038, "roe": 0.09, "roa": 0.04, "debt_to_equity": 55.0, "revenue": 5.8e9, "revenue_growth": -0.05, "earnings_growth": -0.08, "profit_margin": 0.18, "operating_margin": 0.30, "beta": 1.25, "52w_high": 8.5, "52w_low": 6.0, "avg_volume": 10000000, "return_1y": -0.05, "return_6m": -0.10},
    {"ticker": "COL.AX", "name": "Coles Group Limited", "sector": "Consumer Defensive", "industry": "Grocery Stores", "market_cap": 25e9, "current_price": 18.80, "pe_ratio": 28.0, "forward_pe": 24.0, "pb_ratio": 5.0, "dividend_yield": 0.035, "roe": 0.18, "roa": 0.04, "debt_to_equity": 180.0, "revenue": 43.0e9, "revenue_growth": 0.05, "earnings_growth": 0.08, "profit_margin": 0.02, "operating_margin": 0.04, "beta": 0.40, "52w_high": 20.0, "52w_low": 15.0, "avg_volume": 5000000, "return_1y": 0.15, "return_6m": 0.06},
    {"ticker": "QBE.AX", "name": "QBE Insurance Group", "sector": "Financial Services", "industry": "Insurance", "market_cap": 24e9, "current_price": 19.50, "pe_ratio": 10.0, "forward_pe": 9.5, "pb_ratio": 1.6, "dividend_yield": 0.040, "roe": 0.15, "roa": 0.03, "debt_to_equity": 70.0, "revenue": 20.5e9, "revenue_growth": 0.10, "earnings_growth": 0.25, "profit_margin": 0.08, "operating_margin": 0.12, "beta": 0.90, "52w_high": 21.0, "52w_low": 14.0, "avg_volume": 4000000, "return_1y": 0.28, "return_6m": 0.12},
]

SAMPLE_NEWS = {
    "BHP.AX": [
        {"title": "BHP reports record iron ore production, strong earnings beat expectations", "publisher": "AFR", "link": "", "date": "2026-03-28"},
        {"title": "BHP expansion plans boost growth outlook for mining giant", "publisher": "Reuters", "link": "", "date": "2026-03-27"},
    ],
    "CBA.AX": [
        {"title": "Commonwealth Bank profit margins under pressure from rate cut concerns", "publisher": "SMH", "link": "", "date": "2026-03-28"},
        {"title": "CBA digital banking innovation drives positive customer growth", "publisher": "AFR", "link": "", "date": "2026-03-27"},
    ],
    "CSL.AX": [
        {"title": "CSL plasma expansion delivers strong revenue growth momentum", "publisher": "Reuters", "link": "", "date": "2026-03-28"},
        {"title": "CSL innovation pipeline bullish on new immunoglobulin treatments", "publisher": "AFR", "link": "", "date": "2026-03-26"},
    ],
    "FMG.AX": [
        {"title": "Fortescue green energy bet faces risk as hydrogen costs surge", "publisher": "Bloomberg", "link": "", "date": "2026-03-28"},
        {"title": "FMG iron ore rally drives record dividend gains for investors", "publisher": "AFR", "link": "", "date": "2026-03-27"},
    ],
    "GMG.AX": [
        {"title": "Goodman Group data centre expansion fuels bullish growth rally", "publisher": "AFR", "link": "", "date": "2026-03-28"},
        {"title": "Goodman profit beats expectations with record development earnings", "publisher": "Reuters", "link": "", "date": "2026-03-27"},
    ],
    "XRO.AX": [
        {"title": "Xero subscriber growth exceeds forecast with strong momentum", "publisher": "Bloomberg", "link": "", "date": "2026-03-28"},
        {"title": "Xero earnings surge on cloud accounting expansion and innovation", "publisher": "AFR", "link": "", "date": "2026-03-26"},
    ],
    "PME.AX": [
        {"title": "Pro Medicus wins record US hospital contract, rally continues", "publisher": "AFR", "link": "", "date": "2026-03-28"},
        {"title": "PME AI imaging innovation positions it for strong outperformance", "publisher": "Reuters", "link": "", "date": "2026-03-27"},
    ],
    "QBE.AX": [
        {"title": "QBE Insurance profit surge as underwriting margins beat forecasts", "publisher": "AFR", "link": "", "date": "2026-03-28"},
        {"title": "QBE positive on premium growth outlook despite risk concerns", "publisher": "Bloomberg", "link": "", "date": "2026-03-27"},
    ],
    "STO.AX": [
        {"title": "Santos faces decline in oil prices, earnings miss weighs on outlook", "publisher": "Reuters", "link": "", "date": "2026-03-28"},
        {"title": "Santos Barossa project hit by lawsuit and investigation delays", "publisher": "AFR", "link": "", "date": "2026-03-27"},
    ],
    "REA.AX": [
        {"title": "REA Group property listings growth beats expectations with strong rally", "publisher": "AFR", "link": "", "date": "2026-03-28"},
    ],
}

# Add neutral/empty news for stocks without specific entries
for s in SAMPLE_STOCKS:
    if s["ticker"] not in SAMPLE_NEWS:
        SAMPLE_NEWS[s["ticker"]] = [
            {"title": f"{s['name']} delivers steady quarterly results", "publisher": "AFR", "link": "", "date": "2026-03-28"}
        ]


def get_sample_dataframe() -> pd.DataFrame:
    return pd.DataFrame(SAMPLE_STOCKS)


def get_sample_news() -> dict:
    return SAMPLE_NEWS
