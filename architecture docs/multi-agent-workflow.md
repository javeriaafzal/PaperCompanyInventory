# Multi-Agent Workflow Diagram

This diagram shows how customer inquiries move through orchestrated agents for inventory checks, quote generation, and order fulfillment.

```mermaid
flowchart TD
    C[Customer Inquiry\n(product, quantity, delivery target)] --> O[Orchestrator Agent]

    O --> T1[(Tool: Inventory Check DB)]
    O --> IQ[Inventory Agent]
    O --> QG[Quote Agent]
    O --> OF[Order Fulfillment Agent]

    IQ --> T1
    T1 --> IQ
    IQ --> D1{Enough stock?}

    D1 -- Yes --> IQR[Inventory response:\navailable now]
    D1 -- No --> T3[(Tool: Supplier Timeline)]
    T3 --> IQ
    IQ --> R1{Reorder needed?}
    R1 -- Yes --> RR[Recommend reorder qty\nand ETA]
    R1 -- No --> IQR

    O --> T2[(Tool: Quote History)]
    T2 --> QG
    IQR --> QG
    RR --> QG
    QG --> Q1[Apply pricing rules\n+ bulk discount tiers]
    QG --> Q2[Build quote options:\nstandard vs expedited]
    Q1 --> QR[Quote package\n(price, terms, ETA)]
    Q2 --> QR

    QR --> O
    O --> C
    C -->|Accept quote| O

    O --> OF
    OF --> V1{Inventory still valid?}
    V1 -- No --> IQ
    V1 -- Yes --> T4[(Tool: Fulfill Order / Update DB)]
    T4 --> OF
    OF --> O
    O --> CONF[Order Confirmation\n(order id, ship date, delivery ETA)]
    CONF --> C

    %% Optional external channels
    OF --> EXT[Carrier/Supplier APIs]
```

## Sequence Notes

1. **Orchestrator Agent** receives the customer request and delegates to specialist agents.
2. **Inventory Agent** validates stock and decides whether reorder is needed based on thresholds and supplier lead time.
3. **Quote Agent** combines inventory results with quote history to produce optimized pricing and discount strategies.
4. **Order Fulfillment Agent** re-validates inventory at commit time, then fulfills the order and updates records.
5. **Tools** serve as controlled interfaces to internal databases and external supplier/delivery services.
