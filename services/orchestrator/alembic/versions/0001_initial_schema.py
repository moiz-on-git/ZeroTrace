"""Initial schema migration for ZeroTrace tables

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. requests table
    op.create_table(
        'requests',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('job_id', sa.String(length=32), nullable=True),
        sa.Column('channel', sa.String(length=16), nullable=False),
        sa.Column('language', sa.String(length=16), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('subject_ref', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw_input_meta', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_requests_job_id'), 'requests', ['job_id'], unique=False)
    op.create_index(op.f('ix_requests_subject_ref'), 'requests', ['subject_ref'], unique=False)

    # 2. jobs table
    op.create_table(
        'jobs',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('request_id', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('subject_ref', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metrics_json', sa.Text(), nullable=True),
        sa.Column('stage_timeline_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)
    op.create_index(op.f('ix_jobs_subject_ref'), 'jobs', ['subject_ref'], unique=False)

    # 3. job_events table
    op.create_table(
        'job_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_id', sa.String(length=32), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('stage', sa.String(length=32), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('layer', sa.String(length=16), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_job_events_job_id'), 'job_events', ['job_id'], unique=False)
    op.create_index(op.f('ix_job_events_seq'), 'job_events', ['seq'], unique=False)

    # 4. plans table
    op.create_table(
        'plans',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('job_id', sa.String(length=32), nullable=False),
        sa.Column('blast_radius_json', sa.Text(), nullable=False),
        sa.Column('cost_json', sa.Text(), nullable=False),
        sa.Column('steps_json', sa.Text(), nullable=False),
        sa.Column('warnings_json', sa.Text(), nullable=True),
        sa.Column('holds_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plans_job_id'), 'plans', ['job_id'], unique=False)

    # 5. receipts table
    op.create_table(
        'receipts',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('job_id', sa.String(length=32), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('policy_version', sa.String(length=32), nullable=False),
        sa.Column('subject_commitment', sa.String(length=64), nullable=False),
        sa.Column('pre_root', sa.String(length=64), nullable=False),
        sa.Column('post_root', sa.String(length=64), nullable=False),
        sa.Column('diff_root', sa.String(length=64), nullable=False),
        sa.Column('receipt_json', sa.Text(), nullable=False),
        sa.Column('signer_public_key', sa.String(length=64), nullable=False),
        sa.Column('signature', sa.String(length=128), nullable=False),
        sa.Column('anchor_status', sa.String(length=16), nullable=True),
        sa.Column('anchor_tx_hash', sa.String(length=66), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_receipts_job_id'), 'receipts', ['job_id'], unique=False)
    op.create_index(op.f('ix_receipts_subject_commitment'), 'receipts', ['subject_commitment'], unique=False)


def downgrade() -> None:
    op.drop_table('receipts')
    op.drop_table('plans')
    op.drop_table('job_events')
    op.drop_table('jobs')
    op.drop_table('requests')
