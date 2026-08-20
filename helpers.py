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


def _normalize_as_of_date(as_of_date: Union[str, datetime]) -> str:
    """Normalize date-only cutoffs to include the full day."""
    if isinstance(as_of_date, datetime):
        return as_of_date.isoformat()
    return f"{as_of_date}T23:59:59" if len(as_of_date) == 10 else as_of_date


def generate_sample_inventory(paper_supplies: list, coverage: float = 1.0, seed: int = 137) -> pd.DataFrame:
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


def _parse_quantity(quantity_text: str) -> int:
    """Convert a quantity token that may include thousands separators."""
    return int(quantity_text.replace(",", ""))


def _singularize_item_phrase(item_phrase: str) -> str:
    """Normalize an extracted item phrase for reporting catalog misses."""
    item_phrase = re.sub(r"\s+", " ", item_phrase.strip(" .;:!"))
    words = item_phrase.split()
    while words and words[0] in {"of", "the", "a", "an", "assorted", "various"}:
        words.pop(0)
    item_phrase = " ".join(words) or "Unknown item"
    if item_phrase.endswith("ies"):
        item_phrase = f"{item_phrase[:-3]}y"
    elif item_phrase.endswith("s") and not item_phrase.endswith("ss"):
        item_phrase = item_phrase[:-1]
    return item_phrase[:1].upper() + item_phrase[1:]


def parse_request(request_text: str, paper_supplies: list) -> Dict[str, Union[str, int, bool]]:
    """Extract requested item and quantity from free-form text.

    Args:
        request_text: Customer request body.
        paper_supplies: Product catalog to match item names.

    Returns:
        Mapping with normalized ``item_name``, integer ``quantity``, and whether
        the item was found in the submitted product catalog.
    """
    req_l = request_text.lower()
    quantity_pattern = r"(\d{1,3}(?:,\d{3})+|\d+)"
    mentions = []
    for paper in paper_supplies:
        item_l = paper["item_name"].lower()
        pattern = rf"{quantity_pattern}\s+(?:sheets?\s+of\s+|rolls?\s+of\s+|reams?\s+of\s+)?(?:[a-z0-9.%-]+[,\s]+){{0,4}}{re.escape(item_l)}"
        for m in re.finditer(pattern, req_l):
            mentions.append((_parse_quantity(m.group(1)), paper["item_name"], True))
    if mentions:
        quantity, item, catalog_match = max(mentions, key=lambda x: x[0])
        return {"item_name": item, "quantity": quantity, "catalog_match": catalog_match}

    unknown_match = re.search(
        rf"{quantity_pattern}\s+(?:sheets?\s+of\s+|rolls?\s+of\s+|reams?\s+of\s+)?([a-z][a-z0-9 .%'-]*?)(?=,|\band\b|\.|$)",
        req_l,
    )
    if unknown_match:
        return {
            "item_name": _singularize_item_phrase(unknown_match.group(2)),
            "quantity": _parse_quantity(unknown_match.group(1)),
            "catalog_match": False,
        }

    item = next((p["item_name"] for p in paper_supplies if p["item_name"].lower() in req_l), "A4 paper")
    return {"item_name": item, "quantity": 100, "catalog_match": item != "A4 paper"}


def create_transaction(db_engine: Engine, item_name: str, transaction_type: str, quantity: int, price: float, date: Union[str, datetime]) -> int:
    """Persist a sales or stock-order transaction.

    Args:
        db_engine: SQLAlchemy engine to write to.
        item_name: Inventory item involved in the transaction.
        transaction_type: Either ``stock_orders`` or ``sales``.
        quantity: Number of units.
        price: Total transaction amount.
        date: ISO date string or datetime.

    Returns:
        Inserted transaction row id.
    """
    date_str = date.isoformat() if isinstance(date, datetime) else date
    if transaction_type not in {"stock_orders", "sales"}:
        raise ValueError("Transaction type must be 'stock_orders' or 'sales'")
    transaction = pd.DataFrame([{
        "item_name": item_name,
        "transaction_type": transaction_type,
        "units": quantity,
        "price": price,
        "transaction_date": date_str,
    }])
    transaction.to_sql("transactions", db_engine, if_exists="append", index=False)
    result = pd.read_sql("SELECT last_insert_rowid() as id", db_engine)
    return int(result.iloc[0]["id"])


