"""A2A server wrapping the credit-check analysis agent.

Exposes the AnalyseAgent as an A2A-compliant service using
strands.multiagent.a2a.A2AServer and FastAPI.

Usage:
    1. Start the RuleFetchMCP server:
           cd RuleFetchMCP && python server.py
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
from strands.models.ollama import OllamaModel
from strands.multiagent.a2a import A2AServer
from strands.tools.mcp import MCPClient
import textwrap

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a senior credit analyst at a bank.

    You will receive TWO pieces of information from the user:
      1. A **user profile** describing the applicant (age, employment, income, etc.).
      2. A **credit-check result** with bureau score, debt-to-income ratio,
         credit utilisation, delinquencies, bankruptcies, hard inquiries, etc.

    Your job:
      a. Determine which loan product the applicant is applying for.
      b. Call the `get_credit_check_rules` tool with the matching policy_type
         (one of: personal_loan, vehicle_loan, mortgage_refinance) to retrieve
         the bank's current credit policy.
      c. Compare every field in the applicant's profile and credit report
         against the policy thresholds.
      d. Produce a structured analysis containing:
           - PASS / FAIL / MANUAL REVIEW recommendation
           - A table of each rule, the applicant's value, the threshold, and
             whether it passed.
           - A plain-English summary explaining the decision.

    If the user's text does not specify a loan product, infer the most likely
    one from context, or ask the user to clarify.
""")

DEFAULT_MCP_URL = "http://localhost:8000/mcp"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5"

logger = logging.getLogger(__name__)

MCP_URL = os.getenv("MCP_URL", DEFAULT_MCP_URL)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
MODEL_ID = os.getenv("MODEL_ID", DEFAULT_MODEL)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))

# MCP connection kept alive for the lifetime of the process.
mcp_client = MCPClient(lambda: streamablehttp_client(MCP_URL))
mcp_client.__enter__()
atexit.register(lambda: mcp_client.__exit__(None, None, None))

tools = mcp_client.list_tools_sync()

ollama_model = OllamaModel(host=OLLAMA_HOST, model_id=MODEL_ID)

agent = Agent(
    name="Credit Check Analysis Agent",
    description=(
        "Analyses user profiles and credit-check results against "
        "bank credit-policy rules. Returns a PASS / FAIL / MANUAL "
        "REVIEW recommendation with a detailed rule-by-rule breakdown."
    ),
    model=ollama_model,
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
                "Given a user profile and credit-check result, fetches "
                "the applicable bank credit-policy rules and produces a "
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
