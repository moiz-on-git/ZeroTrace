import { useCallback, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/api/client";
import { planZ, type Plan } from "@/api/schemas";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { ErrorState, SkeletonRows } from "@/components/ui/States";
import { Chip } from "@/components/ui/Chip";
import { CostComparison } from "@/components/ui/CostComparison";
import { jobStreamStore } from "@/hooks/useJobEvents";
import { formatCount } from "@/lib/format";

type FileState = "pending" | "targeted" | "rewritten" | "purged";

/**
 * (d) Plan and blast radius. The heat grid maps every data file (§ showtime:
 * 480 deliberately small files); targeted files highlight, rewritten ones
 * change live from ERASE_ICEBERG events. Cost comparison is measured, and the
 * approval control is a hold-to-confirm so a single click is never an accident.
 */
export default function PlanSection({ jobId, status }: { jobId: string; status: string }) {
  const plan = useQuery({
    queryKey: ["plan", jobId],
    queryFn: () => api.get(`/api/v1/jobs/${encodeURIComponent(jobId)}/plan`, planZ),
  });
  const view = jobStreamStore((s) => s.view);
  const qc = useQueryClient();

  const approvalSchema = z.object({ approved: z.boolean() });

  const approve = useMutation({
    mutationFn: (via: string) =>
      api.post(`/api/v1/jobs/${encodeURIComponent(jobId)}/approve`, approvalSchema, { via }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["job", jobId] });
    },
  });
  const reject = useMutation({
    mutationFn: (reason: string) =>
      api.post(`/api/v1/jobs/${encodeURIComponent(jobId)}/reject`, approvalSchema, { reason }),
  });

  const awaitingApproval = status === "AWAITING_APPROVAL" || (view.stages.APPROVAL.status === "running" && !view.finalStatus);

  if (plan.isPending) {
    return (
      <section className="zt-job-section" id="plan">
        <SectionHeading title="Plan and blast radius" hint="Exact files, partitions, counters and cost before anything executes." />
        <SkeletonRows rows={4} />
      </section>
    );
  }
  if (plan.isError) {
    return (
      <section className="zt-job-section" id="plan">
        <SectionHeading title="Plan and blast radius" hint="Plan unavailable." />
        <ErrorState title="Plan unavailable" retry={() => plan.refetch()} />
      </section>
    );
  }

  const data = plan.data as Plan;
  const targeted = new Set(data.targeted_file_ids);
  const rewritten = new Set(view.rewrittenFiles);

  return (
    <section className="zt-job-section" id="plan">
      <SectionHeading
        title="Plan and blast radius"
        hint={`${formatCount(data.blast_radius.files_targeted)} of ${formatCount(data.blast_radius.files_total)} files targeted · ${formatCount(data.blast_radius.partitions_targeted)} of ${formatCount(data.blast_radius.partitions_total)} partitions · locator fpr ${(data.blast_radius.bloom_false_positive_rate * 100).toFixed(4)}%`}
      />

      <div className="zt-plan-grid">
        <HeatGrid files={data.files} targeted={targeted} rewritten={rewritten} />
        <div className="zt-plan-side">
          <CostComparison naiveInr={data.cost.naive_inr} targetedInr={data.cost.targeted_inr} savingPct={data.cost.saving_pct} assumptions={data.cost.assumptions} />
          <div className="zt-warnings">
            <p className="vbg-label">Warnings</p>
            <ul>
              {data.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {(data.holds.length > 0 || view.holdsApplied.length > 0) && (
        <HoldsTable holds={data.holds.length ? data.holds : view.holdsApplied.map((h) => ({ ...h, count: 0, legal_basis: undefined, release_date: undefined }))} />
      )}

      <HoldToConfirm awaiting={awaitingApproval} approve={approve} reject={reject} />
    </section>
  );
}

type HoldRow = { category: string; legal_basis?: string; release_date?: string; count: number; action?: string };

