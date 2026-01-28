# ===========================================
# AGENTIC AI FINANCIAL ADVISOR (FINAL SAFE)
# ===========================================

import sqlite3
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import json
import re
from datetime import datetime, timedelta
import uuid


# ===========================
# Base Agent
# ===========================
class AtomicAgent:
    """
    Base class for all agents.
    Every agent must implement the execute() method.
    """
    def execute(self, conn, context):
        raise NotImplementedError


# ===========================
# Market Data Agent
# ===========================
class MarketDataAgent(AtomicAgent):
    """
    Fetches historical stock price data using yfinance.
    Stores the data in SQLite table: market_data.
    """
    def execute(self, conn, context):
        print("📥 Fetching market data...")

        # Download data for tickers over the date range
        data = yf.download(
            context["tickers"],
            start=context["start_date"],
            end=context["end_date"],
            auto_adjust=True,
            progress=False
        )

        # yfinance returns MultiIndex columns when multiple tickers are used.
        # Convert them to a flat column name like "Close_AAPL".
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [f"{c[0]}_{c[1]}" for c in data.columns]

        # Store the dataframe into SQLite table
        data.reset_index().to_sql(
            "market_data",
            conn,
            if_exists="replace",
            index=False
        )


# ===========================
# Technical Analysis Agent
# ===========================
class TechnicalAnalysisAgent(AtomicAgent):
    """
    Computes technical indicators:
    - SMA 20 & SMA 50
    - RSI
    - Rolling volatility
    Saves results into SQLite table: technical_analysis.
    """
    def execute(self, conn, context):
        print("📊 Running technical analysis...")

        df = pd.read_sql("SELECT * FROM market_data", conn)
        out = []

        for ticker in context["tickers"]:
            close_col = f"Close_{ticker}"
            temp = df[["Date", close_col]].copy()

            # Simple Moving Averages
            temp["SMA_20"] = temp[close_col].rolling(20).mean()
            temp["SMA_50"] = temp[close_col].rolling(50).mean()

            # RSI
            temp["RSI"] = self.rsi(temp[close_col])

            # Rolling volatility over 20 days
            temp["Volatility"] = temp[close_col].pct_change().rolling(20).std()

            # Add ticker column to identify which stock row belongs to
            temp["Ticker"] = ticker

            out.append(temp)

        # Combine all ticker data and save to SQLite
        pd.concat(out).to_sql(
            "technical_analysis",
            conn,
            if_exists="replace",
            index=False
        )

    def rsi(self, series, period=14):
        """
        Calculates Relative Strength Index (RSI).
        RSI indicates overbought/oversold conditions.
        """
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        rs = gain.rolling(period).mean() / loss.rolling(period).mean()
        return 100 - (100 / (1 + rs))


# ===========================
# Risk Analysis Agent
# ===========================
class RiskAnalysisAgent(AtomicAgent):
    """
    Computes risk metrics:
    - Annual volatility (standard deviation scaled to 252 trading days)
    - Maximum drawdown (largest peak-to-trough drop)
    Saves results into SQLite table: risk_analysis.
    """
    def execute(self, conn, context):
        print("⚠️ Running risk analysis...")

        df = pd.read_sql("SELECT * FROM technical_analysis", conn)
        risks = []

        for ticker in context["tickers"]:
            temp = df[df["Ticker"] == ticker]
            price = temp.iloc[:, 1]
            returns = price.pct_change()

            risks.append({
                "Ticker": ticker,
                "Annual_Volatility": returns.std() * np.sqrt(252),
                "Max_Drawdown": (price / price.cummax() - 1).min()
            })

        pd.DataFrame(risks).to_sql(
            "risk_analysis",
            conn,
            if_exists="replace",
            index=False
        )


# ===========================
# SAFE JSON PARSER
# ===========================
def safe_json_parse(text):
    """
    Parses JSON safely from LLM output.
    If parsing fails, returns a safe fallback strategy.
    """
    try:
        # Extract JSON object from text using regex
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON found")

        return json.loads(match.group())

    except Exception:
        print("⚠️ Invalid LLM output detected. Using fallback.")
        return {
            "short_term": "Hold",
            "long_term": "Hold",
            "confidence": 0.0,
            "reason": "LLM output parsing failed"
        }


# ===========================
# Strategy Agent (LLM)
# ===========================
class StrategyAgent(AtomicAgent):
    """
    Calls an LLM (local API) to generate Buy/Sell/Hold strategies.
    Stores strategies in context.
    """
    def execute(self, conn, context):
        print("🤖 Generating strategies using LLM...")

        tech = pd.read_sql("SELECT * FROM technical_analysis", conn)
        risk = pd.read_sql("SELECT * FROM risk_analysis", conn)

        strategies = {}
        run_id = str(uuid.uuid4())

        for ticker in context["tickers"]:
            # Get latest technical and risk data
            t = tech[tech["Ticker"] == ticker].iloc[-1]
            r = risk[risk["Ticker"] == ticker].iloc[0]

            # Build prompt for LLM
            prompt = f"""
You are a cautious professional financial advisor.

Ticker: {ticker}
Price: {t.iloc[1]}
SMA20: {t['SMA_20']}
SMA50: {t['SMA_50']}
RSI: {t['RSI']}
Volatility: {t['Volatility']}
Annual Risk: {r['Annual_Volatility']}
Max Drawdown: {r['Max_Drawdown']}

Return ONLY a valid JSON object.
No markdown. No explanations.

{{
  "short_term": "Buy | Sell | Hold",
  "long_term": "Buy | Sell | Hold",
  "confidence": 0.0,
  "reason": "one sentence explanation"
}}
"""

            # Call LLM API (local Ollama server)
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7}
                },
                timeout=60
            )

            raw_text = response.json().get("response", "")
            print(f"\n🧠 RAW LLM OUTPUT ({ticker}):\n{raw_text}\n")

            # Parse the output safely
            strategies[ticker] = safe_json_parse(raw_text)

        # Save results to context for report generation
        context["strategies"] = strategies
        context["run_id"] = run_id


# ===========================
# Report Agent
# ===========================
class ReportAgent(AtomicAgent):
    """
    Generates a final text report and stores it in SQLite.
    """
    def execute(self, conn, context):
        print("📝 Generating report...")

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

        context["report"] = report


# ===========================
# Orchestrator
# ===========================
class FinancialAdvisorOrchestrator:
    """
    Controls the execution order of agents.
    """
    def __init__(self):
        self.agents = [
            MarketDataAgent(),
            TechnicalAnalysisAgent(),
            RiskAnalysisAgent(),
            StrategyAgent(),
            ReportAgent()
        ]

    def run(self, context):
        conn = sqlite3.connect("advisor.db")
        try:
            for agent in self.agents:
                agent.execute(conn, context)
            conn.commit()
            print("✅ Pipeline completed successfully")
        except Exception as e:
            conn.rollback()
            print("❌ Pipeline failed:", e)
        finally:
            conn.close()


# ===========================
# Entry Point
# ===========================
if __name__ == "__main__":
    # Context contains configuration values for the pipeline
    context = {
        "tickers": ["AAPL", "MSFT", "NVDA", "TSLA"],
        "start_date": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d")
    }

    advisor = FinancialAdvisorOrchestrator()
    advisor.run(context)

    print("\n========== FINAL REPORT ==========\n")
    print(context["report"])
