# Foundry Agent Application Client using OpenAI SDK


# **THIS SCRIPT DOES NOT WORK YET. WILL BE UPDATED SOON**


# Uses the Application Endpoint (published agent) with OpenAI-compatible Responses API.
# See: https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/publish-agent
#
# KEY DIFFERENCE from Project Endpoint:
# - Application endpoints are STATELESS - no /conversations API
# - Client must maintain full conversation history and send it each turn
# - This enables user data isolation (SaaS-like behavior)
# - Messages must include "type": "message" in addition to role/content
#
# Before running:
#    pip install openai azure-identity python-dotenv
#    az login

import os
from dotenv import load_dotenv
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Load environment variables from .env file
load_dotenv()

# Configuration from .env
USE_STREAMING = os.getenv("USE_STREAMING", "true").lower() == "true"

# Application endpoint - the published agent's stable endpoint
# Format: https://{account}.services.ai.azure.com/api/projects/{project}/applications/{app}/protocols/openai
APPLICATION_ENDPOINT = os.getenv("PROJECT_APPLICATION_ENDPOINT", "")

# Ensure endpoint ends with /protocols/openai (or similar)
# Remove trailing slash if present for consistency
if APPLICATION_ENDPOINT.endswith("/"):
    APPLICATION_ENDPOINT = APPLICATION_ENDPOINT[:-1]

# Create Azure AD token provider for authentication
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://ai.azure.com/.default"
)

# Global client
client = None

# Conversation history - maintained client-side for stateless API
conversation_history = []


def create_client():
    """Create an OpenAI client configured for the Agent Application endpoint."""
    global client
    client = OpenAI(
        api_key=token_provider(),
        base_url=APPLICATION_ENDPOINT,
        default_query={"api-version": "2025-11-15-preview"}
    )
    return client


def refresh_token():
    """Refresh the authentication token if needed."""
    global client
    if client:
        client.api_key = token_provider()


def reset_conversation():
    """Reset the conversation history."""
    global conversation_history
    conversation_history = []


def build_conversation_input(history, new_message):
    """
    Build the input for a multi-turn conversation.
    
    Published applications are stateless - we must send the full
    conversation history with each request.
    
    Messages must include "type": "message" in addition to role and content.
    """
    messages = []
    
    for msg in history:
        messages.append({
            "type": "message",
            "role": msg["role"],
            "content": msg["content"]
        })
    
    messages.append({
        "type": "message",
        "role": "user",
        "content": new_message
    })
    
    return messages


def send_message_streaming(user_message: str) -> str:
    """Send a message using streaming and return the response.
    
    Application endpoints are STATELESS - we send full conversation history each turn.
    """
    global client, conversation_history
    
    # Refresh token before request
    refresh_token()
    
    # Build input with full conversation history (proper format with "type": "message")
    input_items = build_conversation_input(conversation_history, user_message)
    
    # Create streaming response - no agent reference needed for application endpoints
    stream = client.responses.create(
        stream=True,
        input=input_items
    )
    
    response_text = ""
    is_streaming_text = False
    
    for event in stream:
        event_type = getattr(event, 'type', None)
        
        # Text streaming events
        if event_type == "response.output_text.delta":
            if not is_streaming_text:
                print("\nAssistant: ", end="", flush=True)
                is_streaming_text = True
            
            delta = getattr(event, 'delta', '')
            print(delta, end="", flush=True)
            response_text += delta
        
        # Tool call events (informational)
        elif event_type == "response.output_item.added":
            item = getattr(event, 'item', None)
            if item:
                item_type = getattr(item, 'type', None)
                if item_type == "mcp_call":
                    tool_name = getattr(item, 'name', None) or getattr(item, 'server_label', 'unknown')
                    print(f"\n🔧 Calling tool: {tool_name}")
                elif item_type == "function_call":
                    func_name = getattr(item, 'name', 'unknown')
                    print(f"\n🔧 Calling tool: {func_name}")
        
        elif event_type == "response.mcp_call.completed":
            print(f"   ✅ Tool call completed")
        
        elif event_type == "error":
            error = getattr(event, 'error', None)
            print(f"\n❌ Error: {error}")
            break
    
    print()  # New line after streaming
    
    # Add to conversation history for next turn
    conversation_history.append({"role": "user", "content": user_message})
    if response_text:
        conversation_history.append({"role": "assistant", "content": response_text})
    
    return response_text


