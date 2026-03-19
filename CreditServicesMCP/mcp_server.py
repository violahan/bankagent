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

CREDIT_CHECK_LOOKUPS: dict[str, dict[str, int | float | str]] = {
    "jane_doe": {
        "name": "Jane Doe",
        "address": "123 Maple Street, Springfield, IL 62704",
        "bureau_score": 742,
        "debt_to_income_ratio": 0.31,
        "credit_utilisation": 0.28,
        "delinquency_count": 0,
        "bankruptcies": 0,
        "hard_inquiries_last_6_months": 1,
        "external_rating": "A",
    },
    "john_smith": {
        "name": "John Smith",
        "address": "456 Oak Avenue, Denver, CO 80203",
        "bureau_score": 668,
        "debt_to_income_ratio": 0.42,
        "credit_utilisation": 0.58,
        "delinquency_count": 1,
        "bankruptcies": 0,
        "hard_inquiries_last_6_months": 3,
        "external_rating": "C",
    },
    "maria_garcia": {
        "name": "Maria Garcia",
        "address": "789 Pine Road, Austin, TX 78701",
        "bureau_score": 721,
        "debt_to_income_ratio": 0.35,
        "credit_utilisation": 0.41,
        "delinquency_count": 0,
        "bankruptcies": 0,
        "hard_inquiries_last_6_months": 2,
        "external_rating": "B",
    },
}


def _format_credit_check_report(report: dict[str, int | float | str]) -> str:
    return "\n".join(
        [
            f"Name: {report['name']}",
            f"Address: {report['address']}",
            f"Bureau score: {report['bureau_score']}",
            f"Debt-to-income ratio: {report['debt_to_income_ratio']:.2f}",
            f"Credit utilisation: {report['credit_utilisation']:.2f}",
            f"Number of delinquencies: {report['delinquency_count']}",
            f"Bankruptcies: {report['bankruptcies']}",
            f"Hard inquiries in last 6 months: {report['hard_inquiries_last_6_months']}",
            f"External rating: {report['external_rating']}",
        ]
    )


mcp = FastMCP(
    host="0.0.0.0",
    stateless_http=True,
    name="credit-services",
    instructions=(
        "Use this server to fetch hardcoded bank credit policies and applicant "
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
def get_credit_check(applicant_id: str) -> dict[str, Any]:
    """Return a hardcoded credit check for the requested applicant.

    Args:
        applicant_id: One of `jane_doe`, `john_smith`, or `maria_garcia`.
    """
    if applicant_id not in CREDIT_CHECK_LOOKUPS:
        supported = ", ".join(sorted(CREDIT_CHECK_LOOKUPS))
        raise ValueError(
            f"Unsupported applicant_id '{applicant_id}'. Supported values: {supported}."
        )

    report = CREDIT_CHECK_LOOKUPS[applicant_id]
    return {
        "source": "demo_credit_check",
        "applicant_id": applicant_id,
        "report": report,
        "formatted_report": _format_credit_check_report(report),
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
        "credit_check_input_contract": ["applicant_id"],
        "supported_applicant_ids": sorted(CREDIT_CHECK_LOOKUPS),
        "credit_check_output_contract": [
            "source",
            "applicant_id",
            "report",
            "formatted_report",
        ],
    }


@mcp.prompt()
def credit_rules_prompt() -> str:
    """Provide a ready-to-use prompt for the available MCP tools."""
    types = ", ".join(f"`{t}`" for t in sorted(RULE_SETS))
    applicants = ", ".join(f"`{a}`" for a in sorted(CREDIT_CHECK_LOOKUPS))
    return (
        f"Call `get_credit_check_rules` with one of these policy types: {types}. "
        f"Call `get_credit_check` with one of these applicant ids: {applicants}."
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
