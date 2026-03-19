from typing import Any

from mcp.server.fastmcp import FastMCP

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
    name="credit-check-rules",
    instructions="Use this server to fetch hardcoded bank credit-check rules.",
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


@mcp.resource("credit-check://policy-overview")
def policy_overview() -> dict[str, Any]:
    """Describe the available policy types and response shape."""
    return {
        "server": "credit-check-rules",
        "policy_source": "demo_rules",
        "input_contract": ["policy_type"],
        "supported_policy_types": sorted(RULE_SETS),
        "output_contract": ["source", "policy_type", "rules"],
    }


@mcp.prompt()
def credit_rules_prompt() -> str:
    """Provide a ready-to-use prompt for fetching a rule set."""
    types = ", ".join(f"`{t}`" for t in sorted(RULE_SETS))
    return f"Call `get_credit_check_rules` with one of these policy types: {types}."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
