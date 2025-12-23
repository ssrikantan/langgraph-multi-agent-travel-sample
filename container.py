"""Container entrypoint to host the LangGraph agent in Microsoft AI Foundry."""

from dotenv import load_dotenv
from agent_framework.observability import setup_observability

# Load environment variables (e.g., AZURE_OPENAI_* and model deployment names)
load_dotenv(override=True)

from workflow_core import create_agent, get_credential


def main() -> None:
    # We accept get_credential for symmetry with the agent-framework sample; the
    # LangGraph adapter currently does not require the credential directly, but
    # your graph may use DefaultAzureCredential/ManagedIdentityCredential internally
    # (as travel_agent.app does for Azure OpenAI).
    _ = get_credential()
    setup_observability(vs_code_extension_port=4319, enable_sensitive_data=False)
    adapter = create_agent(chat_client=None, as_agent=False)
    adapter.run()


if __name__ == "__main__":
    main()
