# Paper Company Multi-Agent Inventory Project

Welcome to the starter code repository for the **Paper Company Multi-Agent Inventory Project**. This project focuses on designing, building, and testing a multi-agent system that supports day-to-day business operations at a fictional paper manufacturing company.

## Project Context

You are acting as an AI consultant for a fictional paper company that wants to modernize key workflows using autonomous, text-coordinated agents. The system should automate:

- **Inventory checks** and restocking decisions
- **Quote generation** for incoming sales inquiries
- **Order fulfillment** including supplier logistics and transactions

### Core Constraints

- Use a maximum of **5 agents**
- Process inputs and outputs through **text-based communication only**
- Coordinate the full workflow across inventory, quoting, and fulfillment

The project is intended to exercise agent orchestration, data handling, and practical LLM workflow design using tools such as `pydantic-ai`, `smolagents`, or equivalent frameworks.

---

## What’s Included

This repository currently includes:

- `project_starter.py`: Starter script and baseline scaffold for agent logic
- `multi_agent_system.py`: Main multi-agent orchestration implementation file
- `quote.csv`: Historical quote reference data
- `quote_requests.csv`: Incoming customer quote request dataset
- `quote_requests_sample.csv`: Small sample request set for quick test scenarios
- `architecture docs/multi-agent-workflow.md`: Workflow and architecture documentation

### Purpose of the CSV Files

Because this project uses a shared quoting-and-operations data pattern, each CSV has a specific role:

- `quote.csv`
  - Stores historical quote outcomes (e.g., prior pricing patterns and discount behavior)
  - Used by quoting logic to make pricing more consistent with past business decisions
  - Serves as a lightweight reference dataset for evaluation and regression checks

- `quote_requests.csv`
  - Represents production-like inbound customer quote requests
  - Used as the primary workload for quote-generation and downstream inventory/fulfillment decisions
  - Helps validate how agents parse request fields and apply business rules at scale

- `quote_requests_sample.csv`
  - Contains a smaller, curated subset of request scenarios
  - Intended for quick local validation, smoke tests, and iteration while developing agent logic
  - Useful for debugging interactions before running larger/full datasets

---

## Local Setup Instructions

### 1) Install Dependencies

Use Python 3.8+ (or newer), then install project dependencies:

```bash
pip install -r requirements.txt
```


For other `pydantic-ai` framework, use each framework’s official installation guidance.

### 2) Create a `.env` File

Add your API key:
If your environment uses an OpenAI-compatible proxy endpoint, configure that according to your runtime requirements.

---

## How to Run the Project

1. Implement your agents in the designated multi-agent section of the starter/implementation script.
2. Run the test scenario entry point (for example, the project’s provided simulation runner).
3. Verify that the system coordinates:
   - inventory checks,
   - quote generation,
   - and order/fulfillment decisions.

Typical outputs should include:

- Agent-level responses/logs
- Inventory and cash-state updates
- End-of-run summary metrics
- Generated evaluation artifacts (such as CSV test logs)

---

## Tips for Success

- Read **workflow diagram** before coding to define clear agent responsibilities.
- Validate each tool path (inventory, quote, fulfillment) independently before full orchestration.
- Include **explicit dates** in inter-agent payloads when relevant to business logic.
- Keep quote logic consistent with historical data and discount rules.
- Use canonical item names consistently to prevent transaction mismatches.

---

## Agent Framework Selection

For this project, the current baseline framework choice is **pydantic-ai**.

### Why pydantic-ai

- Typed schemas for predictable quote and inventory workflows
- Strong validation to reduce business-logic errors
- Flexible orchestration patterns for multi-step agent collaboration

---

## Contributing

Contributions are welcome. For improvements, please open an issue or pull request describing:

- the problem being solved,
- the proposed approach,
- and any testing performed.
