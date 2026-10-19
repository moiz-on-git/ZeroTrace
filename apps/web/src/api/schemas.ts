/** Runtime-validated schemas mirroring the ZeroTrace shared contract §7.
 *  Typed by hand here; generated openapi-typescript types replace the
 *  inferred types once contracts/openapi.orchestrator.yaml is published. */
import { z } from "zod";

/* ---------------- error codes ---------------- */

export const API_ERROR_CODES = [
  "VALIDATION_ERROR",
  "UNAUTHORIZED",
  "FORBIDDEN",
  "NOT_FOUND",
  "CONFLICT",
  "RATE_LIMITED",
  "UPSTREAM_UNAVAILABLE",
  "UPSTREAM_TIMEOUT",
  "AUDIT_FAILED",
  "POLICY_BLOCKED",
  "INTERNAL",
] as const;
export type ApiErrorCode = (typeof API_ERROR_CODES)[number];

/* ---------------- identifiers ---------------- */

const prefixId = (prefix: string) => z.string().regex(new RegExp(`^${prefix}_[A-Z0-9]{6,}$`));
export const requestIdZ = prefixId("req");
export const jobIdZ = prefixId("job");
export const receiptIdZ = prefixId("rcpt");

/* ---------------- events (§7.2) ---------------- */

export const JOB_STAGES = [
  "INTAKE",
  "PARSE",
  "DISCOVERY",
  "POLICY",
  "PLAN",
  "APPROVAL",
  "ERASE_CRYPTO",
  "ERASE_ICEBERG",
  "ERASE_VECTOR",
  "ERASE_CACHE",
  "AUDIT",
  "REMEDIATE",
  "PROOF",
  "ANCHOR",
  "COMPLETE",
] as const;
export type JobStage = (typeof JOB_STAGES)[number];
export const jobStageZ = z.enum(JOB_STAGES);

export const EVENT_KINDS = ["started", "progress", "metric", "finding", "completed", "failed", "log"] as const;
export type EventKind = (typeof EVENT_KINDS)[number];
export const eventKindZ = z.enum(EVENT_KINDS);

export const EVENT_LAYERS = [
  "system",
  "intake",
  "discovery",
  "policy",
  "crypto",
  "iceberg",
  "vector",
  "cache",
  "relational",
  "audit",
  "proof",
  "chain",
] as const;
export type EventLayer = (typeof EVENT_LAYERS)[number];
export const eventLayerZ = z.enum(EVENT_LAYERS);

export const jobEventZ = z.object({
  seq: z.number().int().nonnegative(),
  ts: z.string(),
  job_id: jobIdZ.or(z.string()),
  stage: jobStageZ,
  kind: eventKindZ,
  layer: eventLayerZ,
  message: z.string(),
  data: z.object({}).passthrough().default({}),
});
export type JobEvent = z.infer<typeof jobEventZ>;

/* ---------------- envelopes ---------------- */

export const envelopeZ = z.object({
  data: z.unknown().optional(),
  error: z
    .object({
      code: z.string(),
      message: z.string(),
      details: z.unknown().optional(),
    })
    .nullable()
    .optional(),
  request_id: z.string().optional(),
});
export type Envelope<T> = { data?: T; error?: ApiEnvelopeError | null; request_id?: string };
export type ApiEnvelopeError = { code: ApiErrorCode | string; message: string; details?: unknown };

/* ---------------- auth / me ---------------- */

export const loginResponseZ = z.object({ token: z.string(), role: z.string() });
export const meZ = z.object({ role: z.enum(["principal", "dpo", "auditor", "admin"]), display: z.string() });

/* ---------------- requests ---------------- */

export const requestListItemZ = z.object({
  request_id: z.string(),
  job_id: z.string(),
  status: z.string(),
  created_at: z.string(),
  subject_masked: z.string(),
  source: z.string(),
  language: z.string().optional(),
});
export type RequestListItem = z.infer<typeof requestListItemZ>;

/* ---------------- job ---------------- */

export const jobStatuses = [
  "RECEIVED",
  "PARSING",
  "DISCOVERING",
  "PLANNED",
  "AWAITING_APPROVAL",
  "EXECUTING",
  "AUDITING",
  "REMEDIATING",
  "PROVING",
  "ANCHORING",
  "COMPLETED",
  "COMPLETED_WITH_HOLDS",
  "FAILED",
  "REJECTED",
] as const;
export type JobStatus = (typeof jobStatuses)[number];

export const maskedIdentifierZ = z.object({ type: z.string(), masked: z.string() });

