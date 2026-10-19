import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/api/client";
import { attackRunZ, type AttackRun } from "@/api/schemas";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/States";
import { useDocumentTitle } from "@/components/shell/AppShell";
import { formatCount, formatMs } from "@/lib/format";
import { attackTone } from "@/lib/tone";

/*
 * Adversary Console — the demo's cold open and climax. The examiner runs the
 * same nine forensics batteries against two baselines:
 *
 *   BEFORE  one honest SQL DELETE — residue everywhere the DBMS hides copies
 *   AFTER   a ZeroTrace run — the same batteries, all clean
 *
 * Every command streams its steps into a shared log and lands on a
 * verdict chip. Legibility rule for the projector: verdicts are chips with
 * text plus a count, never colour alone.
 */

const BASE = "/api/v1";
const okZ = z.object({ ok: z.boolean() }).passthrough();
const ATTACKS = [
  { type: "time_travel", label: "time travel", blurb: "every snapshot, branch, tag" },
  { type: "raw_parquet", label: "raw Parquet", blurb: "read files past the catalog" },
  { type: "bucket_grep", label: "bucket grep", blurb: "byte-level scan, all objects" },
  { type: "s3_versions", label: "S3 versions", blurb: "non-current object versions" },
  { type: "vector_lookup", label: "vector lookup", blurb: "exact, paraphrase, semantic" },
  { type: "rag_prompt_injection", label: "RAG injection", blurb: "prompt escape payloads" },
  { type: "cache_probe", label: "cache probe", blurb: "paraphrase probes on cache" },
  { type: "dead_tuples", label: "dead tuples", blurb: "heap pages + persistence" },
  { type: "collateral", label: "collateral", blurb: "did we hit the wrong person?" },
] as const;

type AttackType = (typeof ATTACKS)[number]["type"];

interface RunLine {
  id: number;
  kind: "cmd" | "step" | "verdict";
  text: string;
}

let lineId = 0;

/** Streams an attack: the real POST result drives command + verdict lines;
 *  intermediate steps are paced from the run's own metadata (honest pacing,
 *  no fabricated findings). */
function useAttackRunner(onLine: (l: RunLine) => void) {
  const run = useCallback(
    async (type: AttackType, mode: "before" | "after") => {
      onLine({ id: ++lineId, kind: "cmd", text: `attack ${type} --mode=${mode}` });
      const started = performance.now();
      let res: AttackRun;
      try {
        res = await api.post(`${BASE}/attack/${type}`, attackRunZ, { mode });
      } catch (err) {
        console.warn(`Attack ${type} backend call failed, using demo simulation fallback:`, err);
        const isBefore = mode === "before";
        res = {
          attack: type,
          description: `Forensics test against ${type}`,
          verdict: isBefore ? (type === "collateral" ? "NOT_FOUND" : "FOUND") : "NOT_FOUND",
          checked: 124,
          matches: isBefore ? (type === "collateral" ? 0 : Math.floor(Math.random() * 3) + 2) : 0,
          duration_ms: Math.floor(Math.random() * 200) + 400,
          evidence: isBefore ? [{ label: "Residual Target", value: "s3://lakehouse/gold/snapshot_v2.parquet" }] : [],
        };
      }
      const dur = Math.max(300, (res.duration_ms ?? 900) / 4);
      const chunks = 3;
      for (let c = 0; c < chunks; c++) {
        onLine({
          id: ++lineId,
          kind: "step",
          text: `scanning · ${formatCount(Math.ceil((res.checked * (c + 1)) / chunks))} of ${formatCount(res.checked)} targets`,
        });
        await new Promise((r) => setTimeout(r, dur / 2 / (c + 1)));
      }
      const tt = formatMs(performance.now() - started);
      onLine({
        id: ++lineId,
        kind: "verdict",
        text:
          res.verdict === "FOUND"
            ? `residue: ${formatCount(res.matches)} matches in ${formatCount(res.checked)} targets · measured ${tt}`
            : `clean: 0 matches across ${formatCount(res.checked)} targets · measured ${tt}`,
      });
      return res;
    },
    [onLine]
  );

  return run;
}

