# ===========================================
# ATOMIC AGENT FINANCIAL ADVISOR (OLLAMA)
# ===========================================

import sqlite3
import pandas as pd
import yfinance as yf
import requests
import json
from datetime import datetime, timedelta
import uuid


# ---------------------------
# Base Agent
# ---------------------------
class AtomicAgent:
    def execute(self, conn, context):
        raise NotImplementedError


# ---------------------------
# Market Data Agent
# ---------------------------
class MarketDataAgent(AtomicAgent):
    def execute(self, conn, context):
        data = yf.download(
            context["tickers"],
            start=context["start_date"],
            end=context["end_date"]
        )

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [f"{c[0]}_{c[1]}" for c in data.columns]

        data.reset_index().to_sql(
            "market_data",
            conn,
            if_exists="replace",
            index=False
        )


# ---------------------------
# Market Analysis Agent
# ---------------------------
class MarketAnalysisAgent(AtomicAgent):
    def execute(self, conn, context):
        df = pd.read_sql("SELECT * FROM market_data", conn)
        out = []

        for ticker in context["tickers"]:
            close_col = f"Close_{ticker}"
            temp = df[[close_col]].copy()

            temp["SMA_20"] = temp[close_col].rolling(20).mean()
            temp["SMA_50"] = temp[close_col].rolling(50).mean()
            temp["Volatility"] = temp[close_col].pct_change().rolling(20).std()
            temp["Ticker"] = ticker

            out.append(temp)

        pd.concat(out).to_sql("analysis", conn, if_exists="replace", index=False)


# ---------------------------
# Ollama Strategy Agent
# ---------------------------
class OllamaStrategyAgent(AtomicAgent):
    def execute(self, conn, context):
        df = pd.read_sql("SELECT * FROM analysis", conn)
        strategies = {}

        run_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        for ticker in context["tickers"]:
            latest = df[df["Ticker"] == ticker].iloc[-1]
            close_col = f"Close_{ticker}"

            prompt = f"""
You are a cautious financial analyst.

Run ID: {run_id}
Timestamp: {timestamp}

Ticker: {ticker}
Price: {latest[close_col]}
SMA 20: {latest['SMA_20']}
SMA 50: {latest['SMA_50']}
Volatility: {latest['Volatility']}

Return JSON only:
{{
  "short_term": "Buy | Sell | Hold",
  "long_term": "Buy | Sell | Hold",
  "confidence": "0.0 to 1.0",
  "reason": "one sentence explanation"
}}
"""

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.9,
                        "top_p": 0.9
                    }
                },
                timeout=60
            )

            # Debug print (optional)
            # print("LLM Response:", response.json())

            strategies[ticker] = json.loads(response.json()["response"])

        context["strategies"] = strategies
        context["run_id"] = run_id


# ---------------------------
# Report Agent
# ---------------------------
class ReportAgent(AtomicAgent):
    def execute(self, conn, context):
        report = "LLM FINANCIAL ADVISOR REPORT\n"
        report += f"Run ID: {context['run_id']}\n"
        report += f"Generated: {datetime.now()}\n\n"

        for ticker, s in context["strategies"].items():
            report += f"Ticker: {ticker}\n"
            report += f"Short-term: {s['short_term']}\n"
            report += f"Long-term: {s['long_term']}\n"
            report += f"Confidence: {float(s['confidence']):.2f}\n"
            report += f"Reason: {s['reason']}\n"
            report += "-" * 35 + "\n"

        conn.execute("CREATE TABLE IF NOT EXISTS report (text TEXT)")
        conn.execute("DELETE FROM report")
        conn.execute("INSERT INTO report VALUES (?)", (report,))
        context["report_text"] = report


# ---------------------------
# Orchestrator
# ---------------------------
class FinancialAdvisorOrchestrator:
    def __init__(self):
        self.agents = [
            MarketDataAgent(),
            MarketAnalysisAgent(),
            OllamaStrategyAgent(),
            ReportAgent()
        ]

    def run(self, context):
        conn = sqlite3.connect("advisor.db")

        try:
            conn.execute("BEGIN")
            for agent in self.agents:
                agent.execute(conn, context)
            conn.commit()
            print("✅ Pipeline finished")

        except Exception as e:
            conn.rollback()
            print("❌ Error:", e)

        finally:
            conn.close()


# ---------------------------
# Entry Point
# ---------------------------
if __name__ == "__main__":
    context = {
        "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"],
        "start_date": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d")
    }

    orchestrator = FinancialAdvisorOrchestrator()
    orchestrator.run(context)

    conn = sqlite3.connect("advisor.db")
    print("\n========== REPORT ==========\n")
    print(conn.execute("SELECT text FROM report").fetchone()[0])
    conn.close()
