"""Credit-check analysis agent.

Connects to the RuleFetchMCP server, fetches the relevant policy rules, and
analyses a user profile + credit-check result against those rules.

Usage:
    1. Start the RuleFetchMCP server:
           cd RuleFetchMCP && python mcp_server.py
    2. Make sure Ollama is running with a tool-capable model pulled:
           ollama pull qwen2.5
    3. Run this agent:
           cd AnalyseAgent && python agent.py
"""

import argparse
import os
import textwrap

from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models.anthropic import AnthropicModel
from strands.models.ollama import OllamaModel
from strands.tools.mcp import MCPClient

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
DEFAULT_MODEL_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_ANTHROPIC_MAX_TOKENS = 4096


def analyse(
    user_profile: str,
    credit_result: str,
    *,
    mcp_url: str = DEFAULT_MCP_URL,
    model_provider: str = os.getenv("MODEL_PROVIDER", DEFAULT_MODEL_PROVIDER).strip().lower(),
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    model_id: str = DEFAULT_MODEL,
) -> str:
    """Run a single analysis and return the agent's response text."""

    prompt = (
        f"## User Profile\n{user_profile}\n\n"
        f"## Credit-Check Result\n{credit_result}\n\n"
        "Please fetch the applicable credit-check rules and analyse this application."
    )

    mcp_client = MCPClient(lambda: streamablehttp_client(mcp_url))

    if model_provider == "anthropic":
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when MODEL_PROVIDER=anthropic.")
        model = AnthropicModel(
            client_args={"api_key": anthropic_api_key},
            model_id=model_id,
            max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", str(DEFAULT_ANTHROPIC_MAX_TOKENS))),
        )
    elif model_provider == "ollama":
        model = OllamaModel(
            host=ollama_host,
            model_id=model_id,
        )
    else:
        raise ValueError(
            f"Unsupported MODEL_PROVIDER={model_provider!r}. Use 'anthropic' or 'ollama'."
        )

    with mcp_client:
        tools = mcp_client.list_tools_sync()
        agent = Agent(
            model=model,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
            # callback_handler=None,
        )
        result = agent(prompt)

    return result.message["content"][0]["text"]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Credit-check analysis agent")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL, help="RuleFetchMCP streamable-HTTP URL")
    parser.add_argument("--provider", default=os.getenv("MODEL_PROVIDER", DEFAULT_MODEL_PROVIDER), help="Model provider: anthropic or ollama")
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST, help="Ollama server address")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model id")
    return parser.parse_args(argv)


SAMPLE_USER_PROFILE = textwrap.dedent("""\
    Name: Jane Doe
    Age: 34
    Employment status: full-time
    Annual income: $85,000
    Existing monthly debt payments: $1,200
    Applying for: personal loan for debt consolidation
""")

SAMPLE_CREDIT_RESULT = textwrap.dedent("""\
    Bureau score: 710
    Debt-to-income ratio: 0.35
    Credit utilisation: 0.42
    Number of delinquencies: 0
    Bankruptcies: 0
    Hard inquiries in last 6 months: 2
    External rating: B
""")


if __name__ == "__main__":
    args = _parse_args()

    print("=" * 60)
    print("Credit-Check Analysis Agent")
    print("=" * 60)

    user_profile = input("\nPaste the user profile (or press Enter for sample):\n> ").strip()
    if not user_profile:
        user_profile = SAMPLE_USER_PROFILE
        print(f"\nUsing sample profile:\n{user_profile}")

    credit_result = input("\nPaste the credit-check result (or press Enter for sample):\n> ").strip()
    if not credit_result:
        credit_result = SAMPLE_CREDIT_RESULT
        print(f"\nUsing sample credit result:\n{credit_result}")

    print("\n" + "-" * 60)
    print("Running analysis …")
    print("-" * 60 + "\n")

    response = analyse(
        user_profile,
        credit_result,
        mcp_url=args.mcp_url,
        model_provider=args.provider,
        ollama_host=args.ollama_host,
        model_id=args.model,
    )

    print("\n" + "=" * 60)
    print("ANALYSIS RESULT")
    print("=" * 60)
    print(response)
