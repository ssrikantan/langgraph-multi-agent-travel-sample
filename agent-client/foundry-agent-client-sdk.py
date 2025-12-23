# Foundry Agent Client using OpenAI SDK
#
# Uses the OpenAI-compatible Responses API with Azure authentication.
# See: https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/publish-agent
#
# Before running:
#    pip install openai azure-identity
#    az login

import json
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Configuration
USE_STREAMING = True  # Set to False for non-streaming behavior

# Foundry endpoint components
FOUNDRY_RESOURCE_NAME = "sansri-foundry-hosted-agents-pro"
PROJECT_NAME = "sansri-foundry-hosted-agents-project"
AGENT_NAME = "travel-multi-agent"  # Agent name to reference

# Use the PROJECT endpoint (not application endpoint) - this is what works
# The agent is specified in the request payload, not the URL
BASE_URL = f"https://{FOUNDRY_RESOURCE_NAME}.services.ai.azure.com/api/projects/{PROJECT_NAME}/openai"

# Create Azure AD token provider for authentication
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://ai.azure.com/.default"
)

# Global client - will be refreshed as needed
client = None


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


def build_conversation_input(history: list, new_message: str) -> list:
    """Build the input for a multi-turn conversation.
    
    Published applications are stateless - we must send the full
    conversation history with each request.
    """
    messages = []
    
    for msg in history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    messages.append({
        "role": "user",
        "content": new_message
    })
    
    return messages


def send_message_streaming(conversation_history: list, user_message: str) -> str:
    """Send a message using streaming and return the response."""
    global client
    
    input_messages = build_conversation_input(conversation_history, user_message)
    
    # Refresh token before request
    refresh_token()
    
    # Create streaming response with agent reference
    # Use extra_body to pass the agent reference since SDK doesn't have native support
    stream = client.responses.create(
        stream=True,
        input=input_messages,
        extra_body={
            "agent": {"name": AGENT_NAME, "type": "agent_reference"}
        }
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


def send_message_non_streaming(conversation_history: list, user_message: str) -> str:
    """Send a message without streaming and return the response."""
    global client
    
    input_messages = build_conversation_input(conversation_history, user_message)
    
    # Refresh token before request
    refresh_token()
    
    # Create response with agent reference
    # Use extra_body to pass the agent reference since SDK doesn't have native support
    response = client.responses.create(
        input=input_messages,
        extra_body={
            "agent": {"name": AGENT_NAME, "type": "agent_reference"}
        }
    )
    
    # Get the response text
    response_text = getattr(response, 'output_text', '') or ''
    
    if response_text:
        print(f"\nAssistant: {response_text}")
    
    return response_text


def send_message(conversation_history: list, user_message: str) -> str:
    """Send a message to the agent and return the response.
    
    Uses stateless approach: client maintains full history and sends
    all messages each turn.
    """
    if USE_STREAMING:
        return send_message_streaming(conversation_history, user_message)
    else:
        return send_message_non_streaming(conversation_history, user_message)


def interactive_chat():
    """Run an interactive chat session with the agent using OpenAI SDK."""
    print("=" * 60)
    print("Travel Support Agent - Interactive Chat (OpenAI SDK)")
    print("=" * 60)
    print(f"Agent: {AGENT_NAME}")
    print(f"Streaming: {'Enabled' if USE_STREAMING else 'Disabled'}")
    print(f"Mode: Stateless (client maintains history)")
    print("\nType 'quit' or 'exit' to end the conversation.")
    print("Type 'new' to start a new conversation.")
    print("Type 'history' to see conversation history.")
    print("=" * 60)
    
    # Create client
    create_client()
    print(f"Connected to: {BASE_URL}\n")
    
    conversation_history = []
    
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
            conversation_history = []
            print("\n--- Starting new conversation ---\n")
            continue
        
        if user_input.lower() == 'history':
            print("\n--- Conversation History ---")
            for i, msg in enumerate(conversation_history):
                role = msg["role"].capitalize()
                content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                print(f"{i+1}. {role}: {content}")
            print(f"--- Total: {len(conversation_history)} messages ---\n")
            continue
        
        # Send message with full history
        try:
            response_text = send_message(
                conversation_history,
                user_input
            )
            
            if response_text:
                # Add both user message and response to history
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": response_text})
        
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
    
    print("\n--- Sending: 'Hey there! What time is my flight?' ---")
    
    response_text = send_message(
        [],  # No history
        "Hey there! What time is my flight?"
    )
    
    print(f"\n--- Response received ({len(response_text)} chars) ---")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        # Run single-turn demo
        single_turn_demo()
    else:
        # Run interactive chat (default)
        interactive_chat()
