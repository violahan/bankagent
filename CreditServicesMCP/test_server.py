import json

import pytest

from mcp_server import mcp, RULE_SETS

ALL_POLICY_TYPES = sorted(RULE_SETS)
SAMPLE_REQUEST = "I want the credit check result from Jane Doe whose address is 123 Maple Street, Springfield, IL 62704."


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

    assert payload["source"] == "demo_rules"
    assert payload["policy_type"] == policy_type
    assert payload["rules"] == RULE_SETS[policy_type]
    assert payload["rules"]["policy_name"] == RULE_SETS[policy_type]["policy_name"]


@pytest.mark.asyncio
async def test_call_tool_invalid_policy_type():
    with pytest.raises((ValueError, Exception)):
        await mcp.call_tool("get_credit_check_rules", {"policy_type": "nonexistent"})


@pytest.mark.asyncio
async def test_call_credit_check_tool_returns_expected_shape():
    result = await mcp.call_tool("get_credit_check", {"request_text": SAMPLE_REQUEST})

    if isinstance(result, tuple):
        content_blocks, raw = result
        payload = json.loads(content_blocks[0].text)
    elif isinstance(result, list):
        payload = json.loads(result[0].text)
    else:
        payload = result

    report = payload["report"]

    assert payload["source"] == "demo_credit_check"
    assert payload["request_text"] == SAMPLE_REQUEST.strip()
    assert report["name"] == "Jane Doe"
    assert report["address"] == "123 Maple Street, Springfield, IL 62704"
    assert "Bureau score:" in payload["formatted_report"]


@pytest.mark.asyncio
async def test_call_credit_check_tool_rejects_invalid_request():
    with pytest.raises((ValueError, Exception)):
        await mcp.call_tool("get_credit_check", {"request_text": "check Jane Doe"})


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
    assert "request_text" in payload["credit_check_input_contract"]
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
