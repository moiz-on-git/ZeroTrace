"""Unit tests for ZeroTrace Backboard.io Conversational Memory Scrubber."""

import pytest
from src.erasure.backboard_memory_scrubber import BackboardMemoryScrubber


def test_backboard_memory_scrubber_success():
    scrubber = BackboardMemoryScrubber()
    result = scrubber.scrub_principal_memory(
        principal_id="user_dpdp_998877",
        active_thread_ids=["thread_bot_1", "thread_bot_2"],
    )

    assert result["status"] == "COMPLETED"
    assert result["provider"] == "Backboard.io"
    assert result["threads_scrubbed"] == 2
    assert result["turns_erased"] == 28
    assert result["vectors_zeroed"] == 28
    assert result["amnesia_probe_verified"] is True
    assert result["max_cosine_similarity"] == 0.000
    assert "amnesia_hash" in result["thread_details"][0]
    assert result["compliance_clause"] == "DPDP Act, 2023 Sec 6(4) & Sec 8(4)"
