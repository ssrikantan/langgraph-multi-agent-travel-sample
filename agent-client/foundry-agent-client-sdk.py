# Foundry Agent Client using OpenAI SDK
# This client connects to the LangGraph 'Hosted Agent' in Microsoft Foundry.
# Uses the OpenAI-compatible Responses API with Azure authentication.
# See: https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/publish-agent
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

# Foundry endpoint components
FOUNDRY_RESOURCE_NAME = os.getenv("FOUNDRY_RESOURCE_NAME", "")
PROJECT_NAME = os.getenv("PROJECT_NAME", "")
AGENT_NAME = os.getenv("AGENT_NAME", "")

# Use the PROJECT endpoint (not application endpoint) - this is what works
# The agent is specified in the request payload, not the URL
BASE_URL = f"https://{FOUNDRY_RESOURCE_NAME}.services.ai.azure.com/api/projects/{PROJECT_NAME}/openai"

# Create Azure AD token provider for authentication
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://ai.azure.com/.default"
)

# Global client and thread tracking
client = None
current_thread_id = None


def create_client():
    """Create an OpenAI client configured for Azure Foundry."""
    global client
    client = OpenAI(
        api_key=token_provider(),
        base_url=BASE_URL,
        default_query={"api-version": "2025-11-15-preview"}
    )
    return client


def refresh_token():
    """Refresh the authentication token if needed."""
    global client
    if client:
        client.api_key = token_provider()


def get_or_create_thread_id() -> str:
    """Get the current thread_id or create a new one via Foundry API.
    
    Uses the Foundry conversations.create() API to create a server-side
    conversation that persists state across requests.
    """
    global current_thread_id, client
    if not current_thread_id:
        # Create a conversation using Foundry's conversations API
        refresh_token()
        conversation = client.conversations.create()
        current_thread_id = conversation.id
        print(f"Created new conversation: {current_thread_id}")
    return current_thread_id


def reset_thread():
    """Reset the conversation by creating a new thread_id via Foundry API."""
    global current_thread_id, client
    refresh_token()
    conversation = client.conversations.create()
    current_thread_id = conversation.id
    return current_thread_id


def send_message_streaming(user_message: str, passenger_id: str = None) -> str:
    """Send a message using streaming and return the response.
    
    Uses stateful approach: framework maintains conversation history via conversation_id.
    Pass input directly with conversation parameter for context.
    """
    global client
    
    conversation_id = get_or_create_thread_id()
    
    # Refresh token before request
    refresh_token()
    
    # Build extra_body with agent reference
    extra_body = {
        "agent": {"name": AGENT_NAME, "type": "agent_reference"},
    }
    
    # Create streaming response with conversation for context and input for the message
    stream = client.responses.create(
        stream=True,
        input=[{"role": "user", "content": user_message}],  # Message as list
        conversation=conversation_id,  # Conversation for context
        extra_body=extra_body
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
    return response_text


def send_message_non_streaming(user_message: str, passenger_id: str = None) -> str:
    """Send a message without streaming and return the response.
    
    Uses stateful approach: framework maintains conversation history via conversation_id.
    Pass input directly with conversation parameter for context.
    """
    global client
    
    conversation_id = get_or_create_thread_id()
    
    # Refresh token before request
    refresh_token()
    
    # Build extra_body with agent reference
    extra_body = {
        "agent": {"name": AGENT_NAME, "type": "agent_reference"},
    }
    
    # Create response with conversation for context and input for the message
    response = client.responses.create(
        input=[{"role": "user", "content": user_message}],  # Message as list
        conversation=conversation_id,  # Conversation for context
        extra_body=extra_body
    )
    
    # Get the response text
    response_text = getattr(response, 'output_text', '') or ''
    
    if response_text:
        print(f"\nAssistant: {response_text}")
    
    return response_text


def send_message(user_message: str, passenger_id: str = None) -> str:
    """Send a message to the agent and return the response.
    
    Uses stateful approach: framework maintains conversation history via thread_id.
    Client only sends new messages; server tracks conversation state.
    """
    if USE_STREAMING:
        return send_message_streaming(user_message, passenger_id)
    else:
        return send_message_non_streaming(user_message, passenger_id)


def interactive_chat():
    """Run an interactive chat session with the agent using OpenAI SDK."""
    print("=" * 60)
    print("Travel Support Agent - Interactive Chat (OpenAI SDK)")
    print("=" * 60)
    print(f"Agent: {AGENT_NAME}")
    print(f"Streaming: {'Enabled' if USE_STREAMING else 'Disabled'}")
    print(f"Mode: Stateful (Foundry manages conversation server-side)")
    print("\nType 'quit' or 'exit' to end the conversation.")
    print("Type 'new' to start a new conversation.")
    print("Type 'conversation' to see current conversation ID.")
    print("=" * 60)
    
    # Create client
    create_client()
    print(f"Connected to: {BASE_URL}\n")
    
    # Initialize conversation via Foundry API
    conversation_id = get_or_create_thread_id()
    print(f"Conversation ID: {conversation_id}\n")
    
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
            conversation_id = reset_thread()
            print(f"\n--- Starting new conversation (ID: {conversation_id}) ---\n")
            continue
        
        if user_input.lower() in ['conversation', 'thread']:
            print(f"\nCurrent Conversation ID: {conversation_id}")
            print("(Foundry maintains conversation history server-side)\n")
            continue
        
        # Send only the new message - Foundry handles history via conversation
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
    print(f"Agent: {AGENT_NAME}")
    print(f"Streaming: {'Enabled' if USE_STREAMING else 'Disabled'}")
    
    # Create client
    create_client()
    print(f"Connected to: {BASE_URL}")
    
    # Get conversation ID
    conversation_id = get_or_create_thread_id()
    print(f"Conversation ID: {conversation_id}")
    
    print("\n--- Sending: 'Hey there! What time is my flight?' ---")
    
    response_text = send_message("Hey there! What time is my flight?")
    
    print(f"\n--- Response received ({len(response_text)} chars) ---")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        # Run single-turn demo
        single_turn_demo()
    else:
        # Run interactive chat (default)
        interactive_chat()
