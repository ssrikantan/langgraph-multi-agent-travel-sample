# Travel Support Hosted Agent (LangGraph sample)

This project is a modified version of the LangGraph tutorial [here](https://langchain-ai.github.io/langgraph/tutorials/customer-support/customer-support/#part-4-specialized-workflows), tailored to exercise Microsoft Foundry Hosted Agents. It wires multiple assistants (flights, hotels, cars, excursions) into a single graph and can be run locally or as a hosted agent.

## Hosted Agent docs
- Hosted agents (concepts): https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/hosted-agents?view=foundry&tabs=cli
- VS Code workflow for hosted agents (Python): https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/vs-code-agents-workflow-pro-code?view=foundry&tabs=windows-powershell&pivots=python

## What’s included
- Multi-agent LangGraph in [travel_agent/app.py](travel_agent/app.py) with routing, tools, and interrupt handling.
- Azure OpenAI-backed tools for flight/hotel/car/excursion flows and a policy lookup tool.
- Azure hosting entrypoint [container.py](container.py) and adapter wrapper [workflow_core.py](workflow_core.py).
- Local demos: streaming CLI [clients/cli_runner.py](clients/cli_runner.py), HTTP/SSE client [clients/http_client.py](clients/http_client.py).
- Env samples in [.env.example](.env.example).

## File overview
Packaged to run as a hosted agent in Microsoft Foundry via the LangGraph adapter.

- **container.py** — Azure-hosted entrypoint; loads env, sets up observability, and runs the LangGraph adapter via create_agent().
- **workflow_core.py** — Exposes create_agent() that wraps part_4_graph with the Agent Framework adapter; handles credential selection.
- **travel_agent/app.py** — Core LangGraph graph (part_4_graph) with multi-agent routing, tools, state management, and checkpointing.
- travel_agent/utilities.py — Shared helper for tool fallbacks and pretty-printing streamed events.
- travel_agent/data/db.py — SQLite path and date adjustment helpers for seeded travel data.
- travel_agent/tools/flight_tools.py — Flight search/update/cancel tool fns backed by SQLite.
- travel_agent/tools/hotels_tools.py — Hotel search/book/update/cancel tool fns.
- travel_agent/tools/car_rental_tools.py — Car rental search/book/update/cancel tool fns.
- travel_agent/tools/excursions.py — Excursion search/book/update/cancel tool fns.
- travel_agent/tools/policies.py — Policy lookup tool using Azure OpenAI.
- agent-client/ — SDK clients for interacting with the Foundry-hosted agent (see folder for details).
- test_local.py — Quick local test to verify the LangGraph works in-process.

## Prerequisites
- Python 3.10+ and `pip install -r requirements.txt`
- Azure OpenAI + Tavily keys (see `.env.example` for required vars)
- For hosted runs: Managed Identity or DefaultAzureCredential access to your Azure OpenAI resource

## Running locally (quick start)
1) Copy `.env.example` to `.env` and adjust values.
2) Run `python test_local.py` for a quick test, or use the SDK clients in `agent-client/` to interact with the hosted agent.

### Providing passenger_id
The sample data uses passenger_id `3442 587242`. You can provide it in two ways:
1. **In conversation**: Just mention it in your message (e.g., "my passenger id is 3442 587242")
2. **Default from .env**: Set `DEFAULT_PASSENGER_ID` in your `.env` file

## Deploying as a hosted agent (Foundry)
1) Ensure env vars in your deployment (matches `.env.example`).
2) Use [container.py](container.py) with the LangGraph adapter (see [workflow_core.py](workflow_core.py)).
3) Follow the Hosted Agent docs (links above) to publish in Microsoft Foundry. Once deployed, chat in the Foundry Playground.

### Hosted Agent telemetry and streaming (Foundry)
- Telemetry (traces) is automatically captured per `conversation_id` when the LangGraph is hosted as a Foundry Hosted Agent; you can inspect runs and tool activity in the Foundry UI. Example trace view: ![Tracing](images/Tracing.png)
- The SDK client sample also demonstrates **streaming responses** with inline hints of the tool calls LangGraph is performing. Example streaming view: ![Streaming responses](images/streaming-responses.png)

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

## Request/Response Pipeline (Foundry → LangGraph)

Understanding how config and state flow through the system:

### 1. Client Request
Client (e.g., [foundry-agent-client-sdk.py](agent-client/foundry-agent-client-sdk.py)) sends messages to the Foundry Agent Server endpoint. The server assigns or receives a `conversation_id` to track the conversation.

### 2. Container Startup
[container.py](container.py) starts the Agent Framework server:
- Loads environment variables and credentials
- Creates the LangGraph adapter via `create_agent()` from [workflow_core.py](workflow_core.py)
- Calls `adapter.run()` to listen for incoming requests

