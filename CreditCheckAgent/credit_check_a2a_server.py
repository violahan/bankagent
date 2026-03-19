"""A2A server wrapping the credit-check agent.

Exposes the CreditCheckAgent as an A2A-compliant service using
strands.multiagent.a2a.A2AServer and FastAPI.

Usage:
    1. Make sure Ollama is running:
           ollama pull qwen2.5
    2. Start this A2A server:
           cd CreditCheckAgent && uvicorn a2a_server:app --host 0.0.0.0 --port 8082
"""

from __future__ import annotations

import logging
import os
import textwrap

from a2a.types import AgentSkill
from strands import Agent, tool
from strands.models.anthropic import AnthropicModel
from strands.models.ollama import OllamaModel
from strands.multiagent.a2a import A2AServer

from credit_lookup import format_credit_check_report, lookup_credit_check, parse_credit_check_request

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a bank credit check agent.

    You should only handle requests in this format:
    "I want the credit check result from <name> whose address is <address>"

    Your job:
      1. Pass the user's raw request text to the `get_credit_check` tool.
      2. Return the credit check result clearly and concisely.

    Always call the tool for credit-check requests.
    If the request is not in the expected format, ask the user to restate it exactly
    as: I want the credit check result from <name> whose address is <address>
    When you return a completed lookup, include the report fields exactly as provided
    by the tool so downstream agents can use them directly.
""")

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_ANTHROPIC_MAX_TOKENS = 4096

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", DEFAULT_MODEL_PROVIDER).strip().lower()
MODEL_ID = os.getenv("MODEL_ID", DEFAULT_MODEL)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", str(DEFAULT_ANTHROPIC_MAX_TOKENS)))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8082"))


@tool
def get_credit_check(request_text: str) -> str:
    """Return a mock credit check from the raw credit-check request sentence."""

    name, address = parse_credit_check_request(request_text)
    report = lookup_credit_check(name=name, address=address)
    return format_credit_check_report(report)


if MODEL_PROVIDER == "anthropic":
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is required when MODEL_PROVIDER=anthropic.")
    model = AnthropicModel(
        client_args={"api_key": ANTHROPIC_API_KEY},
        model_id=MODEL_ID,
        max_tokens=ANTHROPIC_MAX_TOKENS,
    )
elif MODEL_PROVIDER == "ollama":
    model = OllamaModel(host=OLLAMA_HOST, model_id=MODEL_ID)
else:
    raise ValueError(
        f"Unsupported MODEL_PROVIDER={MODEL_PROVIDER!r}. Use 'anthropic' or 'ollama'."
    )

agent = Agent(
    name="Credit Check Agent",
    description=(
        "Accepts a narrow credit-check request sentence, extracts the applicant, and "
        "returns bureau score, debt-to-income ratio, credit utilisation, "
        "delinquencies, bankruptcies, hard inquiries, and external rating."
    ),
    model=model,
    tools=[get_credit_check],
    system_prompt=SYSTEM_PROMPT,
    callback_handler=None,
)

a2a_server = A2AServer(
    agent=agent,
    host=HOST,
    port=PORT,
    version="1.0.0",
    skills=[
        AgentSkill(
            id="credit_check",
            name="Credit Check",
            description=(
                "Given a request in the form 'I want the credit check result from "
                "<name> whose address is <address>', returns a structured credit "
                "check containing the fields required for policy analysis."
            ),
            tags=["credit", "bureau", "banking", "loan"],
            examples=[
                "I want the credit check result from Jane Doe whose address is 123 Maple Street, Springfield, IL 62704.",
                "I want the credit check result from John Smith whose address is 456 Oak Avenue, Denver, CO 80203.",
            ],
        ),
    ],
)

app = a2a_server.to_fastapi_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
