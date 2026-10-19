import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/api/client";
import { agentTraceZ, intentZ } from "@/api/schemas";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { ErrorState, SkeletonRows } from "@/components/ui/States";
import { Chip } from "@/components/ui/Chip";
import { formatMs } from "@/lib/format";

/** (a) Intent card: transcript, classification, masked identifiers, statutes,
 *  plus the bounded agent loop trace. Identifiers are masked server-side. */
export default function IntentSection({ jobId }: { jobId: string }) {
  const intent = useQuery({
    queryKey: ["intent", jobId],
    queryFn: () => api.get(`/api/v1/jobs/${encodeURIComponent(jobId)}/intent`, intentZ),
  });
  const trace = useQuery({
    queryKey: ["agent-trace", jobId],
    queryFn: () => api.get(`/api/v1/jobs/${encodeURIComponent(jobId)}/agent-trace`, agentTraceZ),
  });
  const [showTrace, setShowTrace] = useState(false);

  return (
    <section className="zt-job-section" id="intent">
      <SectionHeading
        title="Legal intent"
        hint="Parsed from the subject's own words. Statutory citations require legal review."
      />

      {intent.isPending ? <SkeletonRows rows={4} /> : null}
      {intent.isError ? (
        <ErrorState title="Intent unavailable" body="The intent lookup did not respond." retry={() => intent.refetch()} />
      ) : null}

      {intent.data ? (
        <div className="zt-intent-grid">
          <div className="zt-intent-transcript">
            <p className="vbg-label">{`${intent.data.source.language_label} · voice`}</p>
            <blockquote className="zt-transcript" lang={intent.data.source.language}>
              {intent.data.transcript.raw}
            </blockquote>
            <p className="zt-caption" lang="en">
              English rendering: {intent.data.transcript.english}
            </p>
          </div>

          <div className="zt-intent-facts">
            <div className="zt-intent-chips">
              <Chip tone="success">{intent.data.classification.intent.replace(/_/g, " ").toLowerCase()}</Chip>
              <Chip tone="warning">consent {intent.data.classification.consent_state.replace("_", " ").toLowerCase()}</Chip>
              <Chip tone="neutral">scope {intent.data.classification.scope.replace(/_/g, " ").toLowerCase()}</Chip>
            </div>
            <dl className="zt-meta-list">
              <dt>Confidence</dt>
              <dd className="zt-num">{Math.round(intent.data.classification.confidence * 100)}%</dd>
              <dt>Identifiers</dt>
              <dd>
                {intent.data.identifiers_masked.map((i) => (
                  <span className="zt-id zt-maskchip" key={i.type} title={i.type}>
                    {i.masked}
                  </span>
                ))}
              </dd>
              <dt>Verification</dt>
              <dd>
                {intent.data.verification.mode} · {intent.data.verification.status}
              </dd>
              <dt>Parser</dt>
              <dd>{intent.data.parsed_by}</dd>
            </dl>

            <div className="zt-statutes">
              <p className="vbg-label">Statutory basis</p>
              <ul className="zt-statute-list">
                {intent.data.statutes.map((s) => (
                  <li key={s.cite}>
                    <span className="zt-statute-cite">{s.cite}</span>
                    <span className="zt-statute-what">{s.what}</span>
                    {s.legal_review_required ? <Chip tone="warning">legal review</Chip> : null}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ) : null}

      {trace.data && trace.data.length > 0 ? (
        <div className="zt-agent-trace">
          <button type="button" className="zt-button" onClick={() => setShowTrace((v) => !v)} aria-expanded={showTrace} data-variant="neutral">
            {showTrace ? "Hide" : "Show"} agent trace ({trace.data.length} steps)
          </button>
          {showTrace ? (
            <div className="vbg-table-wrap zt-trace-table">
              <table>
                <thead>
                  <tr>
                    <th scope="col" className="vbg-numeric">
                      Step
                    </th>
                    <th scope="col">Tool</th>
                    <th scope="col">Call</th>
                    <th scope="col">Result</th>
                    <th scope="col" className="vbg-numeric">
                      Time
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {trace.data.map((s) => (
                    <tr key={s.i}>
                      <td className="vbg-numeric zt-num">{s.i}</td>
                      <td>
                        <span className="zt-id">{s.tool}</span>
                      </td>
                      <td>{s.action}</td>
                      <td className="zt-trace-result">{s.result}</td>
                      <td className="vbg-numeric zt-num">{formatMs(s.duration_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
