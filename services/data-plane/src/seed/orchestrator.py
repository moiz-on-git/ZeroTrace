"""
Top-level seed and reset orchestrator.
Coordinates: Iceberg tables, pgvector, Redis cache.
Provides timed reset (<20s target using DROP+recreate strategy).
"""
from __future__ import annotations

import time
from typing import Literal

from src.core.config import get_settings
from src.core.logging import get_logger
from src.seed.cache_seeder import clear_cache, seed_cache
from src.seed.generator import generate_all_rows
from src.seed.iceberg_writer import drop_all_tables, write_all_tables
from src.seed.vector_seeder import clear_vectors, seed_vectors

logger = get_logger("seed.orchestrator")
cfg = get_settings()


def seed(profile: Literal["small", "showtime"] = "small") -> dict:
    """
    Full seed: generate rows, write Iceberg tables, embed vectors, populate cache.
    Returns a summary dict.
    """
    t0 = time.perf_counter()
    seed_val = cfg.seed_random_seed

    logger.info("seed.start", profile=profile, seed=seed_val)

    # 1. Generate rows
    all_rows = generate_all_rows(profile, seed_val)

    # 2. Write Iceberg (PySpark)
    file_counts = write_all_tables(all_rows, profile)

    # 3. Embed vectors
    vector_result = seed_vectors(
        tickets=all_rows["support_tickets"],
        transcripts=all_rows["call_transcripts"],
    )

    # 4. Seed Redis cache
    cache_result = seed_cache()

    elapsed = time.perf_counter() - t0

    summary = {
        "profile": profile,
        "elapsed_s": round(elapsed, 2),
        "tables": {t: len(r) for t, r in all_rows.items()},
        "iceberg_batches": file_counts,
        "vectors": vector_result,
        "cache": cache_result,
    }
    logger.info("seed.done", **summary)
    return summary


def reset(profile: Literal["small", "showtime"] = "showtime") -> dict:
    """
    Full reset: drop everything and re-seed.
    Target: ≤ 20s for small profile, measured for showtime.
    """
    t0 = time.perf_counter()
    logger.info("reset.start", profile=profile)

    # 1. Drop Iceberg tables
    drop_all_tables()

    # 2. Clear vectors
    clear_vectors()

    # 3. Clear cache
    clear_cache()

    # 4. Re-seed
    result = seed(profile)

    elapsed = time.perf_counter() - t0
    result["reset_total_s"] = round(elapsed, 2)
    logger.info("reset.done", elapsed_s=elapsed)
    return result