### 3. Azure SDK Adapter (`from_langgraph`)
When a request arrives, the `azure.ai.agentserver.langgraph.from_langgraph()` adapter (internal SDK code):
- Extracts `conversation_id` from the incoming Foundry request
- Creates a `RunnableConfig` with `{"configurable": {"thread_id": conversation_id}}`
- Also includes any `passenger_id` from the request in the config
- Calls `part_4_graph.invoke(state, config=config)` directly with this config

### 4. LangGraph Execution
The travel agent graph (`part_4_graph`):
- Uses the `thread_id` from config to load checkpointed state (passenger_id, dialog_state, etc.)
- Processes the new user message
- Tools access `passenger_id` from `config.get("configurable", {}).get("passenger_id")`
- Updates state and saves checkpoint
- Returns updated state with new messages

### 5. Response Flow
The adapter:
- Receives the final state from the graph
- Extracts messages for the response
- Formats according to Foundry's response protocol
- Sends back to the client (streaming or non-streaming)

### Key Points
- **Single graph, single checkpoint** - No wrapper graph, simpler state management
- **You don't create the config** - the `from_langgraph` adapter creates it from Foundry's `conversation_id`
- **Thread persistence is automatic** - the `thread_id` ensures conversation state is maintained across multiple turns
- **passenger_id flows through config** - Tools receive it via `config.get("configurable", {}).get("passenger_id")`

---

## Conversation State Management: Foundry ↔ LangGraph

This section explains how **Foundry Hosted Agents** manage conversation state and how it maps to **LangGraph's checkpointer**.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────┐  │
│  │   SDK Client        │    │   HTTP Client       │    │  Playground     │  │
│  │   (OpenAI SDK)      │    │   (REST API)        │    │  (Foundry UI)   │  │
│  └──────────┬──────────┘    └──────────┬──────────┘    └────────┬────────┘  │
│             │                          │                         │          │
│             │  conversation_id         │  conversation_id        │          │
│             │  = conv_abc123...        │  = conv_xyz789...       │          │
│             ▼                          ▼                         ▼          │
└─────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FOUNDRY AGENT SERVER                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    from_langgraph() Adapter                         │   │
│   │                                                                     │   │
│   │   1. Receives request with conversation_id                          │   │
│   │   2. Creates RunnableConfig:                                        │   │
│   │      {                                                              │   │
│   │        "configurable": {                                            │   │
│   │          "thread_id": "conv_abc123...",  ◄──Foundry conversation_id │   │
│   │          "passenger_id": "3442 587242"   ◄── Business data          │   │
│   │        }                                                            │   │
│   │      }                                                              │   │
│   │   3. Invokes graph.invoke(messages, config)                         │   │
│   │                                                                     │   │
│   └───────────────────────────────┬─────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      LangGraph (part_4_graph)                       │   │
│   │                                                                     │   │
│   │   ┌───────────────────┐    ┌───────────────────────────────────┐    │   │
│   │   │   Checkpointer    │◄──►│         Graph Execution           │    │   │
│   │   │  (InMemorySaver)  │    │                                   │    │   │
│   │   │                   │    │  • Loads state for thread_id      │    │   │
│   │   │  thread_id →      │    │  • Runs nodes (user_info, etc.)   │    │   │
│   │   │  ┌─────────────┐  │    │  • Executes tools                 │    │   │
│   │   │  │ conv_abc123 │  │    │  • Saves updated state            │    │   │
│   │   │  │ ─────────── │  │    │                                   │    │   │
│   │   │  │ messages: []│  │    └───────────────────────────────────┘    │   │
│   │   │  │ passenger_id│  │                                             │   │
│   │   │  │ dialog_state│  │                                             │   │
│   │   │  └─────────────┘  │                                             │   │
│   │   │                   │                                             │   │
│   │   │  ┌─────────────┐  │                                             │   │
│   │   │  │ conv_xyz789 │  │  ◄── Different conversation = different     │   │
│   │   │  │ ─────────── │  │      isolated state                         │   │
│   │   │  │ messages: []│  │                                             │   │
│   │   │  │ passenger_id│  │                                             │   │
│   │   │  └─────────────┘  │                                             │   │
│   │   └───────────────────┘                                             │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### How Conversation State Flows

