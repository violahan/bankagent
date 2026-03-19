from pathlib import Path
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared_credit_check import (  # noqa: E402
    format_credit_check_report,
    lookup_credit_check,
    parse_credit_check_request,
)


RULE_SETS: dict[str, dict] = {
    "personal_loan": {
        "policy_name": "Personal Loan Policy",
        "policy_version": "2026.03",
        "last_updated": "2026-03-18",
        "minimum_age": 18,
        "minimum_bureau_score": 680,
        "maximum_debt_to_income_ratio": 0.4,
        "maximum_credit_utilization_ratio": 0.55,
        "max_bankruptcies": 0,
        "max_hard_inquiries_last_6_months": 4,
        "accepted_external_ratings": ["A", "B"],
        "restricted_employment_statuses": ["unemployed"],
        "manual_review_if_delinquency_count_at_least": 1,
        "auto_decline_if_delinquency_count_at_least": 3,
        "supported_loan_purposes": ["personal", "debt_consolidation"],
    },
    "vehicle_loan": {
        "policy_name": "Vehicle Loan Policy",
        "policy_version": "2026.03",
        "last_updated": "2026-03-18",
        "minimum_age": 18,
        "minimum_bureau_score": 650,
        "maximum_debt_to_income_ratio": 0.45,
        "maximum_credit_utilization_ratio": 0.6,
        "max_bankruptcies": 0,
        "max_hard_inquiries_last_6_months": 5,
        "accepted_external_ratings": ["A", "B", "C"],
        "restricted_employment_statuses": ["unemployed"],
        "manual_review_if_delinquency_count_at_least": 2,
        "auto_decline_if_delinquency_count_at_least": 4,
        "supported_loan_purposes": ["vehicle"],
    },
    "mortgage_refinance": {
        "policy_name": "Mortgage Refinance Policy",
        "policy_version": "2026.03",
        "last_updated": "2026-03-18",
        "minimum_age": 21,
        "minimum_bureau_score": 720,
        "maximum_debt_to_income_ratio": 0.36,
        "maximum_credit_utilization_ratio": 0.5,
        "max_bankruptcies": 0,
        "max_hard_inquiries_last_6_months": 3,
        "accepted_external_ratings": ["A", "B"],
        "restricted_employment_statuses": ["unemployed", "contract"],
        "manual_review_if_delinquency_count_at_least": 1,
        "auto_decline_if_delinquency_count_at_least": 2,
        "supported_loan_purposes": ["mortgage_refinance"],
    },
}


mcp = FastMCP(
    host="0.0.0.0",
    stateless_http=True,
    name="credit-services",
    instructions=(
        "Use this server to fetch hardcoded bank credit policies and run mock "
        "credit checks."
    ),
)


@mcp.tool()
def get_credit_check_rules(policy_type: str) -> dict[str, Any]:
    """Return a hardcoded bank credit policy for the requested product type.

    Args:
        policy_type: One of `personal_loan`, `vehicle_loan`, or `mortgage_refinance`.
    """
    if policy_type not in RULE_SETS:
        supported = ", ".join(sorted(RULE_SETS))
        raise ValueError(
            f"Unsupported policy_type '{policy_type}'. Supported values: {supported}."
        )

    return {
        "source": "demo_rules",
        "policy_type": policy_type,
        "rules": RULE_SETS[policy_type],
    }


@mcp.tool()
def get_credit_check(request_text: str) -> dict[str, Any]:
    """Return a mock credit check from the raw request sentence.

    Args:
        request_text: Request in the form
            `I want the credit check result from <name> whose address is <address>`.
    """
    name, address = parse_credit_check_request(request_text)
    report = lookup_credit_check(name=name, address=address)
    return {
        "source": "demo_credit_check",
        "request_text": request_text.strip(),
        "report": report,
        "formatted_report": format_credit_check_report(report),
    }


@mcp.resource("credit-services://overview")
def policy_overview() -> dict[str, Any]:
    """Describe the available tools and response shapes."""
    return {
        "server": "credit-services",
        "policy_source": "demo_rules",
        "credit_check_source": "demo_credit_check",
        "tools": ["get_credit_check_rules", "get_credit_check"],
        "rule_input_contract": ["policy_type"],
        "supported_policy_types": sorted(RULE_SETS),
        "rule_output_contract": ["source", "policy_type", "rules"],
        "credit_check_input_contract": ["request_text"],
        "credit_check_output_contract": [
            "source",
            "request_text",
            "report",
            "formatted_report",
        ],
    }


@mcp.prompt()
def credit_rules_prompt() -> str:
    """Provide a ready-to-use prompt for the available MCP tools."""
    types = ", ".join(f"`{t}`" for t in sorted(RULE_SETS))
    return (
        f"Call `get_credit_check_rules` with one of these policy types: {types}. "
        "Call `get_credit_check` with "
        "`I want the credit check result from <name> whose address is <address>`."
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
