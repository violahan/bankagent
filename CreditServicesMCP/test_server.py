import json

import pytest

from mcp_server import RULE_SETS, mcp

ALL_POLICY_TYPES = sorted(RULE_SETS)
SAMPLE_NAME = "Jane Doe"
SAMPLE_ADDRESS = "123 Maple Street, Springfield, IL 62704"


# -- Tools -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_tools_contains_get_credit_check_rules():
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    assert "get_credit_check_rules" in names
    assert "get_credit_check" in names


@pytest.mark.asyncio
@pytest.mark.parametrize("policy_type", ALL_POLICY_TYPES)
async def test_call_tool_returns_correct_rules(policy_type: str):
    result = await mcp.call_tool("get_credit_check_rules", {"policy_type": policy_type})

    # call_tool may return (content_blocks, dict), a list, or a dict
    if isinstance(result, tuple):
        content_blocks, raw = result
        payload = json.loads(content_blocks[0].text)
    elif isinstance(result, list):
        payload = json.loads(result[0].text)
    else:
        payload = result

    assert payload["ok"] is True
    assert payload["source"] == "demo_rules"
    assert payload["policy_type"] == policy_type
    assert payload["rules"] == RULE_SETS[policy_type]
    assert payload["rules"]["policy_name"] == RULE_SETS[policy_type]["policy_name"]


@pytest.mark.asyncio
async def test_call_tool_invalid_policy_type():
    result = await mcp.call_tool("get_credit_check_rules", {"policy_type": "nonexistent"})

    if isinstance(result, tuple):
        content_blocks, raw = result
        payload = json.loads(content_blocks[0].text)
    elif isinstance(result, list):
        payload = json.loads(result[0].text)
    else:
        payload = result

    assert payload["ok"] is False
    assert payload["tool"] == "get_credit_check_rules"
    assert "Supported values" in payload["message"]
    assert "Provide `policy_type`." in payload["requirements"]


@pytest.mark.asyncio
async def test_call_credit_check_tool_returns_expected_shape():
    result = await mcp.call_tool(
        "get_credit_check",
        {"name": SAMPLE_NAME, "address": SAMPLE_ADDRESS},
    )

    if isinstance(result, tuple):
        content_blocks, raw = result
        payload = json.loads(content_blocks[0].text)
    elif isinstance(result, list):
        payload = json.loads(result[0].text)
    else:
        payload = result

    report = payload["report"]

    assert payload["ok"] is True
    assert payload["source"] == "demo_credit_check"
    assert payload["name"] == SAMPLE_NAME
    assert payload["address"] == SAMPLE_ADDRESS
    assert report["name"] == SAMPLE_NAME
    assert report["address"] == SAMPLE_ADDRESS
    assert 300 <= report["bureau_score"] <= 850
    assert 0.18 <= report["debt_to_income_ratio"] <= 0.55
    assert 0.0 <= report["credit_utilisation"] <= 0.8
    assert 0 <= report["delinquency_count"] <= 3
    assert report["bankruptcies"] in (0, 1)
    assert 0 <= report["hard_inquiries_last_6_months"] <= 6
    assert report["external_rating"] in ("A", "B", "C", "D")
    assert "Bureau score:" in payload["formatted_report"]


@pytest.mark.asyncio
async def test_call_credit_check_tool_rejects_invalid_request():
    result = await mcp.call_tool(
        "get_credit_check",
        {"name": "JD", "address": "Main Street"},
    )

    if isinstance(result, tuple):
        content_blocks, raw = result
        payload = json.loads(content_blocks[0].text)
    elif isinstance(result, list):
        payload = json.loads(result[0].text)
    else:
        payload = result

    assert payload["ok"] is False
    assert payload["tool"] == "get_credit_check"
    assert "name must be at least 3 characters" in payload["message"]
    assert "address must contain a street number" in payload["message"]
    assert "Provide `name` with at least 3 characters." in payload["requirements"]
    assert "Ensure `address` contains a street number." in payload["requirements"]


# -- Resources ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_resources_contains_policy_overview():
    resources = await mcp.list_resources()
    uris = [str(r.uri) for r in resources]
    assert "credit-services://overview" in uris


@pytest.mark.asyncio
async def test_read_resource_policy_overview():
    contents = await mcp.read_resource("credit-services://overview")
    item = list(contents)[0]
    payload = json.loads(item.content)

    assert payload["server"] == "credit-services"
    assert payload["policy_source"] == "demo_rules"
    assert payload["credit_check_source"] == "demo_credit_check"
    assert payload["supported_policy_types"] == ALL_POLICY_TYPES
    assert "policy_type" in payload["rule_input_contract"]
    assert "rules" in payload["rule_output_contract"]
    assert "name" in payload["credit_check_input_contract"]
    assert "address" in payload["credit_check_input_contract"]
    assert "formatted_report" in payload["credit_check_output_contract"]


# -- Prompts -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_prompt_credit_rules():
    result = await mcp.get_prompt("credit_rules_prompt", {})
    text = result.messages[0].content.text

    assert "get_credit_check_rules" in text
    assert "get_credit_check" in text
    for pt in ALL_POLICY_TYPES:
        assert pt in text
    assert "name" in text
    assert "address" in text
