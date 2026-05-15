# Multi-Agent Workflow Diagram

This flowchart reflects the implemented Step 4 agent orchestration in `multi_agent_system.py`.

```mermaid
flowchart LR
    C[Customer Inquiry] --> O[Orchestrator Agent]

    subgraph Inventory_Path[Inventory Path]
        O --> IA[Inventory Agent]
        IA --> DB[(SQLite Inventory DB)]
        DB --> IA
        IA --> S{Enough stock?}
        S -->|Yes| AV[Available Now]
        S -->|No| ETA[(estimate_supplier_delivery helper)]
        ETA --> IA
        IA --> RE[Reorder Recommendation + ETA]
    end

    subgraph Quote_Path[Quote Path]
        O --> QA[Quote Agent]
        QA --> TX[(Transactions Ledger via DB helper)]
        TX --> QA
        AV --> QA
        RE --> QA
        QA --> BAL[(get_current_cash_balance helper)]
        BAL --> QA
        QA --> QP[Quote Package\nPrice, Terms, ETA]
    end

    QP --> O
    O --> C
    C -->|Accept Quote| O

    subgraph Fulfillment_Path[Fulfillment Path]
        O --> FA[Order Fulfillment Agent]
        FA --> V{Inventory still valid?}
        V -->|No| IA
        V -->|Yes| FO[(update_stock + record_transaction helpers)]
        FO --> FA
        FA --> OC[Order Confirmation\nOrder ID, Ship Date, ETA]
    end

    OC --> C
```

## Implementation Notes (Step 4)

- The orchestrator is implemented as `OrchestratorAgent` and manages control/data flow.
- Worker agents are implemented as:
  - `InventoryAgent`
  - `QuoteAgent`
  - `OrderFulfillmentAgent`
- Tooling is wired directly to starter helpers in `project_starter.py`:
  - `init_db`
  - `get_stock` / `update_stock`
  - `record_transaction`
  - `estimate_supplier_delivery`
  - `get_current_cash_balance`
- The low-stock branch produces an ETA and returns a quote with replenishment timing.
- The fulfillment branch revalidates stock before committing inventory and ledger writes.
