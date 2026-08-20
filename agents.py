"""Agent definitions and orchestration workflow."""

import json
from typing import Any, Dict, Union

from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import Engine

from helpers import (
    create_transaction,
    generate_financial_report,
    get_all_inventory,
    get_cash_balance,
    get_stock_level,
    get_supplier_delivery_date,
    parse_request,
    search_quote_history,
)


def _tool_invocation_model(tool_name: str) -> FunctionModel:
    """Create a deterministic pydantic-ai model that invokes one registered tool.

    The first model request turns the JSON user prompt into a tool call. After
    pydantic-ai executes the tool, the second model request returns the tool
    result as JSON text, letting callers consume the worker's output while still
    exercising pydantic-ai's ``run_sync`` and tool execution path.
    """

    def invoke_tool(messages: list, _agent_info: AgentInfo) -> ModelResponse:
        for message in reversed(messages):
            for part in getattr(message, "parts", []):
                if isinstance(part, ToolReturnPart):
                    return ModelResponse([TextPart(json.dumps(part.content))])

        for message in reversed(messages):
            for part in getattr(message, "parts", []):
                content = getattr(part, "content", None)
                if isinstance(content, str):
                    try:
                        payload = json.loads(content)
                    except json.JSONDecodeError:
                        continue
                    return ModelResponse([ToolCallPart(tool_name, payload)])

        return ModelResponse([TextPart("{}")])

    return FunctionModel(invoke_tool, model_name=f"deterministic-{tool_name}-model")


