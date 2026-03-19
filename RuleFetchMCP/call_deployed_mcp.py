import json

import boto3
from botocore.exceptions import ClientError


client = boto3.client("bedrock-agentcore", region_name="ap-southeast-2")
runtime_arn = (
    "arn:aws:bedrock-agentcore:ap-southeast-2:590183866516:"
    "runtime/bank_rules_mcp_server-lbEMT9Cr0z"
)


def _extract_jsonrpc_message(raw: str) -> dict:
    """Parse a JSON-RPC message from either JSON or SSE payloads."""
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty response payload from runtime.")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    candidates: list[dict] = []
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue

        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            continue

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, dict):
            candidates.append(payload)

    if not candidates:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"Unable to parse runtime response: {raw}")
        return json.loads(raw[start : end + 1])

    for payload in reversed(candidates):
        if "result" in payload or "error" in payload:
            return payload

    return candidates[-1]


def call_mcp(method: str, params: dict | None = None) -> dict:
    """Call an MCP method on the deployed AgentCore runtime."""
    if params is None:
        params = {}

    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
    ).encode()

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            payload=payload,
            qualifier="DEFAULT",
            contentType="application/json",
            accept="application/json, text/event-stream",
        )
    except ClientError as exc:
        print(f"\n{'=' * 60}")
        print("Error Response:")
        print(json.dumps(exc.response, indent=2, default=str))
        print(f"{'=' * 60}\n")
        raise

    raw = response["response"].read().decode()
    message = _extract_jsonrpc_message(raw)

    if "error" in message:
        raise RuntimeError(json.dumps(message["error"], indent=2))

    return message["result"]


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_tool_call(policy_type: str) -> None:
    _print_section(f"get_loan_application_review_rules(policy_type={policy_type!r})")
    result = call_mcp(
        "tools/call",
        {
            "name": "get_loan_application_review_rules",
            "arguments": {"policy_type": policy_type},
        },
    )
    print(json.dumps(result.get("structuredContent", result), indent=2))


def main() -> None:
    _print_section("Available Tools")
    tools_result = call_mcp("tools/list")
    for tool in tools_result["tools"]:
        print(f"{tool['name']}: {tool['description']}")

    _print_section("Available Resources")
    resources_result = call_mcp("resources/list")
    for resource in resources_result.get("resources", []):
        print(f"{resource['uri']}: {resource['name']}")

    _print_section("Overview Resource")
    overview_result = call_mcp(
        "resources/read",
        {"uri": "bank-rules-mcp-server://overview"},
    )
    print(json.dumps(overview_result, indent=2))

    _print_section("Available Prompts")
    prompts_result = call_mcp("prompts/list")
    for prompt in prompts_result.get("prompts", []):
        print(f"{prompt['name']}: {prompt['description']}")

    _print_section("Prompt Payload")
    prompt_result = call_mcp("prompts/get", {"name": "credit_rules_prompt"})
    print(json.dumps(prompt_result, indent=2))

    for policy_type in (
        "personal_loan",
        "vehicle_loan",
        "mortgage_refinance",
        "invalid_policy",
    ):
        _print_tool_call(policy_type)


if __name__ == "__main__":
    main()
