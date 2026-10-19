/** Pure event-view reducer: turns the §7.2 event stream into everything the
 *  Job Detail screen renders. Unit-tested; or the screen would lie. */
import { JOB_STAGES, type JobEvent, type JobStage } from "@/api/schemas";

export type StageStatus = "pending" | "running" | "done" | "failed";

export interface StageView {
  stage: JobStage;
  status: StageStatus;
  startedSeq?: number;
  completedSeq?: number;
  failedSeq?: number;
  startedTs?: string;
  completedTs?: string;
  /** sum of stage wall-clock from first started/progress to completed/failed */
  durationMs?: number;
  lastProgress?: string;
}

export interface AuditAttack {
  attack: string;
  verdict: "FOUND" | "NOT_FOUND" | "PASS" | "FAIL";
  checked?: number;
  matches?: number;
  round: number;
  special?: boolean;
  message?: string;
}

export interface AuditRound {
  round: number;
  verdict: "PASS" | "FAIL";
  attacks: AuditAttack[];
  collateral?: { rows_compared?: number; checksum_match?: boolean; other_subjects_affected?: number; decoys_untouched?: number };
  residualLocations: Array<{ layer: string; object_id?: string; resource?: string }>;
}

export interface ProofView {
  leafCounts?: Record<string, number>;
  itemsErasedCounts?: Record<string, number>;
  preRoot?: string;
  postRoot?: string;
  diffRoot?: string;
}

export interface AnchorView {
  network?: string;
  status: "idle" | "submitted" | "confirmed" | "failed";
  txHash?: string;
  block?: string;
  explorerUrl?: string;
}

export interface GhostFinding {
  seq: number;
  layer: string;
  resourceId: string;
  resource: string;
  matchBasis?: string;
  metadataLinked?: boolean;
}

export interface JobEventView {
  stages: Record<JobStage, StageView>;
  lastSeq: number;
  lastTs?: string;
  firstTs?: string;
  metrics: Record<string, number>;
  rewrittenFiles: string[];
  revealedNodes: string[];
  auditRounds: AuditRound[];
  remediationCount: number;
  proof: ProofView;
  anchor: AnchorView;
  finalStatus?: string;
  receiptId?: string;
  ghostFindings: GhostFinding[];
  holdsApplied: Array<{ category: string; action?: string; release_date?: string }>;
}

export const STAGE_ORDER: readonly JobStage[] = JOB_STAGES;

export function initialView(): JobEventView {
  const stages = {} as Record<JobStage, StageView>;
  for (const s of STAGE_ORDER) {
    stages[s] = { stage: s, status: "pending" };
  }
  return {
    stages,
    lastSeq: 0,
    metrics: {},
    rewrittenFiles: [],
    revealedNodes: [],
    auditRounds: [],
    remediationCount: 0,
    proof: {},
    anchor: { status: "idle" },
    ghostFindings: [],
    holdsApplied: [],
  };
}

function pushRound(view: JobEventView, roundNo: number): AuditRound {
  const existing = view.auditRounds.find((r) => r.round === roundNo);
  if (existing) return existing;
  const round: AuditRound = { round: roundNo, verdict: "FAIL", attacks: [], residualLocations: [] };
  view.auditRounds.push(round);
  return round;
}

