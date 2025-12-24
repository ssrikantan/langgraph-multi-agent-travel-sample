# Before running the sample:
#    pip install --pre azure-ai-projects>=2.0.0b1
#    pip install azure-identity
#    pip install opentelemetry-sdk opentelemetry-api
#    pip install httpx

import uuid
import json
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
import httpx

# Configuration
USE_STREAMING = True  # Set to False for non-streaming behavior
SHOW_TELEMETRY = False  # Set to True to see OpenTelemetry trace output

# Global conversation ID for stateful mode
current_conversation_id = None

# Set up OpenTelemetry tracing
trace.set_tracer_provider(TracerProvider())
tracer_provider = trace.get_tracer_provider()
if SHOW_TELEMETRY:
    tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
tracer = trace.get_tracer(__name__)

myEndpoint = "https://sansri-foundry-hosted-agents-pro.services.ai.azure.com/api/projects/sansri-foundry-hosted-agents-project"

project_client = AIProjectClient(
    endpoint=myEndpoint,
    credential=DefaultAzureCredential(),
)

myAgent = "travel-multi-agent"


def get_auth_token():
    """Get a fresh auth token."""
    credential = DefaultAzureCredential()
    return credential.get_token("https://ai.azure.com/.default").token


def create_conversation():
    """Create a new conversation via the Foundry API."""
    token = get_auth_token()
    api_url = f"{myEndpoint}/openai/conversations?api-version=2025-11-15-preview"
    
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


def get_or_create_conversation_id():
    """Get current conversation ID or create a new one."""
    global current_conversation_id
    if not current_conversation_id:
        current_conversation_id = create_conversation()
        print(f"Created new conversation: {current_conversation_id}")
    return current_conversation_id


def reset_conversation():
    """Reset the conversation by creating a new one."""
    global current_conversation_id
    current_conversation_id = create_conversation()
    return current_conversation_id


def send_message(user_message: str, agent_name: str = myAgent):
    """Send a message to the agent and return the response.
    
    Uses stateful approach: server maintains conversation history via conversation_id.
    Client only sends the new message each turn.
    
    Args:
        user_message: The user's message to send
        agent_name: The name of the agent to call
        
    Returns:
        tuple: (response_text, conversation_id, full_response_data)
    """
    global current_conversation_id
    
    token = get_auth_token()
    api_url = f"{myEndpoint}/openai/responses?api-version=2025-11-15-preview"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Get or create conversation
    conversation_id = get_or_create_conversation_id()
    
    # Build the payload - stateful approach with conversation ID
    payload = {
        "input": [{"role": "user", "content": user_message}],
        "conversation": conversation_id,  # Server maintains history
        "agent": {"name": agent_name, "type": "agent_reference"},
        "stream": USE_STREAMING
    }
    
    # Debug: show what we're sending
    print(f"\n[DEBUG] Sending to conversation: {conversation_id}")
    print(f"[DEBUG] Input: {user_message[:50]}...")
    
    response_text = ""
    response_data = None
    new_conversation_id = None
    
    if USE_STREAMING:
        # Streaming mode - process Server-Sent Events as they arrive
        with httpx.Client(timeout=120.0) as client:
            with client.stream("POST", api_url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    error_text = response.read().decode()
                    print(f"Error: HTTP {response.status_code}: {error_text}")
                    return None, conversation_id, None
                
                for line in response.iter_lines():
                    if not line:
                        continue
                    
                    # SSE format: "data: {...json...}" or "data: [DONE]"
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            event = json.loads(data_str)
                            event_type = event.get("type", "")
                            
                            # Handle different event types
                            if event_type == "response.output_text.delta":
                                # Text chunk - print immediately for real-time effect
                                delta = event.get("delta", "")
                                print(delta, end="", flush=True)
                                response_text += delta
                            
                            elif event_type == "response.completed":
                                # Final response with full data
                                response_data = event.get("response", {})
                            
                            elif event_type == "response.output_item.added":
                                # New output item (message or function call) started
                                item = event.get("item", {})
                                role = item.get("role", "")
                                item_type = item.get("type", "")
                                if role == "assistant":
                                    print("\nAssistant: ", end="", flush=True)
                                elif item_type == "function_call":
                                    # Show tool being called
                                    func_name = item.get("name", "unknown")
                                    print(f"\n🔧 Calling tool: {func_name}", flush=True)
                            
                        except json.JSONDecodeError:
                            pass
        
        # Extract conversation ID from final response
        if response_data:
            conversation = response_data.get("conversation")
            new_conversation_id = conversation.get("id") if conversation else None
        
        print()  # New line after streaming
    
    else:
        # Non-streaming mode - wait for complete response
        with httpx.Client(timeout=120.0) as client:
            response = client.post(api_url, headers=headers, json=payload)
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}: {response.text}")
                return None, conversation_id, None
            response_data = response.json()
        
        # Extract the output messages
        output = response_data.get("output", [])
        for item in output:
            if item and item.get("type") == "message" and item.get("role") == "assistant":
                content = item.get("content", [])
                for c in content:
                    if c.get("type") == "output_text":
                        response_text = c.get("text", "")
                        print(f"\nAssistant: {response_text}")
        
        # Extract conversation ID
        conversation = response_data.get("conversation")
        new_conversation_id = conversation.get("id") if conversation else None
    
    return response_text, new_conversation_id, response_data


