"""Implementation of Step 4 multi-agent orchestration.

Uses simple Python agents wired to starter helper tools. The interfaces are
compatible with later replacement by pydantic-ai Agent wrappers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from project_starter import (
    QuoteInput,
    StockStatus,
    estimate_supplier_delivery,
    get_current_cash_balance,
    get_stock,
    init_db,
    record_transaction,
    update_stock,
)


@dataclass(frozen=True)
class InventoryResult:
    sku: str
    requested_qty: int
    on_hand_qty: int
    available: bool
    shortage_qty: int
    replenishment_eta: str | None


@dataclass(frozen=True)
class QuoteResult:
    sku: str
    quantity: int
    subtotal: float
    terms: str
    eta: str | None
    cash_balance_snapshot: float


@dataclass(frozen=True)
class FulfillmentResult:
    order_id: str
    sku: str
    quantity: int
    ship_eta: str
    final_on_hand_qty: int


class InventoryAgent:
    def check_availability(self, conn, sku: str, requested_qty: int) -> InventoryResult:
        on_hand = get_stock(conn, sku)
        status = StockStatus(sku=sku, requested_qty=requested_qty, on_hand_qty=on_hand)

        if status.is_available:
            return InventoryResult(sku, requested_qty, on_hand, True, 0, None)

        shortage = requested_qty - on_hand
        eta = estimate_supplier_delivery(shortage)
        return InventoryResult(sku, requested_qty, on_hand, False, shortage, eta)


class QuoteAgent:
    def build_quote(self, conn, quote_input: QuoteInput, inv: InventoryResult) -> QuoteResult:
        subtotal = round(quote_input.quantity * quote_input.unit_price, 2)
        cash_balance = get_current_cash_balance(conn)

        terms = "Net 30"
        if cash_balance < 0:
            terms = "Prepayment required"

        eta = None if inv.available else inv.replenishment_eta
        return QuoteResult(
            sku=quote_input.sku,
            quantity=quote_input.quantity,
            subtotal=subtotal,
            terms=terms,
            eta=eta,
            cash_balance_snapshot=round(cash_balance, 2),
        )


class OrderFulfillmentAgent:
    def fulfill_order(self, conn, order_id: str, quote: QuoteResult) -> FulfillmentResult:
        # Revalidate on-hand inventory before committing.
        latest_on_hand = get_stock(conn, quote.sku)
        if latest_on_hand < quote.quantity:
            shortage = quote.quantity - latest_on_hand
            eta = estimate_supplier_delivery(shortage)
            raise ValueError(f"Order cannot be fulfilled now. Short by {shortage}. ETA {eta}")

        final_qty = update_stock(conn, quote.sku, -quote.quantity)
        record_transaction(conn, "sale", quote.subtotal, f"Order {order_id} for {quote.sku}")
        return FulfillmentResult(
            order_id=order_id,
            sku=quote.sku,
            quantity=quote.quantity,
            ship_eta="ships in 1 business day",
            final_on_hand_qty=final_qty,
        )


class OrchestratorAgent:
    def __init__(self) -> None:
        self.inventory_agent = InventoryAgent()
        self.quote_agent = QuoteAgent()
        self.fulfillment_agent = OrderFulfillmentAgent()

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        conn = init_db()
        quote_input = QuoteInput(
            sku=request["sku"],
            quantity=int(request["quantity"]),
            unit_price=float(request["unit_price"]),
        )

        inventory_result = self.inventory_agent.check_availability(
            conn, quote_input.sku, quote_input.quantity
        )
        quote_result = self.quote_agent.build_quote(conn, quote_input, inventory_result)

        response: dict[str, Any] = {
            "inventory": inventory_result,
            "quote": quote_result,
            "status": "quoted",
        }

        if request.get("accept_quote") is True and inventory_result.available:
            fulfillment = self.fulfillment_agent.fulfill_order(
                conn, order_id=request.get("order_id", "AUTO-ORDER-001"), quote=quote_result
            )
            response["fulfillment"] = fulfillment
            response["status"] = "fulfilled"

        return response


if __name__ == "__main__":
    orchestrator = OrchestratorAgent()
    print(
        orchestrator.run(
            {
                "sku": "A4-CASE",
                "quantity": 25,
                "unit_price": 42.50,
                "accept_quote": False,
            }
        )
    )
