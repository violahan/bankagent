"""A2A server wrapping the credit-check analysis agent.

Exposes the AnalyseAgent as an A2A-compliant service using
strands.multiagent.a2a.A2AServer and FastAPI.

Usage:
    1. Start the CreditServicesMCP server:
           cd CreditServicesMCP && python mcp_server.py
    2. Make sure Ollama is running:
           ollama pull qwen2.5
    3. Start this A2A server:
           cd AnalyseAgent && uvicorn a2a_server:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import atexit
import logging
import os

from a2a.types import AgentSkill
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models.anthropic import AnthropicModel
from strands.models.ollama import OllamaModel
from strands.multiagent.a2a import A2AServer
from strands.tools.mcp import MCPClient
import textwrap

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a senior credit analyst at a bank.

    You will receive a user request about a loan application.
    The request may include:
      1. A **user profile** describing the applicant (age, employment, income, etc.).
      2. The applicant's **name** and **address**.
      3. Sometimes a **credit-check result** with bureau score, debt-to-income ratio,
         credit utilisation, delinquencies, bankruptcies, hard inquiries, etc.

    Your job:
      a. Determine which loan product the applicant is applying for.
      b. If the user did not already provide a credit-check result but did provide
         name and address, call the `get_credit_check` tool with those exact
         `name` and `address` values to generate the credit-check result.
      c. Call the `get_credit_check_rules` tool with the matching policy_type
         (one of: personal_loan, vehicle_loan, mortgage_refinance) to retrieve
         the bank's current credit policy.
      d. Compare every field in the applicant's profile and credit report
         against the policy thresholds.
      e. Produce a structured analysis containing:
           - PASS / FAIL / MANUAL REVIEW recommendation
           - A table of each rule, the applicant's value, the threshold, and
             whether it passed.
           - A plain-English summary explaining the decision.

    If the user's text does not specify a loan product, infer the most likely
    one from context, or ask the user to clarify.
    If neither a credit-check result nor enough information to call
    `get_credit_check` is present, ask the user for the missing information.
""")

DEFAULT_MCP_URL = "http://localhost:8000/mcp"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_ANTHROPIC_MAX_TOKENS = 4096

logger = logging.getLogger(__name__)

MCP_URL = os.getenv("MCP_URL", DEFAULT_MCP_URL)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", DEFAULT_MODEL_PROVIDER).strip().lower()
MODEL_ID = os.getenv("MODEL_ID", DEFAULT_MODEL)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", str(DEFAULT_ANTHROPIC_MAX_TOKENS)))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))

# MCP connection kept alive for the lifetime of the process.
mcp_client = MCPClient(lambda: streamablehttp_client(MCP_URL))
mcp_client.__enter__()
atexit.register(lambda: mcp_client.__exit__(None, None, None))

tools = mcp_client.list_tools_sync()

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
    name="Credit Check Analysis Agent",
    description=(
        "Analyses loan applications by generating or using a credit-check result, "
        "then comparing it against bank credit-policy rules."
    ),
    model=model,
    tools=tools,
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
            id="credit_analysis",
            name="Credit Analysis",
            description=(
                "Given a loan application, generates or uses a credit-check result, "
                "fetches the applicable bank credit-policy rules, and returns a "
                "structured PASS/FAIL/MANUAL REVIEW recommendation."
            ),
            tags=["credit", "analysis", "banking", "loan"],
            examples=[
                "Analyse this personal loan application for Jane Doe …",
                "Check whether this vehicle loan applicant passes policy …",
            ],
        ),
    ],
)

app = a2a_server.to_fastapi_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