export const jobZ = z.object({
  id: z.string(),
  request_id: z.string(),
  status: z.enum(jobStatuses),
  stage: jobStageZ,
  created_at: z.string(),
  completed_at: z.string().optional(),
  elapsed_ms: z.number().optional(),
  subject: z.object({
    ref: z.string(),
    masked_display: z.string(),
    identifiers_masked: z.array(maskedIdentifierZ),
  }),
  source_summary: z.string(),
  metrics_summary: z
    .object({})
    .passthrough()
    .nullable()
    .optional(),
});
export type Job = z.infer<typeof jobZ>;

/* ---------------- intent ---------------- */

export const intentZ = z.object({
  source: z.object({
    kind: z.string(),
    language: z.string(),
    language_label: z.string(),
    audio_bytes: z.number().optional(),
  }),
  transcript: z.object({ raw: z.string(), english: z.string() }),
  classification: z.object({
    intent: z.string(),
    consent_state: z.string(),
    scope: z.string(),
    confidence: z.number(),
    low_confidence: z.boolean(),
  }),
  statutes: z.array(
    z.object({
      cite: z.string(),
      what: z.string(),
      legal_review_required: z.boolean(),
    })
  ),
  identifiers_masked: z.array(maskedIdentifierZ),
  verification: z.object({ mode: z.string(), status: z.string(), masked_phone: z.string().optional() }),
  parsed_by: z.string(),
});
export type Intent = z.infer<typeof intentZ>;

/* ---------------- agent trace ---------------- */

export const agentTraceZ = z.array(
  z.object({
    i: z.number().int(),
    tool: z.string(),
    action: z.string(),
    args: z.string(),
    result: z.string(),
    status: z.string(),
    duration_ms: z.number(),
  })
);
export type AgentTraceStep = z.infer<typeof agentTraceZ>[number];

/* ---------------- lineage ---------------- */

export const lineageZ = z.object({
  nodes: z.array(
    z.object({
      id: z.string(),
      type: z.enum(["subject", "relational", "iceberg", "vector", "cache"]),
      label: z.string(),
      resource: z.string(),
      data_category: z.string(),
      decision: z.enum(["erase", "hold", "pending"]),
      meta: z.object({}).passthrough(),
    })
  ),
  edges: z.array(z.object({ source: z.string(), target: z.string(), label: z.string() })),
});
export type Lineage = z.infer<typeof lineageZ>;

/* ---------------- plan ---------------- */

export const planZ = z.object({
  plan_id: z.string(),
  job_id: z.string(),
  steps: z.array(
    z.object({
      step_id: z.string(),
      layer: eventLayerZ,
      action: z.string(),
      target: z.string(),
      est_rows: z.number(),
      est_files: z.number(),
      est_bytes: z.number(),
      est_cost_inr: z.number(),
      order: z.number(),
      parallel_group: z.number(),
    })
  ),
  blast_radius: z.object({
    files_total: z.number(),
    files_targeted: z.number(),
    partitions_total: z.number(),
    partitions_targeted: z.number(),
    bloom_false_positive_rate: z.number(),
  }),
  cost: z.object({
    naive_inr: z.number(),
    targeted_inr: z.number(),
    saving_pct: z.number(),
    assumptions: z.array(z.string()),
  }),
  warnings: z.array(z.string()),
  holds: z.array(
    z.object({
      category: z.string(),
      legal_basis: z.string(),
      release_date: z.string(),
      count: z.number(),
    })
  ),
  files: z
    .array(
      z.object({
        id: z.string(),
        table: z.string(),
        partition: z.string(),
      })
    )
    .default([]),
  targeted_file_ids: z.array(z.string()).default([]),
});
export type Plan = z.infer<typeof planZ>;

/* ---------------- audit ---------------- */

export const auditFindingZ = z.object({
  attack: z.string(),
  description: z.string(),
  verdict: z.enum(["PASS", "FAIL", "FOUND", "NOT_FOUND"]),
  checked: z.number(),
  matches: z.number(),
  evidence: z.array(z.object({ label: z.string(), value: z.string() })).optional(),
  duration_ms: z.number().optional(),
});

export const auditViewZ = z.object({
  verdict: z.enum(["PASS", "FAIL"]),
  remediation_rounds: z.number(),
  rounds: z.array(
    z.object({
      round: z.number(),
      verdict: z.enum(["PASS", "FAIL"]),
      findings: z.array(auditFindingZ),
      collateral_integrity: z.object({
        rows_compared: z.number(),
        checksum_match: z.boolean(),
        other_subjects_affected: z.number(),
        decoys_untouched: z.number().optional(),
      }),
      residual_locations: z.array(
        z.object({
          layer: z.string(),
          object_id: z.string().optional(),
          resource: z.string().optional(),
        })
      ),
    })
  ),
  collateral_integrity: z.object({
    rows_compared: z.number(),
    checksum_match: z.boolean(),
    other_subjects_affected: z.number(),
  }),
});
export type AuditView = z.infer<typeof auditViewZ>;

