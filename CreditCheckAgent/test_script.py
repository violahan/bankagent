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
import random
import re

SYSTEM_PROMPT = textwrap.dedent("""\
    You are the bank's credit-check retrieval agent.

    Scope:
    - Handle only requests that ask for a credit check and include a person's name
      and address.
    - Do not answer unrelated banking, underwriting, policy, or general questions.
    - Do not invent, estimate, or summarize credit data yourself.

    Required behavior:
    1. Read the user's message and extract the applicant's full name and full address.
    2. Call `get_credit_check` with those two extracted fields.
    3. After the tool returns, respond with the tool output only.
    4. Preserve every field name, value, order, and line break exactly as returned.

    Invalid or incomplete requests:
    - If the user's message does not clearly provide both a name and an address,
      do not call the tool.
    - Ask the user to provide both the applicant's full name and full address.
    - Keep that correction message short and do not add extra explanation unless needed.

    Output rules:
    - For successful lookups, return only the credit report text.
    - Do not add headings, bullets, markdown, commentary, analysis, or disclaimers.
    - Do not rename fields or reformat the report.
    - This output is consumed by downstream agents, so fidelity matters more than style.
""")

DEFAULT_AWS_REGION = "ap-southeast-2"
DEFAULT_MODEL = "apac.anthropic.claude-sonnet-4-20250514-v1:0"
DEFAULT_MAX_TOKENS = 4096


@tool
def get_credit_check(name: str, address: str) -> str:
    """Return a mock credit check for the supplied applicant details."""

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


def _validate_inputs(name: str, address: str) -> None:
    errors: list[str] = []

    if len(name.strip()) < 3:
        errors.append("name must be at least 3 characters")
    if len(address.strip()) < 10:
        errors.append("address must be at least 10 characters")
    if address and not re.search(r"\d", address):
        errors.append("address must contain a street number")

    if errors:
        raise ValueError("; ".join(errors))


def _external_rating(score: int) -> str:
    if score >= 740:
        return "A"
    if score >= 680:
        return "B"
    if score >= 620:
        return "C"
    return "D"


def lookup_credit_check(name: str, address: str) -> dict[str, int | float | str]:
    """Return a mock credit report for the supplied applicant."""

    _validate_inputs(name, address)

    rng = random.SystemRandom()

    bureau_score = rng.randint(300, 850)
    debt_to_income_ratio = round(rng.uniform(0.18, 0.55), 2)
    credit_utilisation = round(rng.uniform(0.00, 0.80), 2)
    delinquency_count = rng.randint(0, 3)
    bankruptcies = rng.choices([0, 1], weights=[9, 1], k=1)[0]
    hard_inquiries_last_6_months = rng.randint(0, 6)
    external_rating = _external_rating(bureau_score)

    return {
        "name": name.strip(),
        "address": address.strip(),
        "bureau_score": bureau_score,
        "debt_to_income_ratio": debt_to_income_ratio,
        "credit_utilisation": credit_utilisation,
        "delinquency_count": delinquency_count,
        "bankruptcies": bankruptcies,
        "hard_inquiries_last_6_months": hard_inquiries_last_6_months,
        "external_rating": external_rating,
    }


def format_credit_check_report(report: dict[str, int | float | str]) -> str:
    """Format the report in the field names expected by the analysis agent."""

    return "\n".join(
        [
            f"Name: {report['name']}",
            f"Address: {report['address']}",
            f"Bureau score: {report['bureau_score']}",
            f"Debt-to-income ratio: {report['debt_to_income_ratio']:.2f}",
            f"Credit utilisation: {report['credit_utilisation']:.2f}",
            f"Number of delinquencies: {report['delinquency_count']}",
            f"Bankruptcies: {report['bankruptcies']}",
            f"Hard inquiries in last 6 months: {report['hard_inquiries_last_6_months']}",
            f"External rating: {report['external_rating']}",
        ]
    )


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
