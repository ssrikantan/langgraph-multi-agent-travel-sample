# Project file overview

Brief purpose notes for the main Python scripts.

Packaged to run as a hosted agent in Microsoft Foundry via the LangGraph adapter (see container.py and workflow_core.py).

- container.py — Azure-hosted entrypoint; loads env, sets up observability, and runs the LangGraph adapter via create_agent().
- workflow_core.py — Wraps part_4_graph for Agent Server; loads env, selects credential (MSI or DefaultAzureCredential), exposes create_agent/get_credential.
- travel_agent/app.py — Core LangGraph graph and state machine; wiring of assistants, tools, routing, prompts, and interrupts.
- travel_agent/utilities.py — Shared helper for tool fallbacks and pretty-printing streamed events.
- travel_agent/data/db.py — SQLite path and date adjustment helpers for seeded travel data.
- travel_agent/tools/flight_tools.py — Flight search/update/cancel tool fns backed by SQLite.
- travel_agent/tools/hotels_tools.py — Hotel search/book/update/cancel tool fns.
- travel_agent/tools/car_rental_tools.py — Car rental search/book/update/cancel tool fns.
- travel_agent/tools/excursions.py — Excursion search/book/update/cancel tool fns.
- travel_agent/tools/policies.py — Policy lookup tool using Azure OpenAI.
- travel_agent/stream_demo.py — Streaming helper that runs the graph and auto-approves interrupts for local demos.
- travel_agent/server_demo.py — Non-streaming CLI helper that walks the tutorial Q&A flow with optional approvals.
- clients/cli_runner.py — Local interactive CLI that streams events and prompts for approvals; uses stream_demo.
- clients/http_client.py — Minimal HTTP/SSE client for the hosted agent (send one message, stream response or poll).
