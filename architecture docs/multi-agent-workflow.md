# Multi-Agent Workflow Diagram (Updated for Step 6)

The system uses **4 agents** (max allowed is 5):
1. OrchestrationAgent (orchestrator)
2. InventoryAgent
3. QuoteAgent
4. OrderingAgent

```mermaid
flowchart LR
    U[Customer request] --> O[OrchestrationAgent]
    O --> P[parse_request]

    P --> I[InventoryAgent]
    I --> I1[get_stock_level]
    I --> I2[get_supplier_delivery_date]
    I --> IR[Inventory result]

    IR --> Q[QuoteAgent]
    Q --> Q1[search_quote_history]
    Q --> Q2[get_cash_balance]
    Q --> QR[Quote result]

    QR --> D{Auto accept in eval mode}
    D -->|No| RQ[Return quote]
    D -->|Yes| F[OrderingAgent]

    F --> F1[get_stock_level recheck]
    F --> F2[create_transaction stock_order]
    F --> F3[create_transaction sale]
    F --> FR[Fulfillment result]

    RQ --> OUT[Customer response]
    FR --> OUT
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
