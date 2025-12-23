"""Credential helper and LangGraph adapter for Foundry-hosted agent.

Mirrors the structure of the agent framework sample's workflow_core.py so it can be
consumed by a container entrypoint (e.g., container.py) that hosts the agent in
Azure AI Foundry/Agent Server.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, AsyncGenerator, AsyncIterator

from dotenv import load_dotenv
from azure.ai.agentserver.langgraph import from_langgraph
from azure.identity.aio import DefaultAzureCredential, ManagedIdentityCredential
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env here as well to cover direct imports of this module
load_dotenv(override=True)

from travel_agent.app import part_4_graph


def get_credential():
    """Use Managed Identity in Azure; fall back to DefaultAzureCredential locally."""
    return ManagedIdentityCredential() if os.getenv("MSI_ENDPOINT") else DefaultAzureCredential()


def invoke_travel_agent(state: MessagesState) -> MessagesState:
    """Wrapper node that invokes the travel agent graph and returns MessagesState."""
    logger.info(f"invoke_travel_agent: input messages count={len(state.get('messages', []))}")
    
    # Convert MessagesState to travel agent's State format
    input_messages = list(state.get("messages", []))
    
    # DEBUG: First verify wrapper is working by adding a test message
    logger.info("invoke_travel_agent: Starting travel agent invocation")
    
    travel_state = {
        "messages": input_messages,
        "user_info": "",
        "passenger_id": None,  # Will be extracted from user messages by the graph
        # Note: Don't include dialog_state - let the graph initialize it properly
    }
    
    # Create a config with thread_id for the checkpointer
    import uuid
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    logger.info(f"invoke_travel_agent: Using thread_id={thread_id}")
    
    try:
        # Use invoke to get the final state
        logger.info(f"invoke_travel_agent: Calling part_4_graph.invoke")
        result = part_4_graph.invoke(travel_state, config=config)
        logger.info(f"invoke_travel_agent: part_4_graph returned, result keys: {result.keys() if result else 'None'}")
        
        # Extract messages from the result
        output_messages = result.get("messages", [])
        logger.info(f"invoke_travel_agent: output messages count={len(output_messages)}")
        
        # Log all messages for debugging
        for i, msg in enumerate(output_messages):
            msg_type = type(msg).__name__
            msg_content = getattr(msg, 'content', str(msg))[:100] if hasattr(msg, 'content') else str(msg)[:100]
            logger.info(f"invoke_travel_agent: message[{i}] type={msg_type}, content={msg_content}")
        
        # Return all messages (input + output from agent)
        return {"messages": output_messages}
    except Exception as e:
        logger.error(f"invoke_travel_agent: Error invoking travel agent: {e}", exc_info=True)
        # Return error message so we can see it in the response
        error_msg = AIMessage(content=f"Error occurred while processing your request: {str(e)}")
        return {"messages": input_messages + [error_msg]}


def build_wrapper_graph():
    """Build a simple wrapper graph that uses MessagesState for compatibility."""
    builder = StateGraph(MessagesState)
    builder.add_node("travel_agent", invoke_travel_agent)
    builder.add_edge(START, "travel_agent")
    builder.add_edge("travel_agent", END)
    return builder.compile()


# Build the wrapper graph
wrapper_graph = build_wrapper_graph()


def create_agent(chat_client=None, as_agent: bool = True):
    """Expose the LangGraph as an Agent Framework-compatible agent.

    The chat_client parameter is accepted for parity with the agent-framework sample,
    but is not required by the LangGraph adapter.
    """
    logger.info("create_agent: Using wrapper graph with MessagesState")
    adapter = from_langgraph(wrapper_graph)
    return adapter.as_agent() if as_agent else adapter
