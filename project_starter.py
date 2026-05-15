import ast
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Union

import importlib
import numpy as np
import pandas as pd
from sqlalchemy import Engine, create_engine
from sqlalchemy.sql import text

# Create an SQLite database
db_engine = create_engine("sqlite:///munder_difflin.db")

# Optional env loading for future model-backed agents.

if importlib.util.find_spec("dotenv") is not None:
    import dotenv
    dotenv.load_dotenv()

# List containing the different kinds of papers
paper_supplies = [
    {"item_name": "A4 paper", "category": "paper", "unit_price": 0.05},
    {"item_name": "Letter-sized paper", "category": "paper", "unit_price": 0.06},
    {"item_name": "Cardstock", "category": "paper", "unit_price": 0.15},
    {"item_name": "Colored paper", "category": "paper", "unit_price": 0.10},
    {"item_name": "Glossy paper", "category": "paper", "unit_price": 0.20},
    {"item_name": "Matte paper", "category": "paper", "unit_price": 0.18},
    {"item_name": "Recycled paper", "category": "paper", "unit_price": 0.08},
    {"item_name": "Eco-friendly paper", "category": "paper", "unit_price": 0.12},
    {"item_name": "Poster paper", "category": "paper", "unit_price": 0.25},
    {"item_name": "Banner paper", "category": "paper", "unit_price": 0.30},
    {"item_name": "Kraft paper", "category": "paper", "unit_price": 0.10},
    {"item_name": "Construction paper", "category": "paper", "unit_price": 0.07},
    {"item_name": "Wrapping paper", "category": "paper", "unit_price": 0.15},
    {"item_name": "Glitter paper", "category": "paper", "unit_price": 0.22},
    {"item_name": "Decorative paper", "category": "paper", "unit_price": 0.18},
    {"item_name": "Letterhead paper", "category": "paper", "unit_price": 0.12},
    {"item_name": "Legal-size paper", "category": "paper", "unit_price": 0.08},
    {"item_name": "Crepe paper", "category": "paper", "unit_price": 0.05},
    {"item_name": "Photo paper", "category": "paper", "unit_price": 0.25},
    {"item_name": "Uncoated paper", "category": "paper", "unit_price": 0.06},
    {"item_name": "Butcher paper", "category": "paper", "unit_price": 0.10},
    {"item_name": "Heavyweight paper", "category": "paper", "unit_price": 0.20},
    {"item_name": "Standard copy paper", "category": "paper", "unit_price": 0.04},
    {"item_name": "Bright-colored paper", "category": "paper", "unit_price": 0.12},
    {"item_name": "Patterned paper", "category": "paper", "unit_price": 0.15},
    {"item_name": "Paper plates", "category": "product", "unit_price": 0.10},
    {"item_name": "Paper cups", "category": "product", "unit_price": 0.08},
    {"item_name": "Paper napkins", "category": "product", "unit_price": 0.02},
    {"item_name": "Disposable cups", "category": "product", "unit_price": 0.10},
    {"item_name": "Table covers", "category": "product", "unit_price": 1.50},
    {"item_name": "Envelopes", "category": "product", "unit_price": 0.05},
    {"item_name": "Sticky notes", "category": "product", "unit_price": 0.03},
    {"item_name": "Notepads", "category": "product", "unit_price": 2.00},
    {"item_name": "Invitation cards", "category": "product", "unit_price": 0.50},
    {"item_name": "Flyers", "category": "product", "unit_price": 0.15},
    {"item_name": "Party streamers", "category": "product", "unit_price": 0.05},
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},
    {"item_name": "Paper party bags", "category": "product", "unit_price": 0.25},
    {"item_name": "Name tags with lanyards", "category": "product", "unit_price": 0.75},
    {"item_name": "Presentation folders", "category": "product", "unit_price": 0.50},
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},
    {"item_name": "100 lb cover stock", "category": "specialty", "unit_price": 0.50},
    {"item_name": "80 lb text paper", "category": "specialty", "unit_price": 0.40},
    {"item_name": "250 gsm cardstock", "category": "specialty", "unit_price": 0.30},
    {"item_name": "220 gsm poster paper", "category": "specialty", "unit_price": 0.35},
]


