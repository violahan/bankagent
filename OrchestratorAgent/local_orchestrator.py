from __future__ import annotations

import argparse
import os
import sys
import textwrap
import time
from typing import Any
from urllib.parse import quote

from orchestrator import (
    DEFAULT_ANALYSE_AGENT_ARN,
    DEFAULT_CREDIT_CHECK_AGENT_ARN,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL_ID,
    DEFAULT_REGION,
    build_orchestrator,
)

TEST_QUESTIONS = [
    {
        "label": "Full loan application (credit lookup + policy analysis)",
        "prompt": textwrap.dedent("""\
            I'd like to apply for a personal loan for debt consolidation.
            Here is my information:
              Name: Jane Doe
              Address: 123 Maple Street, Springfield, IL 62704
              Age: 34
              Employment status: full-time
              Annual income: $85,000
              Existing monthly debt payments: $1,200
            Please pull my credit report and evaluate my application against
            the bank's policy.
        """),
    },
    # {
    #     "label": "Credit report lookup only",
    #     "prompt": textwrap.dedent("""\
    #         Can you pull the credit report for the following person?
    #           Full name: John Smith
    #           Address: 456 Oak Avenue, Denver, CO 80203
    #     """),
    # },
    # {
    #     "label": "Policy analysis with provided credit data",
    #     "prompt": textwrap.dedent("""\
    #         I already have a credit report for a vehicle loan applicant.
    #         Please evaluate it against the bank's vehicle loan policy.
    #
    #         User Profile:
    #           Name: Alice Johnson
    #           Age: 28
    #           Employment status: full-time
    #           Annual income: $62,000
    #           Existing monthly debt payments: $800
    #
    #         Credit Report:
    #           Bureau score: 745
    #           Debt-to-income ratio: 0.28
    #           Credit utilisation: 0.30
    #           Number of delinquencies: 0
    #           Bankruptcies: 0
    #           Hard inquiries in last 6 months: 1
    #           External rating: A
    #     """),
    # },
    # {
    #     "label": "Edge case – low credit score applicant",
    #     "prompt": textwrap.dedent("""\
    #         Evaluate the following mortgage refinance application end-to-end.
    #
    #         Applicant:
    #           Name: Robert Brown
    #           Address: 789 Pine Road, Austin, TX 73301
    #           Age: 52
    #           Employment status: self-employed
    #           Annual income: $48,000
    #           Existing monthly debt payments: $2,100
    #
    #         If you need to pull his credit report, please do so, then run
    #         the full policy check.
    #     """),
    # },
    # {
    #     "label": "General banking question (no agent call expected)",
    #     "prompt": "What types of loan products does this bank support?",
    # },
]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test script for the Bank Orchestrator")
    parser.add_argument(
        "--analyse-url",
        default=os.getenv("ANALYSE_AGENT_URL"),
        help="AnalyseAgent A2A URL. Takes precedence over --analyse-agent-arn.",
    )
    parser.add_argument(
        "--bureau-url",
        default=os.getenv("CREDIT_CHECK_AGENT_URL"),
        help="Credit check agent A2A URL. Takes precedence over --bureau-agent-arn.",
    )
    parser.add_argument(
        "--analyse-agent-arn",
        default=os.getenv("ANALYSE_AGENT_ARN", DEFAULT_ANALYSE_AGENT_ARN),
        help="AnalyseAgent Bedrock AgentCore runtime ARN.",
    )
    parser.add_argument(
        "--bureau-agent-arn",
        default=os.getenv("CREDIT_CHECK_AGENT_ARN", DEFAULT_CREDIT_CHECK_AGENT_ARN),
        help="Credit check Bedrock AgentCore runtime ARN.",
    )
    parser.add_argument(
        "--agentcore-qualifier",
        default=os.getenv("AGENTCORE_QUALIFIER"),
        help="Optional AgentCore qualifier for deployed runtime invocations.",
    )
    parser.add_argument(
        "--aws-region",
        default=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", DEFAULT_REGION)),
        help="AWS region for Bedrock and AgentCore runtime URLs.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("MODEL_ID", DEFAULT_MODEL_ID),
        help="Bedrock model id used by the orchestrator.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=int(os.getenv("MAX_TOKENS", str(DEFAULT_MAX_TOKENS))),
        help="Maximum tokens for the orchestrator model response.",
    )
    parser.add_argument(
        "-n", "--number",
        type=int,
        default=None,
        help="Run only the Nth question (1-based). Omit to run all.",
    )
    return parser.parse_args(argv)