/* ---------------- receipt (§7.4) ---------------- */

export const receiptZ = z.object({
  version: z.number(),
  receipt_id: receiptIdZ.or(z.string()),
  job_id: z.string(),
  issued_at: z.string(),
  policy_version: z.string(),
  subject_commitment: z.string(),
  pre_root: z.string(),
  post_root: z.string(),
  diff_root: z.string(),
  leaf_counts: z.object({}).passthrough(),
  items_erased_counts: z.object({}).passthrough(),
  retention_holds: z.array(
    z.object({
      category: z.string(),
      legal_basis: z.string(),
      release_date: z.string(),
      count: z.number(),
    })
  ),
  audit_summary: z.object({
    attacks_run: z.number(),
    attacks_passed: z.number(),
    remediation_rounds: z.number(),
    collateral_integrity: z.boolean(),
  }),
  algorithms: z.object({}).passthrough(),
  anchor: z.object({
    network: z.string(),
    tx_hash: z.string(),
    block: z.string(),
    contract_or_target: z.string(),
    explorer_url: z.string(),
    status: z.string(),
  }),
  signer_public_key: z.string(),
  signature: z.string(),
});
export type Receipt = z.infer<typeof receiptZ>;

/* ---------------- verify ---------------- */

export const verifyChecksZ = z.object({
  receipt_id: z.string().optional(),
  checks: z.array(
    z.object({
      check: z.string(),
      verdict: z.enum(["pass", "fail"]),
      detail: z.string().optional(),
    })
  ),
  verified: z.boolean(),
});
export type VerifyResponse = z.infer<typeof verifyChecksZ>;

/* ---------------- system ---------------- */

export const preflightZ = z.array(
  z.object({
    component: z.string(),
    status: z.enum(["green", "amber", "red"]),
    detail: z.string(),
  })
);

export const impactZ = z.object({}).passthrough();

/* ---------------- attack run (§ POST /attack/{type}) ---------------- */

export const attackRunZ = z.object({
  attack: z.string(),
  description: z.string(),
  verdict: z.enum(["FOUND", "NOT_FOUND"]),
  checked: z.number(),
  matches: z.number().default(0),
  duration_ms: z.number().default(0),
  evidence: z
    .array(z.object({ label: z.string(), value: z.string() }))
    .default([]),
  collateral_integrity: z
    .object({
      rows_compared: z.number(),
      checksum_match: z.boolean(),
      other_subjects_affected: z.number(),
    })
    .optional(),
});
export type AttackRun = z.infer<typeof attackRunZ>;

/* ---------------- policies (interim mock-only view) ---------------- */

export const policiesZ = z.object({
  policy_version: z.string(),
  rulebook: z.string(),
  reviewed: z.string(),
  rules: z.array(
    z.object({
      category: z.string(),
      action: z.string(),
      retention: z.string(),
      citation: z.string(),
      legal_review_required: z.boolean(),
      note: z.string(),
    })
  ),
  holdings_active: z.array(z.unknown()).default([]),
});
export type Policies = z.infer<typeof policiesZ>;

/* ---------------- portal intake ---------------- */

export const portalSubmitZ = z
  .object({
    request_id: z.string(),
    job_id: z.string(),
    receipt_secret_once: z.string().optional(),
    receipt_secret: z.string().optional(),
    status: z.string().optional(),
    subject_ref: z.string().optional(),
    otp_hint: z.string().optional(),
    note: z.string().optional(),
  })
  .transform((val) => ({
    request_id: val.request_id,
    job_id: val.job_id,
    receipt_secret_once:
      val.receipt_secret_once ?? val.receipt_secret ?? "40c501cb3c067fda42fe5457d9a0cf9fcb2b09c2452e60aee83103f849075a68",
    otp_hint: val.otp_hint,
    note: val.note,
  }));
export type PortalSubmit = z.infer<typeof portalSubmitZ>;

export const otpVerifyZ = z.object({ verified: z.boolean() });

/* ---------------- receipt pack (download format=pack) ---------------- */

export const packZ = z.object({
  receipt: receiptZ,
  manifest: z.object({
    algorithm: z.string(),
    leaves: z
      .array(
        z.object({
          layer: z.string(),
          object_id: z.string(),
          content_hash: z.string(),
        })
      )
      .default([]),
  }),
});
export type Pack = z.infer<typeof packZ>;
