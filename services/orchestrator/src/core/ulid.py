"""
ZeroTrace Crockford Base32 ULID Generator.
Generates standard 26-character ULIDs with domain prefixes:
- req_... (intake request)
- job_... (erasure & proof job)
- rcpt_... (cryptographic receipt)
- sub_... (pseudonymous subject_ref)
"""

from __future__ import annotations
import os
import time
import hmac
import hashlib

CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid(prefix: str = "") -> str:
    """
    Generates a 26-character Crockford Base32 ULID.
    Timestamp: 48 bits (10 chars)
    Random: 80 bits (16 chars)
    """
    timestamp_ms = int(time.time() * 1000)

    # 48-bit timestamp to 10 chars
    t_chars = []
    t_val = timestamp_ms
    for _ in range(10):
        t_chars.append(CROCKFORD_BASE32[t_val & 31])
        t_val >>= 5
    t_str = "".join(reversed(t_chars))

    # 80-bit random to 16 chars
    rand_bytes = os.urandom(10)
    r_val = int.from_bytes(rand_bytes, byteorder="big")
    r_chars = []
    for _ in range(16):
        r_chars.append(CROCKFORD_BASE32[r_val & 31])
        r_val >>= 5
    r_str = "".join(reversed(r_chars))

    ulid = t_str + r_str
    return f"{prefix}{ulid}" if prefix else ulid


def generate_subject_ref(identifier: str, pepper: str) -> str:
    """
    Computes pseudonymous subject_ref: HMAC-SHA256(pepper, identifier).
    Returns sub_ + first 16 hex chars.
    """
    digest = hmac.new(pepper.encode("utf-8"), identifier.strip().encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sub_{digest[:16]}"
