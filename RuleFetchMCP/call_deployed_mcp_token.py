import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    agent_arn = os.getenv('AGENT_ARN', "arn:aws:bedrock-agentcore:ap-southeast-2:590183866516:runtime/bank_rules_mcp_server_oauth-dk7JZVCwJ9")
    bearer_token = os.getenv('BEARER_TOKEN', "eyJraWQiOiJTK3hsWUNnNWxhSElrOForMDJ0eW1yWlBYT1Q5RnhES0p1WE1OcDY5RFVnPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiI5OTNlOTQ4OC03MGExLTcwNzgtNzEwOS1hNTJmMzU1NzkwMjciLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAuYXAtc291dGhlYXN0LTIuYW1hem9uYXdzLmNvbVwvYXAtc291dGhlYXN0LTJfNkFud0lzc1lEIiwiY2xpZW50X2lkIjoiMmV1c21iZTd1amdoNjExdmg0bTRwNW4yMmciLCJvcmlnaW5fanRpIjoiNjI4MjI4ZDctMTc0Zi00YjhjLWJlM2MtZTUyMDVhZDUzMzQyIiwiZXZlbnRfaWQiOiJjZjY4ZjJjNC0wNjMwLTQ0M2YtYTllMy03M2ZkNmRlZDU4ZGQiLCJ0b2tlbl91c2UiOiJhY2Nlc3MiLCJzY29wZSI6ImF3cy5jb2duaXRvLnNpZ25pbi51c2VyLmFkbWluIiwiYXV0aF90aW1lIjoxNzczOTEzMjQ4LCJleHAiOjE3NzM5MTY4NDgsImlhdCI6MTc3MzkxMzI0OCwianRpIjoiMzNlYmYwYTYtYmE0ZC00MTU5LWE1NDEtODZiM2Q4Y2MwNTkwIiwidXNlcm5hbWUiOiJNQ1BfVVNFUiJ9.CcqDY8qEXhXRzlH13mQXXmaDZcMWLN29171fMeLFZ6my2z3Dva9f-lE8_1ea61sUVrvpHwuUQfDErCNvHnh6W471Wtjgq_VCCo30hfHg6SEdR5qxWNyanXMRRKpHHrqhH1w31y7RmrbztI1PVW-XJq5D3L8670XxlXPJq2xWkkrmtAbo2io8UryDGsqB1-gDx5xXRv3Jisgb3Q58YQDRr-DGo888GLYG4z0uG8fdfyOHnrW6YNi-ggdQ8OsfGS26TXw5zw4UBH2pZZWL6O7LtJE8kc8Sgz9nyR0ZpWFX0qAGBCZ6J-ObyE9HrbHLlv-4LdK10H1iYP0VNK1woLi8lw")
    if not agent_arn or not bearer_token:
        print("Error: AGENT_ARN or BEARER_TOKEN environment variable is not set")
        sys.exit(1)

    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.ap-southeast-2.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    headers = {"authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}
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