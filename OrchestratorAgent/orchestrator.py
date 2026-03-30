"""AgentCore-ready orchestration agent for the bank workflow.

This runtime is intended to be deployed to Bedrock AgentCore and call other
deployed specialist agents over A2A.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import threading
import time
from typing import Any
from urllib.parse import quote

import boto3
import requests
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands_tools.a2a_client import A2AClientToolProvider

DEFAULT_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2"))
DEFAULT_MODEL_ID = os.getenv("MODEL_ID", "apac.anthropic.claude-sonnet-4-20250514-v1:0")
DEFAULT_MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

DEFAULT_DISCOVERY_URL = "https://cognito-idp.ap-southeast-2.amazonaws.com/ap-southeast-2_NeVlNqJt8/.well-known/openid-configuration"
DEFAULT_CLIENT_ID = "4p0e9lcp09e920pgg9hfbqp3tj"
DEFAULT_COGNITO_USERNAME = "MCP_USER"
DEFAULT_COGNITO_PASSWORD = "MCP_PASSWORD"

DEFAULT_ANALYSE_AGENT_ARN = "arn:aws:bedrock-agentcore:ap-southeast-2:543486084696:runtime/analyse_agent_a2a_server-MHGOl53U4r"
DEFAULT_CREDIT_CHECK_AGENT_ARN = "arn:aws:bedrock-agentcore:ap-southeast-2:543486084696:runtime/credit_check_a2a_server-csdekS8so2"

SYSTEM_PROMPT = """You are a bank operations orchestrator.

Return responses in English only.

You have access to two specialist agents:

1. Credit Check Agent
   Use it to retrieve an applicant credit report.
   When you call it, send exactly this sentence and nothing else:
   "I want the credit check result from <name> whose address is <address>"

2. Credit Check Analysis Agent
   Use it to evaluate a user profile and credit report against bank policy.

For an end-to-end loan application:
1. Call the Credit Check Agent with the exact sentence format above.
2. Send the applicant profile and returned credit report to the Credit Check Analysis Agent.
3. Return a final report with these sections in order:
   - User Profile
   - Credit Check Result
   - Rules
   - Recommendation

