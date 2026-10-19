"""Initial migration — create all tables

Revision ID: 0001
Revises: 
Create Date: 2026-10-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── erasure_jobs ────────────────────────────────────────────────────────
    op.create_table(
        "erasure_jobs",
        sa.Column("job_id", sa.String(26), primary_key=True),
        sa.Column("subject_ref", sa.String(64), nullable=False, index=True),
        sa.Column("status", sa.Enum(
            "RECEIVED", "PLANNING", "PLANNED", "EXECUTING", "AUDITING",
            "REMEDIATING", "COMPLETED", "COMPLETED_WITH_HOLDS", "FAILED",
            name="job_status",
        ), nullable=False, server_default="RECEIVED"),
        sa.Column("plan_id", sa.String(26), nullable=True),
        sa.Column("mode", sa.String(32), nullable=False, server_default="both"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("checkpoint", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True, unique=True),
    )

    # ── job_events ──────────────────────────────────────────────────────────
    op.create_table(
        "job_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(26), sa.ForeignKey("erasure_jobs.job_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("layer", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_job_events_job_seq", "job_events", ["job_id", "seq"])

    # ── retention_holds ──────────────────────────────────────────────────────
    op.create_table(
        "retention_holds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(26), sa.ForeignKey("erasure_jobs.job_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subject_ref", sa.String(64), nullable=False, index=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("table_name", sa.String(128), nullable=True),
        sa.Column("legal_basis", sa.Text(), nullable=False),
        sa.Column("release_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vault_table", sa.String(128), nullable=False, server_default="retention_vault"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── bloom_filter_index ──────────────────────────────────────────────────
    op.create_table(
        "bloom_filter_index",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("table_name", sa.String(128), nullable=False, index=True),
        sa.Column("file_path", sa.Text(), nullable=False, unique=True),
        sa.Column("partition_spec", sa.Text(), nullable=True),
        sa.Column("bloom_data", sa.LargeBinary(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("false_positive_rate", sa.Float(), nullable=False, server_default="0.000001"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── data_key_store (crypto shred) ───────────────────────────────────────
    op.create_table(
        "data_key_store",
        sa.Column("subject_ref", sa.String(64), primary_key=True),
        sa.Column("wrapped_key", sa.LargeBinary(), nullable=False),
        sa.Column("algorithm", sa.String(32), nullable=False, server_default="AES-256-GCM"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("destroyed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_destroyed", sa.Boolean(), nullable=False, server_default="false"),
    )

    # ── state_manifest_items ─────────────────────────────────────────────────
    op.create_table(
        "state_manifest_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(26), nullable=False, index=True),
        sa.Column("label", sa.String(8), nullable=False),
        sa.Column("layer", sa.String(32), nullable=False),
        sa.Column("object_id", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("in_scope", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("held", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_manifest_job_label", "state_manifest_items", ["job_id", "label"])

    # ── collateral_baselines ─────────────────────────────────────────────────
    op.create_table(
        "collateral_baselines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(26), nullable=False, index=True),
        sa.Column("table_name", sa.String(128), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("collateral_baselines")
    op.drop_table("state_manifest_items")
    op.drop_table("data_key_store")
    op.drop_table("bloom_filter_index")
    op.drop_table("retention_holds")
    op.drop_table("job_events")
    op.drop_table("erasure_jobs")
