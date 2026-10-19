"""
Prometheus-style metrics collection — lightweight, no external dependency.
Exposes /metrics endpoint in text exposition format.
Tracks: request counts, latencies, job durations, erasure metrics, audit results.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class Counter:
    name: str
    help: str
    labels: list[str]
    values: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    _lock: Lock = field(default_factory=Lock, repr=False)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = self._label_key(labels)
        with self._lock:
            self.values[key] += amount

    def _label_key(self, labels: dict[str, str]) -> str:
        return "|".join(f"{k}={labels.get(k, '')}" for k in self.labels)


@dataclass
class Histogram:
    name: str
    help: str
    labels: list[str]
    buckets: list[float]
    counts: dict[str, list[int]] = field(default_factory=dict)
    sums: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    totals: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _lock: Lock = field(default_factory=Lock, repr=False)

    def observe(self, value: float, **labels: str) -> None:
        key = self._label_key(labels)
        with self._lock:
            if key not in self.counts:
                self.counts[key] = [0] * len(self.buckets)
            for i, b in enumerate(self.buckets):
                if value <= b:
                    self.counts[key][i] += 1
            self.sums[key] += value
            self.totals[key] += 1

    def _label_key(self, labels: dict[str, str]) -> str:
        return "|".join(f"{k}={labels.get(k, '')}" for k in self.labels)


@dataclass
class Gauge:
    name: str
    help: str
    value: float = 0.0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def set(self, value: float) -> None:
        with self._lock:
            self.value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self.value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self.value -= amount


class MetricsRegistry:
    """Central metrics registry."""

    def __init__(self):
        # HTTP metrics
        self.http_requests_total = Counter(
            "zt_http_requests_total",
            "Total HTTP requests",
            ["method", "path", "status"],
        )
        self.http_request_duration_seconds = Histogram(
            "zt_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "path"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        )
        self.http_requests_in_flight = Gauge(
            "zt_http_requests_in_flight",
            "HTTP requests currently being processed",
        )

        # Erasure metrics
        self.erasure_jobs_total = Counter(
            "zt_erasure_jobs_total",
            "Total erasure jobs started",
            ["mode"],
        )
        self.erasure_jobs_completed = Counter(
            "zt_erasure_jobs_completed_total",
            "Total erasure jobs completed",
            ["status"],
        )
        self.erasure_duration_seconds = Histogram(
            "zt_erasure_duration_seconds",
            "Erasure job duration in seconds",
            [],
            buckets=[5, 10, 20, 30, 45, 60, 90, 120, 180, 300],
        )
        self.files_rewritten_total = Counter(
            "zt_files_rewritten_total",
            "Total Iceberg data files rewritten",
            ["table"],
        )
        self.vectors_deleted_total = Counter(
            "zt_vectors_deleted_total",
            "Total vector embeddings deleted",
            [],
        )
        self.cache_keys_deleted_total = Counter(
            "zt_cache_keys_deleted_total",
            "Total Redis cache keys deleted",
            [],
        )
        self.bytes_shredded_total = Counter(
            "zt_bytes_shredded_total",
            "Total bytes shredded",
            [],
        )
        self.cost_saved_inr_total = Counter(
            "zt_cost_saved_inr_total",
            "Total cost saved in INR vs full-table rewrite",
            [],
        )

        # Audit metrics
        self.audit_runs_total = Counter(
            "zt_audit_runs_total",
            "Total audit runs",
            ["verdict"],
        )
        self.audit_attacks_total = Counter(
            "zt_audit_attacks_total",
            "Total individual attacks run",
            ["attack_type", "verdict"],
        )
        self.audit_remediation_rounds = Counter(
            "zt_audit_remediation_rounds_total",
            "Total audit remediation rounds",
            [],
        )

        # Health metrics
        self.spark_warm = Gauge(
            "zt_spark_warm",
            "1 if Spark session is warm, 0 otherwise",
        )
        self.db_connected = Gauge(
            "zt_db_connected",
            "1 if Postgres is reachable, 0 otherwise",
        )
        self.redis_connected = Gauge(
            "zt_redis_connected",
            "1 if Redis is reachable, 0 otherwise",
        )
        self.s3_connected = Gauge(
            "zt_s3_connected",
            "1 if S3/MinIO is reachable, 0 otherwise",
        )

        # Rate limit metrics
        self.rate_limited_total = Counter(
            "zt_rate_limited_total",
            "Total requests rejected by rate limiter",
            ["client_ip"],
        )

    def render_prometheus(self) -> str:
        """Render all metrics in Prometheus text exposition format."""
        lines: list[str] = []

        # Counters
        for counter in self._get_counters():
            lines.append(f"# HELP {counter.name} {counter.help}")
            lines.append(f"# TYPE {counter.name} counter")
            for key, value in sorted(counter.values.items()):
                labels = self._parse_labels(key, counter.labels)
                label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                lines.append(f"{counter.name}{{{label_str}}} {value}")

        # Gauges
        for gauge in self._get_gauges():
            lines.append(f"# HELP {gauge.name} {gauge.help}")
            lines.append(f"# TYPE {gauge.name} gauge")
            lines.append(f"{gauge.name} {gauge.value}")

        # Histograms
        for hist in self._get_histograms():
            lines.append(f"# HELP {hist.name} {hist.help}")
            lines.append(f"# TYPE {hist.name} histogram")
            for key, counts in sorted(hist.counts.items()):
                labels = self._parse_labels(key, hist.labels)
                for i, bucket in enumerate(hist.buckets):
                    label_str = ",".join(
                        f'{k}="{v}"' for k, v in labels.items()
                    ) + f',le="{bucket}"' if labels else f'le="{bucket}"'
                    lines.append(f"{hist.name}_bucket{{{label_str}}} {counts[i]}")
                # +Inf bucket
                total = hist.totals.get(key, 0)
                label_str = ",".join(
                    f'{k}="{v}"' for k, v in labels.items()
                ) + ',le="+Inf"' if labels else 'le="+Inf"'
                lines.append(f"{hist.name}_bucket{{{label_str}}} {total}")
                # Sum and count
                label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                lines.append(f"{hist.name}_sum{{{label_str}}} {hist.sums.get(key, 0)}")
                lines.append(f"{hist.name}_count{{{label_str}}} {total}")

        return "\n".join(lines) + "\n"

    def _get_counters(self) -> list[Counter]:
        return [
            self.http_requests_total,
            self.erasure_jobs_total,
            self.erasure_jobs_completed,
            self.files_rewritten_total,
            self.vectors_deleted_total,
            self.cache_keys_deleted_total,
            self.bytes_shredded_total,
            self.cost_saved_inr_total,
            self.audit_runs_total,
            self.audit_attacks_total,
            self.audit_remediation_rounds,
            self.rate_limited_total,
        ]

    def _get_gauges(self) -> list[Gauge]:
        return [
            self.http_requests_in_flight,
            self.spark_warm,
            self.db_connected,
            self.redis_connected,
            self.s3_connected,
        ]

    def _get_histograms(self) -> list[Histogram]:
        return [
            self.http_request_duration_seconds,
            self.erasure_duration_seconds,
        ]

    @staticmethod
    def _parse_labels(key: str, label_names: list[str]) -> dict[str, str]:
        values = key.split("|")
        return {
            name: val
            for name, val in zip(label_names, values)
        }


# Global singleton
metrics = MetricsRegistry()
