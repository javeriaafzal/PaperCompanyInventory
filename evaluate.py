"""Test harness for scenario evaluation."""

import os
import time

import pandas as pd
from sqlalchemy import Engine

from agents import OrchestrationAgent
from helpers import generate_financial_report, init_database


def run_test_scenarios(db_engine: Engine, paper_supplies: list) -> list:
    """Run sample requests and export evaluation results.

    Args:
        db_engine: SQLAlchemy engine for seeded state.
        paper_supplies: Product catalog for orchestration.

    Returns:
        List of per-request evaluation records.
    """
    init_database(db_engine, paper_supplies, db_engine)
    quote_requests_sample = pd.read_csv("quote_requests_sample.csv") if os.path.exists("quote_requests_sample.csv") else pd.DataFrame([
        {"job": "office manager", "event": "team offsite", "request": "Need 300 A4 paper for packets", "request_date": "01/05/25"}
    ])
    quote_requests_sample["request_date"] = pd.to_datetime(quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce")
    quote_requests_sample.dropna(subset=["request_date"], inplace=True)
    quote_requests_sample = quote_requests_sample.sort_values("request_date")

    orchestrator = OrchestrationAgent(db_engine, paper_supplies)
    results = []
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")
        response = orchestrator._process_request(f"{row['request']} (Date of request: {request_date})", request_date)
        inv, quote, order = response["inventory"], response["quote"], response["order"]
        customer_response = orchestrator._compose_customer_response(quote, order)
        profitability = round(
            float(quote["total_amount"])
            - float(quote.get("estimated_cost", quote["quantity"] * quote["unit_price"] * 0.8)),
            2,
        )
        financials = generate_financial_report(db_engine, request_date)
        order_status = order.get("status", "not_ordered")
        results.append({
            "request_id": idx + 1,
            "request_date": request_date,
            "request_text": row["request"],
            "customer_response": customer_response["message"],
            "reason_code": customer_response["quote"]["reason_code"],
            "item_name": quote["item_name"],
            "quantity": quote["quantity"],
            "available_at_request": inv["available"],
            "shortage_units": inv["shortage"],
            "eta_if_short": inv["eta"],
            "quoted_unit_price": quote["unit_price"],
            "base_subtotal": quote["base_subtotal"],
            "discount_rate": quote["discount_rate"],
            "quoted_total": quote["total_amount"],
            "order_status": order_status,
            "orders_accommodated": order_status == "fulfilled",
            "competitive_pricing": quote["total_amount"] <= quote["base_subtotal"] and profitability >= 0,
            "profitability_dollars": profitability,
            "cash_balance": round(float(financials["cash_balance"]), 2),
            "inventory_value": round(float(financials["inventory_value"]), 2),
        })
        time.sleep(0.05)

    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results
