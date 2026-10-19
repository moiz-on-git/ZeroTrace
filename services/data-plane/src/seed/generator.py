"""
Deterministic seed generator for Kaveri Finserv (fictional NBFC).
Produces ~50 000 customers, multiple Iceberg snapshots, pgvector embeddings,
Redis semantic cache entries, and plants HERO subject + DECOY subjects.

Profiles:
  small    — 500 customers, fast (tests)
  showtime — 50 000 customers, ~480 Parquet files, multiple snapshots
"""
from __future__ import annotations

import hashlib
import json
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from faker import Faker

from src.core.config import get_settings
from src.core.logging import get_logger
from src.seed.subjects import HERO, DECOY_1, DECOY_2, Subject

logger = get_logger("seed")

# Faker with Indian locale, seeded
fake = Faker(["en_IN", "hi_IN"])
cfg = get_settings()


# ── Profile sizes ─────────────────────────────────────────────────────────────

PROFILES: dict[str, dict[str, Any]] = {
    "small": {
        "n_customers": 500,
        "n_loans_per_customer": (0, 2),
        "n_tickets_per_customer": (0, 3),
        "n_transcripts": 50,
        "n_marketing_events": 800,
        "n_payments_per_loan": (1, 5),
        "target_files": 20,
    },
    "showtime": {
        "n_customers": 50_000,
        "n_loans_per_customer": (0, 3),
        "n_tickets_per_customer": (0, 5),
        "n_transcripts": 2000,
        "n_marketing_events": 80_000,
        "n_payments_per_loan": (1, 8),
        "target_files": 480,
    },
}

INDIAN_STATES = [
    "Karnataka", "Tamil Nadu", "Telangana", "Maharashtra", "Delhi",
    "Uttar Pradesh", "Gujarat", "West Bengal", "Rajasthan", "Kerala",
]

LOAN_PURPOSES = ["Home Loan", "Personal Loan", "Business Loan", "Education Loan", "Vehicle Loan"]
KYC_TYPES = ["PAN", "Aadhaar", "Passport", "Voter ID", "Driving Licence"]
TICKET_CATEGORIES = ["EMI Query", "Account Closure", "Statement Request", "Fraud Report", "General"]
MARKETING_CHANNELS = ["email", "sms", "push", "whatsapp"]


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def _phone() -> str:
    """10-digit Indian mobile number."""
    prefixes = ["98", "97", "96", "95", "94", "93", "92", "91", "90", "88", "87", "86", "85", "84"]
    p = random.choice(prefixes) + str(random.randint(10_000_000, 99_999_999))
    return p


def _pan() -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return (
        "".join(random.choices(letters, k=5))
        + "".join(random.choices("0123456789", k=4))
        + random.choice(letters)
    )


def _customer_row(cid: str, rng: random.Random) -> dict:
    first = fake.first_name()
    last = fake.last_name()
    return {
        "customer_id": cid,
        "full_name": f"{first} {last}",
        "phone": _phone(),
        "email": f"{first.lower()}.{last.lower()}{rng.randint(1,999)}@example.in",
        "dob": str(date(rng.randint(1960, 2000), rng.randint(1, 12), rng.randint(1, 28))),
        "address_line1": fake.street_address(),
        "city": fake.city(),
        "state": rng.choice(INDIAN_STATES),
        "pincode": str(rng.randint(100000, 999999)),
        "created_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(30, 1825))).isoformat(),
    }


def _hero_customer_row(hero: Subject) -> dict:
    return {
        "customer_id": hero.customer_id,
        "full_name": hero.full_name,
        "phone": hero.phone,
        "email": hero.email,
        "dob": hero.dob,
        "address_line1": "42, MG Road",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pincode": "560001",
        "created_at": "2022-06-15T10:30:00+00:00",
    }


def _kyc_row(cid: str, rng: random.Random, phone: str, pan: str) -> dict:
    return {
        "kyc_id": f"KYC-{uuid.uuid4().hex[:12].upper()}",
        "customer_id": cid,
        "kyc_type": rng.choice(KYC_TYPES),
        "doc_number": pan,
        "verified_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 365))).isoformat(),
        "status": "VERIFIED",
        "phone_at_kyc": phone,
    }


def _loan_row(cid: str, rng: random.Random) -> dict:
    loan_id = f"KF-LOAN-{rng.randint(100000,999999)}"
    amount = rng.randint(50_000, 5_000_000)
    return {
        "loan_id": loan_id,
        "customer_id": cid,
        "purpose": rng.choice(LOAN_PURPOSES),
        "principal_inr": amount,
        "interest_rate_pct": round(rng.uniform(8.5, 24.0), 2),
        "tenure_months": rng.choice([12, 24, 36, 48, 60, 84, 120]),
        "status": rng.choice(["ACTIVE", "CLOSED", "NPA", "SANCTIONED"]),
        "disbursed_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(30, 1000))).isoformat(),
    }


def _payment_row(loan_id: str, cid: str, rng: random.Random) -> dict:
    return {
        "payment_id": f"PAY-{uuid.uuid4().hex[:12].upper()}",
        "loan_id": loan_id,
        "customer_id": cid,
        "amount_inr": rng.randint(1000, 50000),
        "paid_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 300))).isoformat(),
        "method": rng.choice(["UPI", "NEFT", "RTGS", "Cheque", "Auto-debit"]),
        "status": rng.choice(["SUCCESS", "SUCCESS", "SUCCESS", "FAILED", "PENDING"]),
    }


