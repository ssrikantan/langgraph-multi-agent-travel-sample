"""Simple client to exercise the hosted travel agent via HTTP.
You can host the agent locally in the playground in VS Code, after running container.py.
Refer to https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/vs-code-agents-workflow-pro-code?view=foundry&tabs=windows-powershell&pivots=python
for the steps.

Use this Client to ensure it works, before deploying to a hosted environment.

Usage:
    python -m clients.http_client "hello there, what time is my flight?"

Options:
    --base-url https://...   # defaults to TRAVEL_AGENT_URL env or http://127.0.0.1:8088
    --passenger-id "3442 587242"  # defaults to env DEFAULT_PASSENGER_ID
    --thread-id thread-demo-1      # optional; generated if omitted
    --sync                         # call /responses (blocking) instead of /runs (stream-ish)
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
import time
import json
from typing import Iterable

import requests


def build_payload(message: str, passenger_id: str, thread_id: str) -> dict:
    return {
        "input": [{"role": "user", "content": message}],
        "config": {"configurable": {"passenger_id": passenger_id}},
        "thread_id": thread_id,
    }


def stream_responses(base_url: str, payload: dict) -> None:
    """Stream only the assistant text, not the raw SSE JSON."""

    def handle_event(event_type: str, data: dict, buffers: dict[str, str]):
        event_type = event_type or data.get("type", "")
        if event_type == "response.output_text.delta":
            item_id = data.get("item_id")
            if item_id is None:
                return
            buffers[item_id] = buffers.get(item_id, "") + data.get("delta", "")
            # Print streamed chunk without extra structure.
            print(data.get("delta", ""), end="", flush=True)
        elif event_type == "response.output_text.done":
            # Ensure a trailing newline after the completed message.
            print()

    # Responses API streams when `stream: true` is set in the body.
    url = base_url.rstrip("/") + "/responses"
    payload = {**payload, "stream": True}
    resp = requests.post(
        url,
        json=payload,
        headers={"Accept": "text/event-stream"},
        stream=True,
        timeout=(5, 90),
    )
    resp.raise_for_status()

    ctype = resp.headers.get("content-type", "")
    print(f"Status: {resp.status_code}\n")

    # If the service did not return SSE, just dump the body for visibility.
    if "text/event-stream" not in ctype:
        print(resp.text)
        return

    current_event = ""
    buffers: dict[str, str] = {}

    for raw in resp.iter_lines():
        if not raw:
            continue
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = str(raw)

        if text.startswith("event:"):
            current_event = text[len("event:"):].strip()
            continue

        # Data lines may or may not include the "data:" prefix depending on server.
        if text.startswith("data:"):
            text = text[len("data:"):].strip()

        try:
            payload_obj = json.loads(text)
        except Exception:
            # Non-JSON line; ignore.
            continue

        handle_event(current_event, payload_obj, buffers)


def call_responses(base_url: str, payload: dict) -> None:
    url = base_url.rstrip("/") + "/responses"
    resp = requests.post(url, json=payload, timeout=(5, 90))
    resp.raise_for_status()
    print(f"Status: {resp.status_code}\n")

    data = resp.json()
    response_id = data.get("id")
    if not response_id:
        print(data)
        return

    # Poll until output is available or timeout.
    poll_url = f"{url}/{response_id}"
    deadline = time.time() + 60
    while True:
        poll_resp = requests.get(poll_url, timeout=(5, 30))
        poll_resp.raise_for_status()
        payload = poll_resp.json()
        output = payload.get("output")
        status = payload.get("status")

        if output and any(item is not None for item in output):
            first = output[0] or {}
            content = (first.get("content") or [{}])[0]
            text = content.get("text")
            print(text or payload)
            return
        if status in {"failed", "cancelled"}:
            print(payload)
            return
        if time.time() > deadline:
            print({"error": "timeout waiting for response", "last": payload})
            return
        time.sleep(0.5)


def parse_args(argv: Iterable[str]):
    parser = argparse.ArgumentParser()
    parser.add_argument("message", help="User message to send")
    parser.add_argument(
        "--base-url",
        default=os.getenv("TRAVEL_AGENT_URL", "http://127.0.0.1:8088"),
        help="Base URL of the hosted agent (set TRAVEL_AGENT_URL to override)",
    )
    parser.add_argument(
        "--passenger-id",
        default=os.getenv("DEFAULT_PASSENGER_ID", "3442 587242"),
        help="Passenger ID to look up user flights",
    )
    parser.add_argument("--thread-id", default=None, help="Optional thread id; generated if omitted")
    parser.add_argument("--sync", action="store_true", help="Call /responses instead of SSE streaming")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    thread_id = args.thread_id or f"thread-{uuid.uuid4()}"
    payload = build_payload(args.message, args.passenger_id, thread_id)

    try:
        if args.sync:
            call_responses(args.base_url, payload)
        else:
            stream_responses(args.base_url, payload)
    except requests.HTTPError as http_err:
        print(f"HTTP error: {http_err}\nBody: {getattr(http_err.response, 'text', '')}")
        return 1
    except Exception as exc:  # pragma: no cover - helper script
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
