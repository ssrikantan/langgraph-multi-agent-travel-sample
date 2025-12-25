# Travel Support Hosted Agent (LangGraph sample)

This project is a modified version of the LangGraph tutorial [here](https://langchain-ai.github.io/langgraph/tutorials/customer-support/customer-support/#part-4-specialized-workflows), tailored to exercise Microsoft Foundry Hosted Agents. It wires multiple assistants (flights, hotels, cars, excursions) into a single graph and can be run locally or as a hosted agent.

## Table of Contents

- [Hosted Agent Documentation](#hosted-agent-docs)
- [Prerequisites](#prerequisites)
- [Server-Side Code](#server-side-code)
  - [File Overview](#server-side-file-overview)
  - [Running Locally](#running-locally)
  - [Deploying to Foundry](#deploying-as-a-hosted-agent-foundry)
- [Client-Side Code](#client-side-code)
  - [Client Options Overview](#client-options-overview)
  - [Applications Endpoint Clients (Production)](#applications-endpoint-clients-production)
  - [Project Endpoint Clients (Development)](#project-endpoint-clients-development)
  - [Endpoint Comparison](#endpoint-comparison)
  - [Streaming vs Non-Streaming](#streaming-vs-non-streaming-critical)
- [Sample Conversation Script](#sample-conversation-script-multi-agent-flow)
- [Architecture Deep Dives](#architecture-deep-dives)

---

## Hosted Agent docs
- Hosted agents (concepts): https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/hosted-agents?view=foundry&tabs=cli
- VS Code workflow for hosted agents (Python): https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/vs-code-agents-workflow-pro-code?view=foundry&tabs=windows-powershell&pivots=python

## Prerequisites
- Python 3.10+ and `pip install -r requirements.txt`
- Azure OpenAI + Tavily keys (see `.env.example` for required vars)
- For hosted runs: Managed Identity or DefaultAzureCredential access to your Azure OpenAI resource

---

# Server-Side Code

The server-side code implements the LangGraph travel agent and the Azure AI Foundry hosting adapter.

## Server-Side File Overview

| File | Purpose |
|------|---------|
| [container.py](container.py) | Azure-hosted entrypoint; loads env, sets up observability, runs the LangGraph adapter |
| [workflow_core.py](workflow_core.py) | Exposes `create_agent()` that wraps the graph with the Agent Framework adapter |
| [custom_state_converter.py](custom_state_converter.py) | **Custom converter that fixes non-streaming mode** for tool-calling agents |
| [travel_agent/app.py](travel_agent/app.py) | Core LangGraph graph with multi-agent routing, tools, state management |
| [travel_agent/utilities.py](travel_agent/utilities.py) | Shared helper for tool fallbacks and pretty-printing |
| [travel_agent/data/db.py](travel_agent/data/db.py) | SQLite path and date adjustment helpers |
| [travel_agent/tools/flight_tools.py](travel_agent/tools/flight_tools.py) | Flight search/update/cancel tools |
| [travel_agent/tools/hotels_tools.py](travel_agent/tools/hotels_tools.py) | Hotel search/book/update/cancel tools |
| [travel_agent/tools/car_rental_tools.py](travel_agent/tools/car_rental_tools.py) | Car rental search/book/update/cancel tools |
| [travel_agent/tools/excursions.py](travel_agent/tools/excursions.py) | Excursion search/book/update/cancel tools |
| [travel_agent/tools/policies.py](travel_agent/tools/policies.py) | Policy lookup tool using Azure OpenAI |
| [test_local.py](test_local.py) | Quick local test to verify the graph works in-process |

## Running Locally

1. Copy `.env.example` to `.env` and adjust values
2. Run `python test_local.py` for a quick in-process test

### Providing passenger_id
The sample data uses passenger_id `3442 587242`. You can provide it in two ways:
1. **In conversation**: Just mention it in your message (e.g., "my passenger id is 3442 587242")
2. **Default from .env**: Set `DEFAULT_PASSENGER_ID` in your `.env` file

## Deploying as a Hosted Agent (Foundry)

1. Ensure env vars in your deployment (matches `.env.example`)
2. Use [container.py](container.py) with the LangGraph adapter (see [workflow_core.py](workflow_core.py))
3. Follow the Hosted Agent docs (links above) to publish in Microsoft Foundry

### Telemetry and Tracing
Telemetry is automatically captured per `conversation_id` when hosted as a Foundry Hosted Agent. Inspect runs and tool activity in the Foundry UI.

![Tracing](images/Tracing.png)

---

# Client-Side Code

All client code is in the `agent-client/` folder. There are **four client options** depending on your use case.

## Client Options Overview

| Client | Endpoint | Protocol | State Management | Use Case |
|--------|----------|----------|-----------------|----------|
| [foundry-agent-app-sdk-client.py](agent-client/foundry-agent-app-sdk-client.py) | Applications | OpenAI SDK | Client-side | **Production** |
| [foundry-agent-app-http-client.py](agent-client/foundry-agent-app-http-client.py) | Applications | HTTP/REST | Client-side | **Production** |
| [foundry-agent-client-sdk.py](agent-client/foundry-agent-client-sdk.py) | Project | OpenAI SDK | Server-side | Development |
| [foundry-agent-http-client.py](agent-client/foundry-agent-http-client.py) | Project | HTTP/REST | Server-side | Development |

---

## Applications Endpoint Clients (Production)

The **Applications endpoint** is the production-ready endpoint for published agents. Use these clients for customer-facing applications.

### 1. OpenAI SDK Client (Recommended)
**File:** [foundry-agent-app-sdk-client.py](agent-client/foundry-agent-app-sdk-client.py)

```bash
cd agent-client
python foundry-agent-app-sdk-client.py
```

**Features:**
- Uses OpenAI SDK (`openai.responses.create()`)
- Streaming mode with real-time delta events
- Tool call indicators displayed during execution
- Multi-turn conversation support

**URL Pattern:**
```
{project}/applications/{app-name}/protocols/openai/responses?api-version=...
```

### 2. HTTP/REST Client
**File:** [foundry-agent-app-http-client.py](agent-client/foundry-agent-app-http-client.py)

```bash
cd agent-client
python foundry-agent-app-http-client.py
```

**Features:**
- Direct HTTP requests using `httpx`
- SSE (Server-Sent Events) streaming
- Manual history management in payload
- Lower-level control for custom integrations

**Key Characteristics of Applications Endpoint:**
- **Stateless**: No server-side conversation state
- **Client manages history**: Full conversation history sent with each request
- **No Conversations API**: Cannot use `client.conversations.create()`
- **Streaming required**: See [Streaming section](#streaming-vs-non-streaming-critical) below

---

## Project Endpoint Clients (Development)

The **Project endpoint** is for development and internal use. It provides server-side state management.

### 1. OpenAI SDK Client
**File:** [foundry-agent-client-sdk.py](agent-client/foundry-agent-client-sdk.py)

```bash
cd agent-client
python foundry-agent-client-sdk.py
```

**Features:**
- Uses Foundry's Conversations API for server-side state
- Automatic conversation management via `client.conversations.create()`
- `conversation` parameter in requests for state tracking

**URL Pattern:**
```
{project}/openai/responses?api-version=...
```

### 2. HTTP/REST Client
**File:** [foundry-agent-http-client.py](agent-client/foundry-agent-http-client.py)

**Key Characteristics of Project Endpoint:**
- **Stateful**: Server maintains conversation state
- **Conversations API**: Use `POST /openai/conversations` to create conversations
- **Agent Reference**: Specify agent via `agent: {"name": "...", "type": "agent_reference"}`

---

## Endpoint Comparison

| Feature | Applications Endpoint | Project Endpoint |
|---------|----------------------|------------------|
| **URL** | `{project}/applications/{app-name}/protocols/openai` | `{project}/openai` |
| **Purpose** | Production/Published agents | Development/Internal |
| **State** | Stateless (client manages) | Stateful (server manages) |
| **Conversations API** | ❌ Not available | ✅ Available |
| **Agent Specification** | In URL path (`/applications/{app-name}`) | In payload (`agent.name`) |
| **Streaming** | Required for tool calls | Recommended |

---

## Streaming vs Non-Streaming (CRITICAL)

### ⚠️ Non-Streaming Issues with Tool-Calling Agents

When the agent calls tools (which it does for most travel queries), the **default adapter** has issues with non-streaming mode.

### The Problem with Default Adapter

The default `LanggraphMessageStateConverter` uses `stream_mode="updates"` for non-streaming requests, which produces intermediate step outputs. When tools are called, this results in **sparse null arrays**:

```json
{
  "error": {
    "code": "response_parsing_error",
    "message": "..."
  },
  "output": [null, null, null, null, null, null, null],
  "status": "failed"
}
```

### The Fix: RobustStateConverter

This project includes a custom state converter ([custom_state_converter.py](custom_state_converter.py)) that fixes non-streaming responses:

**Key changes:**
1. Uses `stream_mode="values"` (final state only, not intermediate updates)
2. Extracts only the last AI message as the response
3. Avoids null entries from intermediate tool execution steps

**How it's configured** (in [workflow_core.py](workflow_core.py)):
```python
from custom_state_converter import RobustStateConverter
adapter = from_langgraph(part_4_graph, state_converter=RobustStateConverter())
```

### What Works Now

| Request Type | Tool Calls | Default Adapter | With RobustStateConverter |
|-------------|------------|-----------------|---------------------------|
| Streaming | With tools | ✅ Yes | ✅ Yes |
| Streaming | No tools | ✅ Yes | ✅ Yes |
| Non-streaming | No tools | ✅ Yes | ✅ Yes |
| Non-streaming | With tools | ❌ FAILS | ✅ **FIXED** |

### Teams / M365 Copilot / Bot Service Integration

These channels use the **Activity Protocol** which makes non-streaming calls internally. With the `RobustStateConverter`, they should now work correctly with tool-calling agents.

### Configuration in SDK Clients

Both SDK clients have a `USE_STREAMING` flag for testing:

```python
# In foundry-agent-app-sdk-client.py and foundry-agent-client-sdk.py
USE_STREAMING = True   # Streaming works with default and custom converter
USE_STREAMING = False  # Non-streaming now works with RobustStateConverter
```

### Streaming Response Example

![Streaming responses](images/streaming-responses.png)

---

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

---

# Architecture Deep Dives

## Request/Response Pipeline (Foundry → LangGraph)

Understanding how config and state flow through the system:

### 1. Client Request
Client sends messages to the Foundry Agent Server endpoint. The server assigns or receives a `conversation_id` to track the conversation.

### 2. Container Startup
[container.py](container.py) starts the Agent Framework server:
- Loads environment variables and credentials
- Creates the LangGraph adapter via `create_agent()` from [workflow_core.py](workflow_core.py)
- Calls `adapter.run()` to listen for incoming requests

### 3. Azure SDK Adapter (`from_langgraph`)
When a request arrives, the `azure.ai.agentserver.langgraph.from_langgraph()` adapter:
- Extracts `conversation_id` from the incoming Foundry request
- Creates a `RunnableConfig` with `{"configurable": {"thread_id": conversation_id}}`
- Also includes any `passenger_id` from the request in the config
- Calls `part_4_graph.invoke(state, config=config)` directly with this config

### 4. LangGraph Execution
The travel agent graph (`part_4_graph`):
- Uses the `thread_id` from config to load checkpointed state
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
- **Thread persistence is automatic** - the `thread_id` ensures conversation state is maintained
- **passenger_id flows through config** - Tools receive it via `config.get("configurable", {}).get("passenger_id")`

---

## Conversation State Management: Foundry ↔ LangGraph

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

### The Key Mapping: conversation_id → thread_id

| Foundry Concept | LangGraph Concept | Purpose |
|-----------------|-------------------|---------|
| `conversation_id` | `thread_id` | Identifies a unique conversation session |
| Foundry Conversations API | `InMemorySaver` checkpointer | Persists state across turns |
| `client.conversations.create()` | N/A (Foundry creates it) | Initiates a new conversation |
| Messages in conversation | `state["messages"]` | The conversation history |

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
