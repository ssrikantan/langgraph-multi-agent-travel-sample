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

# Set up OpenTelemetry tracing
trace.set_tracer_provider(TracerProvider())
tracer_provider = trace.get_tracer_provider()
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
tracer = trace.get_tracer(__name__)

myEndpoint = "https://sansri-foundry-hosted-agents-pro.services.ai.azure.com/api/projects/sansri-foundry-hosted-agents-project"

project_client = AIProjectClient(
    endpoint=myEndpoint,
    credential=DefaultAzureCredential(),
)

myAgent = "travel-multi-agent"
# Generate a unique conversation ID for telemetry tracking
local_conversation_id = str(uuid.uuid4())
print(f"Local Conversation ID: {local_conversation_id}")

# Get an existing agent
agent = project_client.agents.get(agent_name=myAgent)
print(f"Retrieved agent: {agent.name}")

# Get auth token for direct HTTP call
credential = DefaultAzureCredential()
token = credential.get_token("https://ai.azure.com/.default").token

# Make direct HTTP request to avoid SDK parsing issues
with tracer.start_as_current_span("agent-request") as span:
    span.set_attribute("local.conversation.id", local_conversation_id)
    span.set_attribute("agent.name", agent.name)
    
    api_url = f"{myEndpoint}/openai/responses?api-version=2025-11-15-preview"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "input": [{"role": "user", "content": "Hey there! What time is my flight?"}],
        "agent": {"name": agent.name, "type": "agent_reference"}
    }
    
    with httpx.Client(timeout=120.0) as client:
        response = client.post(api_url, headers=headers, json=payload)
        print(f"\nHTTP Status: {response.status_code}")
        print(f"Raw Response: {response.text[:1000]}")  # First 1000 chars for debugging
        response_data = response.json()
    
    # Extract telemetry info with null checks
    conversation = response_data.get("conversation") if response_data else None
    foundry_conversation_id = conversation.get("id", "unknown") if conversation else "unknown"
    response_id = response_data.get("id", "unknown") if response_data else "unknown"
    
    span.set_attribute("foundry.conversation.id", foundry_conversation_id)
    span.set_attribute("response.id", response_id)
    
    print(f"\nFoundry Conversation ID: {foundry_conversation_id}")
    print(f"Response ID: {response_id}")
    
    # Extract the output messages
    output = response_data.get("output", [])
    for item in output:
        if item and item.get("type") == "message":
            content = item.get("content", [])
            for c in content:
                if c.get("type") == "output_text":
                    print(f"\nAgent Response: {c.get('text')}")

print(f"\nFull Response: {json.dumps(response_data, indent=2)}")
