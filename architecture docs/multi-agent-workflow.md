# Multi-Agent Workflow Diagram

This updated flowchart shows how a customer inquiry moves through orchestrated agents for inventory checks, quote generation, and order fulfillment.

```mermaid
flowchart LR
    C[Customer Inquiry] --> O[Orchestrator Agent]

    subgraph Inventory_Path[Inventory Path]
        O --> IA[Inventory Agent]
        IA --> DB[(Inventory DB)]
        DB --> IA
        IA --> S{Enough stock?}
        S -->|Yes| AV[Available Now]
        S -->|No| ST[(Supplier Timeline Tool)]
        ST --> IA
        IA --> RE[Reorder Recommendation + ETA]
    end

    subgraph Quote_Path[Quote Path]
        O --> QA[Quote Agent]
        QA --> QH[(Quote History Tool)]
        QH --> QA
        AV --> QA
        RE --> QA
        QA --> PR[Pricing + Discount Rules]
        PR --> QP[Quote Package\nPrice, Terms, ETA]
    end

    QP --> O
    O --> C
    C -->|Accept Quote| O

    subgraph Fulfillment_Path[Fulfillment Path]
        O --> FA[Order Fulfillment Agent]
        FA --> V{Inventory still valid?}
        V -->|No| IA
        V -->|Yes| FO[(Fulfill Order + Update DB)]
        FO --> FA
        FA --> OC[Order Confirmation\nOrder ID, Ship Date, ETA]
    end

    OC --> C
```

## Sequence Notes

1. **Orchestrator Agent** receives the customer request and delegates to specialist agents.
2. **Inventory Agent** validates stock and checks supplier timing when inventory is low.
3. **Quote Agent** combines inventory outcomes with pricing history to produce quote options.
4. **Order Fulfillment Agent** re-validates inventory before committing the order and updating systems.
5. **Tools** provide controlled access to data stores and external services.
