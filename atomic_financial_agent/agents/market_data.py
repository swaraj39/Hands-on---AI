# market_data.py
# Fetches historical stock prices using yfinance and saves to SQLite.

import pandas as pd
import yfinance as yf
from .base import AtomicAgent


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
