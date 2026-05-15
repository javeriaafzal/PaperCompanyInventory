# Multi-Agent Workflow Diagram

This updated flowchart shows how a customer inquiry moves through orchestrated agents for inventory checks, quote generation, and order fulfillment.

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
        V -->|Yes| FO[(stock update + transaction write helpers)]
        FO --> FA
        FA --> OC[Order Confirmation\nOrder ID, Ship Date, ETA]
    end

    OC --> C
```

## Step 2: Starter Code Review Notes (`project_starter.py`)

> **Important repo note:** the file `project_starter.py` is not present in this repository snapshot, so the notes below are based on the capabilities described in the assignment prompt.

### Function-by-function understanding (from provided capability list)

1. **SQLite initialization / connection management function(s)**  
   Responsible for creating the database, initializing required tables, and returning a usable connection/session for other helpers.

2. **Inventory stock management function(s)**  
   Reads and mutates on-hand quantities (e.g., add stock, decrement stock on allocation/sale, and check whether requested quantity is available).

3. **Financial transaction generation/tracking function(s)**  
   Persists cashflow events (sales revenue, purchasing costs, adjustments) to a transaction ledger to support later reporting.

4. **Supplier delivery-date estimator utility**  
   Computes expected replenishment timing when stock is insufficient, enabling quote ETA and reorder decisions.

5. **Current cash-balance utility**  
   Aggregates transaction records to produce a current liquidity value used by planning/purchasing logic.

6. **Bottom-of-file evaluation stub**  
   A local test harness that exercises core flows; useful for quickly validating agent/tool wiring and regression-checking behavior during iteration.

## Updated Tool Plan (replacing hypothetical tools from Step 1)

The initial generic tools ("Supplier Timeline Tool", "Quote History Tool", "Fulfill Order + Update DB") should be replaced with starter-code-backed helper calls:

- **`init_db` / DB bootstrap helper(s)** for startup and persistence layer readiness.
- **`get_stock` + `update_stock` helper(s)** for inventory checks and reservation/fulfillment writes.
- **`record_transaction` helper** for every financial state change.
- **`estimate_supplier_delivery` helper** for low-stock ETA generation.
- **`get_current_cash_balance` helper** for quote risk checks and purchase feasibility.
- **Provided evaluation stub** as the standard integration check before accepting workflow changes.

## Sequence Notes

1. **Orchestrator Agent** receives the customer request and delegates to specialist agents.
2. **Inventory Agent** validates stock and calls delivery-estimation helpers when inventory is low.
3. **Quote Agent** combines inventory outcomes and cash constraints to produce quote options.
4. **Order Fulfillment Agent** re-validates inventory before committing the order and writing inventory + ledger updates.
5. **Tools** are concrete helper-function calls from `project_starter.py` instead of external/hypothetical services.
