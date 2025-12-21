"""Lightweight streaming helper: yields LangGraph events so callers can forward to clients.

Intended usage:
- Call run_stream_demo with an on_event callback that sends events to your client transport
    (SSE/WebSocket/etc.). This module does not print by default.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional

from .server_demo import create_app_context, stream_user_message, apply_tool_response


def run_stream_demo(
    questions: Iterable[str],
    *,
    on_event: Optional[Callable[[dict], None]] = None,
    on_interrupt: Optional[Callable[[dict], str]] = None,
    approve_content: str = "Approved",
    graph=None,
    config=None,
):
    """Stream events for each user message and surface them via a callback.

    - on_event: called for every event; push it to your client transport here.
    - approve_content: text sent back when auto-approving sensitive tool calls.
    """
    if graph is None or config is None:
        graph, config = create_app_context()
    emit = on_event or (lambda _e: None)

    for question in questions:
        last_event = None
        for event in stream_user_message(question, graph, config):
            last_event = event
            emit(event)

        snapshot = graph.get_state(config)
        while snapshot.next:
            if not (last_event and last_event.get("messages")):
                break
            tool_call_id = last_event["messages"][-1].tool_calls[0]["id"]

            if on_interrupt:
                response_content = on_interrupt(last_event)
            else:
                response_content = approve_content

            followup = apply_tool_response(tool_call_id, response_content, graph, config)
            if isinstance(followup, list):
                for item in followup:
                    emit(item)
            else:
                emit(followup)
            snapshot = graph.get_state(config)


def _default_questions():
    return [
        "Hi there, what time is my flight?",
        "Am i allowed to update my flight to something sooner? I want to leave later today.",
        "Update my flight to sometime next week then",
        "The next available option is great",
        "what about lodging and transportation?",
        "Yeah i think i'd like an affordable hotel for my week-long stay (7 days). And I'll want to rent a car.",
        "OK could you place a reservation for your recommended hotel? It sounds nice.",
        "yes go ahead and book anything that's moderate expense and has availability.",
        "Now for a car, what are my options?",
        "Awesome let's just get the cheapest option. Go ahead and book for 7 days",
        "Cool so now what recommendations do you have on excursions?",
        "Are they available while I'm there?",
        "interesting - i like the museums, what options are there? ",
        "OK great pick one and book it for my second day there.",
    ]