def _run_worker(agent: Agent, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke a pydantic-ai worker agent synchronously and parse JSON output."""
    result = agent.run_sync(json.dumps(payload))
    output = json.loads(result.output)
    return output if isinstance(output, dict) else {"result": output}


class InventoryAgent:
    """Worker agent responsible for stock checks and replenishment ETAs."""

    def __init__(self, db_engine: Engine) -> None:
        self.db_engine = db_engine
        self.agent = Agent(
            _tool_invocation_model("check_inventory"),
            name="inventory_agent",
            system_prompt="Check inventory availability and predict replenishment ETA.",
        )
        self._register_tools()

    def _register_tools(self) -> None:
        @self.agent.tool_plain
        def check_inventory(
            item_name: str, quantity: int, request_date: str
        ) -> Dict[str, Union[bool, int, str, None]]:
            """Evaluate stock availability and shortage ETA."""
            stock_df = get_stock_level(self.db_engine, item_name, request_date)
            current_stock = (
                int(stock_df["current_stock"].iloc[0]) if not stock_df.empty else 0
            )
            available = current_stock >= quantity
            shortage = max(0, quantity - current_stock)
            eta = (
                None
                if available
                else get_supplier_delivery_date(request_date, shortage)
            )
            return {
                "available": available,
                "current_stock": current_stock,
                "shortage": shortage,
                "eta": eta,
            }

        @self.agent.tool_plain
        def list_inventory(as_of_date: str) -> list[dict]:
            """Get computed stock levels for every inventory item."""
            return get_all_inventory(self.db_engine, as_of_date).to_dict(
                orient="records"
            )

    def check_inventory(
        self, item_name: str, quantity: int, request_date: str
    ) -> Dict[str, Any]:
        return _run_worker(
            self.agent,
            {
                "item_name": item_name,
                "quantity": quantity,
                "request_date": request_date,
            },
        )


class QuoteAgent:
    """Worker agent responsible for pricing, discounts, and quote terms."""

    def __init__(self, db_engine: Engine, paper_supplies: list) -> None:
        self.db_engine = db_engine
        self.paper_supplies = paper_supplies
        self.agent = Agent(
            _tool_invocation_model("create_quote"),
            name="quote_agent",
            system_prompt="Generate competitive, profitable quotes based on inventory and cash state.",
        )
        self._register_tools()

    def _register_tools(self) -> None:
        @self.agent.tool_plain
        def create_quote(
            item_name: str, quantity: int, request_date: str, inventory_result: Dict
        ) -> Dict:
            """Build a profitable quote with light competitive discounting."""
            unit_price = next(
                (
                    p["unit_price"]
                    for p in self.paper_supplies
                    if p["item_name"] == item_name
                ),
                0.1,
            )
            base_subtotal = round(unit_price * quantity, 2)
            discount_rate = (
                0.00
                if quantity < 200
                else 0.03 if quantity < 1000 else 0.06 if quantity < 5000 else 0.09
            )
            discounted_subtotal = round(base_subtotal * (1 - discount_rate), 2)
            estimated_cost = round(base_subtotal * 0.80, 2)
            minimum_profitable = round(estimated_cost * 1.08, 2)
            total_amount = max(discounted_subtotal, minimum_profitable)
            historical = search_quote_history(
                self.db_engine, [item_name.split()[0]], limit=3
            )
            terms = (
                "Net 30"
                if get_cash_balance(self.db_engine, request_date) >= 0
                else "Prepay"
            )
            return {
                "item_name": item_name,
                "quantity": quantity,
                "unit_price": unit_price,
                "base_subtotal": base_subtotal,
                "discount_rate": discount_rate,
                "estimated_cost": estimated_cost,
                "total_amount": round(total_amount, 2),
                "eta": inventory_result["eta"],
                "terms": terms,
                "history_matches": historical,
            }

        @self.agent.tool_plain
        def quote_history(search_terms: list[str], limit: int = 5) -> list[dict]:
            """Search historical quotes by keyword."""
            return search_quote_history(self.db_engine, search_terms, limit)

    def create_quote(
        self, item_name: str, quantity: int, request_date: str, inventory_result: Dict
    ) -> Dict[str, Any]:
        return _run_worker(
            self.agent,
            {
                "item_name": item_name,
                "quantity": quantity,
                "request_date": request_date,
                "inventory_result": inventory_result,
            },
        )


class OrderingAgent:
    """Worker agent responsible for order finalization and sales records."""

    def __init__(self, db_engine: Engine) -> None:
        self.db_engine = db_engine
        self.agent = Agent(
            _tool_invocation_model("fulfill_quote"),
            name="ordering_agent",
            system_prompt="Execute stock replenishment and sales transactions for accepted quotes.",
        )
        self._register_tools()

    def _register_tools(self) -> None:
        @self.agent.tool_plain
        def fulfill_quote(quote: Dict, request_date: str) -> Dict:
            """Attempt to fulfill a quote and create sales transaction."""
            item_name = quote["item_name"]
            quantity = int(quote["quantity"])
            current_stock = int(
                get_stock_level(self.db_engine, item_name, request_date)[
                    "current_stock"
                ].iloc[0]
            )
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
            create_transaction(
                self.db_engine,
                item_name,
                "sales",
                quantity,
                quote["total_amount"],
                request_date,
            )
            return {
                "status": "fulfilled",
                "item_name": item_name,
                "quantity": quantity,
                "total_amount": quote["total_amount"],
            }

        @self.agent.tool_plain
        def record_transaction(
            item_name: str,
            transaction_type: str,
            quantity: int,
            price: float,
            date: str,
        ) -> int:
            """Create a transaction for sales or stock replenishment."""
            return create_transaction(
                self.db_engine, item_name, transaction_type, quantity, price, date
            )

    def fulfill_quote(self, quote: Dict, request_date: str) -> Dict[str, Any]:
        return _run_worker(self.agent, {"quote": quote, "request_date": request_date})


class ReportingAgent:
    """Worker agent responsible for financial and inventory reporting snapshots."""

    def __init__(self, db_engine: Engine) -> None:
        self.db_engine = db_engine
        self.agent = Agent(
            _tool_invocation_model("financial_report"),
            name="reporting_agent",
            system_prompt="Generate financial and inventory snapshots for reporting.",
        )
        self._register_tools()

    def _register_tools(self) -> None:
        @self.agent.tool_plain
        def financial_report(as_of_date: str) -> Dict[str, Union[str, float]]:
            """Generate financial summary metrics as of a date."""
            return generate_financial_report(self.db_engine, as_of_date)

    def financial_report(self, as_of_date: str) -> Dict[str, Any]:
        return _run_worker(self.agent, {"as_of_date": as_of_date})


class OrchestrationAgent:
    """Coordinate inventory, quoting, fulfillment, and reporting worker agents."""

    def __init__(self, db_engine: Engine, paper_supplies: list):
        self.db_engine = db_engine
        self.paper_supplies = paper_supplies
        self.inventory_agent = InventoryAgent(db_engine)
        self.quote_agent = QuoteAgent(db_engine, paper_supplies)
        self.ordering_agent = OrderingAgent(db_engine)
        self.reporting_agent = ReportingAgent(db_engine)

    def _process_request(self, request_text: str, request_date: str) -> Dict[str, Any]:
        """Run internal workflow and retain agent details for evaluation/reporting."""
        parsed = parse_request(request_text, self.paper_supplies)
        inv = self.inventory_agent.check_inventory(
            parsed["item_name"], parsed["quantity"], request_date
        )
        if not parsed.get("catalog_match", True):
            inv["available"] = False
            inv["shortage"] = parsed["quantity"]
            inv["reason"] = f"{parsed['item_name']} is not in the product catalog."
        quote = self.quote_agent.create_quote(
            parsed["item_name"], parsed["quantity"], request_date, inv
        )
        order = self.ordering_agent.fulfill_quote(quote, request_date)
        return {
            "inventory": inv,
            "quote": quote,
            "order": order,
            "status": order.get("status", "quoted"),
        }

    def _compose_customer_response(
        self, quote: Dict[str, Any], order: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a customer-safe response that omits internal pricing and state."""
        discount_rate = float(quote.get("discount_rate", 0.0))
        discount_applied = (
            f"{discount_rate:.0%}" if discount_rate > 0 else "No discount applied"
        )
        status = order.get("status", "quoted")
        eta = order.get("eta") or quote.get("eta")
        fulfillment = status.capitalize()
        if eta and status != "fulfilled":
            fulfillment = f"{fulfillment}; estimated availability {eta}"

        customer_quote = {
            "item": quote["item_name"],
            "quantity": int(quote["quantity"]),
            "total_price": round(float(quote["total_amount"]), 2),
            "discount_applied": discount_applied,
            "payment_terms": quote["terms"],
            "fulfillment_status": fulfillment,
        }
        message_parts = [
            f"Quote for {customer_quote['quantity']} units of {customer_quote['item']}:",
            f"total price ${customer_quote['total_price']:.2f}.",
            f"Discount: {customer_quote['discount_applied']}.",
            f"Payment terms: {customer_quote['payment_terms']}.",
            f"Fulfillment status: {customer_quote['fulfillment_status']}.",
        ]
        return {
            "message": " ".join(message_parts),
            "quote": customer_quote,
        }

    def handle_request(self, request_text: str, request_date: str) -> Dict[str, Any]:
        """Return a readable, customer-facing response for an incoming request."""
        result = self._process_request(request_text, request_date)
        return self._compose_customer_response(result["quote"], result["order"])
