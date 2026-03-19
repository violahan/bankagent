"""Backward-compatible wrapper around the shared credit-check helpers."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared_credit_check import (  # noqa: E402
    format_credit_check_report,
    lookup_credit_check,
    parse_credit_check_request,
)