def get_all_inventory(db_engine: Engine, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """Return computed stock levels for all inventory items as of a date.

    Args:
        db_engine: SQLAlchemy engine to query.
        as_of_date: ISO date string or datetime cutoff.

    Returns:
        DataFrame with inventory metadata and computed stock columns.
    """
    as_of_date = _normalize_as_of_date(as_of_date)
    query = """
        SELECT i.item_name, i.category, i.unit_price, i.min_stock_level,
        COALESCE(SUM(CASE
            WHEN t.transaction_type='stock_orders' THEN t.units
            WHEN t.transaction_type='sales' THEN -t.units
            ELSE 0
        END), 0) AS current_stock
        FROM inventory i
        LEFT JOIN transactions t
            ON i.item_name = t.item_name AND t.transaction_date <= :as_of_date
        GROUP BY i.item_name, i.category, i.unit_price, i.min_stock_level
        ORDER BY i.item_name
    """
    return pd.read_sql(query, db_engine, params={"as_of_date": as_of_date})


def get_stock_level(db_engine: Engine, item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """Return computed stock level for one item as of a date.

    Args:
        db_engine: SQLAlchemy engine to query.
        item_name: Item to evaluate.
        as_of_date: ISO date string or datetime cutoff.

    Returns:
        DataFrame with ``item_name`` and ``current_stock`` columns.
    """
    as_of_date = _normalize_as_of_date(as_of_date)
    query = """
        SELECT item_name,
        COALESCE(SUM(CASE WHEN transaction_type='stock_orders' THEN units WHEN transaction_type='sales' THEN -units ELSE 0 END),0) AS current_stock
        FROM transactions
        WHERE item_name=:item_name AND transaction_date <= :as_of_date
    """
    return pd.read_sql(query, db_engine, params={"item_name": item_name, "as_of_date": as_of_date})


def get_cash_balance(db_engine: Engine, as_of_date: Union[str, datetime]) -> float:
    """Calculate cash balance from historical transactions.

    Args:
        db_engine: SQLAlchemy engine to query.
        as_of_date: ISO date string or datetime cutoff.

    Returns:
        Cash as sales total minus purchase total.
    """
    as_of_date = _normalize_as_of_date(as_of_date)
    transactions = pd.read_sql("SELECT * FROM transactions WHERE transaction_date <= :as_of_date", db_engine, params={"as_of_date": as_of_date})
    if transactions.empty:
        return 0.0
    sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
    purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
    return float(sales - purchases)


def generate_financial_report(db_engine: Engine, as_of_date: Union[str, datetime]) -> Dict[str, Union[str, float]]:
    """Generate a financial snapshot as of a date.

    Args:
        db_engine: SQLAlchemy engine to query.
        as_of_date: ISO date string or datetime cutoff.

    Returns:
        Mapping with cash balance, sales, stock-order spend, inventory value, and profit.
    """
    as_of_date = _normalize_as_of_date(as_of_date)
    transactions = pd.read_sql("SELECT * FROM transactions WHERE transaction_date <= :as_of_date", db_engine, params={"as_of_date": as_of_date})
    sales_total = 0.0 if transactions.empty else float(transactions.loc[transactions["transaction_type"] == "sales", "price"].sum())
    stock_order_total = 0.0 if transactions.empty else float(transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum())
    inventory = get_all_inventory(db_engine, as_of_date)
    inventory_value = 0.0 if inventory.empty else float((inventory["current_stock"] * inventory["unit_price"]).sum())
    return {
        "as_of_date": as_of_date,
        "cash_balance": sales_total - stock_order_total,
        "sales_total": sales_total,
        "stock_order_total": stock_order_total,
        "inventory_value": inventory_value,
        "gross_profit": sales_total - stock_order_total,
    }


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
