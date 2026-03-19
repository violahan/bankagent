"""Test script for the Bank Orchestrator agent.

Sends a series of predefined questions to the orchestrator and prints the
responses.  Useful for smoke-testing after bringing up the full stack:

    1. cd RuleFetchMCP && python server.py
    2. cd AnalyseAgent && uvicorn a2a_server:app --host 0.0.0.0 --port 8001
    3. cd OrchestratorAgent && python test_script.py
"""

from __future__ import annotations

import argparse
import sys
import textwrap
import time

from orchestrator import (
    ANALYSE_AGENT_URL,
    CREDIT_CHECK_AGENT_URL,
    MODEL_ID,
    AWS_REGION,
    build_orchestrator,
    extract_result_text,
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
    parser.add_argument("--analyse-url", default=ANALYSE_AGENT_URL, help="AnalyseAgent A2A URL")
    parser.add_argument("--bureau-url", default=CREDIT_CHECK_AGENT_URL, help="Credit check agent A2A URL")
    parser.add_argument("--aws-region", default=AWS_REGION, help="AWS region for Bedrock")
    parser.add_argument("--model", default=MODEL_ID, help="Model id")
    parser.add_argument(
        "-n", "--number",
        type=int,
        default=None,
        help="Run only the Nth question (1-based). Omit to run all.",
    )
    return parser.parse_args(argv)


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

    print("Building orchestrator …")
    orchestrator = build_orchestrator(
        analyse_url=args.analyse_url,
        credit_check_url=args.bureau_url,
        aws_region=args.aws_region,
        model_id=args.model,
    )
    print("Orchestrator ready.\n")

    run_tests(orchestrator, TEST_QUESTIONS, selected=args.number)

    print("\nAll tests finished.")