/** mutates `view` (a working draft) with one event */
export function applyEvent(view: JobEventView, ev: JobEvent): void {
  if (ev.seq <= view.lastSeq) return;
  view.lastSeq = ev.seq;
  view.lastTs = ev.ts;
  if (!view.firstTs) view.firstTs = ev.ts;

  const st: StageView = view.stages[ev.stage];
  if (st) {
    if ("started" === ev.kind) {
      if (st.status === "pending") {
        st.status = "running";
        st.startedSeq = ev.seq;
        st.startedTs = ev.ts;
      }
    } else if ("completed" === ev.kind) {
      st.status = "done";
      st.completedSeq = ev.seq;
      st.completedTs = ev.ts;
      if (st.startedTs) st.durationMs = Date.parse(ev.ts) - Date.parse(st.startedTs);
    } else if ("failed" === ev.kind) {
      st.status = "failed";
      st.failedSeq = ev.seq;
      if (st.startedTs) st.durationMs = Date.parse(ev.ts) - Date.parse(st.startedTs);
    } else if ("progress" === ev.kind || "log" === ev.kind) {
      if (st.status === "pending") {
        st.status = "running";
        st.startedSeq = ev.seq;
        st.startedTs = ev.ts;
      }
      st.lastProgress = ev.message;
    }
  }

  /* metric keys accumulate last-wins (events carry counters cumulatively) */
  for (const [k, v] of Object.entries(ev.data)) {
    if (typeof v === "number") {
      view.metrics[k] = v;
    }
  }

  /* heat grid: fold rewritten file ids in arrival order */
  const rewritten = ev.data["rewritten_file_ids"];
  if (Array.isArray(rewritten)) {
    for (const id of rewritten) {
      if (typeof id === "string" && !view.rewrittenFiles.includes(id)) view.rewrittenFiles.push(id);
    }
  }

  /* lineage: DISCOVERY progress events reveal one node each */
  if (ev.stage === "DISCOVERY" && ev.kind === "progress" && typeof ev.data["node_id"] === "string") {
    const nodeId = ev.data["node_id"] as string;
    if (!view.revealedNodes.includes(nodeId)) view.revealedNodes.push(nodeId);
  }

  /* audit */
  if (ev.stage === "AUDIT") {
    if (ev.kind === "started") {
      const roundNo = typeof ev.data["round"] === "number" ? ev.data["round"] : view.auditRounds.length + 1;
      pushRound(view, roundNo);
    } else if (ev.kind === "finding") {
      const roundNo = typeof ev.data["round"] === "number" ? ev.data["round"] : (view.auditRounds[view.auditRounds.length - 1]?.round ?? 1);
      const round = pushRound(view, roundNo);
      const attack = ev.data["attack"];
      const verdict = ev.data["verdict"];
      if (typeof attack === "string") {
        if (attack === "collateral" && typeof verdict === "string" && ["PASS", "FAIL"].includes(verdict)) {
          round.collateral = {
            rows_compared: typeof ev.data["rows_compared"] === "number" ? ev.data["rows_compared"] : undefined,
            checksum_match: typeof ev.data["checksum_match"] === "boolean" ? ev.data["checksum_match"] : undefined,
            other_subjects_affected: typeof ev.data["other_subjects_affected"] === "number" ? ev.data["other_subjects_affected"] : undefined,
            decoys_untouched: typeof ev.data["decoys_untouched"] === "number" ? ev.data["decoys_untouched"] : undefined,
          };
          if (verdict === "PASS" && round.attacks.every((a) => a.verdict !== "FOUND")) round.verdict = "PASS";
          else if (verdict === "FAIL") round.verdict = "FAIL";
        } else {
          round.attacks.push({
            attack,
            verdict: verdict === "FOUND" || verdict === "NOT_FOUND" ? verdict : "NOT_FOUND",
            checked: typeof ev.data["checked"] === "number" ? ev.data["checked"] : undefined,
            matches: typeof ev.data["matches"] === "number" ? ev.data["matches"] : undefined,
            round: roundNo,
            special: ev.data["special"] === "ghost",
            message: ev.message,
          });
          if (verdict === "FOUND") round.verdict = "FAIL";
        }
      } else if (typeof ev.data["location"] === "object" && ev.data["location"] !== null) {
        const loc = ev.data["location"] as Record<string, unknown>;
        view.ghostFindings.push({
          seq: ev.seq,
          layer: String(loc["layer"] ?? "vector"),
          resourceId: String(loc["object_id"] ?? ""),
          resource: String(loc["resource"] ?? ""),
          matchBasis: loc["match_basis"] ? String(loc["match_basis"]) : undefined,
          metadataLinked: typeof loc["metadata_linked"] === "boolean" ? loc["metadata_linked"] : undefined,
        });
      }
    } else if (ev.kind === "completed") {
      const roundNo = typeof ev.data["round"] === "number" ? ev.data["round"] : (view.auditRounds[view.auditRounds.length - 1]?.round ?? 1);
      const round = pushRound(view, roundNo);
      const verdict = ev.data["verdict"];
      if (verdict === "PASS" || verdict === "FAIL") round.verdict = verdict;
      if (Array.isArray(ev.data["residual_locations"])) {
        for (const loc of ev.data["residual_locations"] as Array<Record<string, unknown>>) {
          round.residualLocations.push({ layer: String(loc["layer"] ?? ""), object_id: loc["object_id"] ? String(loc["object_id"]) : undefined });
        }
      }
    }
  }

  /* remediate */
  if (ev.stage === "REMEDIATE") {
    view.remediationCount = Math.max(view.remediationCount, 1);
    const deleted = ev.data["vectors_deleted"];
    if (typeof deleted === "number") {
      view.metrics["vectors_deleted_remediated"] = (view.metrics["vectors_deleted_remediated"] ?? 0) + deleted;
    }
  }

  /* POLICY holds */
  if (ev.stage === "POLICY" && ev.kind === "finding" && ev.data["category"]) {
    view.holdsApplied.push({
      category: String(ev.data["category"]),
      action: ev.data["action"] ? String(ev.data["action"]) : undefined,
      release_date: ev.data["release_date"] ? String(ev.data["release_date"]) : undefined,
    });
  }

  /* proof */
  if (ev.stage === "PROOF") {
    if (ev.kind === "metric") {
      if (ev.data["leaf_counts"]) view.proof.leafCounts = ev.data["leaf_counts"] as Record<string, number>;
      if (ev.data["items_erased_counts"]) view.proof.itemsErasedCounts = ev.data["items_erased_counts"] as Record<string, number>;
    }
    if (ev.kind === "completed") {
      const proofKeys = { pre_root: "preRoot", post_root: "postRoot", diff_root: "diffRoot" } as const;
      for (const [rawKey, key] of Object.entries(proofKeys)) {
        const value = ev.data[rawKey];
        if (typeof value === "string") (view.proof as Record<string, unknown>)[key] = value;
      }
    }
  }

  /* anchor */
  if (ev.stage === "ANCHOR") {
    if (ev.kind === "started") view.anchor = { ...view.anchor, network: String(ev.data["network"] ?? "chain"), status: "submitted" };
    if (ev.kind === "progress") view.anchor.status = "submitted";
    if (ev.kind === "completed") {
      view.anchor = {
        network: typeof ev.data["network"] === "string" ? ev.data["network"] : view.anchor.network,
        status: "confirmed",
        txHash: typeof ev.data["tx_hash"] === "string" ? ev.data["tx_hash"] : undefined,
        block: ev.data["block"] !== undefined && ev.data["block"] !== null ? String(ev.data["block"]) : undefined,
        explorerUrl: typeof ev.data["explorer_url"] === "string" ? ev.data["explorer_url"] : undefined,
      };
    }
  }

  /* completion */
  if (ev.stage === "COMPLETE") {
    if (ev.kind === "completed") {
      view.finalStatus = typeof ev.data["status"] === "string" ? ev.data["status"] : "COMPLETED";
      view.receiptId = typeof ev.data["receipt_id"] === "string" ? ev.data["receipt_id"] : undefined;
    }
  }
}