def generate_sample_inventory(paper_supplies: list, coverage: float = 0.4, seed: int = 137) -> pd.DataFrame:
    np.random.seed(seed)
    num_items = int(len(paper_supplies) * coverage)
    selected_indices = np.random.choice(range(len(paper_supplies)), size=num_items, replace=False)
    selected_items = [paper_supplies[i] for i in selected_indices]
    inventory = []
    for item in selected_items:
        inventory.append({
            "item_name": item["item_name"],
            "category": item["category"],
            "unit_price": item["unit_price"],
            "current_stock": np.random.randint(200, 800),
            "min_stock_level": np.random.randint(50, 150),
        })
    return pd.DataFrame(inventory)


def init_database(engine: Engine, seed: int = 137) -> Engine:
    transactions_schema = pd.DataFrame({"id": [], "item_name": [], "transaction_type": [], "units": [], "price": [], "transaction_date": []})
    transactions_schema.to_sql("transactions", engine, if_exists="replace", index=False)

    initial_date = datetime(2025, 1, 1).isoformat()

    if os.path.exists("quote_requests.csv"):
        quote_requests_df = pd.read_csv("quote_requests.csv")
    else:
        quote_requests_df = pd.DataFrame({"response": ["Need 250 A4 paper sheets for office event"]})
    quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
    quote_requests_df.to_sql("quote_requests", engine, if_exists="replace", index=False)

    if os.path.exists("quotes.csv"):
        quotes_df = pd.read_csv("quotes.csv")
    else:
        quotes_df = pd.DataFrame({"total_amount": [12.5], "quote_explanation": ["Seed quote"], "request_metadata": ["{'job_type':'admin','order_size':'small','event_type':'office'}"]})
    quotes_df["request_id"] = range(1, len(quotes_df) + 1)
    quotes_df["order_date"] = initial_date
    if "request_metadata" in quotes_df.columns:
        quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
        quotes_df["job_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("job_type", ""))
        quotes_df["order_size"] = quotes_df["request_metadata"].apply(lambda x: x.get("order_size", ""))
        quotes_df["event_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("event_type", ""))
    quotes_df = quotes_df[["request_id", "total_amount", "quote_explanation", "order_date", "job_type", "order_size", "event_type"]]
    quotes_df.to_sql("quotes", engine, if_exists="replace", index=False)

    inventory_df = generate_sample_inventory(paper_supplies, seed=seed)
    initial_transactions = [{"item_name": None, "transaction_type": "sales", "units": None, "price": 50000.0, "transaction_date": initial_date}]
    for _, item in inventory_df.iterrows():
        initial_transactions.append({"item_name": item["item_name"], "transaction_type": "stock_orders", "units": int(item["current_stock"]), "price": float(item["current_stock"] * item["unit_price"]), "transaction_date": initial_date})
    pd.DataFrame(initial_transactions).to_sql("transactions", engine, if_exists="append", index=False)
    inventory_df.to_sql("inventory", engine, if_exists="replace", index=False)
    return engine


def create_transaction(item_name: str, transaction_type: str, quantity: int, price: float, date: Union[str, datetime]) -> int:
    date_str = date.isoformat() if isinstance(date, datetime) else date
    if transaction_type not in {"stock_orders", "sales"}:
        raise ValueError("Transaction type must be 'stock_orders' or 'sales'")
    transaction = pd.DataFrame([{"item_name": item_name, "transaction_type": transaction_type, "units": quantity, "price": price, "transaction_date": date_str}])
    transaction.to_sql("transactions", db_engine, if_exists="append", index=False)
    result = pd.read_sql("SELECT last_insert_rowid() as id", db_engine)
    return int(result.iloc[0]["id"])


def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()
    stock_query = """
        SELECT item_name,
        COALESCE(SUM(CASE WHEN transaction_type='stock_orders' THEN units WHEN transaction_type='sales' THEN -units ELSE 0 END),0) AS current_stock
        FROM transactions
        WHERE item_name=:item_name AND transaction_date <= :as_of_date
    """
    return pd.read_sql(stock_query, db_engine, params={"item_name": item_name, "as_of_date": as_of_date})


def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    days = 0 if quantity <= 10 else 1 if quantity <= 100 else 4 if quantity <= 1000 else 7
    return (input_date_dt + timedelta(days=days)).strftime("%Y-%m-%d")


def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()
    transactions = pd.read_sql("SELECT * FROM transactions WHERE transaction_date <= :as_of_date", db_engine, params={"as_of_date": as_of_date})
    if transactions.empty:
        return 0.0
    sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
    purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
    return float(sales - purchases)


# Multi-agent tools + agents

def parse_request(request_text: str) -> Dict[str, Union[str, int]]:
    req_l = request_text.lower()
    # Parse multiple "qty + item" mentions and choose the line item with the largest value.
    # This keeps the baseline contract (single line-item quote) while handling richer inquiries.
    mentions = []
    for paper in paper_supplies:
        item_l = paper["item_name"].lower()
        pattern = rf"(\d{{1,6}})\s+(?:sheets?\s+of\s+|rolls?\s+of\s+|reams?\s+of\s+)?{re.escape(item_l)}"
        for m in re.finditer(pattern, req_l):
            mentions.append((int(m.group(1)), paper["item_name"]))
    if mentions:
        quantity, item = max(mentions, key=lambda x: x[0])
        return {"item_name": item, "quantity": quantity}
    match_qty = re.search(r"(\d+)", req_l)
    quantity = int(match_qty.group(1)) if match_qty else 100
    item = next((p["item_name"] for p in paper_supplies if p["item_name"].lower() in req_l), "A4 paper")
    return {"item_name": item, "quantity": quantity}


class InventoryAgent:
    def check(self, item_name: str, quantity: int, request_date: str) -> Dict[str, Union[bool, int, str]]:
        stock_df = get_stock_level(item_name, request_date)
        current_stock = int(stock_df["current_stock"].iloc[0]) if not stock_df.empty else 0
        available = current_stock >= quantity
        shortage = max(0, quantity - current_stock)
        eta = None if available else get_supplier_delivery_date(request_date, shortage)
        return {"available": available, "current_stock": current_stock, "shortage": shortage, "eta": eta}


class QuoteAgent:
    def create_quote(self, item_name: str, quantity: int, request_date: str, inventory_result: Dict) -> Dict:
        unit_price = next((p["unit_price"] for p in paper_supplies if p["item_name"] == item_name), 0.1)
        base_subtotal = round(unit_price * quantity, 2)
        # Competitive discounting with profitability floor (>= 8% gross margin).
        discount_rate = 0.00 if quantity < 200 else 0.03 if quantity < 1000 else 0.06 if quantity < 5000 else 0.09
        discounted_subtotal = round(base_subtotal * (1 - discount_rate), 2)
        estimated_cost = round(base_subtotal * 0.80, 2)
        minimum_profitable = round(estimated_cost * 1.08, 2)
        total_amount = max(discounted_subtotal, minimum_profitable)
        historical = search_quote_history([item_name.split()[0]], limit=3)
        cash = get_cash_balance(request_date)
        terms = "Net 30" if cash >= 0 else "Prepay"
        return {
            "item_name": item_name,
            "quantity": quantity,
            "unit_price": unit_price,
            "base_subtotal": base_subtotal,
            "discount_rate": discount_rate,
            "total_amount": round(total_amount, 2),
            "eta": inventory_result["eta"],
            "terms": terms,
            "history_matches": historical,
        }


class OrderingAgent:
    def fulfill(self, quote: Dict, request_date: str) -> Dict:
        item_name = quote["item_name"]
        quantity = int(quote["quantity"])
        stock_df = get_stock_level(item_name, request_date)
        current_stock = int(stock_df["current_stock"].iloc[0]) if not stock_df.empty else 0
        if current_stock < quantity:
            reorder_qty = quantity - current_stock
            reorder_price = reorder_qty * quote["unit_price"]
            create_transaction(item_name, "stock_orders", reorder_qty, reorder_price, request_date)
        create_transaction(item_name, "sales", quantity, quote["total_amount"], request_date)
        return {"status": "fulfilled", "item_name": item_name, "quantity": quantity, "total_amount": quote["total_amount"]}


class OrchestrationAgent:
    def __init__(self):
        self.inventory_agent = InventoryAgent()
        self.quote_agent = QuoteAgent()
        self.ordering_agent = OrderingAgent()

    def handle_request(self, request_text: str, request_date: str) -> Dict:
        parsed = parse_request(request_text)
        inv = self.inventory_agent.check(parsed["item_name"], parsed["quantity"], request_date)
        quote = self.quote_agent.create_quote(parsed["item_name"], parsed["quantity"], request_date, inv)
        result = {"inventory": inv, "quote": quote, "status": "quoted"}
        # Auto-accept demo flow for test harness.
        result["order"] = self.ordering_agent.fulfill(quote, request_date)
        result["status"] = "fulfilled"
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
    """
    with db_engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]


def call_your_multi_agent_system(request_with_date: str, request_date: str, orchestrator: "OrchestrationAgent") -> Dict:
    """Adapter hook used by the test harness to route requests through the multi-agent workflow."""
    return orchestrator.handle_request(request_with_date, request_date)


def generate_financial_report(request_date: str) -> Dict[str, float]:
    """Snapshot core financial state for each processed request date."""
    current_cash = round(get_cash_balance(request_date), 2)
    inventory_query = """
        SELECT COALESCE(SUM(i.unit_price * s.current_stock), 0) AS inventory_value
        FROM inventory i
        LEFT JOIN (
            SELECT item_name,
                   COALESCE(SUM(CASE
                       WHEN transaction_type='stock_orders' THEN units
                       WHEN transaction_type='sales' THEN -units
                       ELSE 0
                   END), 0) AS current_stock
            FROM transactions
            WHERE transaction_date <= :as_of_date
            GROUP BY item_name
        ) s ON i.item_name = s.item_name
    """
    inventory_df = pd.read_sql(inventory_query, db_engine, params={"as_of_date": request_date})
    inventory_value = round(float(inventory_df["inventory_value"].iloc[0]), 2) if not inventory_df.empty else 0.0
    return {"cash_balance": current_cash, "inventory_value": inventory_value}


def run_test_scenarios():
    print("Initializing Database...")
    init_database(db_engine)
    if os.path.exists("quote_requests_sample.csv"):
        quote_requests_sample = pd.read_csv("quote_requests_sample.csv")
    else:
        quote_requests_sample = pd.DataFrame([
            {"job": "office manager", "event": "team offsite", "request": "Need 300 A4 paper for packets", "request_date": "01/05/25"},
            {"job": "designer", "event": "conference", "request": "Please quote 120 Poster paper", "request_date": "01/07/25"},
        ])

    quote_requests_sample["request_date"] = pd.to_datetime(quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce")
    quote_requests_sample.dropna(subset=["request_date"], inplace=True)
    quote_requests_sample = quote_requests_sample.sort_values("request_date")

    # Initialize multi-agent system and create agents.
    orchestrator = OrchestrationAgent()
    results = []
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")
        request_with_date = f"{row['request']} (Date of request: {request_date})"
        # response = call_your_multi_agent_system(request_with_date)
        response = call_your_multi_agent_system(request_with_date, request_date, orchestrator)
        inv = response["inventory"]
        quote = response["quote"]
        order = response.get("order", {})
        # Update state for eg.
        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        print(f"Response: {response}")
        print(f"Updated Cash: ${current_cash:.2f}")
        print(f"Updated Inventory: ${current_inventory:.2f}")
        orders_accommodated = bool(response.get("status") == "fulfilled")
        profitability = round(float(quote["total_amount"]) - float(quote["quantity"]) * float(quote["unit_price"]), 2)
        competitive_pricing = bool(0 <= float(quote.get("discount_rate", 0.0)) <= 0.10)
        results.append(
            {
                "request_id": idx + 1,
                "request_date": request_date,
                "request_text": row["request"],
                "item_name": quote["item_name"],
                "quantity": quote["quantity"],
                "available_at_request": inv["available"],
                "shortage_units": inv["shortage"],
                "eta_if_short": inv["eta"],
                "quoted_unit_price": quote["unit_price"],
                "base_subtotal": quote.get("base_subtotal", round(quote["unit_price"] * quote["quantity"], 2)),
                "discount_rate": quote.get("discount_rate", 0.0),
                "quoted_total": quote["total_amount"],
                "order_status": order.get("status", "not_ordered"),
                "orders_accommodated": orders_accommodated,
                "competitive_pricing": competitive_pricing,
                "profitability_dollars": profitability,
                "cash_balance": current_cash,
                "inventory_value": current_inventory,
            }
        )
        time.sleep(0.1)

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print("\n===== FINAL FINANCIAL REPORT =====")
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")

    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results


if __name__ == "__main__":
    print(run_test_scenarios())
