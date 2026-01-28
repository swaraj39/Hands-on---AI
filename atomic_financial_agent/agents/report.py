# report.py
# Generates final report text and saves to SQLite.

from datetime import datetime
from .base import AtomicAgent


class ReportAgent(AtomicAgent):
    """
    Generates a final text report and stores it in SQLite.
    """

    def execute(self, conn, context):
        print("📝 Generating report...")

        # Header for report
        report = (
            "AGENTIC AI FINANCIAL ADVISOR REPORT\n"
            f"Run ID: {context['run_id']}\n"
            f"Generated: {datetime.now()}\n\n"
        )

        # Build report for each ticker
        for ticker, s in context["strategies"].items():
            report += (
                f"Ticker: {ticker}\n"
                f"Short Term: {s['short_term']}\n"
                f"Long Term: {s['long_term']}\n"
                f"Confidence: {float(s['confidence']):.2f}\n"
                f"Reason: {s['reason']}\n"
                f"{'-'*40}\n"
            )

        # Save report to SQLite
        conn.execute("CREATE TABLE IF NOT EXISTS report (text TEXT)")
        conn.execute("DELETE FROM report")
        conn.execute("INSERT INTO report VALUES (?)", (report,))

        # Save report to context
        context["report"] = report
