"""
Writes generated rows into Iceberg tables via PySpark.
- Format version 2, merge-on-read delete mode (reproduces the positional-delete trap)
- Multiple small appends → many Parquet files (~480 for showtime)
- S3 bucket versioning ON (already set up by s3_client)
- Several intermediate snapshots so time-travel is non-trivial to defeat
"""
from __future__ import annotations

import math
import time
from typing import Any

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.spark_session import get_spark

logger = get_logger("iceberg_writer")
cfg = get_settings()

# PyArrow → Spark type map (all string for simplicity; Iceberg handles typing)
TABLE_SCHEMAS: dict[str, list[str]] = {
    "customers": [
        "customer_id STRING", "full_name STRING", "phone STRING",
        "email STRING", "dob STRING", "address_line1 STRING",
        "city STRING", "state STRING", "pincode STRING", "created_at STRING",
    ],
    "kyc_documents": [
        "kyc_id STRING", "customer_id STRING", "kyc_type STRING",
        "doc_number STRING", "verified_at STRING", "status STRING", "phone_at_kyc STRING",
    ],
    "loan_applications": [
        "loan_id STRING", "customer_id STRING", "purpose STRING",
        "principal_inr DOUBLE", "interest_rate_pct DOUBLE",
        "tenure_months INT", "status STRING", "disbursed_at STRING",
    ],
    "payments": [
        "payment_id STRING", "loan_id STRING", "customer_id STRING",
        "amount_inr DOUBLE", "paid_at STRING", "method STRING", "status STRING",
    ],
    "support_tickets": [
        "ticket_id STRING", "customer_id STRING", "category STRING",
        "description STRING", "status STRING", "created_at STRING", "resolved_at STRING",
    ],
    "call_transcripts": [
        "transcript_id STRING", "customer_id STRING", "transcript_text STRING",
        "language STRING", "call_date STRING", "duration_seconds INT",
    ],
    "marketing_events": [
        "event_id STRING", "customer_id STRING", "channel STRING",
        "campaign_id STRING", "sent_to STRING", "sent_at STRING",
        "opened BOOLEAN", "clicked BOOLEAN",
    ],
}

# Data categories & tags for the inventory endpoint
TABLE_TAGS: dict[str, list[str]] = {
    "customers":        ["identity", "contact"],
    "kyc_documents":    ["kyc", "identity"],
    "loan_applications":["financial"],
    "payments":         ["financial"],
    "support_tickets":  ["support"],
    "call_transcripts": ["support"],
    "marketing_events": ["marketing"],
}

# PII columns per table
TABLE_PII_COLS: dict[str, list[str]] = {
    "customers":         ["full_name", "phone", "email", "dob", "address_line1"],
    "kyc_documents":     ["doc_number", "phone_at_kyc"],
    "loan_applications": [],
    "payments":          [],
    "support_tickets":   ["description"],
    "call_transcripts":  ["transcript_text"],
    "marketing_events":  ["sent_to"],
}


def _rows_to_spark_df(rows: list[dict], table: str):
    spark = get_spark()
    if not rows:
        schema_str = ", ".join(TABLE_SCHEMAS[table])
        return spark.createDataFrame([], spark.sql(f"SELECT {', '.join(c.split()[0] + ' AS ' + c.split()[0] for c in TABLE_SCHEMAS[table])} FROM (SELECT {schema_str}) LIMIT 0").schema)

    # Build schema string for Spark
    schema_ddl = ", ".join(TABLE_SCHEMAS[table])
    # Create from list of Row objects
    from pyspark.sql import Row  # type: ignore[import]
    cols = [c.split()[0] for c in TABLE_SCHEMAS[table]]
    spark_rows = []
    for r in rows:
        row_vals = {}
        for c in cols:
            v = r.get(c)
            # Coerce types
            if c in ("principal_inr", "interest_rate_pct", "amount_inr"):
                row_vals[c] = float(v) if v is not None else None
            elif c in ("tenure_months", "duration_seconds"):
                row_vals[c] = int(v) if v is not None else None
            elif c in ("opened", "clicked"):
                row_vals[c] = bool(v) if v is not None else None
            else:
                row_vals[c] = str(v) if v is not None else None
        spark_rows.append(Row(**row_vals))

    df = spark.createDataFrame(spark_rows)
    return df


