"""
Foundry Agent Applications Endpoint SDK Client
===============================================

This is an OpenAI SDK client that connects to a LangGraph agent published to 
Azure AI Foundry using the **Applications Endpoint** - the production-ready 
endpoint for published agents.

NOTE: This uses the OpenAI SDK (not raw HTTP requests). For the HTTP client 
approach, see: foundry-agent-app-http-client.py

CRITICAL: STREAMING MODE BEHAVIOR
=================================
The USE_STREAMING flag controls how responses are received:

USE_STREAMING = True (RECOMMENDED - DEFAULT):
  - Responses arrive as delta events in real-time
  - Tool calls are handled gracefully via event streaming
  - Works correctly for ALL agent responses (with or without tool calls)

USE_STREAMING = False (FOR TESTING ONLY - WILL FAIL WITH TOOL CALLS):
  - Responses return as a single Response object
  - ⚠️ KNOWN BUG: When the agent calls tools, the response contains sparse
    output arrays filled with nulls, causing a response_parsing_error:
    
    error=ResponseError(code='response_parsing_error', ...)
    "output":[null,null,null,null,null,null,null]
    status='failed'
    
  - Simple text-only responses (no tool calls) work fine in non-streaming mode
  - Responses involving tool execution WILL FAIL
  - This is the same issue affecting the Teams integration (Activity Protocol)
  
  This non-streaming mode is included for testing/debugging purposes only.
  It demonstrates why streaming is required for tool-calling agents.

IMPORTANT SDK CONSIDERATIONS:
-----------------------------
1. STREAMING IS REQUIRED: The applications endpoint returns sparse output arrays
   that cause parse errors in non-streaming mode when tools are called.
2. CLIENT-SIDE HISTORY: The applications endpoint is stateless - you must manage
   conversation history on the client side and send it with each request.
3. NO CONVERSATIONS API: Unlike the project endpoint, applications endpoint does
   not support /conversations API.

ENDPOINT COMPARISON:
--------------------
1. PROJECT ENDPOINT (for development/internal use):
   URL: {project}/openai/responses?api-version=...
   - Supports `conversation` parameter in payload for server-side state
   - Supports `/openai/conversations` API for conversation management
   - Used by: foundry-agent-client-sdk.py, foundry-agent-http-client.py

2. APPLICATIONS ENDPOINT (for production/published agents) - THIS CLIENT:
   URL: {project}/applications/{app-name}/protocols/openai/responses?api-version=...
   - Stateless endpoint - does not support `conversation` parameter
   - Does NOT have `/conversations` API
   - Requires client to manage conversation history in payload
   - Streaming mode REQUIRED to avoid parse errors with tool-calling agents
   - Used by: THIS CLIENT (foundry-agent-app-sdk-client.py)

CLIENT TYPES IN THIS PROJECT:
-----------------------------
- foundry-agent-app-sdk-client.py   - OpenAI SDK, Applications endpoint (THIS FILE)
- foundry-agent-app-http-client.py  - HTTP client, Applications endpoint
- foundry-agent-http-client.py      - HTTP client, Project endpoint
- foundry-agent-client-sdk.py       - OpenAI SDK client, Project endpoint

SDK BASE_URL:
-------------
The OpenAI SDK is configured with base_url pointing to the applications endpoint:
  base_url = "{project}/applications/{app-name}/protocols/openai"

This allows using openai.responses.create() to call the published agent.

AUTHENTICATION:
---------------
Uses Azure DefaultAzureCredential with get_bearer_token_provider()
Requires: az login (or other Azure credential method)

USAGE:
------
    python foundry-agent-app-sdk-client.py

Commands in interactive mode:
    - Type your message and press Enter
    - 'new' - Start a new conversation (resets history)
    - 'quit' - Exit the client

See: https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/publish-agent
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import json

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
FOUNDRY_RESOURCE_NAME = os.getenv("FOUNDRY_RESOURCE_NAME", "")
PROJECT_NAME = os.getenv("PROJECT_NAME", "")
APP_NAME = os.getenv("APP_NAME", "")

# Configuration - toggle streaming mode
# WARNING: Non-streaming mode (False) WILL FAIL when agent calls tools!
# See documentation above for details on the sparse output array bug.
USE_STREAMING = os.getenv("USE_STREAMING", "true").lower() == "true"

# Project endpoint (base)
PROJECT_ENDPOINT = f"https://{FOUNDRY_RESOURCE_NAME}.services.ai.azure.com/api/projects/{PROJECT_NAME}"

# Applications endpoint for the hosted agent (SDK base_url)
# This is the PUBLISHED endpoint for production use
APP_BASE_URL = f"{PROJECT_ENDPOINT}/applications/{APP_NAME}/protocols/openai"
API_VERSION = "2025-11-15-preview"


def create_openai_client() -> OpenAI:
    """Create an OpenAI client configured for the Applications endpoint."""
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), 
        "https://ai.azure.com/.default"
    )
    
    return OpenAI(
        api_key=token_provider(),
        base_url=APP_BASE_URL,
        default_query={"api-version": API_VERSION}
    )


def send_message(client: OpenAI, user_message: str, history: list) -> str:
    """Send a message to the applications endpoint with conversation history.
    
    Args:
        client: The OpenAI client configured for applications endpoint
        user_message: The new user message
        history: List of previous messages in the conversation
        
    Returns:
        The assistant's response text
    """
    # Build input with full conversation history + new message
    # Applications endpoint is stateless - must send full history each time
    input_messages = []
    for msg in history:
        input_messages.append({"role": msg["role"], "content": msg["content"]})
    input_messages.append({"role": "user", "content": user_message})
    
    response_text = ""
    print("\nAssistant: ", end="", flush=True)
    
    try:
        if USE_STREAMING:
            # Streaming mode - handles sparse output arrays gracefully
            stream = client.responses.create(
                input=input_messages,
                stream=True,
            )
            
            for event in stream:
                event_type = getattr(event, 'type', '')
                
                if event_type == "response.output_text.delta":
                    delta = getattr(event, 'delta', '')
                    # Skip raw tool output JSON that leaks into text
                    if delta.strip().startswith('[{"') or delta.strip().startswith('{"'):
                        continue
                    print(delta, end="", flush=True)
                    response_text += delta
                
                elif event_type == "response.output_item.added":
                    item = getattr(event, 'item', None)
                    if item:
                        item_type = getattr(item, 'type', '')
                        
                        # Detect function calls
                        if item_type == "function_call":
                            tool_name = getattr(item, 'name', 'unknown')
                            print(f"\n🔧 Calling: {tool_name}...", end="", flush=True)
                        elif item_type == "function_call_output":
                            print(f"\n🔧 Tool result received...", end="", flush=True)
            
            print()  # New line after response
        
        else:
            # Non-streaming mode - may fail with sparse output arrays
            print("\n[NON-STREAMING MODE]", flush=True)
            response = client.responses.create(
                input=input_messages,
                stream=False,
            )
            
            # Debug: Print raw response structure
            print(f"\n[DEBUG] Response type: {type(response)}", flush=True)
            print(f"[DEBUG] Response: {response}", flush=True)
            
            # Try to extract text from response
            if hasattr(response, 'output_text'):
                response_text = response.output_text
                print(f"\nAssistant: {response_text}")
            elif hasattr(response, 'output'):
                print(f"[DEBUG] Output: {response.output}", flush=True)
                # Try to extract from output array
                for item in response.output:
                    if item and hasattr(item, 'content'):
                        for content in item.content:
                            if hasattr(content, 'text'):
                                response_text += content.text
                print(f"\nAssistant: {response_text}")
            else:
                print(f"[DEBUG] Unable to extract response text", flush=True)
                # Dump full response for analysis
                print(f"[DEBUG] Full response dict: {response.model_dump_json(indent=2)}", flush=True)
        
    except Exception as e:
        print(f"\nError: {e}")
        # Print more details about the error
        import traceback
        traceback.print_exc()
        return None
    
    return response_text


def interactive_chat():
    """Run an interactive multi-turn chat session."""
    print("=" * 60)
    print("Travel Support Agent - Applications Endpoint SDK Client")
    print(f"Streaming Mode: {'ENABLED' if USE_STREAMING else 'DISABLED'}")
    print("=" * 60)
    print("Commands: 'quit' to exit, 'new' for new conversation")
    print("=" * 60)
    
    # Create OpenAI client for applications endpoint
    print("\nInitializing SDK client...")
    client = create_openai_client()
    print("Client ready!\n")
    
    # Conversation history (client-side - applications endpoint is stateless)
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
            print("\nStarting new conversation (clearing history)...")
            history = []  # Reset history
            # Recreate client to get fresh token
            client = create_openai_client()
            print("Ready for new conversation!\n")
            continue
        
        # Send message with history
        response = send_message(client, user_input, history)
        
        if response:
            # Add to history (client-side state management)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
        
        print()  # Blank line between turns


if __name__ == "__main__":
    interactive_chat()