def _ticket_row(cid: str, rng: random.Random, phone: str) -> dict:
    return {
        "ticket_id": f"TKT-{uuid.uuid4().hex[:10].upper()}",
        "customer_id": cid,
        "category": rng.choice(TICKET_CATEGORIES),
        "description": f"Customer query regarding their account. Phone on record: {phone}",
        "status": rng.choice(["OPEN", "RESOLVED", "CLOSED"]),
        "created_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 200))).isoformat(),
        "resolved_at": None,
    }


def _transcript_row(cid: str, rng: random.Random, name: str, phone: str) -> dict:
    texts = [
        f"Agent: Hello, can I speak with {name}? Customer: Yes, this is {name}, my number is {phone}.",
        f"Customer: I want to close my account. Name: {name}. Phone: {phone}.",
        f"Agent: Thank you {name}, we have updated your record. Your registered mobile is {phone}.",
    ]
    return {
        "transcript_id": f"TRX-{uuid.uuid4().hex[:10].upper()}",
        "customer_id": cid,
        "transcript_text": rng.choice(texts),
        "language": rng.choice(["en", "hi", "kn", "ta", "te"]),
        "call_date": (datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 365))).isoformat(),
        "duration_seconds": rng.randint(60, 600),
    }


def _marketing_row(cid: str, rng: random.Random, email: str, phone: str) -> dict:
    return {
        "event_id": f"MKT-{uuid.uuid4().hex[:10].upper()}",
        "customer_id": cid,
        "channel": rng.choice(MARKETING_CHANNELS),
        "campaign_id": f"CAMP-{rng.randint(1,50):03d}",
        "sent_to": email if rng.random() > 0.5 else phone,
        "sent_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 180))).isoformat(),
        "opened": rng.choice([True, False]),
        "clicked": rng.choice([True, False, False]),
    }


# ─────────────────────────────────────────────────────────────────────────────

def generate_all_rows(profile: str, seed: int) -> dict[str, list[dict]]:
    """
    Generate all rows for every table.
    Returns a dict of table_name -> list[row_dict].
    """
    cfg_profile = PROFILES[profile]
    rng = _rng(seed)
    fake.seed_instance(seed)
    random.seed(seed)

    n = cfg_profile["n_customers"]
    logger.info("seed.generating", profile=profile, n_customers=n)

    customers: list[dict] = []
    kyc_docs: list[dict] = []
    loans: list[dict] = []
    payments: list[dict] = []
    tickets: list[dict] = []
    transcripts: list[dict] = []
    marketing: list[dict] = []

    # Always inject hero and decoys first at known positions
    for subj in [HERO, DECOY_1, DECOY_2]:
        row = _hero_customer_row(subj) if subj.is_hero else {
            "customer_id": subj.customer_id,
            "full_name": subj.full_name,
            "phone": subj.phone,
            "email": subj.email,
            "dob": subj.dob,
            "address_line1": fake.street_address(),
            "city": fake.city(),
            "state": rng.choice(INDIAN_STATES),
            "pincode": str(rng.randint(100000, 999999)),
            "created_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(30, 1825))).isoformat(),
        }
        customers.append(row)
        kyc_docs.append(_kyc_row(subj.customer_id, rng, subj.phone, subj.pan))
        # Hero gets multiple tickets and transcripts so data is spread across files
        n_hero_tickets = 5 if subj.is_hero else 2
        for _ in range(n_hero_tickets):
            tickets.append(_ticket_row(subj.customer_id, rng, subj.phone))
            transcripts.append(_transcript_row(subj.customer_id, rng, subj.full_name, subj.phone))
        lo = _loan_row(subj.customer_id, rng)
        loans.append(lo)
        for _ in range(rng.randint(2, 5)):
            payments.append(_payment_row(lo["loan_id"], subj.customer_id, rng))
        for _ in range(3):
            marketing.append(_marketing_row(subj.customer_id, rng, subj.email, subj.phone))

    # Generate regular customers
    for i in range(n):
        cid = f"KF-CUST-{i+10000:06d}"
        cust = _customer_row(cid, rng)
        customers.append(cust)
        kyc_docs.append(_kyc_row(cid, rng, cust["phone"], _pan()))

        n_loans = rng.randint(*cfg_profile["n_loans_per_customer"])
        for _ in range(n_loans):
            lo = _loan_row(cid, rng)
            loans.append(lo)
            for _ in range(rng.randint(*cfg_profile["n_payments_per_loan"])):
                payments.append(_payment_row(lo["loan_id"], cid, rng))

        for _ in range(rng.randint(*cfg_profile["n_tickets_per_customer"])):
            tickets.append(_ticket_row(cid, rng, cust["phone"]))

        if rng.random() < 0.1:
            transcripts.append(_transcript_row(cid, rng, cust["full_name"], cust["phone"]))

        if rng.random() < 0.4:
            for _ in range(rng.randint(1, 3)):
                marketing.append(_marketing_row(cid, rng, cust["email"], cust["phone"]))

    logger.info(
        "seed.rows_generated",
        customers=len(customers),
        kyc=len(kyc_docs),
        loans=len(loans),
        payments=len(payments),
        tickets=len(tickets),
        transcripts=len(transcripts),
        marketing=len(marketing),
    )

    return {
        "customers": customers,
        "kyc_documents": kyc_docs,
        "loan_applications": loans,
        "payments": payments,
        "support_tickets": tickets,
        "call_transcripts": transcripts,
        "marketing_events": marketing,
    }