```
Turn 1: User says "When is my flight?"
─────────────────────────────────────────────────────────────────────────────

  Client                          Foundry                         LangGraph
    │                               │                                │
    │  POST /responses              │                                │
    │  conversation=null ──────────►│                                │
    │                               │                                │
    │                               │  Creates conversation          │
    │                               │  conv_abc123                   │
    │                               │                                │
    │                               │  config = {                    │
    │                               │    "thread_id": "conv_abc123"  │
    │                               │  }                             │
    │                               │                                │
    │                               │  graph.invoke(msg, config) ───►│
    │                               │                                │
    │                               │                                │ Checkpointer.get("conv_abc123")
    │                               │                                │ → No state found (new)
    │                               │                                │
    │                               │                                │ Run graph nodes
    │                               │                                │ → No passenger_id
    │                               │                                │ → Ask user for it
    │                               │                                │
    │                               │                                │ Checkpointer.put("conv_abc123", state)
    │                               │                                │ → Saves: messages, dialog_state
    │                               │◄────────────────────────────── │
    │◄────────────────────────────  │                                │
    │  Response: "Please provide    │                                │
    │   your passenger ID"          │                                │
    │  conversation=conv_abc123     │                                │


Turn 2: User says "passenger id is 3442 587242"
─────────────────────────────────────────────────────────────────────────────

  Client                          Foundry                         LangGraph
    │                               │                                │
    │  POST /responses              │                                │
    │  conversation=conv_abc123 ───►│                                │
    │                               │                                │
    │                               │  config = {                    │
    │                               │    "thread_id": "conv_abc123"  │
    │                               │  }                             │
    │                               │                                │
    │                               │  graph.invoke(msg, config) ───►│
    │                               │                                │
    │                               │                                │ Checkpointer.get("conv_abc123")
    │                               │                                │ → Loads previous state!
    │                               │                                │   - Previous messages
    │                               │                                │   - dialog_state
    │                               │                                │
    │                               │                                │ extract_passenger_id(messages)
    │                               │                                │ → Finds "3442 587242"
    │                               │                                │
    │                               │                                │ fetch_user_flight_information()
    │                               │                                │ → Returns flight details
    │                               │                                │
    │                               │                                │ Checkpointer.put("conv_abc123", state)
    │                               │                                │ → Saves: messages, passenger_id
    │                               │◄────────────────────────────── │
    │◄────────────────────────────  │                                │
    │  Response: "Your flight       │                                │
    │   LX0112 departs at..."       │                                │
```

### The Key Mapping: conversation_id → thread_id

| Foundry Concept | LangGraph Concept | Purpose |
|-----------------|-------------------|---------|
| `conversation_id` | `thread_id` | Identifies a unique conversation session |
| Foundry Conversations API | `InMemorySaver` checkpointer | Persists state across turns |
| `client.conversations.create()` | N/A (Foundry creates it) | Initiates a new conversation |
| Messages in conversation | `state["messages"]` | The conversation history |

### What Foundry's `from_langgraph` Adapter Does

The adapter (from `azure.ai.agentserver.langgraph`) is the bridge between Foundry and LangGraph:

```python
# Pseudocode of what the adapter does internally
def handle_request(foundry_request):
    # 1. Extract conversation_id from Foundry request
    conversation_id = foundry_request.conversation.id  # e.g., "conv_abc123"
    
    # 2. Build LangGraph config with thread_id = conversation_id
    config = {
        "configurable": {
            "thread_id": conversation_id,  # ◄── THE KEY MAPPING
            "passenger_id": foundry_request.get("passenger_id"),
        }
    }
    
    # 3. Invoke the LangGraph graph
    result = langgraph_graph.invoke(
        {"messages": foundry_request.messages},
        config=config  # ◄── Passes thread_id to checkpointer
    )
    
    # 4. Return response to Foundry
    return format_response(result)
```

### Why This Matters

1. **You don't manage thread_id manually** when hosted on Foundry - the adapter handles it
2. **State is automatically persisted** across conversation turns via the checkpointer
3. **Each conversation is isolated** - different `conversation_id` = different `thread_id` = separate state
4. **Business data (passenger_id)** flows through the same config mechanism

### Local vs Hosted Comparison

| Scenario | Who creates thread_id? | Where is state stored? |
|----------|----------------------|----------------------|
| **Local (test_local.py)** | Your code: `config = {"configurable": {"thread_id": "test-001"}}` | `InMemorySaver` (in-process memory) |
| **Foundry Hosted** | Foundry adapter: maps `conversation_id` → `thread_id` | `InMemorySaver` (container memory) |
| **Production (future)** | Same as hosted | Should use persistent store (Redis, Postgres, etc.) |

### Client Code Comparison

**SDK Client (Project Endpoint) - Stateful:**
```python
# Foundry manages conversation server-side
conversation = client.conversations.create()  # Get Foundry conversation_id
response = client.responses.create(
    input=[{"role": "user", "content": message}],
    conversation=conversation.id,  # Foundry maps this to LangGraph thread_id
)
```

**Application Endpoint Client - Stateless:**
```python
# Client maintains full history (no server-side state)
conversation_history.append({"role": "user", "content": message})
response = client.responses.create(
    input=conversation_history,  # Full history each turn
)
# Note: Each request is independent - no thread_id mapping
```

---

## Notes
- Default passenger_id in sample data: `3442 587242`. Provide it in chat or via `configurable.passenger_id` when calling the hosted agent.
- The sample originates from LangGraph tutorials and was adapted to validate Hosted Agents in Microsoft Foundry.
