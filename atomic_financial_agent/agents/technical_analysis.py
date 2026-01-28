# technical_analysis.py
# Computes technical indicators and stores them in SQLite.

import pandas as pd
import numpy as np
from .base import AtomicAgent


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

        # Read market data from SQLite
        df = pd.read_sql("SELECT * FROM market_data", conn)

        out = []

        # Loop through each ticker and compute indicators
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
