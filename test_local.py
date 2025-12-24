"""Local test to verify the travel agent graph works with passenger_id persistence."""
import os
from dotenv import load_dotenv

load_dotenv(override=True)

from langchain_core.messages import HumanMessage
from travel_agent.app import part_4_graph

# Use a consistent thread_id to test state persistence across turns
THREAD_ID = "test-thread-001"

def run_turn(user_message: str, passenger_id: str = None):
    """Run a single turn of the conversation."""
    state = {
        "messages": [HumanMessage(content=user_message)]
    }
    
    config = {"configurable": {"thread_id": THREAD_ID}}
    if passenger_id:
        config["configurable"]["passenger_id"] = passenger_id
    
    print(f"\n👤 User: {user_message}")
    print(f"   Config: {config['configurable']}")
    
    result = part_4_graph.invoke(state, config=config)
    
    # Get the last AI message
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, 'content') and type(msg).__name__ == 'AIMessage':
            content = msg.content[:500] if len(msg.content) > 500 else msg.content
            print(f"\n🤖 Assistant: {content}")
            break
    
    # Show state info
    print(f"\n   State passenger_id: {result.get('passenger_id')}")
    return result


# Test 1: First turn - provide passenger ID via config
print("=" * 60)
print("TEST 1: First turn with passenger_id in config")
print("=" * 60)
try:
    result1 = run_turn("Hey there! What time is my flight?", passenger_id="3442 587242")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()


# Test 2: Second turn - passenger_id should persist from checkpoint
print("\n" + "=" * 60)
print("TEST 2: Second turn - passenger_id should persist")
print("=" * 60)
try:
    result2 = run_turn("Can you postpone my flight by 7 days?")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()


# Test 3: Third turn - still persisted?
print("\n" + "=" * 60)
print("TEST 3: Third turn - still persisted?")
print("=" * 60)
try:
    result3 = run_turn("What hotels are available near my destination?")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
