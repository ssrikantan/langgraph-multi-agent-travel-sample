"""Custom LangGraph state converter for robust non-streaming response handling.

This module provides a custom state converter that addresses the sparse null array
issue when using non-streaming mode with tool-calling agents.

THE PROBLEM:
The default `LanggraphMessageStateConverter` uses `stream_mode="updates"` for 
non-streaming requests. This produces output like:
    [
        {"fetch_user_info": {"messages": [...], "user_info": ...}},
        {"primary_assistant": {"messages": [...]}},
        {"tool_node": {"messages": [...]}},  # Tool execution
        {"primary_assistant": {"messages": [...]}},  # Final response
    ]

When converting this to a Response, the default converter iterates through ALL steps
and tries to convert each message. If any conversion fails or produces None, the
output array gets null entries, causing `response_parsing_error`.

THE SOLUTION:
This custom converter:
1. Uses `stream_mode="values"` to get the FINAL state instead of incremental updates
2. Extracts only the LAST assistant message (the actual response to the user)
3. Filters out intermediate tool calls and tool messages from the output
4. Ensures a clean, single-message response that works with non-streaming clients

USAGE:
    from custom_state_converter import RobustStateConverter
    from azure.ai.agentserver.langgraph import from_langgraph
    
    adapter = from_langgraph(
        part_4_graph,
        state_converter=RobustStateConverter()
    )
"""

import time
from typing import Any, AsyncGenerator, AsyncIterator, Dict

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from azure.ai.agentserver.core.models import projects as project_models
from azure.ai.agentserver.core.models import Response, ResponseStreamEvent
from azure.ai.agentserver.core.server.common.agent_run_context import AgentRunContext
from azure.ai.agentserver.langgraph.models.langgraph_state_converter import LanggraphStateConverter
from azure.ai.agentserver.langgraph.models.langgraph_request_converter import LangGraphRequestConverter
from azure.ai.agentserver.langgraph.models.langgraph_stream_response_converter import LangGraphStreamResponseConverter


class RobustStateConverter(LanggraphStateConverter):
    """
    A more robust state converter that handles non-streaming responses correctly.
    
    Key differences from the default converter:
    1. Uses "values" stream mode for non-streaming to get final state
    2. Only extracts the last AI message for the response (not all intermediate steps)
    3. Properly handles tool execution without producing null entries
    """
    
    def get_stream_mode(self, context: AgentRunContext) -> str:
        """
        Return the stream mode based on whether streaming is requested.
        
        For streaming: "messages" (incremental message updates)
        For non-streaming: "values" (final state values, not step updates)
        """
        if context.request.get("stream"):
            return "messages"
        # Use "values" instead of "updates" to get the final state
        # This avoids the issue of iterating through all intermediate steps
        return "values"
    
    def request_to_state(self, context: AgentRunContext) -> Dict[str, Any]:
        """Convert the incoming request to LangGraph state."""
        converter = LangGraphRequestConverter(context.request)
        return converter.convert()
    
    def state_to_response(self, state: Any, context: AgentRunContext) -> Response:
        """
        Convert the final LangGraph state to a Response.
        
        With stream_mode="values", the state is the final graph state dict,
        not a list of step updates. We extract the last AI message as the response.
        """
        output = []
        
        # With stream_mode="values", state is the final state dict
        # e.g., {"messages": [...], "user_info": "...", "passenger_id": "...", "dialog_state": [...]}
        messages = state.get("messages", [])
        
        # Find the last AI message that has content (the actual response to user)
        last_ai_message = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                # Skip AI messages that are only tool calls (no text content)
                if msg.content and not msg.tool_calls:
                    last_ai_message = msg
                    break
                # If no content but has tool calls, this might be the only response
                # (agent delegating to a tool) - skip it, we want the final text response
        
        if last_ai_message:
            # Convert to output format
            content_text = last_ai_message.content
            if isinstance(content_text, list):
                # Handle list content (e.g., [{"type": "text", "text": "..."}])
                content_text = " ".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in content_text
                )
            
            output.append(
                project_models.ResponsesAssistantMessageItemResource(
                    content=[
                        project_models.ItemContent({
                            "type": project_models.ItemContentType.OUTPUT_TEXT,
                            "text": content_text,
                            "annotations": [],
                        })
                    ],
                    id=context.id_generator.generate_message_id(),
                    status="completed",
                )
            )
        else:
            # Fallback: If no AI message found, return an empty response
            # This shouldn't happen in normal operation
            output.append(
                project_models.ResponsesAssistantMessageItemResource(
                    content=[
                        project_models.ItemContent({
                            "type": project_models.ItemContentType.OUTPUT_TEXT,
                            "text": "I apologize, but I couldn't process your request. Please try again.",
                            "annotations": [],
                        })
                    ],
                    id=context.id_generator.generate_message_id(),
                    status="completed",
                )
            )
        
        agent_id = context.get_agent_id_object()
        conversation = context.get_conversation_object()
        
        response = Response(
            object="response",
            id=context.response_id,
            agent=agent_id,
            conversation=conversation,
            metadata=context.request.get("metadata"),
            created_at=int(time.time()),
            output=output,
            status="completed",
        )
        return response
    
    async def state_to_response_stream(
        self, stream_state: AsyncIterator[Dict[str, Any] | Any], context: AgentRunContext
    ) -> AsyncGenerator[ResponseStreamEvent, None]:
        """
        Convert streaming state updates to response events.
        
        For streaming, we use the default behavior which works correctly.
        The streaming path doesn't have the sparse null array issue.
        """
        response_converter = LangGraphStreamResponseConverter(stream_state, context)
        async for result in response_converter.convert():
            yield result
