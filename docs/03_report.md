# report.py — The Printer (PDF Report Generation)

This file generates professional PDF research reports using **ReportLab**. It's used in two contexts: directly by `tools.py`'s `generate_report` tool, and as a standalone pipeline stage.

---

## Architecture Diagram

```
  Input Data                      report.py
  +----------------+              +----------------------------------+
  | ranked_df      |              |                                  |
  | (DataFrame     +------------->|  generate_report()               |
  |  with stocks)  |              |                                  |
  +----------------+              |  1. Setup document (A4, margins) |
  +----------------+              |  2. Define custom styles         |
  | news           |              |  3. Build story[] elements:      |
  | (dict of       +------------->|                                  |
  |  headlines)    |              |     +------------------------+   |
  +----------------+              |     | Title Page             |   |
                                  |     | "ASX Investment        |   |
                                  |     |  Research Report"      |   |
                                  |     +------------------------+   |
                                  |     | Executive Summary      |   |
                                  |     | "Analyses N stocks     |   |
                                  |     |  using multi-factor    |   |
                                  |     |  scoring model..."     |   |
                                  |     +------------------------+   |
                                  |     | Rankings Table         |   |
                                  |     | #  Ticker  Price  P/E  |   |
                                  |     | 1  BHP     $43   11.2  |   |
                                  |     | 2  FMG     $19    8.5  |   |
                                  |     +------------------------+   |
                                  |     | Stock Profiles         |   |
                                  |     | For each stock:        |   |
                                  |     |  - Metrics table       |   |
                                  |     |  - Recent headlines    |   |
                                  |     +------------------------+   |
                                  |     | Disclaimer             |   |
                                  |     +------------------------+   |
                                  |                                  |
                                  |  4. doc.build(story)             |
                                  |                                  |
                                  +----------------+-----------------+
                                                   |
                                                   v
                                  +----------------------------------+
                                  |  asx_research_report_            |
                                  |  20260329_143022.pdf             |
                                  +----------------------------------+
```

---

## PDF Structure

The generated report has these sections:

### 1. Title Page
- Report title (customisable or default "ASX Investment Research Report")
- Strategy label (growth/value/dividend/balanced)
- Generation timestamp
- Horizontal rule separator

### 2. Executive Summary
- How many stocks were analysed
- Which strategy was used
- Top-ranked stock name and composite score

### 3. Rankings Table
A formatted table with columns:
| # | Ticker | Name | Sector | Price | P/E | ROE | Div Yield | Score |

Styled with:
- Dark navy header row
- Alternating white/grey row backgrounds
- Right-aligned numeric columns

### 4. Individual Stock Profiles
For each top stock:
- **Metrics mini-table**: Price, Market Cap, P/E, Forward P/E, ROE, ROA, Revenue Growth, Earnings Growth, Dividend Yield, D/E, Beta, Sentiment
- **Recent news**: Up to 3 headlines in italics

### 5. Disclaimer
Standard "not financial advice" boilerplate.

---

## Key Dependencies

- **reportlab**: PDF generation library (SimpleDocTemplate, Paragraph, Table, etc.)
- **pandas**: DataFrames for stock data
- **config.py**: Imports `PREFERENCES`, `REPORT_TOP_N`, `REPORT_OUTPUT_DIR` (used in standalone mode)

---

## Custom Styles

| Style Name | Usage | Appearance |
|---|---|---|
| `ReportTitle` | Main title | 22pt, dark navy |
| `ReportSubtitle` | Strategy + date | 11pt, grey, centered |
| `SectionHeader` | Section headings | 14pt, dark blue |
| `StockName` | Individual stock headers | 12pt, medium blue |
| `BodyText2` | Paragraph text / news | 9pt, dark grey |

---

## Two Usage Contexts

### 1. Called by `tools.py` (agent mode)
`tools.py` has its own inline report generation in `tool_generate_report()` that duplicates much of this logic. This is because the tool version fetches data itself and builds the PDF directly.

### 2. Standalone pipeline (line 231)
```python
if __name__ == "__main__":
    # runs: ingest -> analyse -> compare -> report
```
This references `config.py`, `ingest.py`, `analyse.py`, and `compare.py` — modules for a broader pipeline that isn't part of the agent workflow.
