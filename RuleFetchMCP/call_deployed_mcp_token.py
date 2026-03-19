import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from cognito_token_client import CognitoTokenClient


async def main():
    agent_arn = os.getenv('AGENT_ARN', "arn:aws:bedrock-agentcore:ap-southeast-2:590183866516:runtime/bank_rules_mcp_server_oauth-dk7JZVCwJ9")
    if not agent_arn:
        print("Error: AGENT_ARN environment variable is not set")
        sys.exit(1)

    token_client = CognitoTokenClient(
        discovery_url=os.getenv(
            "DISCOVERY_URL",
            "https://cognito-idp.ap-southeast-2.amazonaws.com/ap-southeast-2_6AnwIssYD/.well-known/openid-configuration",
        ),
        client_id=os.getenv("CLIENT_ID", "2eusmbe7ujgh611vh4m4p5n22g"),
        username=os.getenv("USERNAME", "MCP_USER"),
        password=os.getenv("PASSWORD", "MCP_PASSWORD"),
    )

    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.ap-southeast-2.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    headers = {**token_client.authorization_header, "Content-Type": "application/json"}
    print(f"Invoking: {mcp_url}, \nwith headers: {headers}\n")

    async with streamablehttp_client(mcp_url, headers, timeout=120, terminate_on_close=False) as (
            read_stream,
            write_stream,
            _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tool_result = await session.list_tools()
            print(tool_result)


asyncio.run(main())