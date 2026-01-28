# strategy.py
# Calls local LLM server to generate buy/sell/hold strategies.
# Uses retry + fallback logic to prevent crashes.

import requests
import json
import re
import uuid
import pandas as pd
from .base import AtomicAgent
import time


def safe_json_parse(text):
    """
    Parse JSON safely from LLM output.

    If parsing fails, returns a safe fallback object.
    """
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON found")
        return json.loads(match.group())

    except Exception:
        return {
            "short_term": "Hold",
            "long_term": "Hold",
            "confidence": 0.0,
            "reason": "LLM output parsing failed"
        }


class StrategyAgent(AtomicAgent):
    """
    Strategy Agent calls the LLM server to generate Buy/Sell/Hold strategies.

    This agent:
    1. Loads technical analysis data from DB
    2. Loads risk analysis data from DB
    3. Builds prompt for each ticker
    4. Calls local LLM API with retry logic
    5. Parses LLM response safely
    6. Stores strategy into context
    """

    def execute(self, conn, context):
        print("🤖 Generating strategies using LLM...")

        # Read technical analysis results from SQLite
        tech = pd.read_sql("SELECT * FROM technical_analysis", conn)

        # Read risk analysis results from SQLite
        risk = pd.read_sql("SELECT * FROM risk_analysis", conn)

        strategies = {}
        run_id = str(uuid.uuid4())  # Unique run id

        # Loop through each ticker
        for ticker in context["tickers"]:
            t = tech[tech["Ticker"] == ticker].iloc[-1]
            r = risk[risk["Ticker"] == ticker].iloc[0]

            # Build prompt using latest indicators
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

            # Retry logic
            raw_text = ""
            success = False

            # Try 3 times to call LLM
            for attempt in range(3):
                try:
                    response = requests.post(
                        "http://localhost:11434/api/generate",
                        json={
                            "model": "llama3",
                            "prompt": prompt,
                            "stream": False,
                            "options": {"temperature": 0.7}
                        },
                        timeout=180  # increased timeout
                    )

                    raw_text = response.json().get("response", "")
                    success = True
                    break

                except Exception as e:
                    print(f"❌ Attempt {attempt + 1}/3 failed: {e}")
                    time.sleep(5)

            # Fallback if LLM fails
            if not success:
                print("⚠️ LLM not reachable. Using fallback strategy.")
                strategies[ticker] = safe_json_parse("")
                continue

            print(f"\n🧠 RAW LLM OUTPUT ({ticker}):\n{raw_text}\n")

            # Parse output safely
            strategies[ticker] = safe_json_parse(raw_text)

        # Save into context
        context["strategies"] = strategies
        context["run_id"] = run_id
