# orchestrator.py
# Controls the execution order of all agents.
# It uses a SQLite database connection shared between agents.

import sqlite3

from agents.market_data import MarketDataAgent
from agents.technical_analysis import TechnicalAnalysisAgent
from agents.risk_analysis import RiskAnalysisAgent
from agents.strategy import StrategyAgent
from agents.report import ReportAgent


class FinancialAdvisorOrchestrator:
    """
    Orchestrator class controls pipeline execution order:
    1. MarketDataAgent
    2. TechnicalAnalysisAgent
    3. RiskAnalysisAgent
    4. StrategyAgent
    5. ReportAgent
    """

    def __init__(self):
        # List of agent instances to run sequentially
        self.agents = [
            MarketDataAgent(),
            TechnicalAnalysisAgent(),
            RiskAnalysisAgent(),
            StrategyAgent(),
            ReportAgent()
        ]

    def run(self, context):
        # Connect to SQLite database (advisor.db)
        conn = sqlite3.connect("advisor.db")
        try:
            # Execute each agent one by one
            for agent in self.agents:
                agent.execute(conn, context)

            # Commit changes to database after all agents succeed
            conn.commit()
            print("✅ Pipeline completed successfully")

        except Exception as e:
            # If any agent fails, rollback DB changes
            conn.rollback()
            print("❌ Pipeline failed:", e)

        finally:
            # Close DB connection
            conn.close()
