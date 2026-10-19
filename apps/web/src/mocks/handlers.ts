/**
 * MSW handlers implementing the §7.1 orchestrator contract from deterministic
 * fixtures (scripts/generate-fixtures.mjs). In mock mode the whole app runs
 * with no backend, including the SSE event stream (§7.2) via MSW's stream API.
 *
 * Mock-only behaviours (documented in the README):
 * - List/detail job responses reflect the scenario's END status; the SSE
 *   stream replays live from seq 0 (fresh) or from `?from=` (resume).
 * - Replaying from zero pauses at the approval gate until POST approve or
 *   POST reject; resuming from a prior session skips the wait.
 */
import { delay, http, sse, HttpResponse, type HttpHandler } from "msw";
import successFx from "./fixtures/success.json";
import ghostFx from "./fixtures/ghost.json";
import holdsFx from "./fixtures/holds.json";
import { env } from "@/lib/env";

/* ---------------- fixtures ---------------- */

interface FixtureEvent {
  seq: number;
  ts: string;
  job_id: string;
  stage: string;
  kind: string;
  layer: string;
  message: string;
  data: Record<string, unknown>;
}
type Fixture = {
  meta: { scenario: string };
  request: Record<string, unknown>;
  job: Record<string, unknown>;
  intent: Record<string, unknown>;
  agent_trace: Array<Record<string, unknown>>;
  lineage: Record<string, unknown>;
  plan: Record<string, unknown>;
  audit: Record<string, unknown>;
  receipt: Record<string, unknown>;
  manifest: { algorithm: string; leaves: Array<Record<string, string>> };
  policies: Record<string, unknown>;
  attack_runs: Record<string, Record<string, unknown>>;
  attack_runs_before: Record<string, Record<string, unknown>>;
  preflight: Array<Record<string, unknown>>;
  impact: Record<string, unknown>;
  demo_secret: { receipt_secret: string; otp_code: string; note: string };
  demo_subjects?: Record<string, unknown>;
  events: FixtureEvent[];
};

const FIXTURES = {
  success: successFx as unknown as Fixture,
  ghost: ghostFx as unknown as Fixture,
  holds: holdsFx as unknown as Fixture,
} satisfies Record<string, Fixture>;

type ScenarioKey = keyof typeof FIXTURES;

let currentScenario: ScenarioKey = "success";
const fixture = (): Fixture => FIXTURES[currentScenario];
const fixtureForJob = (jobId: unknown): Fixture | undefined =>
  Object.values(FIXTURES).find((f) => String(f.job["id"]) === String(jobId));

const toInt = (v: unknown): number | null => {
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : null;
};

/* ---------------- helpers ---------------- */

const requestId = () => `req_mock_${Math.random().toString(36).slice(2, 10)}`;

/* the §7.1 envelope body; wide enough for every resolver in this module */
type Envelope = Record<string, unknown>;
type EnvelopeResponse = HttpResponse<Envelope>;

function json(data: unknown, init?: ResponseInit): EnvelopeResponse {
  const body = { data, error: null, request_id: requestId() } satisfies Envelope;
  return HttpResponse.json(body, init);
}

function jsonMissing(message: string): EnvelopeResponse {
  const body = {
    data: null,
    error: { code: "NOT_FOUND", message, details: null },
    request_id: requestId(),
  } satisfies Envelope;
  return HttpResponse.json(body, { status: 404 });
}

/** Presenter's upstream-degradation switch: x-zt-demo-upstream: offline. */
function upstreamOffline(request: Request): boolean {
  return request.headers.get("x-zt-demo-upstream") === "offline";
}

function upstreamDown(): EnvelopeResponse {
  return HttpResponse.json(
    {
      data: null,
      error: { code: "UPSTREAM_UNAVAILABLE", message: "Upstream degraded (demo switch). The orchestrator cannot reach the data plane.", details: { switched_by: "x-zt-demo-upstream header" } },
      request_id: requestId(),
    } satisfies Envelope,
    { status: 503 }
  );
}

const latency = (ms = 120): Promise<void> => delay(ms);
const ok = (data: unknown) => json(data);

/* ---------------- byte generators (downloads) ---------------- */

/** A tiny valid PDF (one page, Helvetica) carrying the receipt's key values.
 *  The orchestrator's real PDF proof-of-visual replaces this at integration. */
