"""Credit-check agent.

Looks up a mock credit report from a narrow request sentence.

Usage:
    1. Ensure AWS credentials and region for Bedrock are available.
    2. Run this agent:
           cd CreditCheckAgent && python test_script.py
"""

from __future__ import annotations

import argparse
import os
import textwrap

import boto3
from strands import Agent, tool
from strands.models import BedrockModel

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

DEFAULT_AWS_REGION = "ap-southeast-2"
DEFAULT_MODEL = "apac.anthropic.claude-sonnet-4-20250514-v1:0"
DEFAULT_MAX_TOKENS = 4096


@tool
def get_credit_check(request_text: str) -> str:
    """Return a mock credit check from the raw credit-check request sentence."""

    name, address = parse_credit_check_request(request_text)
    report = lookup_credit_check(name=name, address=address)
    return format_credit_check_report(report)


def run_credit_check(
    request_text: str,
    *,
    aws_region: str = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", DEFAULT_AWS_REGION)),
    model_id: str = DEFAULT_MODEL,
) -> str:
    """Run a single credit check and return the agent response text."""

    session = boto3.Session(region_name=aws_region)
    model = BedrockModel(
        model_id=model_id,
        max_tokens=int(os.getenv("MAX_TOKENS", str(DEFAULT_MAX_TOKENS))),
        boto_session=session,
    )

    agent = Agent(
        model=model,
        tools=[get_credit_check],
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )
    result = agent(request_text)
    return result.message["content"][0]["text"]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Credit-check agent")
    parser.add_argument("--aws-region", default=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", DEFAULT_AWS_REGION)), help="AWS region for Bedrock")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model id")
    return parser.parse_args(argv)


SAMPLE_REQUEST = "I want the credit check result from Jane Doe whose address is 123 Maple Street, Springfield, IL 62704"


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
        aws_region=args.aws_region,
        model_id=args.model,
    )

    print("\n" + "=" * 60)
    print("CREDIT CHECK RESULT")
    print("=" * 60)
    print(response)
