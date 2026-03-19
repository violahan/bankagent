"""Credit-check analysis agent.

Connects to the RuleFetchMCP server (local or remote), fetches the relevant
policy rules, and analyses a user profile + credit-check result against those
rules.

Usage (remote – default):
    cd AnalyseAgent && python test_script.py

Usage (local):
    1. Start the RuleFetchMCP server:  cd RuleFetchMCP && python mcp_server.py
    2. Run with --mcp-url:
           cd AnalyseAgent && python test_script.py --mcp-url http://localhost:8000/mcp
"""

import argparse
import base64
import json
import os
import re
import textwrap
import threading
import time

import boto3
import requests
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient


class CognitoTokenClient:
    """Manages Cognito OAuth tokens with automatic renewal.

    Uses the Cognito public REST API directly — no boto3 or AWS credentials required.
    Only needs the OIDC discovery URL and client ID (from the authorizer config)
    plus user credentials.
    """

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
        """Extract the Cognito API endpoint and region from the OIDC discovery URL."""
        match = re.match(
            r"https://cognito-idp\.([a-z0-9-]+)\.amazonaws\.com/", discovery_url
        )
        if not match:
            raise ValueError(f"Cannot parse region from discovery URL: {discovery_url}")
        region = match.group(1)
        endpoint = f"https://cognito-idp.{region}.amazonaws.com/"
        return endpoint, region

    def _call_initiate_auth(self, auth_flow: str, auth_params: dict) -> dict:
        """Call the Cognito InitiateAuth REST API directly."""
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
                pass

        self._store_tokens(self._authenticate())

    @property
    def access_token(self) -> str:
        """Returns a valid access token, refreshing or re-authenticating as needed. Thread-safe."""
        with self._lock:
            self._ensure_valid_token()
            return self._access_token

    @property
    def id_token(self) -> str | None:
        with self._lock:
            self._ensure_valid_token()
            return self._id_token

    @property
    def authorization_header(self) -> dict[str, str]:
        """Returns a header dict ready for HTTP requests."""
        return {"Authorization": f"Bearer {self.access_token}"}

    def invalidate(self) -> None:
        """Force re-authentication on next access."""
        with self._lock:
            self._expires_at = 0

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

DEFAULT_AGENT_ARN = "arn:aws:bedrock-agentcore:ap-southeast-2:590183866516:runtime/bank_rules_mcp_server_oauth-dk7JZVCwJ9"
DEFAULT_DISCOVERY_URL = "https://cognito-idp.ap-southeast-2.amazonaws.com/ap-southeast-2_6AnwIssYD/.well-known/openid-configuration"
DEFAULT_CLIENT_ID = "2eusmbe7ujgh611vh4m4p5n22g"
DEFAULT_COGNITO_USERNAME = "MCP_USER"
DEFAULT_COGNITO_PASSWORD = "MCP_PASSWORD"

DEFAULT_AWS_REGION = "ap-southeast-2"
DEFAULT_MODEL = "apac.anthropic.claude-sonnet-4-20250514-v1:0"
DEFAULT_MAX_TOKENS = 4096


def _build_remote_mcp_url(agent_arn: str) -> str:
    encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
    return f"https://bedrock-agentcore.ap-southeast-2.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"


def _build_mcp_client(
    *,
    mcp_url: str | None = None,
    agent_arn: str | None = None,
) -> MCPClient:
    """Build an MCPClient for either a local URL or a remote ARN with Cognito auth."""
    if mcp_url:
        return MCPClient(lambda: streamablehttp_client(mcp_url))

    arn = agent_arn or os.getenv("AGENT_ARN", DEFAULT_AGENT_ARN)
    remote_url = _build_remote_mcp_url(arn)

    token_client = CognitoTokenClient(
        discovery_url=os.getenv("DISCOVERY_URL", DEFAULT_DISCOVERY_URL),
        client_id=os.getenv("CLIENT_ID", DEFAULT_CLIENT_ID),
        username=os.getenv("USERNAME", DEFAULT_COGNITO_USERNAME),
        password=os.getenv("PASSWORD", DEFAULT_COGNITO_PASSWORD),
    )

    def _connect():
        headers = {**token_client.authorization_header, "Content-Type": "application/json"}
        return streamablehttp_client(remote_url, headers=headers, timeout=120, terminate_on_close=False)

    return MCPClient(_connect)


def analyse(
    user_profile: str,
    credit_result: str,
    *,
    mcp_url: str | None = None,
    agent_arn: str | None = None,
    aws_region: str = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", DEFAULT_AWS_REGION)),
    model_id: str = DEFAULT_MODEL,
) -> str:
    """Run a single analysis and return the agent's response text."""

    prompt = (
        f"## User Profile\n{user_profile}\n\n"
        f"## Credit-Check Result\n{credit_result}\n\n"
        "Please fetch the applicable credit-check rules and analyse this application."
    )

    mcp_client = _build_mcp_client(mcp_url=mcp_url, agent_arn=agent_arn)

    session = boto3.Session(region_name=aws_region)
    model = BedrockModel(
        model_id=model_id,
        max_tokens=int(os.getenv("MAX_TOKENS", str(DEFAULT_MAX_TOKENS))),
        boto_session=session,
    )

    with mcp_client:
        tools = mcp_client.list_tools_sync()
        agent = Agent(
            model=model,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )
        result = agent(prompt)

    return result.message["content"][0]["text"]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Credit-check analysis agent")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--mcp-url", default=None, help="Local RuleFetchMCP streamable-HTTP URL (e.g. http://localhost:8000/mcp)")
    group.add_argument("--agent-arn", default=None, help="Remote Bedrock AgentCore runtime ARN (default: uses built-in ARN)")
    parser.add_argument("--aws-region", default=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", DEFAULT_AWS_REGION)), help="AWS region for Bedrock")
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
        agent_arn=args.agent_arn,
        aws_region=args.aws_region,
        model_id=args.model,
    )

    print("\n" + "=" * 60)
    print("ANALYSIS RESULT")
    print("=" * 60)
    print(response)