function minimalPdf(lines: string[]): string {
  const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
  const content = lines.map((l, i) => `BT /F1 ${i === 0 ? 16 : 10} Tf 56 ${750 - i * 28} Td (${esc(l)}) Tj ET`).join("\n");
  const objects = [
    "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
    "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
    "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n",
    `5 0 obj\n<< /Length ${content.length} >>\nstream\n${content}\nendstream\nendobj\n`,
  ];
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  for (const o of objects) {
    offsets.push(out.length);
    out += o;
  }
  const xrefStart = out.length;
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const off of offsets) out += `${String(off).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF\n`;
  return out;
}

function bsaCertificateHtml(r: Record<string, unknown>): string {
  const anchor = r.anchor as { network?: string; tx_hash?: string; block?: string; status?: string } | undefined;
  const row = (k: string, v: unknown) => `<tr><th scope="row">${k}</th><td><code>${String(v ?? "—")}</code></td></tr>`;
  const holds = Array.isArray(r.retention_holds)
    ? (r.retention_holds as Array<Record<string, unknown>>)
        .map((h) => `<li>${String(h.category)} — ${String(h.legal_basis)} — release ${String(h.release_date)} (${String(h.count)} rows)</li>`)
        .join("")
    : "";
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Certificate under BSA 2023 §63 — ${String(r.receipt_id)}</title>
<style>body{font:14px/1.5 Georgia,serif;max-width:44rem;margin:3rem auto;padding:0 1rem;color:#111}h1{font-size:19px;border-bottom:1px solid #111;padding-bottom:.5rem}table{border-collapse:collapse;width:100%}th,td{border:1px solid #999;padding:6px 8px;text-align:left;vertical-align:top}th{width:180px;background:#f4f2ee;font-weight:600}code{font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}</style>
</head><body><h1>Certificate under BSA 2023 §63 (electronic record) — demo artefact</h1>
<p>Kaveri Finserv (demo NBFC), through ZeroTrace, certifies the erasure recorded in receipt <code>${String(r.receipt_id)}</code>. This certificate states the machine-verifiable record; it does not name the data subject — identification runs against the subject commitment in the Data Principal Portal.</p>
<table><tbody>
${row("Receipt version", r.version)}${row("Job", r.job_id)}${row("Issued (UTC)", r.issued_at)}${row("Policy version", r.policy_version)}
${row("Pre-purge root", r.pre_root)}${row("Post-purge root", r.post_root)}${row("Diff root", r.diff_root)}
${row("Leaf counts", JSON.stringify(r.leaf_counts))}${row("Anchor", `${String(anchor?.network)} tx ${String(anchor?.tx_hash)} (block ${String(anchor?.block)}, ${String(anchor?.status)})`)}
${row("Signer public key", r.signer_public_key)}${row("Signature (ed25519)", r.signature)}
${row("Algorithms", JSON.stringify(r.algorithms))}
</tbody></table>
<h2>Lawful retention</h2><ul>${holds || "<li>None — everything feasible was erased at execution time.</li>"}</ul>
<p style="border-top:1px solid #111;margin-top:2rem;padding-top:.75rem">Signatory: Data Protection Officer, Kaveri Finserv (demo). Every statutory reference requires legal review before production use. Verification: open <code>/verify/${String(r.receipt_id)}</code> — checks recompute in the browser.</p>
</body></html>`;
}

/* ---------------- approval gate ---------------- */

let autoApprove = false;
let releaseGate: (() => void) | null = null;

const waitAtGate = (): Promise<void> =>
  new Promise<void>((resolve) => {
    releaseGate = resolve;
  });

function openGate(): void {
  const release = releaseGate;
  releaseGate = null;
  if (release) release();
}

/* ---------------- portal submission state ---------------- */

/* Principal submissions (portal). In mock mode each submission maps onto the
   success scenario stream with the gate pre-opened; the receipt secret leaves
   the server exactly once (in this POST's response envelope) and only its
   sha256 commitment ever appears in a receipt. */
let submissions: Array<Record<string, unknown>> = [];
let submissionSecret = "";
let submissionOtp = "";

const submitPortal = (source: string, language: string, audioBytes: number) => {
  const fx = FIXTURES.success;
  autoApprove = true; // the principal never waits at a DPO gate
  openGate();
  submissionSecret = fx.demo_secret.receipt_secret;
  submissionOtp = fx.demo_secret.otp_code;
  const local = `req_mock_${Math.random().toString(36).slice(2, 10)}`;
  submissions = [
    {
      request_id: local,
      job_id: fx.job["id"],
      status: fx.job["status"],
      created_at: new Date().toISOString(),
      subject_masked: "New submission (demo)",
      source,
      language,
      audio_bytes: audioBytes,
      receipt_id: fx.receipt["receipt_id"],
    },
    ...submissions,
  ];
  return {
    request_id: local,
    job_id: String(fx.job["id"]),
    receipt_secret_once: submissionSecret,
    otp_hint: submissionOtp,
    note: "mock transport — the real orchestrator delivers the secret on the principal's verified channel only",
  };
};

/* ---------------- SSE stream ---------------- */

const sseJobEvents = sse("/api/v1/jobs/:jobId/events", async ({ client, request }) => {
  const url = new URL(request.url);
  const sc = url.searchParams.get("scenario");
  const fx = sc !== null && sc in FIXTURES ? FIXTURES[sc as ScenarioKey] : fixture();
  const from = toInt(request.headers.get("Last-Event-ID")) ?? toInt(url.searchParams.get("from")) ?? 0;
  const speedQ = toInt(url.searchParams.get("speed")) ?? 1;
  const speed = Math.max(speedQ, env.mockSpeed);
  const resumed = from > 0;
  const gateIdx = fx.events.findIndex(
    (e) => e.stage === "APPROVAL" && e.kind === "metric" && e.data["approval_granted"] === 1
  );

  for (let i = 0; i < fx.events.length; i++) {
    const ev = fx.events[i];
    if (!ev || typeof ev.seq !== "number" || ev.seq <= from) continue;

    if (!resumed && ev.seq > gateIdx && gateIdx > -1 && !autoApprove) {
      await waitAtGate();
    }
    const prev = i > 0 ? fx.events[i - 1] : undefined;
    const naturalGap = prev && typeof prev.ts === "string" ? (Date.parse(ev.ts) - Date.parse(prev.ts)) / speed : 0;
    const gap = Math.max(30, Math.min(resumed ? 240 : 5_000, (resumed ? naturalGap / 6 : naturalGap) || 60));
    await delay(gap);

    client.send({ data: JSON.stringify(ev) });
  }

  client.close();
});

/* ---------------- handlers ---------------- */

export const handlers: HttpHandler[] = [
  sseJobEvents,

  /* ---- auth ---- */
  http.post("/api/v1/auth/demo-login", async ({ request }) => {
    const body = (await request.json().catch(() => ({}))) as { role?: string };
    const role = body?.role ?? "dpo";
    await latency(180);
    return ok({ token: `jwt_demo.${role}.${Date.now()}`, role });
  }),
  http.get("/api/v1/me", async () => {
    await latency(90);
    return ok({ role: "dpo", display: "Data Protection Officer (demo)" });
  }),

  /* ---- requests ---- */
  http.post("/api/v1/requests/voice", async ({ request }) => {
    if (upstreamOffline(request)) return upstreamDown();
    const form = await request.formData().catch(() => null);
    const audio = form?.get("audio");
    const language = String(form?.get("language_hint") ?? "en-IN");
    if (!form || !(audio instanceof Blob) || audio.size === 0) {
      return HttpResponse.json(
        { data: null, error: { code: "VALIDATION_ERROR", message: "An audio recording is required (field 'audio').", details: null } },
        { status: 400 }
      ) as unknown as EnvelopeResponse;
    }
    await latency(1_150);
    return ok(submitPortal("voice", language, audio.size));
  }),
  http.post("/api/v1/requests/text", async ({ request }) => {
    if (upstreamOffline(request)) return upstreamDown();
    const body = (await request.json().catch(() => ({}))) as { text?: string; language_hint?: string };
    const text = String(body?.text ?? "").trim();
    if (text.length < 12) {
      return HttpResponse.json(
        { data: null, error: { code: "VALIDATION_ERROR", message: "Describe your erasure request in at least twelve characters.", details: null } },
        { status: 400 }
      ) as unknown as EnvelopeResponse;
    }
    await latency(680);
    return ok(submitPortal("text", String(body?.language_hint ?? "en-IN"), text.length));
  }),
  http.post("/api/v1/requests/:id/otp", async ({ request }) => {
    if (upstreamOffline(request)) return upstreamDown();
    const body = (await request.json().catch(() => ({}))) as { code?: string };
    await latency(420);
    if (!submissionOtp || String(body?.code ?? "").trim() !== submissionOtp) {
      return HttpResponse.json(
        {
          data: null,
          error: { code: "VALIDATION_ERROR", message: "That code does not match the demo OTP. Mock transport always issues 230671.", details: null },
        },
        { status: 400 }
      ) as unknown as EnvelopeResponse;
    }
    return ok({ verified: true });
  }),

  http.get("/api/v1/requests", async () => {
    await latency(140);
    const list = (["holds", "ghost", "success"] as const).map((k) => FIXTURES[k]).map((f) => {
      const intent = f.intent as { source?: { language?: string } } | undefined;
      return {
        request_id: String(f.request["request_id"]),
        job_id: String(f.job["id"]),
        status: String(f.job["status"]),
        created_at: String(f.request["created_at"]),
        subject_masked: String(f.request["subject_masked"]),
        source: "voice",
        language: intent?.source?.language ?? "kn-IN",
      };
    });
    return ok([...submissions, ...list]);
  }),
  http.get("/api/v1/requests/:id", async ({ params }) => {
    await latency(120);
    const local = submissions.find((s) => String(s.request_id) === String(params.id));
    if (local) return ok(local);
    const f = Object.values(FIXTURES).find((x) => String(x.request["request_id"]) === String(params.id));
    if (!f) return jsonMissing("request not found");
    return ok(f.request);
  }),

  /* ---- jobs ---- */
  http.get("/api/v1/jobs/:jobId", async ({ params }) => {
    await latency(140);
    const f = fixtureForJob(params.jobId);
    if (!f) return jsonMissing("job not found");
    return ok(f.job);
  }),
  http.get("/api/v1/jobs/:jobId/intent", async ({ params }) => {
    const f = fixtureForJob(params.jobId);
    if (!f) return jsonMissing("job not found");
    await latency(160);
    return ok(f.intent);
  }),
  http.get("/api/v1/jobs/:jobId/lineage", async ({ params }) => {
    const f = fixtureForJob(params.jobId);
    if (!f) return jsonMissing("job not found");
    await latency(140);
    return ok(f.lineage);
  }),
  http.get("/api/v1/jobs/:jobId/plan", async ({ params }) => {
    const f = fixtureForJob(params.jobId);
    if (!f) return jsonMissing("job not found");
    await latency(140);
    return ok(f.plan);
  }),
  http.get("/api/v1/jobs/:jobId/audit", async ({ params }) => {
    const f = fixtureForJob(params.jobId);
    if (!f) return jsonMissing("job not found");
    await latency(140);
    return ok(f.audit);
  }),
  http.get("/api/v1/jobs/:jobId/agent-trace", async ({ params }) => {
    const f = fixtureForJob(params.jobId);
    if (!f) return jsonMissing("job not found");
    await latency(100);
    return ok(f.agent_trace);
  }),

  http.post("/api/v1/jobs/:jobId/approve", async () => {
    await latency(260);
    autoApprove = true;
    openGate();
    return ok({ approved: true, approved_by: "dpo_console" });
  }),
  http.post("/api/v1/jobs/:jobId/reject", async () => {
    await latency(240);
    autoApprove = false;
    openGate();
    return ok({ approved: false });
  }),

  /* ---- receipts ---- */
  http.get("/api/v1/receipts/:id", async ({ params }) => {
    await latency(150);
    const f = Object.values(FIXTURES).find((x) => String(x.receipt["receipt_id"]) === String(params.id));
    if (!f) return jsonMissing("receipt not found");
    return ok(f.receipt);
  }),

  /* download endpoints stream real bytes so the \"save receipt\" UX is honest */
  http.get("/api/v1/receipts/:id/download", async ({ params, request }) => {
    const f = Object.values(FIXTURES).find((x) => String(x.receipt["receipt_id"]) === String(params.id));
    if (!f) return jsonMissing("receipt not found");
    const format = new URL(request.url).searchParams.get("format") ?? "json";
    await latency(200);
    if (format === "pdf") {
      const r = f.receipt as Record<string, unknown>;
      const pdfDoc = minimalPdf([
        "ZeroTrace erasure receipt (demo)",
        `receipt ${r.receipt_id}`,
        `job ${r.job_id}`,
        `issued ${r.issued_at} · policy ${r.policy_version}`,
        `pre  ${r.pre_root}`,
        `post ${r.post_root}`,
        `diff ${r.diff_root}`,
        `anchor ${r.explorer_url ?? ""}`,
        "verify at /verify (browser-side, no trust in this server)",
      ]);
      return new HttpResponse(pdfDoc, {
        headers: { "Content-Type": "application/pdf", "Content-Disposition": `attachment; filename="${String(r.receipt_id)}.pdf"` },
      });
    }
    if (format === "pack") {
      const pack = { receipt: f.receipt, manifest: { algorithm: f.manifest.algorithm, leaves: f.manifest.leaves } };
      return new HttpResponse(JSON.stringify(pack, null, 2), {
        headers: { "Content-Type": "application/json", "Content-Disposition": `attachment; filename="${String(f.receipt["receipt_id"])}-pack.json"` },
      });
    }
    return new HttpResponse(JSON.stringify(f.receipt, null, 2), {
      headers: { "Content-Type": "application/json", "Content-Disposition": `attachment; filename="${String(f.receipt["receipt_id"])}.json"` },
    });
  }),

  /* BSA §63-style certificate: printable HTML with the commitment values */
  http.get("/api/v1/receipts/:id/certificate", async ({ params }) => {
    const f = Object.values(FIXTURES).find((x) => String(x.receipt["receipt_id"]) === String(params.id));
    if (!f) return jsonMissing("receipt not found");
    await latency(180);
    const r = f.receipt as Record<string, unknown>;
    const html = bsaCertificateHtml(r);
    return new HttpResponse(html, { headers: { "Content-Type": "text/html; charset=utf-8" } });
  }),

  /* interim mock-only view feeding the DPO Policies page */
  http.get("/api/v1/policies", async () => {
    await latency(120);
    return ok(fixture().policies);
  }),

  /* ---- public verifier ---- */
  http.post("/api/v1/verify", async () => {
    await latency(220);
    const anchor = (fixture().receipt as { anchor?: { block?: string } }).anchor;
    const checks = [
      { check: "receipt_schema", verdict: "pass", detail: "schema v1 fields present" },
      { check: "signature", verdict: "pass", detail: "ed25519 over the canonical receipt bytes" },
      { check: "subject_commitment_format", verdict: "pass", detail: "64-hex commitment" },
      { check: "pre_root", verdict: "pass", detail: "committed in the anchor payload" },
      { check: "post_root", verdict: "pass", detail: "committed in the anchor payload" },
      { check: "diff_root", verdict: "pass", detail: "recomputed from manifest membership" },
      { check: "anchor", verdict: "pass", detail: `confirmed on-chain at block ${anchor?.block ?? "—"}` },
    ];
    return ok({ receipt_id: String((fixture().receipt as Record<string, unknown>)["receipt_id"]), checks, verified: true });
  }),

  /* ---- attacks ---- */
  /* mode is additive: body { mode?: "before" | "after" } — naive-DELETE
     baseline vs post-ZeroTrace. Contract request filed in CONTRACT_REQUESTS.md. */
  http.post("/api/v1/attack/:type", async ({ params, request }) => {
    if (upstreamOffline(request)) return upstreamDown();
    await latency(700);
    const t = String(params.type);
    const body = (await request.json().catch(() => ({}))) as { mode?: "before" | "after" };
    const f = fixture();
    const runs = body?.mode === "before" ? f.attack_runs_before : f.attack_runs;
    if (t in runs) return ok(runs[t]);
    return jsonMissing(`unknown attack type ${t}`);
  }),

  /* ---- system ---- */
  http.get("/api/v1/system/preflight", async ({ request }) => {
    await latency(160);
    const list = [...fixture().preflight];
    if (upstreamOffline(request)) {
      const sarvam = list.find((c) => c.component === "sarvam");
      if (sarvam) sarvam.detail = "upstream switch set to OFFLINE in Demo Director";
    }
    return ok(list);
  }),
  http.get("/api/v1/system/impact", async () => {
    await latency(160);
    return ok(fixture().impact);
  }),

  /* ---- demo ---- */
  http.post("/api/v1/demo/reset", async ({ request }) => {
    if (upstreamOffline(request)) return upstreamDown();
    await latency(420);
    autoApprove = false;
    submissions = [];
    submissionSecret = "";
    submissionOtp = "";
    currentScenario = "success";
    return ok({ ok: true, scenario: currentScenario });
  }),
  http.post("/api/v1/demo/seed", async ({ request }) => {
    if (upstreamOffline(request)) return upstreamDown();
    await latency(520);
    const body = (await request.json().catch(() => ({}))) as { scenario?: string; auto_approve?: boolean };
    if (body?.scenario && body.scenario in FIXTURES) currentScenario = body.scenario as keyof typeof FIXTURES;
    if (typeof body?.auto_approve === "boolean") {
      autoApprove = body.auto_approve;
      if (autoApprove) openGate();
    }
    return ok({ ok: true, scenario: currentScenario, auto_approve: autoApprove });
  }),
  http.post("/api/v1/demo/naive-delete", async ({ request }) => {
    if (upstreamOffline(request)) return upstreamDown();
    await latency(380);
    return ok({ ok: true, mode: "naive", note: "Baseline written: one SQL DELETE, time-travel untouched, embeddings intact. Run the battery." });
  }),
];
