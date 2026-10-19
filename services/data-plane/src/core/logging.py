"""
Structured JSON logging with automatic PII redaction.
Raw identifiers must NEVER appear in logs — only subject_ref and job_id.
"""
from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

# Patterns that look like personal identifiers — redacted at log time
_REDACT_PATTERNS = [
    re.compile(r"\b[6-9]\d{9}\b"),                        # 10-digit mobile
    re.compile(r"\+91[-\s]?\d{5}[-\s]?\d{5}"),           # +91 mobile
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),  # email
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),            # PAN
    re.compile(r"\b[0-9]{12}\b"),                          # Aadhaar
]
_REDACT_REPLACE = "***REDACTED***"


def _redact_pii(value: str) -> str:
    for pattern in _REDACT_PATTERNS:
        value = pattern.sub(_REDACT_REPLACE, value)
    return value


def _pii_redactor(
    logger: WrappedLogger, method: str, event_dict: EventDict
) -> EventDict:
    """Structlog processor: walk string values and redact PII patterns."""
    def _clean(v: Any) -> Any:
        if isinstance(v, str):
            return _redact_pii(v)
        if isinstance(v, dict):
            return {k: _clean(vv) for k, vv in v.items()}
        if isinstance(v, (list, tuple)):
            return type(v)(_clean(i) for i in v)
        return v

    return {k: _clean(v) for k, v in event_dict.items()}


def configure_logging(level: str = "INFO") -> None:
    """Call once at startup."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _pii_redactor,
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def get_logger(name: str = "data-plane") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