def send_message_non_streaming(user_message: str) -> str:
    """Send a message without streaming and return the response.
    
    Application endpoints are STATELESS - we send full conversation history each turn.
    """
    global client, conversation_history
    
    # Refresh token before request
    refresh_token()
    
    # Build input with full conversation history (proper format with "type": "message")
    input_items = build_conversation_input(conversation_history, user_message)
    
    # Create response - no agent reference needed for application endpoints
    response = client.responses.create(
        input=input_items
    )
    
    # Get the response text
    response_text = getattr(response, 'output_text', '') or ''
    
    if response_text:
        print(f"\nAssistant: {response_text}")
    
    # Add to conversation history for next turn
    conversation_history.append({"role": "user", "content": user_message})
    if response_text:
        conversation_history.append({"role": "assistant", "content": response_text})
    
    return response_text


def send_message(user_message: str) -> str:
    """Send a message to the agent and return the response."""
    if USE_STREAMING:
        return send_message_streaming(user_message)
    else:
        return send_message_non_streaming(user_message)


def interactive_chat():
    """Run an interactive chat session with the published agent."""
    print("=" * 60)
    print("Travel Support Agent - Application Endpoint Client")
    print("=" * 60)
    print(f"Endpoint: {APPLICATION_ENDPOINT[:80]}...")
    print(f"Streaming: {'Enabled' if USE_STREAMING else 'Disabled'}")
    print(f"Mode: Stateless (client maintains conversation history)")
    print("\nType 'quit' or 'exit' to end the conversation.")
    print("Type 'new' to start a new conversation.")
    print("Type 'history' to see conversation history.")
    print("=" * 60)
    
    # Create client
    create_client()
    print(f"Connected to application endpoint\n")
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() in ['quit', 'exit']:
            print("\nGoodbye!")
            break
        
        if user_input.lower() == 'new':
            reset_conversation()
            print("\n--- Starting new conversation (history cleared) ---\n")
            continue
        
        if user_input.lower() == 'history':
            print(f"\nConversation history ({len(conversation_history)} messages):")
            for i, msg in enumerate(conversation_history):
                role = msg['role'].capitalize()
                content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
                print(f"  {i+1}. [{role}]: {content}")
            print()
            continue
        
        # Send message with full history
        try:
            response_text = send_message(user_input)
        
        except Exception as e:
            print(f"\nError: {e}")
            # If authentication error, try refreshing token
            if "401" in str(e) or "unauthorized" in str(e).lower():
                print("Attempting to refresh authentication...")
                refresh_token()


def single_turn_demo():
    """Run a single-turn demo."""
    print(f"Endpoint: {APPLICATION_ENDPOINT}")
    print(f"Streaming: {'Enabled' if USE_STREAMING else 'Disabled'}")
    
    # Create client
    create_client()
    
    print("\n--- Sending: 'Hey there! What can you help me with?' ---")
    
    response_text = send_message("Hey there! What can you help me with?")
    
    print(f"\n--- Response received ({len(response_text)} chars) ---")


if __name__ == "__main__":
    import sys
    
    if not APPLICATION_ENDPOINT:
        print("Error: PROJECT_APPLICATION_ENDPOINT not set in .env file")
        print("Please add: PROJECT_APPLICATION_ENDPOINT=https://...")
        sys.exit(1)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        # Run single-turn demo
        single_turn_demo()
    else:
        # Run interactive chat (default)
        interactive_chat()
