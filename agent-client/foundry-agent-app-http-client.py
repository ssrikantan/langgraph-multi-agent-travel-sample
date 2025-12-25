"""
Foundry Agent Applications Endpoint HTTP Client
================================================

This is an HTTP client (using httpx) that connects to a LangGraph agent published 
to Azure AI Foundry using the **Applications Endpoint** - the production-ready 
endpoint for published agents.

NOTE: This is a direct HTTP client, NOT an SDK client. It uses httpx to make raw
HTTP requests to the Azure AI Foundry REST API. For the SDK-based approach using
the OpenAI SDK, see: foundry-agent-client-sdk.py

ENDPOINT COMPARISON:
--------------------
1. PROJECT ENDPOINT (for development/internal use):
   URL: {project}/openai/responses?api-version=...
   - Supports `conversation` parameter in payload for server-side state
   - Supports `/openai/conversations` API for conversation management
   - Used by: foundry-agent-http-client.py

2. APPLICATIONS ENDPOINT (for production/published agents) - THIS CLIENT:
   URL: {project}/applications/{app-name}/protocols/openai/responses?api-version=...
   - Stateless endpoint - does not support `conversation` parameter
   - Does NOT have `/conversations` API
   - Requires client to manage conversation history in payload
   - Streaming mode recommended to avoid parse errors with sparse output arrays
   - Used by: THIS CLIENT (foundry-agent-app_client.py)

CLIENT TYPES IN THIS PROJECT:
-----------------------------
- foundry-agent-app_client.py   - HTTP client, Applications endpoint (THIS FILE)
- foundry-agent-http-client.py  - HTTP client, Project endpoint
- foundry-agent-client-sdk.py   - OpenAI SDK client, Project endpoint

REQUEST URLS USED:
------------------
- Conversation creation (via PROJECT endpoint):
  POST {PROJECT_ENDPOINT}/openai/conversations?api-version={API_VERSION}

- Message sending (via APPLICATIONS endpoint):
  POST {PROJECT_ENDPOINT}/applications/{app-name}/protocols/openai/responses?api-version={API_VERSION}

AUTHENTICATION:
---------------
Uses Azure DefaultAzureCredential with scope "https://ai.azure.com/.default"
Requires: az login (or other Azure credential method)

USAGE:
------
    python foundry-agent-app_client.py

Commands in interactive mode:
    - Type your message and press Enter
    - 'new' - Start a new conversation
    - 'quit' - Exit the client

See: https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/publish-agent
"""

import os
import json
import httpx
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
FOUNDRY_RESOURCE_NAME = os.getenv("FOUNDRY_RESOURCE_NAME", "")
PROJECT_NAME = os.getenv("PROJECT_NAME", "")
APP_NAME = os.getenv("APP_NAME", "")

# Project endpoint (for creating conversations)
PROJECT_ENDPOINT = f"https://{FOUNDRY_RESOURCE_NAME}.services.ai.azure.com/api/projects/{PROJECT_NAME}"

# Applications endpoint for the hosted agent
# This is the PUBLISHED endpoint for production use
# URL pattern: {project}/applications/{app-name}/protocols/openai
APP_ENDPOINT = f"{PROJECT_ENDPOINT}/applications/{APP_NAME}/protocols/openai"
API_VERSION = "2025-11-15-preview"


def get_auth_token():
    """Get a fresh auth token."""
    credential = DefaultAzureCredential()
    return credential.get_token("https://ai.azure.com/.default").token


def create_conversation() -> str:
    """Create a conversation via the PROJECT endpoint (which supports it)."""
    token = get_auth_token()
    # Use project endpoint for conversation creation
    api_url = f"{PROJECT_ENDPOINT}/openai/conversations?api-version={API_VERSION}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(api_url, headers=headers, json={})
        if response.status_code != 200:
            print(f"Error creating conversation: HTTP {response.status_code}: {response.text}")
            return None
        data = response.json()
        return data.get("id")


def send_message(user_message: str, conversation_id: str, history: list):
    """Send a message to the applications endpoint with conversation history (streaming).
    
    Args:
        user_message: The new user message
        conversation_id: The conversation ID for server-side state
        history: List of previous messages in the conversation
        
    Returns:
        The assistant's response text
    """
    token = get_auth_token()
    api_url = f"{APP_ENDPOINT}/responses?api-version={API_VERSION}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Build input with full conversation history + new message
    input_messages = []
    for msg in history:
        input_messages.append({"type": "message", "role": msg["role"], "content": msg["content"]})
    input_messages.append({"type": "message", "role": "user", "content": user_message})
    
    # Use streaming to avoid parse errors with sparse output arrays
    payload = {
        "input": input_messages,
        "metadata": {"conversation_id": conversation_id},
        "stream": True,
    }
    
    with httpx.Client(timeout=120.0) as client:
        with client.stream("POST", api_url, headers=headers, json=payload) as response:
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                return None
            
            response_text = ""
            print("\nAssistant: ", end="", flush=True)
            
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                
                try:
                    event = json.loads(data_str)
                    event_type = event.get("type", "")
                    
                    if event_type == "response.output_text.delta":
                        delta = event.get("delta", "")
                        # Skip raw tool output JSON that leaks into text
                        if delta.strip().startswith('[{"') or delta.strip().startswith('{"'):
                            continue
                        print(delta, end="", flush=True)
                        response_text += delta
                    
                    elif event_type == "response.output_item.added":
                        item = event.get("item", {})
                        item_type = item.get("type", "")
                        
                        # Detect function calls
                        if item_type == "function_call":
                            tool_name = item.get("name", "unknown")
                            print(f"\n🔧 Calling: {tool_name}...", end="", flush=True)
                        elif item_type == "function_call_output":
                            print(f"\n🔧 Tool result received...", end="", flush=True)
                    
                except json.JSONDecodeError:
                    pass
            
            print()  # New line after response
            return response_text


def interactive_chat():
    """Run an interactive multi-turn chat session."""
    print("=" * 60)
    print("Travel Support Agent - Applications Endpoint Client")
    print("=" * 60)
    print("Commands: 'quit' to exit, 'new' for new conversation")
    print("=" * 60)
    
    # Create initial conversation
    print("\nCreating conversation...")
    conv_id = create_conversation()
    if not conv_id:
        print("Failed to create conversation!")
        return
    print(f"Conversation: {conv_id}\n")
    
    # Conversation history
    history = []
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() == "quit":
            print("Goodbye!")
            break
        
        if user_input.lower() == "new":
            print("\nCreating new conversation...")
            conv_id = create_conversation()
            if conv_id:
                print(f"New conversation: {conv_id}")
                history = []  # Reset history
            else:
                print("Failed to create new conversation!")
            continue
        
        # Send message with history
        response = send_message(user_input, conv_id, history)
        
        if response:
            # Add to history
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
        
        print()  # Blank line between turns


if __name__ == "__main__":
    interactive_chat()