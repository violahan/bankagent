import json

import pytest

from mcp_server import mcp, RULE_SETS

ALL_POLICY_TYPES = sorted(RULE_SETS)


# -- Tools -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_tools_contains_get_credit_check_rules():
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    assert "get_credit_check_rules" in names


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


# -- Resources ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_resources_contains_policy_overview():
    resources = await mcp.list_resources()
    uris = [str(r.uri) for r in resources]
    assert "credit-check://policy-overview" in uris


@pytest.mark.asyncio
async def test_read_resource_policy_overview():
    contents = await mcp.read_resource("credit-check://policy-overview")
    item = list(contents)[0]
    payload = json.loads(item.content)

    assert payload["server"] == "credit-check-rules"
    assert payload["policy_source"] == "demo_rules"
    assert payload["supported_policy_types"] == ALL_POLICY_TYPES
    assert "policy_type" in payload["input_contract"]
    assert "rules" in payload["output_contract"]


# -- Prompts -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_prompt_credit_rules():
    result = await mcp.get_prompt("credit_rules_prompt", {})
    text = result.messages[0].content.text

    assert "get_credit_check_rules" in text
    for pt in ALL_POLICY_TYPES:
        assert pt in text
