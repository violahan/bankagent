"""Credit-check agent.

Looks up a mock credit report from a narrow request sentence.

Usage:
    1. Make sure Ollama is running with a tool-capable model pulled:
           ollama pull qwen2.5
    2. Run this agent:
           cd CreditCheckAgent && python test_script.py
"""

from __future__ import annotations

import argparse
import os
import textwrap

from strands import Agent, tool
from strands.models.anthropic import AnthropicModel
from strands.models.ollama import OllamaModel

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


@tool
def get_credit_check(request_text: str) -> str:
    """Return a mock credit check from the raw credit-check request sentence."""

    name, address = parse_credit_check_request(request_text)
    report = lookup_credit_check(name=name, address=address)
    return format_credit_check_report(report)


def run_credit_check(
    request_text: str,
    *,
    model_provider: str = os.getenv("MODEL_PROVIDER", DEFAULT_MODEL_PROVIDER).strip().lower(),
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    model_id: str = DEFAULT_MODEL,
) -> str:
    """Run a single credit check and return the agent response text."""

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
        model = OllamaModel(host=ollama_host, model_id=model_id)
    else:
        raise ValueError(
            f"Unsupported MODEL_PROVIDER={model_provider!r}. Use 'anthropic' or 'ollama'."
        )

    agent = Agent(
        model=model,
        tools=[get_credit_check],
        system_prompt=SYSTEM_PROMPT,
    )
    result = agent(request_text)
    return result.message["content"][0]["text"]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Credit-check agent")
    parser.add_argument("--provider", default=os.getenv("MODEL_PROVIDER", DEFAULT_MODEL_PROVIDER), help="Model provider: anthropic or ollama")
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST, help="Ollama server address")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model id")
    return parser.parse_args(argv)


SAMPLE_REQUEST = "I want the credit check result from John Smith whose address is 456 Oak Avenue, Denver, CO 80203"


if __name__ == "__main__":
    args = _parse_args()

    print("=" * 60)
    print("Credit-Check Agent")
    print("=" * 60)

    request_text = input("\nCredit-check request sentence (or press Enter for sample):\n> ").strip()
    if not request_text:
        request_text = SAMPLE_REQUEST
        print(f"\nUsing sample request:\n{request_text}")

    print("\n" + "-" * 60)
    print("Running credit check …")
    print("-" * 60 + "\n")

    response = run_credit_check(
        request_text,
        model_provider=args.provider,
        ollama_host=args.ollama_host,
        model_id=args.model,
    )

    print("\n" + "=" * 60)
    print("CREDIT CHECK RESULT")
    print("=" * 60)
    print(response)
