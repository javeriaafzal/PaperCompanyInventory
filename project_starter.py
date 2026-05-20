"""Public entrypoint exposing catalog, DB engine, and orchestration APIs."""

import importlib

from sqlalchemy import create_engine

from agents import OrchestrationAgent
from evaluate import run_test_scenarios

if importlib.util.find_spec("dotenv") is not None:
    import dotenv

    dotenv.load_dotenv()

# Create an SQLite database
_db_url = "sqlite:///munder_difflin.db"
db_engine = create_engine(_db_url)

paper_supplies = [
    {"item_name": "A4 paper", "category": "paper", "unit_price": 0.05},
    {"item_name": "Letter-sized paper", "category": "paper", "unit_price": 0.06},
    {"item_name": "Cardstock", "category": "paper", "unit_price": 0.15},
    {"item_name": "Colored paper", "category": "paper", "unit_price": 0.10},
    {"item_name": "Glossy paper", "category": "paper", "unit_price": 0.20},
]


def call_your_multi_agent_system(request_with_date: str, request_date: str, orchestrator: OrchestrationAgent) -> dict:
    """Route a request through the orchestrator.

    Args:
        request_with_date: Request text with contextual date information.
        request_date: ISO request date.
        orchestrator: Instantiated orchestration agent.

    Returns:
        Workflow result dictionary.
    """
    return orchestrator.handle_request(request_with_date, request_date)


if __name__ == "__main__":
    print(run_test_scenarios(db_engine, paper_supplies))
