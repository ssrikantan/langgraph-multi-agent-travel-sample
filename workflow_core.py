"""Credential helper and LangGraph adapter for Foundry-hosted agent.

Provides credential selection and exposes the travel agent graph directly
to the Agent Framework adapter without unnecessary wrappers.
"""

from __future__ import annotations

import os
import logging

from dotenv import load_dotenv
from azure.ai.agentserver.langgraph import from_langgraph
from azure.identity.aio import DefaultAzureCredential, ManagedIdentityCredential

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env here as well to cover direct imports of this module
load_dotenv(override=True)

from travel_agent.app import part_4_graph


def get_credential():
    """Use Managed Identity in Azure; fall back to DefaultAzureCredential locally."""
    return ManagedIdentityCredential() if os.getenv("MSI_ENDPOINT") else DefaultAzureCredential()


def create_agent(chat_client=None, as_agent: bool = True):
    """Expose the LangGraph as an Agent Framework-compatible agent.

    The chat_client parameter is accepted for parity with the agent-framework sample,
    but is not required by the LangGraph adapter.
    
    Uses the travel agent graph directly - no wrapper needed.
    The from_langgraph adapter handles state schema translation automatically.
    """
    logger.info("create_agent: Using part_4_graph directly (no wrapper)")
    adapter = from_langgraph(part_4_graph)
    return adapter.as_agent() if as_agent else adapter
