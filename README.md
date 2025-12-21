# Travel Support Hosted Agent (LangGraph sample)

This project is a modified LangGraph tutorial sample tailored to exercise Microsoft Foundry Hosted Agents. It wires multiple assistants (flights, hotels, cars, excursions) into a single graph and can be run locally or as a hosted agent.

## Hosted Agent docs
- Hosted agents (concepts): https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/hosted-agents?view=foundry&tabs=cli
- VS Code workflow for hosted agents (Python): https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/vs-code-agents-workflow-pro-code?view=foundry&tabs=windows-powershell&pivots=python

## What’s included
- Multi-agent LangGraph in [travel_agent/app.py](travel_agent/app.py) with routing, tools, and interrupt handling.
- Azure OpenAI-backed tools for flight/hotel/car/excursion flows and a policy lookup tool.
- Azure hosting entrypoint [container.py](container.py) and adapter wrapper [workflow_core.py](workflow_core.py).
- Local demos: streaming CLI [clients/cli_runner.py](clients/cli_runner.py), HTTP/SSE client [clients/http_client.py](clients/http_client.py).
- Env samples in [.env.example](.env.example).

## Prerequisites
- Python 3.10+ and `pip install -r requirements.txt`
- Azure OpenAI + Tavily keys (see `.env.example` for required vars)
- For hosted runs: Managed Identity or DefaultAzureCredential access to your Azure OpenAI resource

## Running locally (quick start)
1) Copy `.env.example` to `.env` and adjust values.
2) `python -m clients.cli_runner` (interactive streaming demo), or `python -m clients.http_client "Hi there"` against a running server.

## Deploying as a hosted agent (Foundry)
1) Ensure env vars in your deployment (matches `.env.example`).
2) Use [container.py](container.py) with the LangGraph adapter (see [workflow_core.py](workflow_core.py)).
3) Follow the Hosted Agent docs (links above) to publish in Microsoft Foundry. Once deployed, chat in the Foundry Playground.

## Sample conversation script (multi-agent flow)
Use these messages in order to exercise the full flow (the sample data uses passenger_id `3442 587242`):
1. "Hi there, what time is my flight?"
2. "Am i allowed to update my flight to something sooner? I want to leave later today."
3. "Update my flight to sometime next week then"
4. "The next available option is great"
5. "what about lodging and transportation?"
6. "Yeah i think i'd like an affordable hotel for my week-long stay (7 days). And I'll want to rent a car."
7. "OK could you place a reservation for your recommended hotel? It sounds nice."
8. "yes go ahead and book anything that's moderate expense and has availability."
9. "Now for a car, what are my options?"
10. "Awesome let's just get the cheapest option. Go ahead and book for 7 days"
11. "Cool so now what recommendations do you have on excursions?"
12. "Are they available while I'm there?"
13. "interesting - i like the museums, what options are there? "
14. "OK great pick one and book it for my second day there."

## Notes
- Default passenger_id in sample data: `3442 587242`. Provide it in chat or via `configurable.passenger_id` when calling the hosted agent.
- The sample originates from LangGraph tutorials and was adapted to validate Hosted Agents in Microsoft Foundry.
