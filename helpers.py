"""Utility helpers for inventory, pricing, and financial reporting."""

import ast
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Union

import numpy as np
import pandas as pd
from sqlalchemy import Engine
from sqlalchemy.sql import text


def generate_sample_inventory(paper_supplies: list, coverage: float = 0.4, seed: int = 137) -> pd.DataFrame:
    """Create a random inventory subset.

    Args:
        paper_supplies: Full catalog of paper items.
        coverage: Fraction of catalog items to include.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with seeded inventory rows.
    """
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


def init_database(engine: Engine, paper_supplies: list, db_engine: Engine, seed: int = 137) -> Engine:
    """Initialize inventory, quotes, and transactions tables.

    Args:
        engine: SQLAlchemy engine for table creation.
        paper_supplies: Product catalog used to seed inventory.
        db_engine: Shared DB engine used for transactions.
        seed: Seed for deterministic inventory generation.

    Returns:
        The initialized SQLAlchemy engine.
    """
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


def parse_request(request_text: str, paper_supplies: list) -> Dict[str, Union[str, int]]:
    """Extract requested item and quantity from free-form text.

    Args:
        request_text: Customer request body.
        paper_supplies: Product catalog to match item names.

    Returns:
        Mapping with normalized ``item_name`` and integer ``quantity``.
    """
    req_l = request_text.lower()
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


def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """Compute replenishment ETA based on shortage quantity.

    Args:
        input_date_str: Request date in ISO format.
        quantity: Shortage units to replenish.

    Returns:
        ISO date string for expected delivery.
    """
    input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    days = 0 if quantity <= 10 else 1 if quantity <= 100 else 4 if quantity <= 1000 else 7
    return (input_date_dt + timedelta(days=days)).strftime("%Y-%m-%d")


def search_quote_history(db_engine: Engine, search_terms: List[str], limit: int = 5) -> List[Dict]:
    """Find historical quotes matching search keywords.

    Args:
        db_engine: SQLAlchemy engine to query.
        search_terms: Case-insensitive terms to match.
        limit: Max records to return.

    Returns:
        List of matching quote dictionaries.
    """
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
