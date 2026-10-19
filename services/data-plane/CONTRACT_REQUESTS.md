# Data Plane → Orchestrator Contract Requests

> **Owner: Moiz** — Proposed changes to `contracts/` for platform review.
> Do NOT edit `contracts/` directly — submit requests here.

---

## Open Requests

### CR-001 — `subject_ref` generation algorithm clarification (2026-10-17)

**Context:** The data plane generates `subject_ref` as `HMAC-SHA256(service_key, email|phone)[:20]` prefixed with `sub_`. The orchestrator must generate the **same** ref to pass to `/v1/locate` and `/v1/erasure/plan`.

**Request:** Confirm this algorithm is in the shared contract, or specify a different one.

**Status:** OPEN

---

### CR-002 — Variant list in `/v1/locate` request (2026-10-17)

**Context:** The orchestrator's Gemma intent parser generates identifier variants (phone formats, name transliterations). These should be passed in the `variants` field of the locate request to improve coverage.

**Request:** Confirm the `variants: string[]` field in `LocateRequest` is in the final contract.

**Status:** OPEN

---

### CR-003 — `holds` format in plan request (2026-10-17)

**Context:** The data plane auto-applies PMLA/RBI holds for `kyc` and `financial` categories. The orchestrator can override by passing an explicit `holds` list.

**Request:** Confirm format `{category: string, table: string, legal_basis: string, release_date: ISO8601}` is the canonical hold spec.

**Status:** OPEN

---

## Resolved Requests

_(none yet)_
