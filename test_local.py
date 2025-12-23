"""Local test to verify the wrapper graph works."""
import os
from dotenv import load_dotenv

load_dotenv(override=True)

from langchain_core.messages import HumanMessage
from workflow_core import wrapper_graph, invoke_travel_agent

# Test 1: Without passenger ID - should ask for it
print("=" * 60)
print("TEST 1: Without passenger ID")
print("=" * 60)
test_state = {
    "messages": [HumanMessage(content="Hey there! What time is my flight?")]
}

print(f"Input: {test_state}")

try:
    result = wrapper_graph.invoke(test_state)
    print(f"\nResult keys: {result.keys()}")
    print(f"Messages count: {len(result.get('messages', []))}")
    
    for i, msg in enumerate(result.get("messages", [])):
        print(f"\nMessage {i}:")
        print(f"  Type: {type(msg).__name__}")
        print(f"  Content: {getattr(msg, 'content', str(msg))[:500]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()


# Test 2: With passenger ID in message
print("\n" + "=" * 60)
print("TEST 2: With passenger ID in message")
print("=" * 60)
test_state2 = {
    "messages": [HumanMessage(content="My passenger ID is 3442 587242. What time is my flight?")]
}

print(f"Input: {test_state2}")

try:
    result2 = wrapper_graph.invoke(test_state2)
    print(f"\nResult keys: {result2.keys()}")
    print(f"Messages count: {len(result2.get('messages', []))}")
    
    for i, msg in enumerate(result2.get("messages", [])):
        print(f"\nMessage {i}:")
        print(f"  Type: {type(msg).__name__}")
        print(f"  Content: {getattr(msg, 'content', str(msg))[:500]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
