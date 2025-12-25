"""Credential helper and LangGraph adapter for Foundry-hosted agent.

Provides credential selection and exposes the travel agent graph directly
to the Agent Framework adapter without unnecessary wrappers.

CUSTOM STATE CONVERTER:
-----------------------
This module uses a custom state converter (RobustStateConverter) that fixes
the sparse null array issue in non-streaming responses. The default converter
uses stream_mode="updates" which produces intermediate step outputs that can
fail to serialize properly when tools are called.

The RobustStateConverter:
1. Uses stream_mode="values" for non-streaming (final state only)
2. Extracts only the last AI message as the response
3. Avoids null entries from intermediate tool execution steps

This enables non-streaming clients (Teams, M365 Copilot, Bot Service) to work
correctly with tool-calling agents.
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
from custom_state_converter import RobustStateConverter


def get_credential():
    """Use Managed Identity in Azure; fall back to DefaultAzureCredential locally."""
    return ManagedIdentityCredential() if os.getenv("MSI_ENDPOINT") else DefaultAzureCredential()


def create_agent(chat_client=None, as_agent: bool = True):
    """Expose the LangGraph as an Agent Framework-compatible agent.

    The chat_client parameter is accepted for parity with the agent-framework sample,
    but is not required by the LangGraph adapter.
    
    Uses the travel agent graph directly - no wrapper needed.
    Uses RobustStateConverter to fix non-streaming response issues with tool calls.
    """
    logger.info("create_agent: Using part_4_graph with RobustStateConverter")
    adapter = from_langgraph(part_4_graph, state_converter=RobustStateConverter())
    return adapter.as_agent() if as_agent else adapter
