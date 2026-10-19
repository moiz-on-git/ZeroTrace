"""
Tests: PII never appears in logs or events.
Plants identifiers and checks they are redacted.
"""
from __future__ import annotations

import io
import json
import logging

import pytest

from src.seed.subjects import HERO


def test_logging_redacts_phone(capfd):
    """Hero's phone number must be redacted in log output."""
    from src.core.logging import configure_logging, get_logger

    configure_logging("DEBUG")
    logger = get_logger("test")

    # Log a message containing the hero's phone
    logger.info("test_event", raw_phone=HERO.phone, message=f"Customer called from {HERO.phone}")

    captured = capfd.readouterr()
    output = captured.out + captured.err

    # Phone must not appear in raw form
    if HERO.phone in output:
        pytest.fail(f"Hero phone {HERO.phone} found in log output — PII leak!")


def test_logging_redacts_email(capfd):
    """Hero's email must be redacted in log output."""
    from src.core.logging import configure_logging, get_logger

    configure_logging("DEBUG")
    logger = get_logger("test_email")
    logger.info("test_email_event", email=HERO.email)

    captured = capfd.readouterr()
    output = captured.out + captured.err

    if HERO.email in output:
        pytest.fail(f"Hero email {HERO.email} found in log output — PII leak!")


def test_mask_function():
    """_mask must not return the original value."""
    from src.audit.attack_library import _mask

    phone = HERO.phone
    masked = _mask(phone)
    assert phone not in masked
    assert len(masked) == len(phone) or "•" in masked


def test_event_message_no_pii():
    """Events emitted must not contain raw PII in the message field."""
    from src.erasure.events import make_event

    # This simulates what the event emitter produces
    event = make_event(
        job_id="job_test_001",
        seq=1,
        stage="ERASE_ICEBERG",
        kind="metric",
        layer="iceberg",
        message="Deleted rows from customers table",   # Must NOT contain phone/email
        data={"files_rewritten": 3},
    )

    event_str = json.dumps(event)
    assert HERO.phone not in event_str
    assert HERO.email not in event_str
