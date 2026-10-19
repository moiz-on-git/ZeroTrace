"""
SQLAlchemy ORM models for zt_app and zt_rag databases.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import BaseApp, BaseRag


# ── zt_app models ─────────────────────────────────────────────────────────────

class JobStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PLANNING = "PLANNING"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    AUDITING = "AUDITING"
    REMEDIATING = "REMEDIATING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_HOLDS = "COMPLETED_WITH_HOLDS"
    FAILED = "FAILED"


class ErasureJob(BaseApp):
    __tablename__ = "erasure_jobs"

    job_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    subject_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.RECEIVED, nullable=False
    )
    plan_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    mode: Mapped[str] = mapped_column(String(32), default="both", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Step resume checkpoint
    checkpoint: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Idempotency key
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)

    events: Mapped[list["JobEvent"]] = relationship(back_populates="job", lazy="select")
    holds: Mapped[list["RetentionHold"]] = relationship(back_populates="job", lazy="select")


class JobEvent(BaseApp):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("erasure_jobs.job_id", ondelete="CASCADE"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    layer: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    job: Mapped["ErasureJob"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_job_events_job_seq", "job_id", "seq"),
    )


class RetentionHold(BaseApp):
    __tablename__ = "retention_holds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("erasure_jobs.job_id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    table_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    legal_basis: Mapped[str] = mapped_column(Text, nullable=False)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vault_table: Mapped[str] = mapped_column(String(128), nullable=False, default="retention_vault")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["ErasureJob"] = relationship(back_populates="holds")


class BloomFilterIndex(BaseApp):
    """Subject Locator Index — one row per Iceberg data file."""
    __tablename__ = "bloom_filter_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    partition_spec: Mapped[str | None] = mapped_column(Text, nullable=True)
    bloom_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    false_positive_rate: Mapped[float] = mapped_column(Float, default=1e-6, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DataKeyStore(BaseApp):
    """Per-subject envelope-encrypted data keys for crypto-shred (P1)."""
    __tablename__ = "data_key_store"

    subject_ref: Mapped[str] = mapped_column(String(64), primary_key=True)
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(32), default="AES-256-GCM", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_destroyed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class StateManifestItem(BaseApp):
    """Pre/post manifest items for Merkle proof."""
    __tablename__ = "state_manifest_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(8), nullable=False)   # "pre" | "post"
    layer: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[str] = mapped_column(Text, nullable=False)    # no PII
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    in_scope: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    held: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_manifest_job_label", "job_id", "label"),
    )


class CollateralBaseline(BaseApp):
    """Pre-erasure checksums of non-subject data for collateral integrity."""
    __tablename__ = "collateral_baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── zt_rag models ─────────────────────────────────────────────────────────────

class EmbeddingRecord(BaseRag):
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    source_table: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_pk: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subject_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(384), nullable=False)
    is_ghost: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_embed_subject_ref", "subject_ref"),
    )
