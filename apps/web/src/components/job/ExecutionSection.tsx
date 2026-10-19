import { SectionHeading } from "@/components/ui/SectionHeading";
import { jobStreamStore } from "@/hooks/useJobEvents";
import type { EventLayer } from "@/api/schemas";
import { formatCount, formatBytes, formatMs } from "@/lib/format";
import { Chip, Dot } from "@/components/ui/Chip";
import type { Tone } from "@/lib/tone";

interface LaneDef {
  layer: EventLayer;
  stage: "ERASE_CRYPTO" | "ERASE_ICEBERG" | "ERASE_VECTOR" | "ERASE_CACHE";
  title: string;
  counters: Array<{ key: string; label: string; fmt: "count" | "bytes" }>;
}

const LANES: LaneDef[] = [
  { layer: "crypto", stage: "ERASE_CRYPTO", title: "Key shred", counters: [{ key: "data_keys_destroyed", label: "data keys destroyed", fmt: "count" }] },
  {
    layer: "iceberg",
    stage: "ERASE_ICEBERG",
    title: "Lake (Iceberg on S3)",
    counters: [
      { key: "rows_deleted", label: "rows deleted", fmt: "count" },
      { key: "files_rewritten", label: "files rewritten", fmt: "count" },
      { key: "bytes_rewritten", label: "bytes rewritten", fmt: "bytes" },
      { key: "snapshots_expired", label: "snapshots expired", fmt: "count" },
      { key: "orphan_files_removed", label: "orphans removed", fmt: "count" },
      { key: "metadata_files_removed", label: "metadata purged", fmt: "count" },
      { key: "object_versions_deleted", label: "versions deleted", fmt: "count" },
      { key: "bytes_shredded", label: "bytes shredded", fmt: "bytes" },
    ],
  },
  {
    layer: "vector",
    stage: "ERASE_VECTOR",
    title: "AI memory (pgvector)",
    counters: [
      { key: "vectors_deleted", label: "vectors deleted", fmt: "count" },
      { key: "sweep_queries", label: "sweep queries", fmt: "count" },
      { key: "dead_tuples_vacuumed", label: "dead tuples vacuumed", fmt: "count" },
      { key: "vectors_deleted_remediated", label: "remediated", fmt: "count" },
    ],
  },
  {
    layer: "cache",
    stage: "ERASE_CACHE",
    title: "Semantic cache (Redis)",
    counters: [
      { key: "cache_keys_deleted", label: "cache keys flushed", fmt: "count" },
      { key: "untagged_deleted", label: "untagged found", fmt: "count" },
      { key: "persistence_rewritten", label: "persistence rewritten", fmt: "count" },
    ],
  },
];

function toneFor(status: string): Tone {
  if (status === "done") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "info";
  return "neutral";
}

/** (e) Two-speed tri-layer erasure: a thin crypto lane plus three parallel
 *  physical lanes with live counters. Numbers update in place (tabular). */
export default function ExecutionSection() {
  const view = jobStreamStore((s) => s.view);
  const started = LANES.some((l) => view.stages[l.stage].status !== "pending");

  if (!started) return null;

  return (
    <section className="zt-job-section" id="execution">
      <SectionHeading
        title="Execution"
        hint="Speed 1 destroys the per-subject key (readability gone at once). Speed 2 rewrites, expires, purges and vacuums in parallel."
      />
      <div className="zt-lanes">
        {LANES.map((lane) => {
          const st = view.stages[lane.stage];
          const validCounters = lane.counters.filter((c) => view.metrics[c.key] !== undefined);
          return (
            <div className="zt-lane" key={lane.stage}>
              <div className="zt-lane-head">
                <Dot tone={toneFor(st.status)} />
                <span className="zt-lane-title">{lane.title}</span>
                {st.durationMs ? <span className="zt-caption zt-num">{formatMs(st.durationMs)}</span> : null}
              </div>
              <p className="zt-lane-progress">{st.lastProgress ?? lane.stage.toLowerCase()}</p>
              <div className="zt-lane-counters">
                {validCounters.length === 0 ? (
                  <span className="zt-meta">waiting for first counters</span>
                ) : (
                  validCounters.map((c) => (
                    <span className="zt-counter" key={c.key}>
                      <b>
                        {c.fmt === "bytes" ? formatBytes(view.metrics[c.key] ?? 0) : formatCount(view.metrics[c.key] ?? 0)}
                      </b>
                      <span>{c.label}</span>
                    </span>
                  ))
                )}
                {lane.stage === "ERASE_CRYPTO" && view.metrics["bytes_under_key"] ? (
                  <span className="zt-counter">
                    <b>{formatBytes(view.metrics["bytes_under_key"] ?? 0)}</b>
                    <span>bytes whose key was destroyed</span>
                  </span>
                ) : null}
                {lane.stage === "ERASE_ICEBERG" && st.status === "done" ? <Chip tone="success">lane complete</Chip> : null}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
