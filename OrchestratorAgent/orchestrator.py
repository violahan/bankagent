"""Orchestration agent that coordinates multiple A2A agents.

Connects to:
  - Credit Check Analysis Agent
  - Credit Check Agent

Typical workflow:
  1. Credit Check Agent looks up the applicant by name + address and returns
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
import base64
import json
import logging
import os
import pprint
import re
import sys
import textwrap
import threading
import time
from typing import Any

import boto3
import httpx
import requests
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools.a2a_client import A2AClientToolProvider

ANALYSE_AGENT_ARN = "arn:aws:bedrock-agentcore:ap-southeast-2:543486084696:runtime/analyse_agent_a2a_server-MHGOl53U4r"
CREDIT_CHECK_AGENT_ARN = "arn:aws:bedrock-agentcore:ap-southeast-2:543486084696:runtime/credit_check_a2a_server-csdekS8so2"
ANALYSE_AGENT_URL = f"https://bedrock-agentcore.ap-southeast-2.amazonaws.com/runtimes/{ANALYSE_AGENT_ARN}/invocations/"
CREDIT_CHECK_AGENT_URL = f"https://bedrock-agentcore.ap-southeast-2.amazonaws.com/runtimes/{CREDIT_CHECK_AGENT_ARN}/invocations/"
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2"))
MODEL_ID = os.getenv("MODEL_ID", "apac.anthropic.claude-sonnet-4-20250514-v1:0")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

DEFAULT_DISCOVERY_URL = "https://cognito-idp.ap-southeast-2.amazonaws.com/ap-southeast-2_NeVlNqJt8/.well-known/openid-configuration"
DEFAULT_CLIENT_ID = "4p0e9lcp09e920pgg9hfbqp3tj"
DEFAULT_COGNITO_USERNAME = "MCP_USER"
DEFAULT_COGNITO_PASSWORD = "MCP_PASSWORD"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class CognitoTokenClient:
   """Manages Cognito OAuth tokens with automatic renewal."""

   TOKEN_REFRESH_BUFFER_SECONDS = 600
   COGNITO_SERVICE_TARGET = "AWSCognitoIdentityProviderService.InitiateAuth"

   def __init__(
       self,
       discovery_url: str,
       client_id: str,
       username: str,
       password: str,
   ):
       self._client_id = client_id
       self._username = username
       self._password = password

       self._endpoint, self._region = self._parse_discovery_url(discovery_url)

       self._access_token: str | None = None
       self._refresh_token: str | None = None
       self._id_token: str | None = None
       self._expires_at: float = 0
       self._lock = threading.Lock()

   @staticmethod
   def _parse_discovery_url(discovery_url: str) -> tuple[str, str]:
       match = re.match(
           r"https://cognito-idp\.([a-z0-9-]+)\.amazonaws\.com/", discovery_url
       )
       if not match:
           raise ValueError(f"Cannot parse region from discovery URL: {discovery_url}")
       region = match.group(1)
       endpoint = f"https://cognito-idp.{region}.amazonaws.com/"
       return endpoint, region

   def _call_initiate_auth(self, auth_flow: str, auth_params: dict) -> dict:
       resp = requests.post(
           self._endpoint,
           headers={
               "Content-Type": "application/x-amz-json-1.1",
               "X-Amz-Target": self.COGNITO_SERVICE_TARGET,
           },
           json={
               "AuthFlow": auth_flow,
               "ClientId": self._client_id,
               "AuthParameters": auth_params,
           },
           timeout=30,
       )
       if resp.status_code != 200:
           raise RuntimeError(
               f"Cognito InitiateAuth failed ({resp.status_code}): {resp.text}"
           )
       return resp.json()["AuthenticationResult"]

   def _authenticate(self) -> dict:
       return self._call_initiate_auth(
           "USER_PASSWORD_AUTH",
           {"USERNAME": self._username, "PASSWORD": self._password},
       )

   def _refresh(self) -> dict:
       return self._call_initiate_auth(
           "REFRESH_TOKEN_AUTH",
           {"REFRESH_TOKEN": self._refresh_token},
       )

   @staticmethod
   def _decode_jwt_payload(token: str) -> dict:
       payload_b64 = token.split(".")[1]
       payload_b64 += "=" * (4 - len(payload_b64) % 4)
       return json.loads(base64.urlsafe_b64decode(payload_b64))

   def _is_token_expired(self) -> bool:
       return time.time() >= (self._expires_at - self.TOKEN_REFRESH_BUFFER_SECONDS)

   def _store_tokens(self, auth_result: dict) -> None:
       self._access_token = auth_result["AccessToken"]
       self._id_token = auth_result.get("IdToken")
       if "RefreshToken" in auth_result:
           self._refresh_token = auth_result["RefreshToken"]
       self._expires_at = self._decode_jwt_payload(self._access_token)["exp"]

   def _ensure_valid_token(self) -> None:
       if not self._is_token_expired():
           return

       if self._refresh_token:
           try:
               self._store_tokens(self._refresh())
               return
           except RuntimeError:
               logger.warning("Cognito token refresh failed; falling back to re-authentication.")

       self._store_tokens(self._authenticate())

   @property
   def access_token(self) -> str:
       with self._lock:
           self._ensure_valid_token()
           return self._access_token

   @property
   def authorization_header(self) -> dict[str, str]:
       return {"Authorization": f"Bearer {self.access_token}"}

   def invalidate(self) -> None:
       with self._lock:
           self._expires_at = 0


class CognitoBearerAuth(httpx.Auth):
   """Inject a fresh Cognito bearer token into each outbound request."""

   def __init__(self, token_client: CognitoTokenClient):
       self._token_client = token_client

   def auth_flow(self, request: httpx.Request):
       request.headers["Authorization"] = f"Bearer {self._token_client.access_token}"
       yield request


def _build_a2a_httpx_client_args(*, known_agent_urls: list[str]) -> dict[str, Any]:
   """Build optional httpx client args for remote Cognito-protected A2A agents."""
   if not any(url for url in known_agent_urls):
       return {}

   discovery_url = os.getenv("DISCOVERY_URL", DEFAULT_DISCOVERY_URL)
   client_id = os.getenv("CLIENT_ID", DEFAULT_CLIENT_ID)
   username = os.getenv("USERNAME", DEFAULT_COGNITO_USERNAME)
   password = os.getenv("PASSWORD", DEFAULT_COGNITO_PASSWORD)

   token_client = CognitoTokenClient(
       discovery_url=discovery_url,
       client_id=client_id,
       username=username,
       password=password,
   )
   logger.info("Configured Cognito auth for remote A2A agent access.")

   return {
       "auth": CognitoBearerAuth(token_client),
       "headers": {"Content-Type": "application/json"},
   }

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a bank operations orchestrator.

    ## important: You MUST return response in English-only.

    You have access to two specialist agents that you can call as tools:

      1. **Credit Check Agent** — performs a credit lookup for an applicant.
         When you contact it, send exactly one
         sentence in this format and nothing else:
         "I want the credit check result from <name> whose address is <address>"
         It returns a credit report containing:
           - score (0-850)
           - rating (e.g. DECLINED, APPROVED)
           - summary (plain-English explanation)
           - details (list of findings, each with a category of INFO / OK /
             WARNING / CRITICAL and a message)

      2. **Credit Check Analysis Agent** — takes a user profile together with
         a credit-check result and evaluates them
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
      4. **Recommendation**
         - Provide a plain-English explanation of the outcome and clearly state
           whether the application is PASS, FAIL, or MANUAL REVIEW.

    When the analysis agent returns a structured recommendation, preserve that
    recommendation accurately. Do not omit the rules section in the final
    report.
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
   aws_region: str = AWS_REGION,
   model_id: str = MODEL_ID,
) -> Agent:
   """Create the orchestrator agent wired to the downstream A2A agents."""
   known_agent_urls = [credit_check_url, analyse_url]
   provider = A2AClientToolProvider(
       known_agent_urls=known_agent_urls,
       httpx_client_args=_build_a2a_httpx_client_args(known_agent_urls=known_agent_urls),
   )

   session = boto3.Session(region_name=aws_region)
   model = BedrockModel(
       model_id=model_id,
       max_tokens=MAX_TOKENS,
       boto_session=session,
   )


   return Agent(
       name="Bank Orchestrator",
       description="Routes banking requests to the appropriate specialist agents.",
       model=model,
       tools=provider.tools,
       system_prompt=SYSTEM_PROMPT,
   )




if __name__ == "__main__":

   from bedrock_agentcore.runtime import BedrockAgentCoreApp

   app = BedrockAgentCoreApp()

   orchestrator = build_orchestrator(
       analyse_url=args.analyse_url,
       credit_check_url=args.bureau_url,
       aws_region=args.aws_region,
       model_id=args.model,
   )

   @app.entrypoint
   def agent_invocation(payload, context):
       """Handler for agent invocation"""
       user_message = payload.get("prompt", "No prompt found in input, please guide customer to create a json payload with prompt key")
       result = orchestrator(user_message)
       return {"result": result.message}


   app.run()