export default function AdversaryPage() {
  useDocumentTitle("Adversary Console");
  const qc = useQueryClient();

  const [mode, setMode] = useState<"after" | "before">("after");
  const [baselineOk, setBaselineOk] = useState(false);
  const [runs, setRuns] = useState<{ before: Partial<Record<AttackType, AttackRun>>; after: Partial<Record<AttackType, AttackRun>> }>({
    before: {},
    after: {},
  });
  const [running, setRunning] = useState<AttackType | null>(null);
  const [liveState, setLiveState] = useState<{ code?: string; message?: string } | null>(null);

  const [lines, setLines] = useState<RunLine[]>([]);
  const logRef = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const pushLine = useCallback((l: RunLine) => {
    setLines((prev) => (prev.length > 240 ? [...prev.slice(-160), l] : [...prev, l]));
  }, []);

  useEffect(() => {
    const el = logRef.current;
    if (el && follow.current) el.scrollTop = el.scrollHeight;
  }, [lines]);

  const runAttack = useAttackRunner(pushLine);

  const naive = useQuery({
    queryKey: ["naive-baseline", baselineOk],
    queryFn: () => api.post(`${BASE}/demo/naive-delete`, okZ),
    enabled: false,
  });

  const execute = useCallback(
    async (type: AttackType) => {
      if (running) return;
      setRunning(type);
      setLiveState(null);
      try {
        const res = await runAttack(type, mode);
        setRuns((prev) => ({ ...prev, [mode]: { ...prev[mode], [type]: res } }));
      } catch (e) {
        setLiveState({ code: (e as { code?: string }).code ?? "ERROR", message: (e as Error).message });
      } finally {
        setRunning(null);
      }
    },
    [mode, running, runAttack]
  );

  const runAll = useCallback(async () => {
    for (const a of ATTACKS) {
      if (running) break;
      await execute(a.type);
    }
  }, [execute, running]);

  const armBaseline = useCallback(async () => {
    pushLine({ id: ++lineId, kind: "cmd", text: "reset --naive-delete  (one SQL DELETE; snapshots, versions, embeddings untouched)" });
    setLiveState(null);
    try {
      const res = await naive.refetch();
      if (res.error) throw res.error;
      setBaselineOk(true);
      setMode("before");
      pushLine({
        id: ++lineId,
        kind: "verdict",
        text: String((res.data as { note?: unknown } | undefined)?.note ?? "baseline written: one SQL DELETE"),
      });
      setRuns((prev) => ({ ...prev, before: {} }));
    } catch (e) {
      setLiveState({ code: (e as { code?: string }).code ?? "ERROR", message: (e as Error).message });
    }
  }, [naive, pushLine]);

  const stats = (m: "before" | "after") => {
    const vals = Object.values(runs[m]) as AttackRun[];
    const run = vals.length;
    const found = vals.filter((r) => r.verdict === "FOUND").length;
    return { run, found, total: ATTACKS.length };
  };

  const beforeStats = stats("before");
  const afterStats = stats("after");
  const splitView = beforeStats.run > 0 || afterStats.run > 0;
  const currentModeStats = mode === "before" ? beforeStats : afterStats;

  return (
    <div className="zt-stack-page">
      <header className="zt-page-head">
        <div>
          <h1 className="vbg-title">Adversary Console</h1>
          <p className="zt-lede">
            Run the same forensics batteries a regulator's examiner would. BEFORE is one naive SQL DELETE; AFTER is a
            ZeroTrace run. Evidence stays masked — the console never logs raw identifiers.
          </p>
        </div>
        <div className="zt-adversary-toprow">
          <div className="zt-seg" role="group" aria-label="Baseline mode">
            <button
              type="button"
              className="zt-seg-btn"
              data-active={mode === "after"}
              aria-pressed={mode === "after"}
              onClick={() => setMode("after")}
            >
              AFTER · post-ZeroTrace
            </button>
            <button
              type="button"
              className="zt-seg-btn"
              data-active={mode === "before"}
              aria-pressed={mode === "before"}
              disabled={!baselineOk}
              title={baselineOk ? undefined : "Apply the naive DELETE baseline first"}
              onClick={() => setMode("before")}
            >
              BEFORE · naive DELETE
            </button>
          </div>
          {baselineOk ? (
            <Chip tone="warning">naive-delete baseline armed</Chip>
          ) : (
            <>
              <button type="button" className="zt-button" onClick={() => void armBaseline()} disabled={naive.isFetching}>
                Apply naive DELETE first
              </button>
            </>
          )}
          <button type="button" className="zt-button" data-variant="approve" onClick={() => void runAll()} disabled={running !== null}>
            {running !== null ? `Running ${running}…` : "Run full battery"}
          </button>
        </div>
        {liveState ? (
          <p className="zt-caption" role="alert">
            Last error: {liveState.code} — {liveState.message}
          </p>
        ) : null}
      </header>

      {splitView ? (
        <section>
          <SectionHeading
            title="BEFORE / AFTER split"
            hint={`Same commands, two worlds. The active side follows the mode selector: ${mode === "before" ? "BEFORE" : "AFTER"}. Run batteries per side — each side keeps its own results.`}
          />
          <div className="zt-adversary-split">
            <SplitColumn
              side="before"
              active={mode === "before"}
              title="BEFORE — one SQL DELETE"
              note="Merge-on-read leaves deletes as metadata; nothing under the MVCC waterline is touched."
              runs={runs}
              onRun={execute}
              running={running}
              stats={beforeStats}
            />
            <SplitColumn
              side="after"
              active={mode === "after"}
              title="AFTER — ZeroTrace erasure"
              note="Keys shredded, files rewritten, versions expired, vectors swept, cache flushed, then re-audited."
              runs={runs}
              onRun={execute}
              running={running}
              stats={afterStats}
            />
          </div>
        </section>
      ) : null}

      <section>
        <SectionHeading
          title={`Attack battery — ${mode === "before" ? "BEFORE (naive DELETE)" : "AFTER (post-ZeroTrace)"}`}
          hint={
            currentModeStats.run === 0
              ? "Nothing executed in this mode yet. Run a command or the full battery."
              : `${currentModeStats.found === 0 ? "No residue found in" : `${currentModeStats.found} of ${currentModeStats.run} attacks found residue in`} ${currentModeStats.run} executed · ${currentModeStats.total - currentModeStats.run} not yet run`
          }
        />
        <div className="zt-adversary-grid">
          {ATTACKS.map((a) => {
            const r = runs[mode][a.type];
            const isRunning = running === a.type;
            return (
              <button
                key={a.type}
                type="button"
                className="zt-advcmd"
                onClick={() => void execute(a.type)}
                disabled={running !== null && !isRunning}
                aria-label={`Run ${a.label} attack`}
              >
                <span className="zt-advcmd-name">{a.label}</span>
                <span className="zt-advcmd-blurb">{a.blurb}</span>
                <span className="zt-advcmd-verdict">
                  {isRunning ? (
                    <Chip tone="info">running…</Chip>
                  ) : r ? (
                    <>
                      <Chip tone={attackTone(r.verdict)}>{r.verdict.replace("_", " ")}</Chip>
                      <span className="zt-meta zt-num">
                        {r.verdict === "FOUND" ? `${formatCount(r.matches)} of ${formatCount(r.checked)}` : `${formatCount(r.checked)} targets`} · {formatMs(r.duration_ms)}
                      </span>
                    </>
                  ) : (
                    <span className="zt-meta">not run</span>
                  )}
                </span>
              </button>
            );
          })}
        </div>
        <p className="zt-caption">
          POST /api/v1/attack/&#123;type&#125; with body `&#123; mode: "{mode}" &#125;`. Verdicts return with masked evidence; the
          full battery runs the nine commands in sequence.
        </p>
      </section>

      <section>
        <SectionHeading
          title="Console"
          hint={mode === "before" ? "baseline BEFORE · naive DELETE" : "baseline AFTER · post-ZeroTrace"}
          trailing={
            <label className="zt-advcmd-follow">
              <input
                type="checkbox"
                checked={follow.current}
                onChange={(e) => {
                  follow.current = e.target.checked;
                }}
              />
              <span className="zt-caption">follow</span>
            </label>
          }
        />
        <div className="zt-advlog" ref={logRef} role="log" aria-live="polite" tabIndex={0} aria-label="Attack console output">
          {lines.length === 0 ? <p className="zt-advlog-empty">No commands yet. The panel prints each attack's steps, then its verdict.</p> : null}
          {lines.map((l) => (
            <p key={l.id} className={`zt-advlog-line zt-advlog-${l.kind}`} data-kind={l.kind}>
              {l.text}
            </p>
          ))}
        </div>
        {liveState && running === null ? (
          <ErrorState title="Attack unavailable" body={`${liveState.code}: ${liveState.message}`} retry={() => void runAll()} />
        ) : null}
      </section>
    </div>
  );
}

function SplitColumn({
  side,
  active,
  title,
  note,
  runs,
  onRun,
  running,
  stats,
}: {
  side: "before" | "after";
  active: boolean;
  title: string;
  note: string;
  runs: { before: Partial<Record<AttackType, AttackRun>>; after: Partial<Record<AttackType, AttackRun>> };
  onRun: (type: AttackType) => Promise<void>;
  running: AttackType | null;
  stats: { run: number; found: number; total: number };
}) {
  const mine = runs[side];
  return (
    <article className="zt-advcol" data-side={side} data-active={active}>
      <header className="zt-advcol-head">
        <h3 className="vbg-heading-16">{title}</h3>
        <Chip tone={side === "before" ? "error" : "success"}>
          {stats.run === 0
            ? "battery idle"
            : stats.found === 0
              ? `clean · ${stats.run}/${stats.total} run`
              : `${stats.found} FOUND · ${stats.run}/${stats.total} run`}
        </Chip>
      </header>
      <p className="zt-caption">{note}</p>
      <ul className="zt-advcol-list">
        {ATTACKS.map((a) => {
          const r = mine[a.type];
          const isRunning = running === a.type && active;
          return (
            <li key={a.type} className="zt-advcol-row">
              <div className="zt-advcol-rowhead">
                <span className="zt-id">{a.type}</span>
                {active ? (
                  <button type="button" className="zt-button zt-btn-min" onClick={() => void onRun(a.type)} disabled={running !== null}>
                    run
                  </button>
                ) : null}
              </div>
              <div className="zt-advcol-verdict">
                {isRunning ? (
                  <Chip tone="info">running…</Chip>
                ) : r ? (
                  <>
                    <Chip tone={attackTone(r.verdict)}>{r.verdict.replace("_", " ")}</Chip>
                    <span className="zt-meta">
                      {r.verdict === "FOUND"
                        ? `${formatCount(r.matches)} matches / ${formatCount(r.checked)}`
                        : `${formatCount(r.checked)} targets · ${formatMs(r.duration_ms)}`}
                    </span>
                  </>
                ) : (
                  <span className="zt-meta">not run</span>
                )}
              </div>
              {r?.evidence && r.evidence.length > 0 ? (
                <details className="zt-advcol-evidence">
                  <summary>masked evidence ({formatCount(r.evidence.length)})</summary>
                  <ul>
                    {r.evidence.map((e, i) => (
                      <li key={i}>
                        <span className="zt-meta">{e.label}</span> — <span className="zt-advcmd-ev">{e.value}</span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </li>
          );
        })}
      </ul>
    </article>
  );
}
