"""
ZeroTrace SQLAlchemy 2 Declarative Database Models (zt_app).
Stores requests, job state machines, append-only events, plans, approvals, receipts, and holds.
"""

from __future__ import annotations
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class RequestRecord(Base):
    __tablename__ = "requests"

    id = Column(String(32), primary_key=True)  # req_...
    job_id = Column(String(32), nullable=True, index=True)
    channel = Column(String(16), nullable=False)  # voice, text, webhook
    language = Column(String(16), nullable=True)  # kn-IN, hi-IN, etc.
    status = Column(String(32), nullable=False, default="RECEIVED")
    subject_ref = Column(String(32), nullable=False, index=True)  # sub_...
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    raw_input_meta = Column(Text, nullable=True)  # JSON metadata (NEVER raw audio or plaintext PII)


class JobRecord(Base):
    __tablename__ = "jobs"

    id = Column(String(32), primary_key=True)  # job_...
    request_id = Column(String(32), ForeignKey("requests.id"), nullable=False)
    status = Column(String(32), nullable=False, default="RECEIVED", index=True)
    # State machine: RECEIVED, PARSING, DISCOVERING, PLANNED, AWAITING_APPROVAL,
    # EXECUTING, AUDITING, REMEDIATING, PROVING, ANCHORING, COMPLETED, COMPLETED_WITH_HOLDS, FAILED, REJECTED
    subject_ref = Column(String(32), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    metrics_json = Column(Text, nullable=True)  # JSON metrics summary
    stage_timeline_json = Column(Text, nullable=True)  # JSON stage durations


class JobEventRecord(Base):
    __tablename__ = "job_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(32), ForeignKey("jobs.id"), nullable=False, index=True)
    seq = Column(Integer, nullable=False, index=True)
    ts = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    stage = Column(String(32), nullable=False)
    kind = Column(String(16), nullable=False)  # started, progress, metric, finding, completed, failed, log
    layer = Column(String(16), nullable=False)  # system, intake, discovery, policy, crypto, iceberg, vector, cache, relational, audit, proof, chain
    message = Column(Text, nullable=False)  # Human-readable progress (NO PII)
    data_json = Column(Text, nullable=True)  # JSON operational data


class PlanRecord(Base):
    __tablename__ = "plans"

    id = Column(String(32), primary_key=True)  # plan_...
    job_id = Column(String(32), ForeignKey("jobs.id"), nullable=False, index=True)
    blast_radius_json = Column(Text, nullable=False)
    cost_json = Column(Text, nullable=False)
    steps_json = Column(Text, nullable=False)
    warnings_json = Column(Text, nullable=True)
    holds_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ApprovalRecord(Base):
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(32), ForeignKey("jobs.id"), nullable=False, index=True)
    approved = Column(Boolean, nullable=False)
    approver = Column(String(64), nullable=False)
    approver_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ReceiptRecord(Base):
    __tablename__ = "receipts"

    id = Column(String(32), primary_key=True)  # rcpt_...
    job_id = Column(String(32), ForeignKey("jobs.id"), nullable=False, index=True)
    issued_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    policy_version = Column(String(32), nullable=False)
    subject_commitment = Column(String(64), nullable=False, index=True)
    pre_root = Column(String(64), nullable=False)
    post_root = Column(String(64), nullable=False)
    diff_root = Column(String(64), nullable=False)
    receipt_json = Column(Text, nullable=False)
    signer_public_key = Column(String(64), nullable=False)
    signature = Column(String(128), nullable=False)
    anchor_status = Column(String(16), default="PENDING")
    anchor_tx_hash = Column(String(66), nullable=True)


class RetentionHoldRecord(Base):
    __tablename__ = "retention_holds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(32), ForeignKey("jobs.id"), nullable=False, index=True)
    category = Column(String(64), nullable=False)
    legal_basis = Column(Text, nullable=False)
    release_date = Column(DateTime(timezone=True), nullable=False)
    count = Column(Integer, nullable=False, default=1)
    status = Column(String(16), default="ACTIVE")  # ACTIVE, RELEASED


class AgentTraceRecord(Base):
    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(32), ForeignKey("jobs.id"), nullable=False, index=True)
    step_num = Column(Integer, nullable=False)
    tool_name = Column(String(64), nullable=False)
    input_json = Column(Text, nullable=True)
    output_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class DemoStateRecord(Base):
    __tablename__ = "demo_state"

    key = Column(String(64), primary_key=True)
    value_json = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
