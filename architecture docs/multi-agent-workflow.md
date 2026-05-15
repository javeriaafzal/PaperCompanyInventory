# Multi-Agent Workflow Diagram (Updated for Step 6)

The system uses **4 agents** (max allowed is 5):
1. OrchestrationAgent (orchestrator)
2. InventoryAgent
3. QuoteAgent
4. OrderingAgent

```mermaid
flowchart TD
    U[Customer Request Text + Request Date] --> O[OrchestrationAgent]

    O --> P[parse_request helper]
    P --> I[InventoryAgent]
    I --> T1[get_stock_level(item_name, as_of_date)]
    I --> T2[get_supplier_delivery_date(request_date, shortage)]
    I --> IR[Inventory result: available / shortage / eta]

    IR --> Q[QuoteAgent]
    Q --> T3[search_quote_history(search_terms, limit)]
    Q --> T4[get_cash_balance(request_date)]
    Q --> QR[Quote result: unit price, discount, total, terms, eta, rationale]

    QR --> O
    O --> D{Auto-accept in eval harness?}

    D -->|Yes| F[OrderingAgent]
    F --> T5[get_stock_level recheck]
    F --> T6[create_transaction(stock_orders)]
    F --> T7[create_transaction(sales)]
    F --> FR[Fulfillment result + status]

    D -->|No| RQ[Return quote only]
    FR --> OUT[Customer-safe response]
    RQ --> OUT
```

## Agent Responsibilities (Non-overlapping)

- **OrchestrationAgent**
  - Routes requests and composes final response.
  - Delegates inventory, quote, and fulfillment in sequence.

- **InventoryAgent**
  - Handles only stock feasibility checks.
  - Computes shortage and delivery ETA for shortages.

- **QuoteAgent**
  - Handles only price construction, discount policy, payment terms, and quote explanation context.
  - Uses cash state and quote history for transparent rationale.

- **OrderingAgent**
  - Handles only execution: recheck stock, create transactions, and finalize order status.

## Tool Mapping and Purpose

- `parse_request`: Parse line item and quantity from natural-language request.
- `get_stock_level`: Determine stock on a specific date.
- `get_supplier_delivery_date`: Estimate supplier ETA for shortages.
- `search_quote_history`: Retrieve similar historical quotes for quote consistency.
- `get_cash_balance`: Set payment terms based on current liquidity.
- `create_transaction`: Record both replenishment buys and finalized sales.

## Orchestration/Data Flow

1. Customer request enters orchestrator.
2. Orchestrator parses request and asks InventoryAgent for availability.
3. QuoteAgent uses inventory outcome + history + cash balance to build quote.
4. In evaluation mode, orchestrator auto-accepts and delegates to OrderingAgent.
5. OrderingAgent writes transactions and returns fulfillment status.
6. Orchestrator returns customer-facing response without exposing sensitive internals.
