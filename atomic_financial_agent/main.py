# main.py
# This is the only file you run.
# It sets up the configuration and starts the orchestrator pipeline.

from orchestrator import FinancialAdvisorOrchestrator
from datetime import datetime, timedelta

if __name__ == "__main__":
    # Context contains configuration values for the pipeline
    # tickers: list of stocks
    # start_date / end_date: time range for historical data
    context = {
        "tickers": ["AAPL", "MSFT", "NVDA", "TSLA"],
        "start_date": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d")
    }

    # Create orchestrator instance
    advisor = FinancialAdvisorOrchestrator()

    # Run the pipeline
    advisor.run(context)

    # Print final report
    print("\n========== FINAL REPORT ==========\n")
    print(context["report"])
