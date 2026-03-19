"""Mock credit lookup helpers for the CreditCheckAgent."""

from __future__ import annotations

import random
import re


REQUEST_PATTERN = re.compile(
    r"^\s*i want the credit check result from\s+(?P<name>.+?)\s+whose address is\s+(?P<address>.+?)\s*[.?!]?\s*$",
    re.IGNORECASE,
)


def _validate_inputs(name: str, address: str) -> None:
    errors: list[str] = []

    if len(name.strip()) < 3:
        errors.append("name must be at least 3 characters")
    if len(address.strip()) < 10:
        errors.append("address must be at least 10 characters")
    if address and not re.search(r"\d", address):
        errors.append("address must contain a street number")

    if errors:
        raise ValueError("; ".join(errors))


def parse_credit_check_request(request_text: str) -> tuple[str, str]:
    """Parse the narrow request format accepted by the CreditCheckAgent."""

    match = REQUEST_PATTERN.match(request_text)
    if not match:
        raise ValueError(
            "request must match: I want the credit check result from <name> whose address is <address>"
        )

    name = match.group("name").strip()
    address = match.group("address").strip()
    _validate_inputs(name, address)
    return name, address


def _external_rating(score: int) -> str:
    if score >= 740:
        return "A"
    if score >= 680:
        return "B"
    if score >= 620:
        return "C"
    return "D"


def lookup_credit_check(name: str, address: str) -> dict[str, int | float | str]:
    """Return a mock credit report for the supplied applicant."""

    _validate_inputs(name, address)

    rng = random.SystemRandom()

    bureau_score = rng.randint(300, 850)
    debt_to_income_ratio = round(rng.uniform(0.18, 0.55), 2)
    credit_utilisation = round(rng.uniform(0.00, 0.80), 2)
    delinquency_count = rng.randint(0, 3)
    bankruptcies = rng.choices([0, 1], weights=[9, 1], k=1)[0]
    hard_inquiries_last_6_months = rng.randint(0, 6)
    external_rating = _external_rating(bureau_score)

    return {
        "name": name.strip(),
        "address": address.strip(),
        "bureau_score": bureau_score,
        "debt_to_income_ratio": debt_to_income_ratio,
        "credit_utilisation": credit_utilisation,
        "delinquency_count": delinquency_count,
        "bankruptcies": bankruptcies,
        "hard_inquiries_last_6_months": hard_inquiries_last_6_months,
        "external_rating": external_rating,
    }


def format_credit_check_report(report: dict[str, int | float | str]) -> str:
    """Format the report in the field names expected by the analysis agent."""

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
