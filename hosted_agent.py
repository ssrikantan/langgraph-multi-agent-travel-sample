"""Hosted agent entrypoint for Foundry using the LangGraph adapter.

Mirrors the pattern from the agent_framework sample: exposes `get_credential`,
`create_agent`, and a main that starts the adapter locally.
"""

import os
import asyncio
from typing import Any

from dotenv import load_dotenv

# Load environment variables from .env before importing app
load_dotenv()

from azure.ai.agentserver.langgraph import from_langgraph
from azure.identity.aio import DefaultAzureCredential, ManagedIdentityCredential

from travel_agent.app import part_4_graph


def get_credential():
    """Prefer MSI in Azure; fall back to DefaultAzureCredential locally."""

    return ManagedIdentityCredential() if os.getenv("MSI_ENDPOINT") else DefaultAzureCredential()


async def create_agent(chat_client: Any, as_agent: bool = True):
    adapter = from_langgraph(part_4_graph)
    return adapter.as_agent() if as_agent else adapter


def main():
    # Launch the hosting adapter that exposes the LangGraph agent on http://localhost:8088
    # Use the async runner so HTTP streaming/SSE works consistently (matches Azure Agent docs).
    asyncio.run(from_langgraph(part_4_graph).run_async())


if __name__ == "__main__":
    main()
