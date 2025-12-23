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


def send_message(user_message: str, conversation_history: list = None, agent_name: str = myAgent):
    """Send a message to the agent and return the response.
    
    Uses stateless approach: sends full conversation history each turn
    since the hosted agent uses InMemorySaver which doesn't persist.
    
    Args:
        user_message: The user's message to send
        conversation_history: Full conversation history to send
        agent_name: The name of the agent to call
        
    Returns:
        tuple: (response_text, conversation_id, full_response_data)
    """
    token = get_auth_token()
    api_url = f"{myEndpoint}/openai/responses?api-version=2025-11-15-preview"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Build input messages from history + new message
    input_messages = []
    if conversation_history:
        for msg in conversation_history:
            input_messages.append({"role": msg["role"], "content": msg["content"]})
    input_messages.append({"role": "user", "content": user_message})
    
    # Build the payload - stateless approach, no conversation ID
    payload = {
        "input": input_messages,
        "agent": {"name": agent_name, "type": "agent_reference"},
        "stream": USE_STREAMING
    }
    
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
                                # New output item (message) started
                                item = event.get("item", {})
                                role = item.get("role", "")
                                if role == "assistant":
                                    print("\nAssistant: ", end="", flush=True)
                            
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
    
    Uses stateless approach: client maintains full history and sends
    all messages each turn (since hosted agent uses InMemorySaver).
    """
    print("=" * 60)
    print("Travel Support Agent - Interactive Chat")
    print("=" * 60)
    print(f"Agent: {myAgent}")
    print(f"Streaming: {'Enabled' if USE_STREAMING else 'Disabled'}")
    print(f"Mode: Stateless (client maintains history)")
    print("\nType 'quit' or 'exit' to end the conversation.")
    print("Type 'new' to start a new conversation.")
    print("Type 'history' to see conversation history.")
    print("=" * 60)
    
    # Get an existing agent
    agent = project_client.agents.get(agent_name=myAgent)
    print(f"Connected to agent: {agent.name}\n")
    
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
        with tracer.start_as_current_span("agent-turn") as span:
            span.set_attribute("user.message", user_input[:100])
            span.set_attribute("conversation.turn", len(conversation_history) + 1)
            span.set_attribute("history.length", len(conversation_history))
            
            response_text, conversation_id, response_data = send_message(
                user_input,
                conversation_history=conversation_history,
                agent_name=agent.name
            )
            
            if response_text:
                # Add both user message and response to history
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": response_text})
                span.set_attribute("assistant.response.length", len(response_text))
            
            if conversation_id:
                span.set_attribute("conversation.id", conversation_id)


def single_turn_demo():
    """Run a single-turn demo (original behavior)."""
    # Generate a unique conversation ID for telemetry tracking
    local_conversation_id = str(uuid.uuid4())
    print(f"Local Conversation ID: {local_conversation_id}")

    # Get an existing agent
    agent = project_client.agents.get(agent_name=myAgent)
    print(f"Retrieved agent: {agent.name}")

    # Make direct HTTP request to avoid SDK parsing issues
    with tracer.start_as_current_span("agent-request") as span:
        span.set_attribute("local.conversation.id", local_conversation_id)
        span.set_attribute("agent.name", agent.name)
        
        print("\n--- Sending: 'Hey there! What time is my flight?' ---")
        response_text, conversation_id, response_data = send_message(
            "Hey there! What time is my flight?",
            conversation_history=None  # No history for single turn
        )
        
        if conversation_id:
            span.set_attribute("foundry.conversation.id", conversation_id)
            print(f"\nFoundry Conversation ID: {conversation_id}")
        
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
