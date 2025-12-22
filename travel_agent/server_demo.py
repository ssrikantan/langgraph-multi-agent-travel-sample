"""Local-only CLI harness for the LangGraph demo.

Purpose
-------
- Runs the travel agent graph entirely in-process for quick local testing and tutorials.
- Shows how to wire `configurable` values (passenger_id, thread_id) and stream events from the graph.

When to use
-----------
- Use locally to iterate on the graph logic without the Azure-hosted adapter.
- Good reference for building your own CLI or service wrapper.

When not to use
---------------
- Not used by the Foundry Hosted Agent runtime; the hosted path is through container.py/workflow_core.py.
"""

import os
import uuid
from typing import Iterable, Optional

from . import app


def create_app_context(passenger_id: Optional[str] = None, thread_id: Optional[str] = None):
    """Prepare runtime config for the agent graph without mutating the core app module."""
    app.db = app.update_dates(app.db)
    resolved_passenger_id = passenger_id or os.getenv("DEFAULT_PASSENGER_ID", "3442 587242")
    resolved_thread_id = thread_id or str(uuid.uuid4())
    config = {
        "configurable": {
            "passenger_id": resolved_passenger_id,
            "thread_id": resolved_thread_id,
        }
    }
    return app.part_4_graph, config


def stream_user_message(message: str, graph=None, config=None):
    """Yield graph events for a single user message so callers can relay them to a client."""
    graph = graph or app.part_4_graph
    if config is None:
        _, config = create_app_context()
    yield from graph.stream({"messages": ("user", message)}, config, stream_mode="values")


def apply_tool_response(tool_call_id: str, content: str, graph=None, config=None):
    """Resume a run after a user approves/denies a sensitive tool. Returns the resulting events."""
    graph = graph or app.part_4_graph
    if config is None:
        _, config = create_app_context()
    return graph.invoke(
        {
            "messages": [
                app.ToolMessage(
                    tool_call_id=tool_call_id,
                    content=content,
                )
            ]
        },
        config,
    )


def run_cli_demo(
    graph=None,
    config=None,
    questions: Optional[Iterable[str]] = None,
):
    """Run the sample CLI interaction loop used in the tutorial."""
    graph = graph or app.part_4_graph
    if config is None:
        _, config = create_app_context()

    _printed = set()
    tutorial_questions = questions or [
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

    for question in tutorial_questions:
        events = graph.stream({"messages": ("user", question)}, config, stream_mode="values")
        for event in events:
            app._print_event(event, _printed)
        snapshot = graph.get_state(config)
        while snapshot.next:
            try:
                user_input = input(
                    "Do you approve of the above actions? Type 'y' to continue;"
                    " otherwise, explain your requested changed.\n\n"
                )
            except Exception:
                user_input = "y"
            if user_input.strip() == "y":
                graph.invoke(None, config)
            else:
                graph.invoke(
                    {
                        "messages": [
                            app.ToolMessage(
                                tool_call_id=event["messages"][-1].tool_calls[0]["id"],
                                content=(
                                    "API call denied by user. Reasoning: "
                                    f"'{user_input}'. Continue assisting, accounting for the user's input."
                                ),
                            )
                        ]
                    },
                    config,
                )
            snapshot = graph.get_state(config)


if __name__ == "__main__":
    graph, config = create_app_context()
    run_cli_demo(graph=graph, config=config)
