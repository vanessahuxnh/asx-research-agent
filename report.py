"""
Stage 4: Report Generation
Produces a structured PDF research summary report.
"""

import os
from datetime import datetime
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER

from config import PREFERENCES, REPORT_TOP_N, REPORT_OUTPUT_DIR


def _fmt(val, fmt_type="str"):
    """Safe formatting helper."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    if fmt_type == "pct":
        return f"{val:.1%}"
    if fmt_type == "price":
        return f"${val:,.2f}"
    if fmt_type == "cap":
        if val >= 1e9:
            return f"${val / 1e9:,.1f}B"
        return f"${val / 1e6:,.0f}M"
    if fmt_type == "score":
        return f"{val:.3f}"
    if fmt_type == "ratio":
        return f"{val:.1f}"
    return str(val)


def generate_report(
    ranked_df: pd.DataFrame,
    news: dict,
    output_path: str | None = None,
) -> str:
    """
    Generate a PDF research report for the top-ranked stocks.
    Returns the output file path.
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(REPORT_OUTPUT_DIR, f"asx_research_report_{timestamp}.pdf")

    # The output directory may not exist yet on a fresh checkout.
    parent = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(parent, exist_ok=True)

    top = ranked_df.head(REPORT_TOP_N).copy()
    strategy = PREFERENCES.get("strategy", "balanced").title()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        "ReportTitle", parent=styles["Title"],
        fontSize=22, spaceAfter=6, textColor=colors.HexColor("#1a1a2e"),
    ))
    styles.add(ParagraphStyle(
        "ReportSubtitle", parent=styles["Normal"],
        fontSize=11, textColor=colors.HexColor("#666666"),
        alignment=TA_CENTER, spaceAfter=20,
    ))
    styles.add(ParagraphStyle(
        "SectionHeader", parent=styles["Heading2"],
        fontSize=14, textColor=colors.HexColor("#16213e"),
        spaceBefore=16, spaceAfter=8,
        borderWidth=0, borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        "StockName", parent=styles["Heading3"],
        fontSize=12, textColor=colors.HexColor("#0f3460"),
        spaceBefore=12, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "BodyText2", parent=styles["Normal"],
        fontSize=9, leading=13, textColor=colors.HexColor("#333333"),
    ))

    story = []

    # ── Title Page ──
    story.append(Spacer(1, 40))
    story.append(Paragraph("ASX Investment Research Report", styles["ReportTitle"]))
    story.append(Paragraph(
        f"Strategy: {strategy} &nbsp;|&nbsp; Generated: {datetime.now().strftime('%d %B %Y %H:%M')}",
        styles["ReportSubtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 12))

    # ── Executive Summary ──
    story.append(Paragraph("Executive Summary", styles["SectionHeader"]))
    n_analysed = len(ranked_df)
    n_shown = len(top)
    best = top.iloc[0] if len(top) > 0 else None
    summary_text = (
        f"This report analyses {n_analysed} ASX-listed equities using a multi-factor "
        f"scoring model aligned to a <b>{strategy}</b> investment strategy. "
        f"Factors include revenue growth, earnings growth, return on equity, "
        f"relative P/E valuation, dividend yield, leverage (D/E), and news sentiment. "
    )
    if best is not None:
        summary_text += (
            f"The top-ranked stock is <b>{best.get('name', best['ticker'])}</b> "
            f"({best['ticker']}) with a composite score of {_fmt(best['composite_score'], 'score')}."
        )
    story.append(Paragraph(summary_text, styles["BodyText2"]))
    story.append(Spacer(1, 12))

    # ── Rankings Table ──
    story.append(Paragraph("Top Stock Rankings", styles["SectionHeader"]))

    table_data = [["#", "Ticker", "Name", "Sector", "Price", "P/E", "ROE", "Div Yld", "Score"]]
    for _, row in top.iterrows():
        table_data.append([
            str(int(row["rank"])),
            row["ticker"].replace(".AX", ""),
            str(row["name"])[:20],
            str(row.get("sector", "N/A"))[:15],
            _fmt(row.get("current_price"), "price"),
            _fmt(row.get("pe_ratio"), "ratio"),
            _fmt(row.get("roe"), "pct"),
            _fmt(row.get("dividend_yield"), "pct"),
            _fmt(row.get("composite_score"), "score"),
        ])

    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

    # ── Individual Stock Profiles ──
    story.append(Paragraph("Individual Stock Profiles", styles["SectionHeader"]))

    for _, row in top.iterrows():
        ticker = row["ticker"]
        name = row.get("name", ticker)

        story.append(Paragraph(
            f"#{int(row['rank'])} — {name} ({ticker.replace('.AX', '')})",
            styles["StockName"],
        ))

        # Key metrics as mini-table
        metrics = [
            ["Price", _fmt(row.get("current_price"), "price"),
             "Market Cap", _fmt(row.get("market_cap"), "cap")],
            ["P/E", _fmt(row.get("pe_ratio"), "ratio"),
             "Fwd P/E", _fmt(row.get("forward_pe"), "ratio")],
            ["ROE", _fmt(row.get("roe"), "pct"),
             "ROA", _fmt(row.get("roa"), "pct")],
            ["Rev Growth", _fmt(row.get("revenue_growth"), "pct"),
             "Earn Growth", _fmt(row.get("earnings_growth"), "pct")],
            ["Div Yield", _fmt(row.get("dividend_yield"), "pct"),
             "D/E", _fmt(row.get("debt_to_equity"), "ratio")],
            ["Beta", _fmt(row.get("beta"), "ratio"),
             "Sentiment", _fmt(row.get("news_sentiment"), "score")],
        ]

        mt = Table(metrics, colWidths=[70, 80, 70, 80])
        mt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#888888")),
            ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#888888")),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(mt)

        # News headlines
        stock_news = news.get(ticker, [])
        if stock_news:
            headlines = "; ".join(
                [n.get("title", "")[:80] for n in stock_news[:3] if n.get("title")]
            )
            if headlines:
                story.append(Paragraph(
                    f"<i>Recent news: {headlines}</i>", styles["BodyText2"]
                ))

        story.append(Spacer(1, 8))

    # ── Disclaimer ──
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<i>Disclaimer: This report is generated by an automated research agent for informational "
        "purposes only. It does not constitute financial advice. Past performance is not indicative "
        "of future results. Always consult a qualified financial advisor before making investment "
        "decisions.</i>",
        ParagraphStyle("Disclaimer", parent=styles["Normal"], fontSize=7, textColor=colors.grey),
    ))

    # Build
    doc.build(story)
    return output_path


if __name__ == "__main__":
    # Standalone smoke test using the bundled sample data.
    # (The original pipeline modules — ingest/analyse/compare — are not part of
    # this project; the agent supplies the ranked DataFrame at runtime instead.)
    from sample_data import get_sample_dataframe, get_sample_news

    print("Generating a sample report...\n")
    df = get_sample_dataframe()
    news_data = get_sample_news()

    # Stand-in for the scoring stage the agent normally performs.
    df["news_sentiment"] = 0.5
    df["composite_score"] = 0.5
    df["rank"] = range(1, len(df) + 1)

    path = generate_report(df, news_data)
    print(f"\n📄 Report saved to: {path}")
