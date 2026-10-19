"""
Pydantic v2 request/response schemas for the data plane API.
All responses use the envelope: {data, error, request_id}.
Raw identifiers must never appear in logs or error messages.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Envelope ─────────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    request_id: str = ""


# ── Shared ────────────────────────────────────────────────────────────────────

class Identifier(BaseModel):
    type: Literal["phone", "email", "customer_id", "name", "full_name", "pan"]
    value: str


class HoldSpec(BaseModel):
    category: str = ""
    table: str = ""
    legal_basis: str
    release_date: Optional[str] = None


# ── Health ────────────────────────────────────────────────────────────────────

class DeepHealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    spark_warm: bool
    s3_ok: bool
    pg_ok: bool
    redis_ok: bool
    versions: dict[str, str]
    uptime_s: float


# ── Inventory ─────────────────────────────────────────────────────────────────

class ColumnInfo(BaseModel):
    name: str
    type: str
    is_pii: bool


class TableInfo(BaseModel):
    name: str
    layer: Literal["iceberg", "relational"]
    tags: list[str]
    columns: list[ColumnInfo]
    pii_columns: list[str]
    row_count: Optional[int] = None


class InventoryResponse(BaseModel):
    tables: list[TableInfo]
    vector_namespaces: list[str]
    cache_keyspaces: list[str]


# ── Locate ────────────────────────────────────────────────────────────────────

class LocateRequest(BaseModel):
    identifiers: list[Identifier]
    variants: list[str] = Field(default_factory=list)


class LocationResult(BaseModel):
    location_id: str
    layer: Literal["iceberg", "vector", "cache", "relational"]
    resource: str
    match_basis: str
    estimated_rows: int
    data_category: str
    pii_columns: list[str]
    files_hit: int
    files_total: int


class LocateResponse(BaseModel):
    locations: list[LocationResult]


# ── Plan ─────────────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    job_id: str
    subject_ref: str
    identifiers: list[Identifier]
    holds: list[HoldSpec] = Field(default_factory=list)


class ErasureStepOut(BaseModel):
    step_id: str
    layer: str
    action: str
    target: str
    est_rows: int
    est_files: int
    est_bytes: int
    est_cost_inr: float
    order: int
    parallel_group: int


class BlastRadiusOut(BaseModel):
    files_total: int
    files_targeted: int
    partitions_total: int
    partitions_targeted: int
    bloom_false_positive_rate: float


class CostEstimateOut(BaseModel):
    naive_inr: float
    targeted_inr: float
    saving_pct: float
    assumptions: list[str]


class PlanResponse(BaseModel):
    plan_id: str
    job_id: str
    steps: list[ErasureStepOut]
    blast_radius: BlastRadiusOut
    cost: CostEstimateOut
    holds: list[dict]
    warnings: list[str]
    created_at: str


# ── Execute ───────────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    job_id: str
    plan_id: str
    mode: Literal["both", "crypto_only", "physical_only"] = "both"


class ExecuteResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ── Job Status ────────────────────────────────────────────────────────────────

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    plan_id: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    checkpoint: Optional[dict] = None


# ── Remediate ────────────────────────────────────────────────────────────────

class RemediateRequest(BaseModel):
    job_id: str
    residual_locations: list[dict]


class RemediateResponse(BaseModel):
    job_id: str
    remediated: int
    message: str


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditRequest(BaseModel):
    job_id: str
    identifiers: list[Identifier]
    attacks: Optional[list[str]] = None


class AttackFinding(BaseModel):
    attack_type: str
    description: str = ""
    verdict: str
    evidence_summary: list[str]
    match_count: int
    duration_ms: float


class CollateralIntegrity(BaseModel):
    rows_compared: int
    checksum_match: bool
    other_subjects_affected: int


class AuditResponse(BaseModel):
    verdict: Literal["PASS", "FAIL"]
    findings: list[AttackFinding]
    collateral_integrity: CollateralIntegrity
    residual_locations: list[dict]


# ── Manifest ─────────────────────────────────────────────────────────────────

class ManifestRequest(BaseModel):
    job_id: str
    label: Literal["pre", "post"]


class ManifestItem(BaseModel):
    layer: str
    object_id: str   # no PII
    content_hash: str
    in_scope: bool
    held: bool


class ManifestResponse(BaseModel):
    job_id: str
    label: str
    items: list[ManifestItem]
    item_count: int


# ── Demo ─────────────────────────────────────────────────────────────────────

class SeedRequest(BaseModel):
    profile: Literal["small", "showtime"] = "small"


class SeedResponse(BaseModel):
    profile: str
    elapsed_s: float
    tables: dict[str, int]
    vectors: dict[str, int]
    cache: dict[str, int]


class SubjectDescriptor(BaseModel):
    customer_id: str
    display_name: str       # not masked for director UI
    masked_phone: str
    masked_email: str
    subject_ref: str
    is_hero: bool
    decoy_note: Optional[str] = None


class ScenarioRequest(BaseModel):
    ghost_miss: Optional[bool] = None
    auto_approve: Optional[bool] = None