Preserve the analysis recommendation accurately. Do not omit the Rules section.
"""

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def _runtime_url_from_arn(runtime_arn: str, region: str) -> str:
    encoded_arn = quote(runtime_arn, safe="")
    return (
        f"https://bedrock-agentcore.{region}.amazonaws.com/"
        f"runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    )


def _resolve_runtime_url(*, env_url: str, env_arn: str, default_arn: str, region: str) -> str:
    direct_url = os.getenv(env_url)
    if direct_url:
        return direct_url

    runtime_arn = os.getenv(env_arn, default_arn)
    return _runtime_url_from_arn(runtime_arn, region)


ANALYSE_AGENT_URL = _resolve_runtime_url(
    env_url="ANALYSE_AGENT_URL",
    env_arn="ANALYSE_AGENT_ARN",
    default_arn=DEFAULT_ANALYSE_AGENT_ARN,
    region=DEFAULT_REGION,
)
CREDIT_CHECK_AGENT_URL = _resolve_runtime_url(
    env_url="CREDIT_CHECK_AGENT_URL",
    env_arn="CREDIT_CHECK_AGENT_ARN",
    default_arn=DEFAULT_CREDIT_CHECK_AGENT_ARN,
    region=DEFAULT_REGION,
)


class CognitoTokenClient:
    """Simple Cognito token manager for outbound requests to protected runtimes."""

    TOKEN_REFRESH_BUFFER_SECONDS = 600
    COGNITO_SERVICE_TARGET = "AWSCognitoIdentityProviderService.InitiateAuth"

    def __init__(self, discovery_url: str, client_id: str, username: str, password: str):
        self._client_id = client_id
        self._username = username
        self._password = password
        self._endpoint = self._parse_discovery_url(discovery_url)
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    @staticmethod
    def _parse_discovery_url(discovery_url: str) -> str:
        match = re.match(r"https://cognito-idp\.([a-z0-9-]+)\.amazonaws\.com/", discovery_url)
        if not match:
            raise ValueError(f"Cannot parse Cognito endpoint from discovery URL: {discovery_url}")
        region = match.group(1)
        return f"https://cognito-idp.{region}.amazonaws.com/"

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict[str, Any]:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))

    def _call_initiate_auth(self, auth_flow: str, auth_parameters: dict[str, str]) -> dict[str, Any]:
        response = requests.post(
            self._endpoint,
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": self.COGNITO_SERVICE_TARGET,
            },
            json={
                "AuthFlow": auth_flow,
                "ClientId": self._client_id,
                "AuthParameters": auth_parameters,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Cognito InitiateAuth failed ({response.status_code}): {response.text}"
            )
        return response.json()["AuthenticationResult"]

    def _store_tokens(self, auth_result: dict[str, Any]) -> None:
        self._access_token = auth_result["AccessToken"]
        if "RefreshToken" in auth_result:
            self._refresh_token = auth_result["RefreshToken"]
        self._expires_at = self._decode_jwt_payload(self._access_token)["exp"]

    def _authenticate(self) -> None:
        self._store_tokens(
            self._call_initiate_auth(
                "USER_PASSWORD_AUTH",
                {"USERNAME": self._username, "PASSWORD": self._password},
            )
        )

    def _refresh(self) -> None:
        if not self._refresh_token:
            self._authenticate()
            return
        self._store_tokens(
            self._call_initiate_auth(
                "REFRESH_TOKEN_AUTH",
                {"REFRESH_TOKEN": self._refresh_token},
            )
        )

    def _ensure_valid_token(self) -> None:
        if time.time() < (self._expires_at - self.TOKEN_REFRESH_BUFFER_SECONDS):
            return

        try:
            self._refresh()
        except RuntimeError:
            logger.warning("Cognito token refresh failed; retrying with full authentication.")
            self._authenticate()

    @property
    def access_token(self) -> str:
        with self._lock:
            self._ensure_valid_token()
            if not self._access_token:
                raise RuntimeError("Failed to obtain Cognito access token.")
            return self._access_token


def _build_httpx_client_args() -> dict[str, Any]:
    token_client = CognitoTokenClient(
        discovery_url=os.getenv("DISCOVERY_URL", DEFAULT_DISCOVERY_URL),
        client_id=os.getenv("CLIENT_ID", DEFAULT_CLIENT_ID),
        username=os.getenv("USERNAME", DEFAULT_COGNITO_USERNAME),
        password=os.getenv("PASSWORD", DEFAULT_COGNITO_PASSWORD),
    )
    logger.info("Cognito access token acquired for orchestrator HTTP client.")
    return {
        "headers": {
            "Authorization": f"Bearer {token_client.access_token}",
            "Content-Type": "application/json",
        },
        "timeout": 300,
    }


def _extract_prompt(payload: dict[str, Any]) -> str:
    for key in ("prompt", "message", "input", "query"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError("Input payload must include a non-empty prompt string.")


def build_orchestrator(
    *,
    aws_region: str = DEFAULT_REGION,
    model_id: str = DEFAULT_MODEL_ID,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Agent:
    analyse_url = _resolve_runtime_url(
        env_url="ANALYSE_AGENT_URL",
        env_arn="ANALYSE_AGENT_ARN",
        default_arn=DEFAULT_ANALYSE_AGENT_ARN,
        region=aws_region,
    )
    credit_check_url = _resolve_runtime_url(
        env_url="CREDIT_CHECK_AGENT_URL",
        env_arn="CREDIT_CHECK_AGENT_ARN",
        default_arn=DEFAULT_CREDIT_CHECK_AGENT_ARN,
        region=aws_region,
    )

    logger.info("Using AnalyseAgent runtime: %s", analyse_url)
    logger.info("Using CreditCheckAgent runtime: %s", credit_check_url)

    provider = A2AClientToolProvider(
        known_agent_urls=[credit_check_url, analyse_url],
        httpx_client_args=_build_httpx_client_args(),
    )

    model = BedrockModel(
        model_id=model_id,
        max_tokens=max_tokens,
        boto_session=boto3.Session(region_name=aws_region),
    )

    return Agent(
        name="Bank Orchestrator",
        description="Coordinates bank workflow requests across deployed specialist agents.",
        model=model,
        tools=provider.tools,
        system_prompt=SYSTEM_PROMPT,
    )


app = BedrockAgentCoreApp()


@app.entrypoint
def agent_invocation(payload: dict[str, Any], context: Any) -> dict[str, Any]:
    del context
    prompt = _extract_prompt(payload)
    orchestrator = build_orchestrator()
    result = orchestrator(prompt)
    return {"result": getattr(result, "message", result)}


if __name__ == "__main__":
    app.run()
