import random
import re
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


def _validate_inputs(name: str, address: str) -> tuple[str, str]:
    cleaned_name = name.strip()
    cleaned_address = address.strip()
    errors: list[str] = []

    if len(cleaned_name) < 3:
        errors.append("name must be at least 3 characters")
    if len(cleaned_address) < 10:
        errors.append("address must be at least 10 characters")
    if cleaned_address and not re.search(r"\d", cleaned_address):
        errors.append("address must contain a street number")

    if errors:
        raise ValueError("; ".join(errors))

    return cleaned_name, cleaned_address


def _external_rating(score: int) -> str:
    if score >= 740:
        return "A"
    if score >= 680:
        return "B"
    if score >= 620:
        return "C"
    return "D"


def _lookup_credit_check(name: str, address: str) -> dict[str, int | float | str]:
    cleaned_name, cleaned_address = _validate_inputs(name, address)

    rng = random.SystemRandom()
    bureau_score = rng.randint(300, 850)
    debt_to_income_ratio = round(rng.uniform(0.18, 0.55), 2)
    credit_utilisation = round(rng.uniform(0.00, 0.80), 2)
    delinquency_count = rng.randint(0, 3)
    bankruptcies = rng.choices([0, 1], weights=[9, 1], k=1)[0]
    hard_inquiries_last_6_months = rng.randint(0, 6)
    external_rating = _external_rating(bureau_score)

    return {
        "name": cleaned_name,
        "address": cleaned_address,
        "bureau_score": bureau_score,
        "debt_to_income_ratio": debt_to_income_ratio,
        "credit_utilisation": credit_utilisation,
        "delinquency_count": delinquency_count,
        "bankruptcies": bankruptcies,
        "hard_inquiries_last_6_months": hard_inquiries_last_6_months,
        "external_rating": external_rating,
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
        "Use this server to fetch hardcoded bank credit policies and generated "
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
def get_credit_check(name: str, address: str) -> dict[str, Any]:
    """Return a generated credit check for the supplied applicant.

    Args:
        name: Applicant name.
        address: Applicant address.
    """
    cleaned_name, cleaned_address = _validate_inputs(name, address)
    report = _lookup_credit_check(name=cleaned_name, address=cleaned_address)
    return {
        "source": "demo_credit_check",
        "name": cleaned_name,
        "address": cleaned_address,
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
        "credit_check_input_contract": ["name", "address"],
        "credit_check_output_contract": [
            "source",
            "name",
            "address",
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
        "Call `get_credit_check` with `name` and `address`."
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