export function reduceEvents(events: readonly JobEvent[]): JobEventView {
  const draft = initialView();
  for (const ev of events) applyEvent(draft, ev);
  return draft;
}

/* ---------------- derived helpers ---------------- */

export function currentStage(view: JobEventView): JobStage | null {
  const running = STAGE_ORDER.find((s) => view.stages[s].status === "running");
  if (running) return running;
  const done = [...STAGE_ORDER].reverse().find((s) => view.stages[s].status === "done");
  return done ?? null;
}

export function statusFromView(view: JobEventView): string {
  if (view.finalStatus) return view.finalStatus;
  const cs = currentStage(view);
  const map: Partial<Record<JobStage, string>> = {
    INTAKE: "PARSING",
    PARSE: "PARSING",
    DISCOVERY: "DISCOVERING",
    POLICY: "DISCOVERING",
    PLAN: "PLANNED",
    APPROVAL: "AWAITING_APPROVAL",
    ERASE_CRYPTO: "EXECUTING",
    ERASE_ICEBERG: "EXECUTING",
    ERASE_VECTOR: "EXECUTING",
    ERASE_CACHE: "EXECUTING",
    AUDIT: "AUDITING",
    REMEDIATE: "REMEDIATING",
    PROOF: "PROVING",
    ANCHOR: "ANCHORING",
    COMPLETE: "COMPLETED",
  };
  return (cs && map[cs]) || "RECEIVED";
}

export const LAST_STAGE: JobStage = "COMPLETE";

export function isTerminal(view: JobEventView): boolean {
  return Boolean(view.finalStatus);
}
