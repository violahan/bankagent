"""Orchestration agent that coordinates multiple A2A agents.

Connects to:
  - Credit Check Analysis Agent  (AnalyseAgent A2A server, localhost:8001)
  - Credit Check Agent           (remote A2A server at localhost:8082)

Typical workflow:
  1. Credit Check Agent looks up the applicant by name + address and returns
     a credit report (score, rating, detailed findings).
  2. Credit Check Analysis Agent evaluates that report against bank policy
     and produces a PASS / FAIL / MANUAL REVIEW recommendation.

Usage:
    1. Start the CreditServicesMCP server:
           cd CreditServicesMCP && python mcp_server.py
    2. Start the AnalyseAgent A2A server:
           cd AnalyseAgent && uvicorn a2a_server:app --host 0.0.0.0 --port 8001
    3. Run this orchestrator:
           cd OrchestratorAgent && python orchestrator.py
"""

from __future__ import annotations

import argparse
import os
import pprint
import sys
import textwrap
from typing import Any

from strands import Agent, tool
from strands.models.anthropic import AnthropicModel
from strands.models.ollama import OllamaModel
from strands_tools.a2a_client import A2AClientToolProvider

ANALYSE_AGENT_URL = os.getenv("ANALYSE_AGENT_URL", "http://localhost:8001")
CREDIT_CHECK_AGENT_URL = os.getenv("CREDIT_CHECK_AGENT_URL", "http://localhost:8082")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "anthropic").strip().lower()
MODEL_ID = os.getenv("MODEL_ID", "claude-sonnet-4-20250514")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096"))

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a bank operations orchestrator.

    ## important: You MUST return response in English-only.

    You have access to two specialist agents that you can call as tools:

      1. **Credit Check Agent** (http://localhost:8082) — performs a credit
         lookup for an applicant.  When you contact it, send exactly one
         sentence in this format and nothing else:
         "I want the credit check result from <name> whose address is <address>"
         It returns a credit report containing:
           - score (0-850)
           - rating (e.g. DECLINED, APPROVED)
           - summary (plain-English explanation)
           - details (list of findings, each with a category of INFO / OK /
             WARNING / CRITICAL and a message)

      2. **Credit Check Analysis Agent** (http://localhost:8001) — takes a user
         profile together with a credit-check result and evaluates them
         against the bank's internal credit-policy rules.  Returns a
         PASS / FAIL / MANUAL REVIEW recommendation with a rule-by-rule
         breakdown.

    Typical end-to-end workflow for a loan application:
      a. Call the **Credit Check Agent** using exactly this sentence shape:
         "I want the credit check result from <name> whose address is <address>"
         Replace `<name>` and `<address>` with the applicant's actual values
         and do not add any extra text.
      b. Forward the user profile AND the credit report to the
         **Credit Check Analysis Agent** for policy evaluation.
      c. Synthesise both outputs into a single, clear response for the
         user.

    For end-to-end loan application outputs, your final report must contain
    these FOUR parts in this order:
      1. **User Profile**
         - Restate the applicant details used for the decision.
      2. **Credit Check Result**
         - Include the credit-check fields returned by the Credit Check Agent.
      3. **Rules**
         - Include the applicable credit-policy rules and the rule-by-rule
           outcome from the analysis.
      4. **Summary**
         - Provide a plain-English explanation of the outcome and clearly state
           whether the application is PASS, FAIL, or MANUAL REVIEW.

    When the analysis agent returns a structured recommendation, preserve that
    recommendation accurately. Do not omit the rules section in the final
    report.

    Before sending any final answer, verify that the response is entirely in
    English.
""")


def extract_result_text(result: Any) -> str:
   """Best-effort extraction of readable text from a Strands agent result."""
   message = getattr(result, "message", None)
   if not isinstance(message, dict):
       return str(result)

   content = message.get("content")
   if isinstance(content, list):
       text_parts: list[str] = []
       for item in content:
           if isinstance(item, dict):
               text = item.get("text")
               if isinstance(text, str) and text.strip():
                   text_parts.append(text)
       if text_parts:
           return "\n".join(text_parts)

   direct_text = message.get("text")
   if isinstance(direct_text, str) and direct_text.strip():
       return direct_text

   return pprint.pformat(message)


def build_orchestrator(
   *,
   analyse_url: str = ANALYSE_AGENT_URL,
   credit_check_url: str = CREDIT_CHECK_AGENT_URL,
   ollama_host: str = OLLAMA_HOST,
   model_provider: str = MODEL_PROVIDER,
   model_id: str = MODEL_ID,
) -> Agent:
   """Create the orchestrator agent wired to the downstream A2A agents."""
   provider = A2AClientToolProvider(
       known_agent_urls=[credit_check_url, analyse_url],
   )

   if model_provider == "anthropic":
       if not ANTHROPIC_API_KEY:
           raise ValueError(
               "ANTHROPIC_API_KEY is required when MODEL_PROVIDER=anthropic."
           )
       model = AnthropicModel(
           client_args={"api_key": ANTHROPIC_API_KEY},
           model_id=model_id,
           max_tokens=ANTHROPIC_MAX_TOKENS,
       )
   elif model_provider == "ollama":
       model = OllamaModel(host=ollama_host, model_id=model_id)
   else:
       raise ValueError(
           f"Unsupported MODEL_PROVIDER={model_provider!r}. Use 'anthropic' or 'ollama'."
       )


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
   parser.add_argument("--bureau-url", default=CREDIT_CHECK_AGENT_URL, help="Credit check agent A2A URL")
   parser.add_argument("--provider", default=MODEL_PROVIDER, help="Model provider: anthropic or ollama")
   parser.add_argument("--ollama-host", default=OLLAMA_HOST, help="Ollama server address")
   parser.add_argument("--model", default=MODEL_ID, help="Model id")
   parser.add_argument("prompt", nargs="?", default=None, help="Prompt to send (interactive if omitted)")
   return parser.parse_args(argv)




if __name__ == "__main__":
   args = _parse_args()


   orchestrator = build_orchestrator(
       analyse_url=args.analyse_url,
       credit_check_url=args.bureau_url,
       ollama_host=args.ollama_host,
       model_provider=args.provider,
       model_id=args.model,
   )


   if args.prompt:
       result = orchestrator(args.prompt)
       print(extract_result_text(result))
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
       print("\n" + extract_result_text(result))
