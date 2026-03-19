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

def _invalid_tool_response(tool_name: str, message: str, requirements: list[str]) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool_name,
        "message": message,
        "requirements": requirements,
    }

mcp = FastMCP(
    host="0.0.0.0",
    stateless_http=True,
    name="bank-rules-mcp-server",
    instructions=(
        "Use this server to fetch the bank rules used to review a loan application."
    ),
)


@mcp.tool()
def get_loan_application_review_rules(policy_type: str) -> dict[str, Any]:
    """Get the bank rules used to review a loan application for a specific product.

    Use this tool when you already know which product the applicant is applying
    for and you need the rule thresholds for decisioning. Pass `policy_type` as
    one of `personal_loan`, `vehicle_loan`, or `mortgage_refinance`.

    On success, this tool returns `ok: true` and a `rules` object containing the
    review criteria for that product. If the input is invalid, it returns
    `ok: false` with a `message` and `requirements` describing what the caller
    must provide.

    Args:
        policy_type: One of `personal_loan`, `vehicle_loan`, or `mortgage_refinance`.
    """
    if policy_type not in RULE_SETS:
        supported = ", ".join(sorted(RULE_SETS))
        return _invalid_tool_response(
            tool_name="get_loan_application_review_rules",
            message=(
                f"Unsupported policy_type '{policy_type}'. "
                f"Supported values: {supported}."
            ),
            requirements=[
                "Provide `policy_type`.",
                f"Use one of: {supported}.",
            ],
        )

    return {
        "ok": True,
        "source": "rules",
        "policy_type": policy_type,
        "rules": RULE_SETS[policy_type],
    }

@mcp.resource("bank-rules-mcp-server://overview")
def policy_overview() -> dict[str, Any]:
    """Describe the available tools and response shapes."""
    return {
        "server": "bank-rules-mcp-server",
        "policy_source": "rules",
        "tools": ["get_loan_application_review_rules"],
        "rule_input_contract": ["policy_type"],
        "supported_policy_types": sorted(RULE_SETS),
        "rule_output_contract": ["ok", "source", "policy_type", "rules"],
    }


@mcp.prompt()
def credit_rules_prompt() -> str:
    """Provide a ready-to-use prompt for the available MCP tools."""
    types = ", ".join(f"`{t}`" for t in sorted(RULE_SETS))
    return f"Call `get_loan_application_review_rules` with one of these policy types: {types}."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
