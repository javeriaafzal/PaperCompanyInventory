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

def build_customer_quote_response(quote: Dict) -> Dict:
    rationale = (
        f"Quoted using a unit price of ${quote['unit_price']:.2f} with a "
        f"{quote['discount_rate']:.0%} volume discount based on order size."
    )
    return {
        "item": quote["item_name"],
        "quantity": quote["quantity"],
        "quoted_unit_price": quote["unit_price"],
        "discount_rate": quote["discount_rate"],
        "total_amount": quote["total_amount"],
        "payment_terms": quote["terms"],
        "eta": quote["eta"],
        "rationale": rationale,
    }


def fulfill_quote(quote: Dict, request_date: str) -> Dict:
    item_name = quote["item_name"]
    quantity = int(quote["quantity"])
    stock_df = get_stock_level(item_name, request_date)
    current_stock = int(stock_df["current_stock"].iloc[0]) if not stock_df.empty else 0
    if current_stock < quantity:
        shortage = quantity - current_stock
        eta = get_supplier_delivery_date(request_date, shortage)
        return {
            "status": "unfulfilled",
            "item_name": item_name,
            "quantity": quantity,
            "shortage": shortage,
            "eta": eta,
            "reason": f"Insufficient stock on {request_date}. Earliest replenishment ETA: {eta}.",
        }
    create_transaction(item_name, "sales", quantity, quote["total_amount"], request_date)
    return {"status": "fulfilled", "item_name": item_name, "quantity": quantity, "total_amount": quote["total_amount"]}


class OrchestrationAgent:
    """Coordinator that wires pydantic-ai Agents + tools into a deterministic pipeline."""

    def __init__(self):
        self.inventory_agent = inventory_agent
        self.quote_agent = quote_agent
        self.ordering_agent = ordering_agent
        self.reporting_agent = reporting_agent

    def handle_request(self, request_text: str, request_date: str) -> Dict:
        parsed = parse_request(request_text)
        inv = check_inventory(parsed["item_name"], parsed["quantity"], request_date)
        quote = create_quote(parsed["item_name"], parsed["quantity"], request_date, inv)
        customer_quote = build_customer_quote_response(quote)
        result = {"quote": customer_quote, "status": "quoted"}
        result["order"] = fulfill_quote(quote, request_date)
        result["financial_report"] = generate_financial_report_tool(request_date)
        result["status"] = result["order"].get("status", "quoted")
        return result


def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    conditions = []
    params = {}
    for i, term in enumerate(search_terms):
        param_name = f"term_{i}"
        conditions.append(f"(LOWER(qr.response) LIKE :{param_name} OR LOWER(q.quote_explanation) LIKE :{param_name})")
        params[param_name] = f"%{term.lower()}%"
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    query = f"""
        SELECT qr.response AS original_request, q.total_amount, q.quote_explanation, q.job_type, q.order_size, q.event_type, q.order_date
        FROM quotes q JOIN quote_requests qr ON q.request_id = qr.id
        WHERE {where_clause}
        ORDER BY q.order_date DESC
        LIMIT {limit}
    Returns:
        Workflow result dictionary.
    """
    return orchestrator.handle_request(request_with_date, request_date)


if __name__ == "__main__":
    print(run_test_scenarios(db_engine, paper_supplies))
