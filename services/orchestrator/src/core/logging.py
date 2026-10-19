"""
ZeroTrace Structlog Logging System with Built-in PII Redaction.
Enforces non-negotiable rule: Raw identifiers NEVER appear in logs or error messages.
"""

from __future__ import annotations
import re
import sys
from typing import Any, Dict
import structlog


# Redaction regex patterns
PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[-.\s]?)?(\d{5}[-.\s]?\d{5}|\d{3}[-.\s]?\d{3}[-.\s]?\d{4})")
EMAIL_PATTERN = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
PAN_PATTERN = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]{1}")
AADHAAR_PATTERN = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")


def redact_string(val: str) -> str:
    val = PHONE_PATTERN.sub("[REDACTED_PHONE]", val)
    val = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", val)
    val = PAN_PATTERN.sub("[REDACTED_PAN]", val)
    val = AADHAAR_PATTERN.sub("[REDACTED_AADHAAR]", val)
    return val


def redact_pii_processor(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively scrubs PII from all log fields.
    """
    def scrub(item: Any) -> Any:
        if isinstance(item, str):
            return redact_string(item)
        elif isinstance(item, dict):
            return {k: scrub(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [scrub(x) for x in item]
        return item

    return scrub(event_dict)


def setup_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_pii_processor,
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


setup_logging()
logger = structlog.get_logger("zerotrace.orchestrator")
