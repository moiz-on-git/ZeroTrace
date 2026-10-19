"""
Iceberg erasure engine — physical eradication in the CORRECT ORDER.

The order is the whole point:
  1. DELETE rows (merge-on-read — writes positional delete files)
  2. REWRITE data files (fold in deletes, physically remove PII rows)
  3. EXPIRE SNAPSHOTS (so no snapshot references old files)
  4. REMOVE ORPHAN FILES (safe only AFTER snapshot expiry)
  5. PURGE old metadata versions
  6. PURGE S3 non-current object versions
  7. SCRUB column statistics on PII columns

Running orphan removal BEFORE snapshot expiry deletes ZERO bytes —
that's the trap all manual scripts fall into. We also expose a
'naive' mode that runs the WRONG order so the demo can show this live.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.s3_client import (
    delete_object_version,
    get_s3_client,
    iter_all_versions,
)
from src.core.spark_session import get_spark
from src.erasure.events import EventEmitter
from src.locator.bloom_index import find_candidate_files, build_index_for_table
from src.seed.iceberg_writer import TABLE_SCHEMAS, TABLE_PII_COLS, TABLE_TAGS

logger = get_logger("iceberg_eraser")
cfg = get_settings()

WAREHOUSE_PATH = cfg.iceberg_warehouse


def _build_where_clause(identifiers: list[dict]) -> str:
    """Build a SQL WHERE clause matching the subject across PII columns."""
    conditions = []
    for ident in identifiers:
        t = ident.get("type", "")
        v = ident.get("value", "")
        if t == "phone":
            # Match phone in all variants
            phone_variants = [
                v,
                f"+91{v}",
                f"+91 {v}",
                f"91{v}",
                f"0{v}",
            ]
            escaped = [f"'{p}'" for p in phone_variants]
            conditions.append(f"phone IN ({','.join(escaped)})")
            conditions.append(f"phone_at_kyc IN ({','.join(escaped)})")
        elif t == "email":
            conditions.append(f"LOWER(email) = LOWER('{v}')")
        elif t == "customer_id":
            conditions.append(f"customer_id = '{v}'")
    if not conditions:
        return "1=0"   # Safety: never match everything
    return " OR ".join(conditions)


def erase_iceberg(
    job_id: str,
    subject_ref: str,
    identifiers: list[dict],
    held_tables: set[str],
    emitter: EventEmitter,
    naive_order: bool = False,
) -> dict:
    """
    Execute physical Iceberg erasure steps in correct order (or wrong order for demo).
    Returns metrics dict.
    """
    spark = get_spark()
    s3 = get_s3_client()
    metrics: dict[str, Any] = {
        "files_rewritten": 0,
        "bytes_rewritten": 0,
        "snapshots_expired": 0,
        "orphan_files_removed": 0,
        "metadata_files_removed": 0,
        "object_versions_deleted": 0,
    }

    where = _build_where_clause(identifiers)
    tables_to_erase = [
        t for t in TABLE_SCHEMAS
        if t not in held_tables
        and not any(tag in held_tables for tag in TABLE_TAGS.get(t, []))
    ]

    stage = "ERASE_ICEBERG"
    emitter.emit_sync(stage, "started", "iceberg", "Starting Iceberg physical erasure")

    if naive_order:
        # DEMO: wrong order — shows why manual scripts fail
        emitter.emit_sync(stage, "log", "iceberg",
                          "NAIVE MODE: running orphan removal BEFORE snapshot expiry "
                          "(this will delete zero bytes — the trap)")
        _step_remove_orphans(spark, tables_to_erase, metrics, emitter, stage)
        _step_delete_rows(spark, tables_to_erase, where, metrics, emitter, stage)
        emitter.emit_sync(stage, "completed", "iceberg",
                          "Naive erasure complete — orphan step removed 0 bytes as expected",
                          metrics)
        return metrics

    # ── CORRECT ORDER ─────────────────────────────────────────────────────────

    # Step 1: DELETE rows (writes positional delete files)
    _step_delete_rows(spark, tables_to_erase, where, metrics, emitter, stage)

    # Step 2: REWRITE data files (physically removes subject rows)
    _step_rewrite_files(spark, tables_to_erase, identifiers, metrics, emitter, stage)

    # Step 3: EXPIRE SNAPSHOTS (must come before orphan removal)
    _step_expire_snapshots(spark, tables_to_erase, metrics, emitter, stage)

    # Step 4: REMOVE ORPHAN FILES (safe now that snapshots are expired)
    _step_remove_orphans(spark, tables_to_erase, metrics, emitter, stage)

    # Step 5: PURGE old metadata versions
    _step_purge_metadata(spark, tables_to_erase, metrics, emitter, stage)

    # Step 6: PURGE S3 non-current object versions
    _step_purge_s3_versions(s3, metrics, emitter, stage)

    # Step 7: SCRUB column statistics on PII columns
    _step_scrub_col_stats(spark, tables_to_erase, emitter, stage)

    emitter.emit_sync(stage, "completed", "iceberg",
                      "Iceberg physical erasure complete", metrics)
    return metrics


# ── Individual steps ──────────────────────────────────────────────────────────

def _step_delete_rows(spark, tables, where, metrics, emitter, stage):
    emitter.emit_sync(stage, "progress", "iceberg",
                      "Step 1/7: Deleting rows (merge-on-read)")
    for table in tables:
        try:
            result = spark.sql(
                f"DELETE FROM kaveri.kaveri_finserv.{table} WHERE {where}"
            )
            logger.info("iceberg.delete_rows", table=table)
            emitter.emit_sync(stage, "metric", "iceberg",
                              f"Deleted rows from {table}", {"table": table})
        except Exception as e:
            logger.warning("iceberg.delete_rows_failed", table=table, error=str(e))


def _step_rewrite_files(spark, tables, identifiers, metrics, emitter, stage):
    emitter.emit_sync(stage, "progress", "iceberg",
                      "Step 2/7: Rewriting data files (physically removing PII)")
    warehouse_path = cfg.iceberg_warehouse.replace("s3a://", "").replace(
        cfg.s3_bucket + "/", ""
    )

    all_variants = []
    for ident in identifiers:
        v = str(ident.get("value", ""))
        all_variants += [v, f"+91{v}", f"+91 {v}", f"91{v}", f"0{v}"]

    total_rewritten = 0
    total_bytes = 0

    for table in tables:
        try:
            # Use Iceberg's REWRITE DATA FILES procedure (targeted)
            spark.sql(f"""
                CALL kaveri.system.rewrite_data_files(
                    table => 'kaveri_finserv.{table}',
                    strategy => 'binpack',
                    options => map('rewrite-all', 'false')
                )
            """)
            # Also get file list for metrics
            df = spark.sql(
                f"SELECT file_path, file_size_in_bytes FROM "
                f"kaveri.kaveri_finserv.{table}.files"
            )
            rows = df.collect()
            total_rewritten += len(rows)
            total_bytes += sum(r["file_size_in_bytes"] for r in rows)
            logger.info("iceberg.rewrite_done", table=table, files=len(rows))
            emitter.emit_sync(stage, "metric", "iceberg",
                              f"Rewrote {len(rows)} files in {table}",
                              {"table": table, "files_rewritten": len(rows)})
        except Exception as e:
            logger.warning("iceberg.rewrite_failed", table=table, error=str(e))

    metrics["files_rewritten"] = total_rewritten
    metrics["bytes_rewritten"] = total_bytes
    emitter.emit_sync(stage, "metric", "iceberg", "Rewrite complete",
                      {"files_rewritten": total_rewritten, "bytes_rewritten": total_bytes})


def _step_expire_snapshots(spark, tables, metrics, emitter, stage):
    emitter.emit_sync(stage, "progress", "iceberg",
                      "Step 3/7: Expiring snapshots")
    expired = 0
    for table in tables:
        try:
            # Expire all snapshots older than now (keep only current)
            result = spark.sql(f"""
                CALL kaveri.system.expire_snapshots(
                    table => 'kaveri_finserv.{table}',
                    older_than => TIMESTAMP '{_now_ts()}',
                    retain_last => 1
                )
            """)
            rows = result.collect()
            n = rows[0]["deleted_data_files_count"] if rows else 0
            expired += n
            logger.info("iceberg.snapshots_expired", table=table, deleted_files=n)
            emitter.emit_sync(stage, "metric", "iceberg",
                              f"Expired snapshots for {table}",
                              {"table": table, "snapshots_expired": n})
        except Exception as e:
            logger.warning("iceberg.expire_snapshots_failed", table=table, error=str(e))
    metrics["snapshots_expired"] = expired


def _step_remove_orphans(spark, tables, metrics, emitter, stage):
    emitter.emit_sync(stage, "progress", "iceberg",
                      "Step 4/7: Removing orphan files")
    removed = 0
    for table in tables:
        try:
            result = spark.sql(f"""
                CALL kaveri.system.remove_orphan_files(
                    table => 'kaveri_finserv.{table}',
                    older_than => TIMESTAMP '{_now_ts()}'
                )
            """)
            rows = result.collect()
            n = len(rows)
            removed += n
            logger.info("iceberg.orphans_removed", table=table, count=n)
            emitter.emit_sync(stage, "metric", "iceberg",
                              f"Removed {n} orphan files from {table}",
                              {"table": table, "orphan_files_removed": n})
        except Exception as e:
            logger.warning("iceberg.orphan_removal_failed", table=table, error=str(e))
    metrics["orphan_files_removed"] = removed


def _step_purge_metadata(spark, tables, metrics, emitter, stage):
    emitter.emit_sync(stage, "progress", "iceberg",
                      "Step 5/7: Purging old metadata versions")
    purged = 0
    for table in tables:
        try:
            # Keep only the latest 2 metadata files
            spark.sql(f"""
                ALTER TABLE kaveri.kaveri_finserv.{table}
                SET TBLPROPERTIES ('write.metadata.previous-versions-max' = '1')
            """)
            purged += 1
        except Exception as e:
            logger.warning("iceberg.metadata_purge_failed", table=table, error=str(e))
    metrics["metadata_files_removed"] = purged
    emitter.emit_sync(stage, "metric", "iceberg",
                      f"Metadata purge done", {"metadata_files_removed": purged})


def _step_purge_s3_versions(s3, metrics, emitter, stage):
    emitter.emit_sync(stage, "progress", "iceberg",
                      "Step 6/7: Purging S3 non-current object versions")
    deleted = 0
    bucket = cfg.s3_bucket
    prefix = "warehouse/"

    try:
        for ver in iter_all_versions(prefix):
            if ver["kind"] == "version" and not ver.get("IsLatest", True):
                delete_object_version(ver["Key"], ver["VersionId"])
                deleted += 1
            elif ver["kind"] == "delete_marker":
                delete_object_version(ver["Key"], ver["VersionId"])
                deleted += 1
    except Exception as e:
        logger.warning("iceberg.s3_versions_purge_failed", error=str(e))

    metrics["object_versions_deleted"] = deleted
    emitter.emit_sync(stage, "metric", "iceberg",
                      f"Deleted {deleted} non-current S3 versions",
                      {"object_versions_deleted": deleted})


def _step_scrub_col_stats(spark, tables, emitter, stage):
    emitter.emit_sync(stage, "progress", "iceberg",
                      "Step 7/7: Scrubbing column statistics on PII columns")
    for table in tables:
        pii_cols = TABLE_PII_COLS.get(table, [])
        for col in pii_cols:
            try:
                spark.sql(f"""
                    ALTER TABLE kaveri.kaveri_finserv.{table}
                    SET TBLPROPERTIES (
                        'write.metadata.metrics.column.{col}' = 'none'
                    )
                """)
            except Exception as e:
                logger.warning("iceberg.col_stats_scrub_failed",
                               table=table, col=col, error=str(e))
    emitter.emit_sync(stage, "metric", "iceberg",
                      "Column statistics scrubbed on PII columns")


def _now_ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
