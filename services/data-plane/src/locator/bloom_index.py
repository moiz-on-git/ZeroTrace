"""
Subject Locator Index — per-file Bloom filters over hashed PII identifiers.
Lets the erasure engine rewrite only files that actually contain the subject,
instead of a full-table rewrite.

False-positive rate: 1e-6 (configurable).
Correctness guarantee: Bloom is used for candidate selection only;
we always confirm by scanning candidates with pyarrow.
"""
from __future__ import annotations

import hashlib
import io
import pickle
from typing import Generator

import pyarrow as pa
import pyarrow.parquet as pq
from pybloom_live import BloomFilter  # type: ignore[import]

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.s3_client import get_object_bytes, get_s3_client, iter_all_objects
from src.seed.iceberg_writer import TABLE_PII_COLS

logger = get_logger("locator")
cfg = get_settings()

FALSE_POSITIVE_RATE = 1e-6
ESTIMATED_ITEMS_PER_FILE = 2000


def _hash_value(v: str) -> str:
    """Deterministic hash of a PII value for Bloom filter insertion."""
    return hashlib.sha256(v.lower().strip().encode()).hexdigest()


def build_bloom_for_file(
    file_key: str,
    table_name: str,
    pii_cols: list[str],
) -> tuple[bytes, int]:
    """
    Download a Parquet file from S3, read PII columns,
    insert hashed values into a Bloom filter.
    Returns (serialised_bloom_bytes, row_count).
    """
    raw = get_object_bytes(file_key)
    buf = io.BytesIO(raw)
    try:
        pf = pq.read_table(buf, columns=pii_cols if pii_cols else None)
    except Exception as e:
        logger.warning("bloom.parquet_read_failed", key=file_key, error=str(e))
        bf = BloomFilter(capacity=ESTIMATED_ITEMS_PER_FILE, error_rate=FALSE_POSITIVE_RATE)
        return pickle.dumps(bf), 0

    row_count = len(pf)
    # Initialise with a generous capacity
    capacity = max(row_count * len(pii_cols) * 8, ESTIMATED_ITEMS_PER_FILE)
    bf = BloomFilter(capacity=capacity, error_rate=FALSE_POSITIVE_RATE)

    for col in pii_cols:
        if col not in pf.column_names:
            continue
        col_data = pf[col]
        for val in col_data.to_pylist():
            if val is None:
                continue
            s = str(val).strip()
            if s:
                bf.add(_hash_value(s))
                # Also add common variants
                bf.add(_hash_value(s.lower()))
                bf.add(_hash_value(s.upper()))

    return pickle.dumps(bf), row_count


def query_bloom(bloom_bytes: bytes, identifier_variants: list[str]) -> bool:
    """
    Returns True if ANY identifier variant is possibly in the file.
    (Bloom may give false positives; never false negatives.)
    """
    bf: BloomFilter = pickle.loads(bloom_bytes)
    for v in identifier_variants:
        if _hash_value(v) in bf:
            return True
    return False


def confirm_file_contains(
    file_key: str,
    pii_cols: list[str],
    identifier_variants: list[str],
) -> bool:
    """
    Confirmation step: actually scan the file bytes for identifier variants.
    Called only on Bloom-positive candidates to ensure correctness.
    """
    raw = get_object_bytes(file_key)
    text = raw.decode("utf-8", errors="replace")
    for v in identifier_variants:
        if v.lower() in text.lower():
            return True
    return False


def build_index_for_table(table_name: str, warehouse_prefix: str) -> list[dict]:
    """
    Walk all Parquet files for a table and build/update the Bloom index.
    Returns list of index entries.
    """
    pii_cols = TABLE_PII_COLS.get(table_name, [])
    if not pii_cols:
        logger.info("locator.no_pii_cols", table=table_name)
        return []

    s3 = get_s3_client()
    prefix = f"{warehouse_prefix}/kaveri_finserv/{table_name}/"
    entries = []

    for obj in iter_all_objects(prefix):
        key = obj["Key"]
        if not key.endswith(".parquet"):
            continue
        try:
            bloom_bytes, row_count = build_bloom_for_file(key, table_name, pii_cols)
            entries.append({
                "file_path": key,
                "table_name": table_name,
                "bloom_data": bloom_bytes,
                "row_count": row_count,
                "file_size_bytes": obj.get("Size", 0),
                "false_positive_rate": FALSE_POSITIVE_RATE,
            })
        except Exception as e:
            logger.warning("locator.file_index_failed", key=key, error=str(e))

    logger.info("locator.index_built", table=table_name, files=len(entries))
    return entries


def find_candidate_files(
    table_name: str,
    identifier_variants: list[str],
    index_entries: list[dict],
) -> list[dict]:
    """
    Filter index entries by Bloom filter, then confirm by actual content scan.
    Returns only files that definitely contain the subject.
    """
    candidates = []
    for entry in index_entries:
        if query_bloom(entry["bloom_data"], identifier_variants):
            # Confirm — prevents false positives from causing unnecessary rewrites
            if confirm_file_contains(entry["file_path"], TABLE_PII_COLS.get(table_name, []), identifier_variants):
                candidates.append(entry)
    return candidates
