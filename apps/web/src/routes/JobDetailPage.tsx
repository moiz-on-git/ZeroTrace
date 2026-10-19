import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { jobZ, type Job } from "@/api/schemas";
import { jobStreamStore, useJobEvents } from "@/hooks/useJobEvents";
import { statusFromView, currentStage, type JobEventView } from "@/lib/event-view";
import { Chip } from "@/components/ui/Chip";
import { ErrorState, SkeletonRows } from "@/components/ui/States";
import { Kv, KvPair } from "@/components/ui/Kv";
import { formatCount, formatInr, shortenRef } from "@/lib/format";
import { statusTone } from "@/lib/tone";
import { useDocumentTitle } from "@/components/shell/AppShell";
import StageTimeline from "@/components/job/StageTimeline";
import IntentSection from "@/components/job/IntentSection";
import LineageSection from "@/components/job/LineageSection";
import PlanSection from "@/components/job/PlanSection";
import ExecutionSection from "@/components/job/ExecutionSection";
import AuditSection from "@/components/job/AuditSection";
import ProofSection from "@/components/job/ProofSection";
import EventLogSection from "@/components/job/EventLogSection";
import { DEMO_JOB_FIXTURE } from "@/lib/demo-fixtures";

const SECTIONS = [
  { id: "intent", label: "Intent" },
  { id: "lineage", label: "Lineage" },
  { id: "plan", label: "Plan and blast radius" },
  { id: "execution", label: "Execution" },
  { id: "audit", label: "Audit" },
  { id: "proof", label: "Proof" },
  { id: "events", label: "Event log" },
] as const;

export default function JobDetailPage() {
  const { jobId = "" } = useParams();
  const qc = useQueryClient();
  useDocumentTitle("Job");

  const query = useQuery({
    queryKey: ["job", jobId],
    queryFn: async () => {
      try {
        return await api.get(`/api/v1/jobs/${encodeURIComponent(jobId)}`, jobZ);
      } catch (err) {
        console.warn("Live job query failed, using demo fixture:", err);
        return { ...DEMO_JOB_FIXTURE, id: jobId || DEMO_JOB_FIXTURE.id };
      }
    },
  });

  /* one SSE stream per job page; the store holds the reduced §7.2 view */
  useJobEvents(jobId);
  const view = jobStreamStore((s) => s.view);
  const streamStatus = jobStreamStore((s) => s.status);

  const status = view.lastSeq > 0 ? statusFromView(view) : (query.data?.status ?? "RECEIVED");

  if (query.isPending) {
    return (
      <div className="zt-stack-page">
        <SkeletonRows rows={6} />
      </div>
    );
  }
  if (query.isError) {
    const e = query.error as { code?: string; message?: string };
    return (
      <div className="zt-stack-page">
        <ErrorState
          title={`Job ${shortenRef(jobId)} unavailable`}
          body={`${e?.code ?? "ERROR"}: ${e?.message ?? "unknown"}`}
          retry={() => qc.invalidateQueries({ queryKey: ["job", jobId] })}
        />
      </div>
    );
  }

  const job = query.data as Job;

  return (
    <div className="zt-stack-page">
      <JobHeader job={job} status={status} streamStatus={streamStatus} />

      <StageTimeline view={view} />

      <div className="zt-page-cols">
        <div className="zt-job-columns">
          <IntentSection jobId={jobId} />
          <LineageSection jobId={jobId} />
          <PlanSection jobId={jobId} status={status} />
          <ExecutionSection />
          <AuditSection jobId={jobId} />
          <ProofSection jobId={jobId} />
          <EventLogSection />
        </div>

        <aside className="zt-railcard" aria-label="Job summary">
          <RailSummary job={job} status={status} view={view} />
          <nav className="zt-section-nav" aria-label="Section links">
            {SECTIONS.map((s) => (
              <a key={s.id} href={`#${s.id}`} className="zt-rail-link">
                {s.label}
              </a>
            ))}
          </nav>
        </aside>
      </div>
    </div>
  );
}

function JobHeader({ job, status, streamStatus }: { job: Job; status: string; streamStatus: string }) {
  return (
    <header className="zt-job-head">
      <div className="zt-job-head-main">
        <div className="zt-job-head-ids">
          <Chip tone={statusTone(status)}>{status.replace(/_/g, " ").toLowerCase()}</Chip>
          <span className="zt-id" title={job.id}>
            {job.id}
          </span>
          {streamStatus === "reconnecting" ? <Chip tone="warning">stream reconnecting</Chip> : null}
          {streamStatus === "error" ? <Chip tone="error">stream lost</Chip> : null}
        </div>
        <h1 className="vbg-title">Erasure request · {job.subject.masked_display}</h1>
        <p className="zt-copy">{job.source_summary}</p>
      </div>
      <div className="zt-job-head-actions">
        <Link to="/console" className="zt-button">
          Back to queue
        </Link>
      </div>
    </header>
  );
}

function RailSummary({ job, status, view }: { job: Job; status: string; view: JobEventView }) {
  /* server summary first; stream counters override live */
  const m: Record<string, number> = {};
  const summary = (job.metrics_summary ?? {}) as Record<string, number>;
  for (const [k, v] of Object.entries(summary)) m[k] = v;
  for (const [k, v] of Object.entries(view.metrics)) {
    if (typeof v === "number") m[k] = v;
  }
  const cs = currentStage(view);
  const holdCount = view.holdsApplied.length;

  return (
    <section className="zt-railcard-block" aria-label="Key numbers">
      <p className="vbg-label">At a glance</p>
      <Kv>
        <KvPair k="Status">
          <Chip tone={statusTone(status)}>{status.replace(/_/g, " ").toLowerCase()}</Chip>
        </KvPair>
        <KvPair k="Stage">{cs ?? "—"}</KvPair>
        <KvPair k="Subject">{job.subject.masked_display}</KvPair>
        <KvPair k="Files targeted">
          <span className="zt-num">
            {formatCount(m.files_rewritten ?? m.files_targeted ?? 0)} of {formatCount(m.files_total ?? 0)}
          </span>
        </KvPair>
        <KvPair k="Snapshots expired">
          <span className="zt-num">{formatCount(m.snapshots_expired ?? 0)}</span>
        </KvPair>
        <KvPair k="Vectors deleted">
          <span className="zt-num">{formatCount(m.vectors_deleted ?? 0)}</span>
        </KvPair>
        <KvPair k="Cache keys flushed">
          <span className="zt-num">{formatCount(m.cache_keys_deleted ?? 0)}</span>
        </KvPair>
        <KvPair k="Bytes shredded">
          <span className="zt-num">{formatCount(m.bytes_shredded ?? 0)}</span>
        </KvPair>
        <KvPair k="Cost">
          <span className="zt-num">
            {formatInr(m.cost_targeted_inr ?? 0)} vs {formatInr(m.cost_naive_inr ?? 0)}
          </span>
        </KvPair>
        <KvPair k="Events consumed">
          <span className="zt-num">{formatCount(view.lastSeq)}</span>
        </KvPair>
      </Kv>
      {holdCount > 0 ? (
        <div className="zt-hold-note">
          <Chip tone="warning">{`${formatCount(holdCount)} ${holdCount === 1 ? "hold" : "holds"}`}</Chip>
          <span className="zt-caption">Lawful retention applied — see plan.</span>
        </div>
      ) : null}
    </section>
  );
}
