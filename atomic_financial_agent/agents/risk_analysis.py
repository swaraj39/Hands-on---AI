# risk_analysis.py
# Computes risk metrics and stores them in SQLite.

import pandas as pd
import numpy as np
from .base import AtomicAgent


class RiskAnalysisAgent(AtomicAgent):
    """
    Computes risk metrics:
    - Annual volatility (standard deviation scaled to 252 trading days)
    - Maximum drawdown (largest peak-to-trough drop)
    Saves results into SQLite table: risk_analysis.
    """

    def execute(self, conn, context):
        print("⚠️ Running risk analysis...")

        # Read technical analysis results from SQLite
        df = pd.read_sql("SELECT * FROM technical_analysis", conn)

        risks = []

        # Loop through each ticker and compute risk metrics
        for ticker in context["tickers"]:
            temp = df[df["Ticker"] == ticker]
            price = temp.iloc[:, 1]  # price column
            returns = price.pct_change()

            risks.append({
                "Ticker": ticker,
                "Annual_Volatility": returns.std() * np.sqrt(252),
                "Max_Drawdown": (price / price.cummax() - 1).min()
            })

        # Save risk metrics to SQLite
        pd.DataFrame(risks).to_sql(
            "risk_analysis",
            conn,
            if_exists="replace",
            index=False
        )
