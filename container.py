"""Container entrypoint to host the LangGraph agent in Microsoft AI Foundry."""

import asyncio

from dotenv import load_dotenv
from agent_framework.observability import setup_observability

# Load environment variables (e.g., AZURE_OPENAI_* and model deployment names)
load_dotenv(override=True)

from workflow_core import create_agent, get_credential


async def main() -> None:
    # We accept get_credential for symmetry with the agent-framework sample; the
    # LangGraph adapter currently does not require the credential directly, but
    # your graph may use DefaultAzureCredential/ManagedIdentityCredential internally
    # (as travel_agent.app does for Azure OpenAI).
    _ = get_credential()
    setup_observability(vs_code_extension_port=4319, enable_sensitive_data=False)
    adapter = await create_agent(chat_client=None, as_agent=False)
    await adapter.run_async()


if __name__ == "__main__":
    asyncio.run(main())
