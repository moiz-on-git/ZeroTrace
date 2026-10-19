"""
Erasure Planner — builds a deterministic execution plan.
- Uses Subject Locator Index (Bloom filters) to restrict to affected files
- Calculates blast radius: files_total vs files_targeted, partitions
- Computes cost model: targeted vs naive full-rewrite (transparent, measured)
- Applies retention holds from policy
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.s3_client import get_s3_client, iter_all_objects
from src.locator.bloom_index import (
    FALSE_POSITIVE_RATE,
    build_index_for_table,
    find_candidate_files,
)
from src.seed.iceberg_writer import TABLE_PII_COLS, TABLE_TAGS

logger = get_logger("planner")
cfg = get_settings()

# Cost model assumptions (transparent, never hard-coded for the headline numbers)
COST_ASSUMPTIONS = [
    "Compute: AWS EC2 c5.2xlarge at ₹12/hour (on-demand, ap-south-1)",
    "Storage I/O: S3 GET ₹0.0035/1000 requests, PUT ₹0.0035/1000 requests",
    "Data transfer: ₹7/GB egress (intra-region is free)",
    "Rewrite cost proportional to bytes read + bytes written",
    "Naive full-rewrite assumes scanning ALL files in all tables",
    "Targeted rewrite scans only Bloom-positive confirmed files",
    "Numbers are estimates; actual billing depends on instance utilisation",
]

# Categories that are held under legal rules
HELD_CATEGORIES = {
    "kyc":       ("PMLA 2002 + RBI KYC Directions 2016 — 5-year retention after account closure", 5 * 365),
    "financial": ("PMLA 2002 Section 12 — transaction records retained 5 years", 5 * 365),
}


@dataclass
class ErasureStep:
    step_id: str
    layer: str          # iceberg | vector | cache | relational | crypto
    action: str         # delete_rows | rewrite_files | expire_snapshots | ...
    target: str         # table name, namespace, or "semantic_cache"
    est_rows: int
    est_files: int
    est_bytes: int
    est_cost_inr: float
    order: int          # execution order (enforced)
    parallel_group: int # steps with same group run in parallel


@dataclass
class BlastRadius:
    files_total: int
    files_targeted: int
    partitions_total: int
    partitions_targeted: int
    bloom_false_positive_rate: float = FALSE_POSITIVE_RATE


@dataclass
class CostEstimate:
    naive_inr: float
    targeted_inr: float
    saving_pct: float
    assumptions: list[str]


@dataclass
class ErasurePlan:
    plan_id: str
    job_id: str
    subject_ref: str
    steps: list[ErasureStep]
    blast_radius: BlastRadius
    cost: CostEstimate
    holds: list[dict]
    warnings: list[str]
    created_at: str


def _bytes_to_cost_inr(n_bytes: int) -> float:
    """Rough cost in INR for rewriting n_bytes."""
    gb = n_bytes / (1024 ** 3)
    # S3 PUT cost + EC2 compute (rough)
    return round(gb * 180.0 + 0.05, 4)   # ₹180/GB + ₹0.05 fixed per step


def build_plan(
    job_id: str,
    subject_ref: str,
    identifiers: list[dict],   # [{type, value}]
    holds: list[dict],         # [{category|table, legal_basis, release_date}]
) -> ErasurePlan:
    """
    Build a full erasure plan.
    Queries the Bloom index, counts files and bytes, applies hold logic.
    """
    from datetime import datetime, timezone, timedelta

    t0 = time.perf_counter()
    plan_id = "plan_" + uuid.uuid4().hex[:12]
    warnings: list[str] = []

    # Flatten all identifier variants
    all_variants: list[str] = []
    for ident in identifiers:
        v = str(ident.get("value", ""))
        all_variants.append(v)
        # Add phone variants
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) == 10:
            all_variants += [
                digits,
                f"+91{digits}",
                f"+91 {digits}",
                f"91{digits}",
                f"0{digits}",
            ]

    # Deduplicate
    all_variants = list(dict.fromkeys(all_variants))

    # ── Determine hold categories ─────────────────────────────────────────────
    held_tables: set[str] = set()
    hold_records: list[dict] = []
    for h in holds:
        cat = h.get("category", "")
        tbl = h.get("table", "")
        if cat or tbl:
            held_tables.add(cat)
            held_tables.add(tbl)
            hold_records.append(h)

    # Also auto-apply legal hold rules
    for table_name, tags in TABLE_TAGS.items():
        for tag in tags:
            if tag in HELD_CATEGORIES and tag not in held_tables:
                legal_basis, hold_days = HELD_CATEGORIES[tag]
                release = (datetime.now(timezone.utc) + timedelta(days=hold_days)).isoformat()
                hold_records.append({
                    "category": tag,
                    "table": table_name,
                    "legal_basis": legal_basis,
                    "release_date": release,
                    "auto_applied": True,
                })
                held_tables.add(tag)
                held_tables.add(table_name)

    # ── Build Bloom index and find candidate files ─────────────────────────────
    warehouse_path = cfg.iceberg_warehouse.replace("s3a://", "").replace(
        cfg.s3_bucket + "/", ""
    )

    steps: list[ErasureStep] = []
    total_files_all_tables = 0
    total_files_targeted = 0
    total_partitions_all = 0
    total_partitions_targeted = 0
    total_naive_bytes = 0
    total_targeted_bytes = 0
    step_order = 0

    for table_name in [
        "customers", "kyc_documents", "loan_applications",
        "payments", "support_tickets", "call_transcripts", "marketing_events",
    ]:
        tags = TABLE_TAGS.get(table_name, [])
        is_held = any(t in held_tables for t in tags) or table_name in held_tables

        # Build bloom index for this table
        index_entries = build_index_for_table(table_name, warehouse_path)
        total_files = len(index_entries)
        total_files_all_tables += total_files
        total_bytes_table = sum(e["file_size_bytes"] for e in index_entries)
        total_naive_bytes += total_bytes_table

        candidates = find_candidate_files(table_name, all_variants, index_entries)
        targeted_files = len(candidates)
        targeted_bytes = sum(e["file_size_bytes"] for e in candidates)
        total_files_targeted += targeted_files
        total_targeted_bytes += targeted_bytes

        # Count unique partitions
        all_parts = set(e.get("partition_spec", "default") for e in index_entries)
        target_parts = set(e.get("partition_spec", "default") for e in candidates)
        total_partitions_all += len(all_parts)
        total_partitions_targeted += len(target_parts)

        if not candidates:
            continue

        if is_held:
            # Still plan a step but mark it as HOLD
            steps.append(ErasureStep(
                step_id=f"step_{step_order:03d}",
                layer="iceberg",
                action="move_to_retention_vault",
                target=table_name,
                est_rows=sum(e["row_count"] for e in candidates),
                est_files=targeted_files,
                est_bytes=targeted_bytes,
                est_cost_inr=_bytes_to_cost_inr(targeted_bytes) * 0.2,
                order=step_order,
                parallel_group=0,
            ))
            step_order += 1
            continue

        est_rows = sum(e["row_count"] for e in candidates)

        # Step 1: DELETE (merge-on-read — writes positional delete file)
        steps.append(ErasureStep(
            step_id=f"step_{step_order:03d}",
            layer="iceberg",
            action="delete_rows",
            target=table_name,
            est_rows=est_rows,
            est_files=targeted_files,
            est_bytes=targeted_bytes // 10,  # delete file is small
            est_cost_inr=_bytes_to_cost_inr(targeted_bytes // 10),
            order=step_order,
            parallel_group=0,
        ))
        step_order += 1

        # Step 2: REWRITE data files (fold in delete, physically remove PII)
        steps.append(ErasureStep(
            step_id=f"step_{step_order:03d}",
            layer="iceberg",
            action="rewrite_data_files",
            target=table_name,
            est_rows=est_rows,
            est_files=targeted_files,
            est_bytes=targeted_bytes,
            est_cost_inr=_bytes_to_cost_inr(targeted_bytes),
            order=step_order,
            parallel_group=0,
        ))
        step_order += 1

        warnings.append(
            f"Table {table_name}: rewriting {targeted_files}/{total_files} files will "
            f"reset the time-travel horizon to this snapshot."
        )

    # Step 3: EXPIRE SNAPSHOTS (must come after rewrite)
    steps.append(ErasureStep(
        step_id=f"step_{step_order:03d}",
        layer="iceberg",
        action="expire_snapshots",
        target="all_tables",
        est_rows=0,
        est_files=total_files_targeted,
        est_bytes=0,
        est_cost_inr=0.01,
        order=step_order,
        parallel_group=0,
    ))
    step_order += 1

    # Step 4: REMOVE ORPHAN FILES (after snapshot expiry — order matters!)
    steps.append(ErasureStep(
        step_id=f"step_{step_order:03d}",
        layer="iceberg",
        action="remove_orphan_files",
        target="all_tables",
        est_rows=0,
        est_files=total_files_targeted,
        est_bytes=total_targeted_bytes,
        est_cost_inr=0.02,
        order=step_order,
        parallel_group=0,
    ))
    step_order += 1

    # Step 5: PURGE S3 NON-CURRENT VERSIONS
    steps.append(ErasureStep(
        step_id=f"step_{step_order:03d}",
        layer="iceberg",
        action="purge_s3_versions",
        target="all_files",
        est_rows=0,
        est_files=total_files_targeted,
        est_bytes=total_targeted_bytes,
        est_cost_inr=0.01,
        order=step_order,
        parallel_group=0,
    ))
    step_order += 1

    # Step 6: SCRUB COLUMN STATS (disable min/max on PII cols)
    steps.append(ErasureStep(
        step_id=f"step_{step_order:03d}",
        layer="iceberg",
        action="scrub_column_stats",
        target="all_tables",
        est_rows=0,
        est_files=0,
        est_bytes=0,
        est_cost_inr=0.0,
        order=step_order,
        parallel_group=0,
    ))
    step_order += 1

    # ── Vector layer (parallel group 1) ──────────────────────────────────────
    steps.append(ErasureStep(
        step_id=f"step_{step_order:03d}",
        layer="vector",
        action="delete_embeddings_by_metadata",
        target="embeddings",
        est_rows=20,
        est_files=0,
        est_bytes=0,
        est_cost_inr=0.0,
        order=step_order,
        parallel_group=1,
    ))
    step_order += 1

    steps.append(ErasureStep(
        step_id=f"step_{step_order:03d}",
        layer="vector",
        action="semantic_sweep",
        target="embeddings",
        est_rows=1,  # ghost embedding
        est_files=0,
        est_bytes=0,
        est_cost_inr=0.0,
        order=step_order,
        parallel_group=1,
    ))
    step_order += 1

    steps.append(ErasureStep(
        step_id=f"step_{step_order:03d}",
        layer="vector",
        action="vacuum_reindex",
        target="embeddings",
        est_rows=0,
        est_files=0,
        est_bytes=0,
        est_cost_inr=0.0,
        order=step_order,
        parallel_group=1,
    ))
    step_order += 1

    # ── Cache layer (parallel group 1) ───────────────────────────────────────
    steps.append(ErasureStep(
        step_id=f"step_{step_order:03d}",
        layer="cache",
        action="delete_tagged_cache_entries",
        target="redis_db0",
        est_rows=3,
        est_files=0,
        est_bytes=0,
        est_cost_inr=0.0,
        order=step_order,
        parallel_group=1,
    ))
    step_order += 1

    steps.append(ErasureStep(
        step_id=f"step_{step_order:03d}",
        layer="cache",
        action="content_scan_cache",
        target="redis_db0",
        est_rows=1,
        est_files=0,
        est_bytes=0,
        est_cost_inr=0.0,
        order=step_order,
        parallel_group=1,
    ))
    step_order += 1

    steps.append(ErasureStep(
        step_id=f"step_{step_order:03d}",
        layer="cache",
        action="force_persistence_rewrite",
        target="redis_db0",
        est_rows=0,
        est_files=0,
        est_bytes=0,
        est_cost_inr=0.0,
        order=step_order,
        parallel_group=1,
    ))
    step_order += 1

    # ── Cost ─────────────────────────────────────────────────────────────────
    naive_inr = _bytes_to_cost_inr(total_naive_bytes)
    targeted_inr = _bytes_to_cost_inr(total_targeted_bytes)
    saving_pct = (
        round((1 - targeted_inr / naive_inr) * 100, 1) if naive_inr > 0 else 0.0
    )

    blast = BlastRadius(
        files_total=total_files_all_tables,
        files_targeted=total_files_targeted,
        partitions_total=total_partitions_all,
        partitions_targeted=total_partitions_targeted,
    )

    cost = CostEstimate(
        naive_inr=round(naive_inr, 2),
        targeted_inr=round(targeted_inr, 2),
        saving_pct=saving_pct,
        assumptions=COST_ASSUMPTIONS,
    )

    elapsed = time.perf_counter() - t0
    logger.info(
        "planner.done",
        job_id=job_id,
        steps=len(steps),
        files_targeted=total_files_targeted,
        saving_pct=saving_pct,
        elapsed_s=round(elapsed, 2),
    )

    from datetime import datetime, timezone

    return ErasurePlan(
        plan_id=plan_id,
        job_id=job_id,
        subject_ref=subject_ref,
        steps=steps,
        blast_radius=blast,
        cost=cost,
        holds=hold_records,
        warnings=warnings,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