def extract_result_text(result: Any) -> str:
    if result is None:
        return ""

    for attr_name in ("message", "content", "text"):
        value = getattr(result, attr_name, None)
        if isinstance(value, str) and value.strip():
            return value

    if isinstance(result, dict):
        for key in ("result", "message", "content", "text"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value

    return str(result)


def build_runtime_invocation_url(
    *,
    aws_region: str,
    runtime_arn: str,
    qualifier: str | None = None,
) -> str:
    url = (
        f"https://bedrock-agentcore.{aws_region}.amazonaws.com/"
        f"runtimes/{quote(runtime_arn, safe='')}/invocations/"
    )
    if qualifier:
        return f"{url}?qualifier={quote(qualifier, safe='')}"
    return url


def configure_runtime_env(args: argparse.Namespace) -> None:
    os.environ["AWS_REGION"] = args.aws_region
    os.environ["MODEL_ID"] = args.model
    os.environ["MAX_TOKENS"] = str(args.max_tokens)

    if args.analyse_url:
        os.environ["ANALYSE_AGENT_URL"] = args.analyse_url
    else:
        os.environ["ANALYSE_AGENT_ARN"] = args.analyse_agent_arn
        os.environ["ANALYSE_AGENT_URL"] = build_runtime_invocation_url(
            aws_region=args.aws_region,
            runtime_arn=args.analyse_agent_arn,
            qualifier=args.agentcore_qualifier,
        )

    if args.bureau_url:
        os.environ["CREDIT_CHECK_AGENT_URL"] = args.bureau_url
    else:
        os.environ["CREDIT_CHECK_AGENT_ARN"] = args.bureau_agent_arn
        os.environ["CREDIT_CHECK_AGENT_URL"] = build_runtime_invocation_url(
            aws_region=args.aws_region,
            runtime_arn=args.bureau_agent_arn,
            qualifier=args.agentcore_qualifier,
        )


def run_tests(
    orchestrator,
    questions: list[dict],
    *,
    selected: int | None = None,
) -> None:
    subset = questions if selected is None else [questions[selected - 1]]

    for idx, q in enumerate(subset, start=1 if selected is None else selected):
        print("\n" + "=" * 70)
        print(f"  TEST {idx}/{len(questions)}: {q['label']}")
        print("=" * 70)
        print(f"\n[PROMPT]\n{q['prompt'].strip()}\n")

        start = time.time()
        try:
            result = orchestrator(q["prompt"])
            elapsed = time.time() - start
            answer = extract_result_text(result)
            print(f"[RESPONSE] ({elapsed:.1f}s)\n{answer}")
        except Exception as exc:
            elapsed = time.time() - start
            print(f"[ERROR] ({elapsed:.1f}s) {exc}")

        print("\n" + "-" * 70)


if __name__ == "__main__":
    args = _parse_args()

    if args.number is not None and not (1 <= args.number <= len(TEST_QUESTIONS)):
        print(f"Error: --number must be between 1 and {len(TEST_QUESTIONS)}", file=sys.stderr)
        sys.exit(1)

    configure_runtime_env(args)

    print("Building orchestrator …")
    orchestrator = build_orchestrator(
        aws_region=args.aws_region,
        model_id=args.model,
        max_tokens=args.max_tokens,
    )
    print("Orchestrator ready.\n")

    run_tests(orchestrator, TEST_QUESTIONS, selected=args.number)

    print("\nAll tests finished.")