function HoldsTable({ holds }: { holds: HoldRow[] }) {
  return (
    <div className="vbg-table-wrap zt-holds-table">
      <table>
        <caption className="vbg-visually-hidden">Lawful retention holds</caption>
        <thead>
          <tr>
            <th scope="col">Category</th>
            <th scope="col">Action</th>
            <th scope="col">Legal basis</th>
            <th scope="col" className="vbg-numeric">
              Rows held
            </th>
            <th scope="col" className="vbg-numeric">
              Release
            </th>
          </tr>
        </thead>
        <tbody>
          {holds.map((h, i) => (
            <tr key={`${h.category}-${i}`}>
              <td>{h.category}</td>
              <td>{h.action ?? "hold-then-erase"}</td>
              <td>
                {h.legal_basis ?? "held by policy rules"} <Chip tone="warning">legal review</Chip>
              </td>
              <td className="vbg-numeric zt-num">{h.count > 0 ? formatCount(h.count) : "—"}</td>
              <td className="vbg-numeric zt-num">{h.release_date ?? "scheduled"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- heat grid ---------- */

const CELL = 13;
const GAP = 4;
const COLS = 46;

function HeatGrid({
  files,
  targeted,
  rewritten,
}: {
  files: Array<{ id: string; table: string; partition: string }>;
  targeted: Set<string>;
  rewritten: Set<string>;
}) {
  const [hoverId, setHoverId] = useState<string | null>(null);
  const width = COLS * (CELL + GAP);
  const rows = Math.ceil(files.length / COLS);
  const height = rows * (CELL + GAP);

  const stateFor = useCallback(
    (id: string): FileState => {
      if (rewritten.has(id)) {
        if (targeted.has(id)) return "rewritten";
        return "purged";
      }
      if (targeted.has(id)) return "targeted";
      return "pending";
    },
    [rewritten, targeted]
  );

  const hoverFile = files.find((f) => f.id === hoverId) ?? null;
  const targetedCount = files.filter((f) => stateFor(f.id) !== "pending").length;

  return (
    <figure className="zt-heat-fig">
      <figcaption className="vbg-caption">
        <span data-filestate="targeted">targeted</span> · <span data-filestate="rewritten">rewritten</span> ·{" "}
        <span data-filestate="purged">purged</span> · <span data-filestate="pending">untouched</span> — one square per
        data file ({formatCount(files.length)}). {formatCount(targetedCount)} touched.
      </figcaption>
      <div
        className="zt-heat-wrap"
        tabIndex={0}
        aria-label="Blast-radius heat grid of data files; highlighted squares are the files this erasure touches"
      >
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="presentation" className="zt-heat-svg">
          {files.map((f, i) => {
            const x = (i % COLS) * (CELL + GAP);
            const y = Math.floor(i / COLS) * (CELL + GAP);
            const st = stateFor(f.id);
            const interactive = st !== "pending";
            return (
              <rect
                key={f.id}
                className="zt-heatcell"
                data-filestate={st}
                x={x}
                y={y}
                width={CELL}
                height={CELL}
                rx={2}
                tabIndex={interactive ? 0 : -1}
                aria-label={`${f.table}, ${f.partition}, ${st}`}
                onMouseEnter={() => setHoverId(f.id)}
                onMouseLeave={() => setHoverId(null)}
                onFocus={() => setHoverId(f.id)}
                onBlur={() => setHoverId(null)}
              />
            );
          })}
        </svg>
      </div>
      <p className="zt-caption" aria-live="polite">
        {hoverFile ? `${hoverFile.id} · ${hoverFile.table} · ${hoverFile.partition} · ${stateFor(hoverFile.id)}` : "Hover or tab through highlighted squares for file detail."}
      </p>
    </figure>
  );
}

/* ---------- hold-to-confirm ---------- */

const HOLD_MS = 1_200;

function HoldToConfirm({
  awaiting,
  approve,
  reject,
}: {
  awaiting: boolean;
  approve: { isPending: boolean; mutate: (v: string) => void };
  reject: { isPending: boolean; mutate: (r: string) => void };
}) {
  const [fill, setFill] = useState(0);
  const holding = useRef(false);
  const raf = useRef(0);
  const startAt = useRef(0);
  const fired = approve.isPending || reject.isPending;

  const beginHold = useCallback(() => {
    if (!awaiting || fired || holding.current) return;
    holding.current = true;
    startAt.current = performance.now();
    const step = () => {
      const p = Math.min(1, (performance.now() - startAt.current) / HOLD_MS);
      setFill(p);
      if (p < 1 && holding.current) {
        raf.current = requestAnimationFrame(step);
      } else if (p >= 1 && holding.current) {
        holding.current = false;
        setFill(0);
        approve.mutate("hold-to-confirm");
      }
    };
    raf.current = requestAnimationFrame(step);
  }, [awaiting, fired, approve]);

  const cancelHold = useCallback(() => {
    if (!holding.current) return;
    holding.current = false;
    if (raf.current) cancelAnimationFrame(raf.current);
    setFill(0);
  }, []);

  if (!awaiting) {
    return (
      <p className="zt-caption zt-approval-note">
        Approval is a one-time human signature (hold-to-confirm runs ~{Math.ceil(HOLD_MS / 1_000)} s). The demo's
        auto-approve switch lives in the Demo Director.
      </p>
    );
  }

  return (
    <div className="zt-approval">
      <button
        type="button"
        className="zt-button zt-holdbtn"
        data-variant="approve"
        aria-label="Press and hold to approve this erasure plan"
        onMouseDown={beginHold}
        onTouchStart={beginHold}
        onMouseUp={cancelHold}
        onMouseLeave={cancelHold}
        onTouchEnd={cancelHold}
        onKeyDown={(e) => {
          if (e.key === " " && !e.repeat) {
            e.preventDefault();
            beginHold();
          }
        }}
        onKeyUp={(e) => {
          if (e.key === " ") cancelHold();
        }}
      >
        <span className="zt-holdbtn-fill" style={{ width: `${fill * 100}%` }} aria-hidden="true" />
        Hold to approve erasure
      </button>
      <ul className="zt-approval-meta">
        <li>Hold for {Math.ceil(HOLD_MS / 1_000)} seconds to execute across lake, vector, cache and relational layers.</li>
        <li>Rejecting stops execution and closes the request without erasure.</li>
      </ul>
      <button type="button" className="zt-button" data-variant="danger" disabled={fired} onClick={() => reject.mutate("operator rejected")}>
        Reject
      </button>
    </div>
  );
}
