"""Orchestration agent that coordinates multiple A2A agents.

Connects to:
  - Credit Check Analysis Agent  (AnalyseAgent A2A server, localhost:8001)
  - Credit Bureau Agent          (remote A2A server at 15.135.186.83:8080)

Typical workflow:
  1. Credit Bureau Agent looks up the applicant by name + address and returns
     a credit report (score, rating, detailed findings).
  2. Credit Check Analysis Agent evaluates that report against bank policy
     and produces a PASS / FAIL / MANUAL REVIEW recommendation.

Usage:
    1. Start the RuleFetchMCP server:
           cd RuleFetchMCP && python server.py
    2. Start the AnalyseAgent A2A server:
           cd AnalyseAgent && uvicorn a2a_server:app --host 0.0.0.0 --port 8001
    3. Run this orchestrator:
           cd OrchestratorAgent && python orchestrator.py
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap

from strands import Agent
from strands.models.ollama import OllamaModel
from strands_tools.a2a_client import A2AClientToolProvider

ANALYSE_AGENT_URL = os.getenv("ANALYSE_AGENT_URL", "http://localhost:8001")
BUREAU_AGENT_URL = os.getenv("BUREAU_AGENT_URL", "http://15.135.186.83:8080")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_ID = os.getenv("MODEL_ID", "qwen2.5")

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a bank operations orchestrator.

    You have access to two specialist agents that you can call as tools:

      1. **Credit Bureau Agent** (15.135.186.83:8080) — performs a credit
         lookup for an applicant.  Send it the applicant's `full_name` and
         `address`.  It returns a credit report containing:
           - score (0-850)
           - rating (e.g. DECLINED, APPROVED)
           - summary (plain-English explanation)
           - details (list of findings, each with a category of INFO / OK /
             WARNING / CRITICAL and a message)

      2. **Credit Check Analysis Agent** (localhost:8001) — takes a user
         profile together with a credit-check result and evaluates them
         against the bank's internal credit-policy rules.  Returns a
         PASS / FAIL / MANUAL REVIEW recommendation with a rule-by-rule
         breakdown.

    Typical end-to-end workflow for a loan application:
      a. Call the **Credit Bureau Agent** with the applicant's full name
         and address to obtain their credit report.
      b. Forward the user profile AND the credit report to the
         **Credit Check Analysis Agent** for policy evaluation.
      c. Synthesise both outputs into a single, clear response for the
         user.

    You may also handle requests that only need one of the two agents
    (e.g. "just pull the credit report for X" or "analyse this existing
    report against policy").
""")


def build_orchestrator(
    *,
    analyse_url: str = ANALYSE_AGENT_URL,
    bureau_url: str = BUREAU_AGENT_URL,
    ollama_host: str = OLLAMA_HOST,
    model_id: str = MODEL_ID,
) -> Agent:
    """Create the orchestrator agent wired to the downstream A2A agents."""
    provider = A2AClientToolProvider(
        known_agent_urls=[bureau_url, analyse_url],
    )

    model = OllamaModel(host=ollama_host, model_id=model_id)

    return Agent(
        name="Bank Orchestrator",
        description="Routes banking requests to the appropriate specialist agents.",
        model=model,
        tools=provider.tools,
        system_prompt=SYSTEM_PROMPT,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bank operations orchestrator")
    parser.add_argument("--analyse-url", default=ANALYSE_AGENT_URL, help="AnalyseAgent A2A URL")
    parser.add_argument("--bureau-url", default=BUREAU_AGENT_URL, help="Credit Bureau agent A2A URL")
    parser.add_argument("--ollama-host", default=OLLAMA_HOST, help="Ollama server address")
    parser.add_argument("--model", default=MODEL_ID, help="Ollama model id")
    parser.add_argument("prompt", nargs="?", default=None, help="Prompt to send (interactive if omitted)")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()

    orchestrator = build_orchestrator(
        analyse_url=args.analyse_url,
        bureau_url=args.bureau_url,
        ollama_host=args.ollama_host,
        model_id=args.model,
    )

    if args.prompt:
        result = orchestrator(args.prompt)
        print(result.message["content"][0]["text"])
        sys.exit(0)

    print("=" * 60)
    print("Bank Orchestrator  (type 'quit' to exit)")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input or user_input.lower() in ("quit", "exit"):
            break

        result = orchestrator(user_input)
        print("\n" + result.message["content"][0]["text"])