def create_iceberg_tables() -> None:
    """Create all Iceberg tables in the kaveri catalog if they don't exist."""
    spark = get_spark()
    spark.sql("CREATE DATABASE IF NOT EXISTS kaveri.kaveri_finserv")

    for table, schema_cols in TABLE_SCHEMAS.items():
        schema_str = ",\n  ".join(schema_cols)
        # Partition by first letter of customer_id for many small files
        partition_clause = "PARTITIONED BY (state)" if "state" in schema_str else ""
        sql = f"""
        CREATE TABLE IF NOT EXISTS kaveri.kaveri_finserv.{table} (
          {schema_str}
        )
        USING iceberg
        {partition_clause}
        TBLPROPERTIES (
          'format-version' = '2',
          'write.delete.mode' = 'merge-on-read',
          'write.update.mode' = 'merge-on-read',
          'write.merge.mode' = 'merge-on-read',
          'write.target-file-size-bytes' = '8388608'
        )
        """
        spark.sql(sql)
        logger.info("iceberg.table_created", table=table)


def write_table_in_batches(
    table: str,
    rows: list[dict],
    batch_size: int = 500,
    n_snapshots: int = 3,
) -> int:
    """
    Write rows in multiple small batches to create many Parquet files.
    Creates n_snapshots intermediate checkpoints so time-travel is meaningful.
    Returns total files written estimate.
    """
    spark = get_spark()
    total = len(rows)
    if total == 0:
        return 0

    # Split into n_snapshots groups
    group_size = math.ceil(total / n_snapshots)
    files_written = 0

    for snap_i in range(n_snapshots):
        group = rows[snap_i * group_size : (snap_i + 1) * group_size]
        if not group:
            continue

        # Further split into small batches within this snapshot
        for batch_start in range(0, len(group), batch_size):
            batch = group[batch_start : batch_start + batch_size]
            if not batch:
                continue
            df = _rows_to_spark_df(batch, table)
            df.writeTo(f"kaveri.kaveri_finserv.{table}").append()
            files_written += 1

        logger.info(
            "iceberg.snapshot_written",
            table=table,
            snapshot_index=snap_i,
            rows_in_group=len(group),
        )

    return files_written


def write_all_tables(all_rows: dict[str, list[dict]], profile: str) -> dict[str, int]:
    """Write all tables. Returns dict of table -> files written."""
    target = 480 if profile == "showtime" else 20
    batch_size = 200 if profile == "showtime" else 100
    n_snapshots = 4 if profile == "showtime" else 2

    create_iceberg_tables()
    results = {}

    for table, rows in all_rows.items():
        logger.info("iceberg.writing_table", table=table, rows=len(rows))
        n = write_table_in_batches(table, rows, batch_size=batch_size, n_snapshots=n_snapshots)
        results[table] = n
        logger.info("iceberg.table_done", table=table, batches_written=n)

    return results


def drop_all_tables() -> None:
    """Drop all Iceberg tables for reset."""
    spark = get_spark()
    for table in TABLE_SCHEMAS:
        try:
            spark.sql(f"DROP TABLE IF EXISTS kaveri.kaveri_finserv.{table}")
            logger.info("iceberg.table_dropped", table=table)
        except Exception as e:
            logger.warning("iceberg.drop_failed", table=table, error=str(e))
    try:
        spark.sql("DROP DATABASE IF EXISTS kaveri.kaveri_finserv")
    except Exception:
        pass


def get_snapshot_ids(table: str) -> list[dict]:
    """Return all snapshot IDs for a table (for time-travel audit)."""
    spark = get_spark()
    try:
        df = spark.sql(
            f"SELECT snapshot_id, committed_at, operation "
            f"FROM kaveri.kaveri_finserv.{table}.snapshots "
            f"ORDER BY committed_at"
        )
        return [row.asDict() for row in df.collect()]
    except Exception as e:
        logger.warning("iceberg.snapshots_failed", table=table, error=str(e))
        return []


def count_table_files(table: str) -> int:
    """Count data files in a table."""
    spark = get_spark()
    try:
        df = spark.sql(
            f"SELECT COUNT(*) as cnt FROM kaveri.kaveri_finserv.{table}.files"
        )
        return df.collect()[0]["cnt"]
    except Exception:
        return 0
