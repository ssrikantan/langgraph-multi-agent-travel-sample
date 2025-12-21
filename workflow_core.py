"""Credential helper and LangGraph adapter for Foundry-hosted agent.

Mirrors the structure of the agent framework sample's workflow_core.py so it can be
consumed by a container entrypoint (e.g., container.py) that hosts the agent in
Azure AI Foundry/Agent Server.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from azure.ai.agentserver.langgraph import from_langgraph
from azure.identity.aio import DefaultAzureCredential, ManagedIdentityCredential

# Load .env here as well to cover direct imports of this module
load_dotenv(override=True)

from travel_agent.app import part_4_graph


def get_credential():
    """Use Managed Identity in Azure; fall back to DefaultAzureCredential locally."""

    return ManagedIdentityCredential() if os.getenv("MSI_ENDPOINT") else DefaultAzureCredential()


async def create_agent(chat_client=None, as_agent: bool = True):
    """Expose the LangGraph as an Agent Framework-compatible agent.

    The chat_client parameter is accepted for parity with the agent-framework sample,
    but is not required by the LangGraph adapter.
    """

    adapter = from_langgraph(part_4_graph)
    return adapter.as_agent() if as_agent else adapter
