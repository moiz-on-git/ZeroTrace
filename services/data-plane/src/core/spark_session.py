"""
Long-lived singleton Spark session with Iceberg support.
Started once at service boot and kept warm — never created per-request.
"""
from __future__ import annotations

import os
import threading
from typing import Optional

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger("spark")
_lock = threading.Lock()
_spark: Optional["pyspark.sql.SparkSession"] = None  # noqa: F821
_spark_warm: bool = False


def _build_spark() -> "pyspark.sql.SparkSession":  # noqa: F821
    from pyspark.sql import SparkSession  # type: ignore[import]

    cfg = get_settings()

    # Iceberg + AWS bundle jars must be in SPARK_JARS_DIR or fetched via Maven
    iceberg_version = "1.7.1"
    aws_bundle = f"org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:{iceberg_version}"
    aws_sdk_bundle = "org.apache.hadoop:hadoop-aws:3.3.4"

    builder = (
        SparkSession.builder.appName("zerotrace-data-plane")
        .master("local[*]")
        .config("spark.driver.memory", cfg.spark_driver_memory)
        .config("spark.executor.memory", cfg.spark_executor_memory)
        .config("spark.local.dir", cfg.spark_local_dirs)
        # Iceberg extensions
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config(
            "spark.sql.catalog.kaveri",
            "org.apache.iceberg.spark.SparkCatalog",
        )
        .config("spark.sql.catalog.kaveri.type", "jdbc")
        .config(
            "spark.sql.catalog.kaveri.uri",
            cfg.iceberg_catalog_jdbc_uri,
        )
        .config("spark.sql.catalog.kaveri.warehouse", cfg.iceberg_warehouse)
        # S3A / MinIO credentials
        .config(
            "spark.hadoop.fs.s3a.endpoint",
            cfg.s3_endpoint,
        )
        .config("spark.hadoop.fs.s3a.access.key", cfg.s3_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", cfg.s3_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        # Iceberg write defaults
        .config("spark.sql.iceberg.write.target-file-size-bytes", str(8 * 1024 * 1024))  # 8 MB
        .config("spark.sql.iceberg.delete.mode", "merge-on-read")
        # Serialization
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        # Maven packages (pulled at first start; cached in ~/.ivy2)
        .config(
            "spark.jars.packages",
            f"{aws_bundle},{aws_sdk_bundle}",
        )
        # Suppress noisy logs
        .config("spark.sql.adaptive.enabled", "true")
    )

    # Set LOG4J level via env so Spark doesn't drown the logs
    os.environ.setdefault("PYSPARK_SUBMIT_ARGS", "--master local[*] pyspark-shell")

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def get_spark() -> "pyspark.sql.SparkSession":  # noqa: F821
    global _spark
    if _spark is None:
        raise RuntimeError("Spark session not initialised — call init_spark() at startup")
    return _spark


def is_spark_warm() -> bool:
    return _spark_warm


def init_spark() -> None:
    """Initialise and warm up the Spark session. Call at service startup."""
    global _spark, _spark_warm

    with _lock:
        if _spark is not None:
            return

        logger.info("spark.starting")
        try:
            spark = _build_spark()
            _spark = spark
            logger.info("spark.session_created")
        except Exception as exc:
            logger.error("spark.init_failed", error=str(exc))
            raise

    # Warm-up query outside the lock so init doesn't block health checks
    try:
        _spark.sql("SELECT 1 + 1 AS two").collect()
        _spark_warm = True
        logger.info("spark.warm")
    except Exception as exc:
        logger.warning("spark.warmup_failed", error=str(exc))
        _spark_warm = False


def stop_spark() -> None:
    global _spark, _spark_warm
    with _lock:
        if _spark is not None:
            try:
                _spark.stop()
            except Exception:
                pass
            _spark = None
            _spark_warm = False
            logger.info("spark.stopped")