def interactive_chat():
    """Run an interactive chat session with the agent.
    
    Uses stateful approach: server maintains conversation history via conversation_id.
    Client only sends new messages each turn.
    """
    print("=" * 60)
    print("Travel Support Agent - Interactive Chat (HTTP)")
    print("=" * 60)
    print(f"Agent: {myAgent}")
    print(f"Streaming: {'Enabled' if USE_STREAMING else 'Disabled'}")
    print(f"Mode: Stateful (server maintains history via conversation_id)")
    print("\nType 'quit' or 'exit' to end the conversation.")
    print("Type 'new' to start a new conversation.")
    print("Type 'conversation' to see current conversation ID.")
    print("=" * 60)
    
    # Get an existing agent
    agent = project_client.agents.get(agent_name=myAgent)
    print(f"Connected to agent: {agent.name}\n")
    
    # Create initial conversation
    conversation_id = get_or_create_conversation_id()
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
            conversation_id = reset_conversation()
            print(f"\n--- Starting new conversation (ID: {conversation_id}) ---\n")
            continue
        
        if user_input.lower() == 'conversation':
            print(f"\nCurrent Conversation ID: {current_conversation_id}")
            print("(Server maintains conversation history)\n")
            continue
        
        # Send only the new message - server handles history
        with tracer.start_as_current_span("agent-turn") as span:
            span.set_attribute("user.message", user_input[:100])
            span.set_attribute("conversation.id", current_conversation_id or "none")
            
            response_text, conv_id, response_data = send_message(
                user_input,
                agent_name=agent.name
            )
            
            if response_text:
                span.set_attribute("assistant.response.length", len(response_text))


def single_turn_demo():
    """Run a single-turn demo (original behavior)."""
    # Get an existing agent
    agent = project_client.agents.get(agent_name=myAgent)
    print(f"Retrieved agent: {agent.name}")

    # Create a conversation
    conversation_id = get_or_create_conversation_id()
    print(f"Conversation ID: {conversation_id}")

    # Make direct HTTP request
    with tracer.start_as_current_span("agent-request") as span:
        span.set_attribute("conversation.id", conversation_id)
        span.set_attribute("agent.name", agent.name)
        
        print("\n--- Sending: 'Hey there! What time is my flight?' ---")
        response_text, conv_id, response_data = send_message(
            "Hey there! What time is my flight?"
        )
        
        if response_data:
            response_id = response_data.get("id", "unknown")
            span.set_attribute("response.id", response_id)
            print(f"Response ID: {response_id}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        # Run single-turn demo (original behavior)
        single_turn_demo()
    else:
        # Run interactive chat (default)
        interactive_chat()
