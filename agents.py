"""Agent definitions and orchestration workflow."""

from datetime import datetime
from typing import Dict, Union

import pandas as pd
from pydantic_ai import Agent, RunContext
from sqlalchemy import Engine

from helpers import get_supplier_delivery_date, parse_request, search_quote_history


class OrchestrationAgent:
    """Coordinate inventory, quoting, fulfillment, and reporting agents.

    Args:
        db_engine: Shared SQLAlchemy engine.
        paper_supplies: Product catalog used across tools.

    Returns:
        None. Use :meth:`handle_request` for workflow execution.
    """

    def __init__(self, db_engine: Engine, paper_supplies: list):
        """Create orchestrator and attach tool-backed sub-agents.

        Args:
            db_engine: Shared SQLAlchemy engine for reads/writes.
            paper_supplies: Product catalog with names and unit prices.

        Returns:
            None.
        """
        self.db_engine = db_engine
        self.paper_supplies = paper_supplies
        self.inventory_agent = Agent(name="inventory_agent", system_prompt="Check inventory availability and predict replenishment ETA.")
        self.quote_agent = Agent(name="quote_agent", system_prompt="Generate competitive, profitable quotes based on inventory and cash state.")
        self.ordering_agent = Agent(name="ordering_agent", system_prompt="Execute stock replenishment and sales transactions for accepted quotes.")
        self.reporting_agent = Agent(name="reporting_agent", system_prompt="Generate financial and inventory snapshots for reporting.")

    def create_transaction(self, item_name: str, transaction_type: str, quantity: int, price: float, date: Union[str, datetime]) -> int:
        """Persist a sales or stock-order transaction.

        Args:
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
        transaction = pd.DataFrame([{"item_name": item_name, "transaction_type": transaction_type, "units": quantity, "price": price, "transaction_date": date_str}])
        transaction.to_sql("transactions", self.db_engine, if_exists="append", index=False)
        result = pd.read_sql("SELECT last_insert_rowid() as id", self.db_engine)
        return int(result.iloc[0]["id"])

    def get_stock_level(self, item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
        """Return computed stock level for one item as of a date.

        Args:
            item_name: Item to evaluate.
            as_of_date: ISO date string or datetime cutoff.

        Returns:
            DataFrame with ``item_name`` and ``current_stock`` columns.
        """
        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.isoformat()
        query = """
            SELECT item_name,
            COALESCE(SUM(CASE WHEN transaction_type='stock_orders' THEN units WHEN transaction_type='sales' THEN -units ELSE 0 END),0) AS current_stock
            FROM transactions
            WHERE item_name=:item_name AND transaction_date <= :as_of_date
        """
        return pd.read_sql(query, self.db_engine, params={"item_name": item_name, "as_of_date": as_of_date})

    def get_cash_balance(self, as_of_date: Union[str, datetime]) -> float:
        """Calculate cash balance from historical transactions.

        Args:
            as_of_date: ISO date string or datetime cutoff.

        Returns:
            Cash as sales total minus purchase total.
        """
        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.isoformat()
        transactions = pd.read_sql("SELECT * FROM transactions WHERE transaction_date <= :as_of_date", self.db_engine, params={"as_of_date": as_of_date})
        if transactions.empty:
            return 0.0
        sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
        purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
        return float(sales - purchases)

    def check_inventory(self, item_name: str, quantity: int, request_date: str) -> Dict[str, Union[bool, int, str, None]]:
        """Evaluate stock availability and shortage ETA.

        Args:
            item_name: Requested item.
            quantity: Requested units.
            request_date: ISO request date.

        Returns:
            Availability, current stock, shortage, and optional ETA.
        """
        stock_df = self.get_stock_level(item_name, request_date)
        current_stock = int(stock_df["current_stock"].iloc[0]) if not stock_df.empty else 0
        available = current_stock >= quantity
        shortage = max(0, quantity - current_stock)
        eta = None if available else get_supplier_delivery_date(request_date, shortage)
        return {"available": available, "current_stock": current_stock, "shortage": shortage, "eta": eta}

    def create_quote(self, item_name: str, quantity: int, request_date: str, inventory_result: Dict) -> Dict:
        """Build a profitable quote with light competitive discounting.

        Args:
            item_name: Requested item.
            quantity: Requested units.
            request_date: ISO request date.
            inventory_result: Prior inventory check output.

        Returns:
            Quote payload with pricing, terms, ETA, and history matches.
        """
        unit_price = next((p["unit_price"] for p in self.paper_supplies if p["item_name"] == item_name), 0.1)
        base_subtotal = round(unit_price * quantity, 2)
        discount_rate = 0.00 if quantity < 200 else 0.03 if quantity < 1000 else 0.06 if quantity < 5000 else 0.09
        discounted_subtotal = round(base_subtotal * (1 - discount_rate), 2)
        estimated_cost = round(base_subtotal * 0.80, 2)
        minimum_profitable = round(estimated_cost * 1.08, 2)
        total_amount = max(discounted_subtotal, minimum_profitable)
        historical = search_quote_history(self.db_engine, [item_name.split()[0]], limit=3)
        terms = "Net 30" if self.get_cash_balance(request_date) >= 0 else "Prepay"
        return {"item_name": item_name, "quantity": quantity, "unit_price": unit_price, "base_subtotal": base_subtotal, "discount_rate": discount_rate, "estimated_cost": estimated_cost, "total_amount": round(total_amount, 2), "eta": inventory_result["eta"], "terms": terms, "history_matches": historical}

    def fulfill_quote(self, quote: Dict, request_date: str) -> Dict:
        """Attempt to fulfill a quote and create sales transaction.

        Args:
            quote: Quote payload with item, quantity, and total amount.
            request_date: ISO request date.

        Returns:
            Fulfillment result with success or shortage details.
        """
        item_name = quote["item_name"]
        quantity = int(quote["quantity"])
        current_stock = int(self.get_stock_level(item_name, request_date)["current_stock"].iloc[0])
        if current_stock < quantity:
            shortage = quantity - current_stock
            eta = get_supplier_delivery_date(request_date, shortage)
            return {"status": "unfulfilled", "item_name": item_name, "quantity": quantity, "shortage": shortage, "eta": eta, "reason": f"Insufficient stock on {request_date}. Earliest replenishment ETA: {eta}."}
        self.create_transaction(item_name, "sales", quantity, quote["total_amount"], request_date)
        return {"status": "fulfilled", "item_name": item_name, "quantity": quantity, "total_amount": quote["total_amount"]}

    def handle_request(self, request_text: str, request_date: str) -> Dict:
        """Run end-to-end request processing.

        Args:
            request_text: Customer request body.
            request_date: ISO request date.

        Returns:
            Result dict including inventory, quote, order, and status.
        """
        parsed = parse_request(request_text, self.paper_supplies)
        inv = self.check_inventory(parsed["item_name"], parsed["quantity"], request_date)
        quote = self.create_quote(parsed["item_name"], parsed["quantity"], request_date, inv)
        order = self.fulfill_quote(quote, request_date)
        return {"inventory": inv, "quote": quote, "order": order, "status": order.get("status", "quoted")}
