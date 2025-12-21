"""Client-side demo that consumes the streaming helper and prints events.
Run: python -m clients.cli_runner
"""

from __future__ import annotations

import uuid
from typing import Optional

from travel_agent import app
from travel_agent.stream_demo import run_stream_demo


def create_app_context(passenger_id: str = "3442 587242", thread_id: Optional[str] = None):
    """Local copy so the client runner is self-contained."""
    app.db = app.update_dates(app.db)
    resolved_thread_id = thread_id or str(uuid.uuid4())
    config = {
        "configurable": {
            "passenger_id": passenger_id,
            "thread_id": resolved_thread_id,
        }
    }
    return app.part_4_graph, config


def main():
    graph, config = create_app_context()
    _printed = set()

    def on_event(evt: dict):
        # Mirror server-side formatting: show dialog_state and pretty-render each message once
        app._print_event(evt, _printed)

    def on_interrupt(evt: dict) -> str:
        # Simple console prompt to approve/deny sensitive tool calls
        tool_call = evt["messages"][-1].tool_calls[0]
        choice = input(
            f"Approve tool call '{tool_call['name']}'? [y/n/custom message]: "
        ).strip()
        if choice.lower() == "y":
            return "Approved"
        if choice.lower() == "n":
            return "Denied by user"
        # Any other input is forwarded verbatim
        return choice or "Approved"

    print("Type your message and press Enter. Ctrl+C to exit.\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye")
            break
        if not user_input:
            continue
        run_stream_demo(
            [user_input],
            on_event=on_event,
            on_interrupt=on_interrupt,
            graph=graph,
            config=config,
        )


if __name__ == "__main__":
    main()
