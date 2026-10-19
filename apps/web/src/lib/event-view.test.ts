import { describe, expect, it } from "vitest";
import { applyEvent, initialView, isTerminal, statusFromView, type JobEventView } from "./event-view";
import { jobEventZ, type JobEvent, type JobStage } from "../api/schemas";

const JOB = "job_01J8BJ0M3Q7W4N8H2RGT6EK9XC";

let seq = 0;
function ev(stage: JobStage, kind: JobEvent["kind"], data: Record<string, unknown> = {}, ts = "2026-01-15T09:00:00Z"): JobEvent {
  seq += 1;
  return jobEventZ.parse({
    seq,
    ts,
    job_id: JOB,
    stage,
    kind,
    layer: "system",
    message: `${stage.toLowerCase()} ${kind}`,
    data,
  });
}

function run(events: JobEvent[]): JobEventView {
  const view = initialView();
  for (const e of events) applyEvent(view, e);
  return view;
}

describe("event view reducer", () => {
  it("ignores stale sequence numbers (dedupe / replay)", () => {
    const view = initialView();
    applyEvent(view, ev("INTAKE", "started"));
    const lastTs = view.lastTs;
    /* seq is 1 now; a duplicate frame with the same seq must not change anything */
    applyEvent(view, { ...ev("INTAKE", "completed"), seq: 1 });
    expect(view.lastSeq).toBe(1);
    expect(view.stages.INTAKE.status).toBe("running");
    expect(view.lastTs).toBe(lastTs);
  });

  it("keeps stage duration from started→completed timestamps", () => {
    const view = initialView();
    applyEvent(view, ev("PLAN", "started", {}, "2026-01-15T09:00:00Z"));
    applyEvent(view, ev("PLAN", "completed", {}, "2026-01-15T09:00:12.400Z"));
    expect(view.stages.PLAN.status).toBe("done");
    expect(view.stages.PLAN.durationMs).toBeCloseTo(12_400, 0);
  });

  it("progress events activate a pending stage and carry the last progress line", () => {
    const view = run([ev("DISCOVERY", "progress", { node_id: "node_sources" })]);
    expect(view.stages.DISCOVERY.status).toBe("running");
    expect(view.revealedNodes).toEqual(["node_sources"]);
  });

  it("recording DISCOVERY node reveals is dedup-safe and ordered", () => {
    const view = run([
      ev("DISCOVERY", "progress", { node_id: "n1" }),
      ev("DISCOVERY", "progress", { node_id: "n2" }),
      ev("DISCOVERY", "progress", { node_id: "n1" }),
    ]);
    expect(view.revealedNodes).toEqual(["n1", "n2"]);
  });

  it("accumulates numeric metric keys last-wins", () => {
    const view = run([
      ev("ERASE_ICEBERG", "metric", { files_total: 480 }),
      ev("ERASE_ICEBERG", "metric", { files_total: 480, files_rewritten: 3 }),
    ]);
    expect(view.metrics["files_total"]).toBe(480);
    expect(view.metrics["files_rewritten"]).toBe(3);
  });

  it("folds rewritten file ids across ERASE_ICEBERG events without duplicates", () => {
    const view = run([
      ev("ERASE_ICEBERG", "progress", { rewritten_file_ids: ["f1", "f2"] }),
      ev("ERASE_ICEBERG", "progress", { rewritten_file_ids: ["f2", "f3"] }),
    ]);
    expect(view.rewrittenFiles).toEqual(["f1", "f2", "f3"]);
  });

  it("tracks erasure holds from POLICY events", () => {
    const view = run([ev("POLICY", "metric", { holds_active: 1, hold_category: "pmla" })]);
    /* the holdsMetro come through the dedicated data payload in fixtures; the
       metric path only bumps the counter */
    expect(view.metrics["holds_active"]).toBe(1);
    expect(view.holdsApplied.length).toBe(0);
  });

  it("records holds from POLICY finding events", () => {
    const view = run([
      ev("POLICY", "finding", {
        category: "pmla",
        action: "hold-then-erase",
        release_date: "2027-05-01",
      }),
    ]);
    expect(view.holdsApplied).toEqual([
      { category: "pmla", action: "hold-then-erase", release_date: "2027-05-01" },
    ]);
  });

  it("builds audit rounds with findings, collateral and ghost verdicts", () => {
    const view = run([
      ev("AUDIT", "started", { round: 1 }),
      ev("AUDIT", "finding", { round: 1, attack: "time_travel", verdict: "NOT_FOUND" }),
      ev("AUDIT", "finding", { round: 1, attack: "raw_parquet", verdict: "NOT_FOUND" }),
      ev("AUDIT", "finding", { round: 1, attack: "collateral", verdict: "PASS", rows_compared: 42, checksum_match: true }),
    ]);
    expect(view.auditRounds).toHaveLength(1);
    const round = view.auditRounds.at(0);
    expect(round).toBeDefined();
    if (!round) return;
    expect(round.round).toBe(1);
    expect(round.verdict).toBe("PASS");
    expect(round.attacks.map((a) => a.attack)).toEqual(["time_travel", "raw_parquet"]);
    expect(round.collateral?.checksum_match).toBe(true);
  });

  it("audit finding FOUND flips the round verdict to FAIL", () => {
    const view = run([
      ev("AUDIT", "started", { round: 1 }),
      ev("AUDIT", "finding", { round: 1, attack: "time_travel", verdict: "NOT_FOUND" }),
      ev("AUDIT", "finding", { round: 1, attack: "s3_versions", verdict: "FOUND" }),
    ]);
    expect(view.auditRounds[0]?.verdict).toBe("FAIL");
  });

  it("records ghost findings from AUDIT finding events without an attack key", () => {
    const view = run([
      ev("AUDIT", "finding", {
        location: {
          layer: "iceberg",
          object_id: "sol-2024q3.parquet",
          resource: "old snapshot",
          metadata_linked: true,
        },
      }),
    ]);
    expect(view.ghostFindings).toHaveLength(1);
    expect(view.ghostFindings[0]?.layer).toBe("iceberg");
    expect(view.ghostFindings[0]?.resourceId).toBe("sol-2024q3.parquet");
    expect(view.ghostFindings[0]?.metadataLinked).toBe(true);
  });

  it("counts remediation once the REMEDIATE stage fires", () => {
    const view = run([
      ev("AUDIT", "completed", { round: 1, verdict: "FAIL" }),
      ev("REMEDIATE", "started", { round: 1 }),
      ev("REMEDIATE", "completed", { round: 1 }),
    ]);
    expect(view.remediationCount).toBe(1);
  });

  it("captures proof roots from PROOF completed and leaf counts from metrics", () => {
    const view = run([
      ev("PROOF", "metric", { leaf_counts: { iceberg: 3, vector: 2 } }),
      ev("PROOF", "completed", {
        pre_root: "aaaa1111",
        post_root: "bbbb2222",
        diff_root: "cccc3333",
      }),
    ]);
    expect(view.proof.leafCounts).toEqual({ iceberg: 3, vector: 2 });
    expect(view.proof.preRoot).toBe("aaaa1111");
    expect(view.proof.postRoot).toBe("bbbb2222");
    expect(view.proof.diffRoot).toBe("cccc3333");
  });

  it("transitions the anchor to confirmed with tx + block on ANCHOR completed", () => {
    const view = run([
      ev("ANCHOR", "started", { network: "sepolia" }),
      ev("ANCHOR", "completed", {
        network: "sepolia",
        tx_hash: "0xdeadbeef1234567890",
        block: "9900442",
      }),
    ]);
    expect(view.anchor.status).toBe("confirmed");
    expect(view.anchor.network).toBe("sepolia");
    expect(view.anchor.txHash).toBe("0xdeadbeef1234567890");
    expect(view.anchor.block).toBe("9900442");
  });

  it("marks completion and picks up the receipt id", () => {
    const view = run([
      ev("COMPLETE", "completed", { status: "ERASED", receipt_id: "rcpt_01J8BK9Z2D5XW6TQN8HVF1P3LB" }),
    ]);
    expect(view.receiptId).toBe("rcpt_01J8BK9Z2D5XW6TQN8HVF1P3LB");
    expect(isTerminal(view)).toBe(true);
  });

  it("derives a human-facing status from the view", () => {
    expect(statusFromView(initialView())).toBe("RECEIVED");
    const started = run([ev("INTAKE", "started")]);
    expect(statusFromView(started)).toBe("PARSING");
    const discover = run([ev("DISCOVERY", "started")]);
    expect(statusFromView(discover)).toBe("DISCOVERING");
    const done = run([ev("COMPLETE", "completed", { status: "ERASED" })]);
    expect(statusFromView(done)).toBe("ERASED");
  });

  it("leaves a failed COMPLETE non-terminal (orchestrator may relaunch the tail)", () => {
    const view = run([ev("COMPLETE", "failed", { reason: "verify_failed" })]);
    expect(isTerminal(view)).toBe(false);
    expect(view.stages.COMPLETE.status).toBe("failed");
  });
});
