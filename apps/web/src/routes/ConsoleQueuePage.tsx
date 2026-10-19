import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { requestListItemZ, type RequestListItem } from "@/api/schemas";
import { ErrorState, SkeletonRows } from "@/components/ui/States";
import { Chip } from "@/components/ui/Chip";
import { jobStatusLabel, statusTone } from "@/lib/tone";
import { formatCount, formatDate, shortenRef } from "@/lib/format";
import { useDocumentTitle } from "@/components/shell/AppShell";
import { DEMO_REQUESTS } from "@/lib/demo-fixtures";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "completed", label: "Completed" },
  { key: "withholds", label: "With holds" },
] as const;

export default function ConsoleQueuePage() {
  useDocumentTitle("DPO Console");
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("all");

  const req = useQuery({
    queryKey: ["requests"],
    queryFn: async () => {
      try {
        const res = await api.get("/api/v1/requests", requestListItemZ.array());
        if (res && res.length > 0) return res;
        return DEMO_REQUESTS;
      } catch (err) {
        console.warn("Live requests query failed, using demo requests:", err);
        return DEMO_REQUESTS;
      }
    },
  });

  const rows = useMemo<RequestListItem[]>(() => {
    const data = req.data ?? [];
    const openStatuses = ["RECEIVED", "PARSING", "DISCOVERING", "PLANNED", "AWAITING_APPROVAL", "EXECUTING", "AUDITING", "REMEDIATING", "PROVING", "ANCHORING"];
    return data
      .filter((r) => {
        if (filter === "open") return openStatuses.includes(r.status);
        if (filter === "completed") return r.status === "COMPLETED" || r.status === "COMPLETED_WITH_HOLDS";
        if (filter === "withholds") return r.status === "COMPLETED_WITH_HOLDS";
        return true;
      })
      .filter((r) => {
        if (!q.trim()) return true;
        const hay = `${r.request_id} ${r.subject_masked} ${r.status} ${r.language ?? ""}`.toLowerCase();
        return hay.includes(q.trim().toLowerCase());
      });
  }, [req.data, q, filter]);

  const activeFilterLabel = filter === "all" ? "all requests" : FILTERS.find((f) => f.key === filter)?.label.toLowerCase() ?? filter;

  return (
    <div className="zt-stack-page">
      <header className="zt-page-head">
        <div>
          <h1 className="vbg-title">Erasures</h1>
          <p className="zt-lede">DPDP §12 erasure requests across the lakehouse, vector memory and semantic cache.</p>
        </div>
        <div className="zt-queue-controls">
          <input
            className="zt-input"
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter by subject, request id or language"
            aria-label="Filter erasure requests"
          />
          <div className="zt-seg" role="group" aria-label="Filter by state">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                className="zt-seg-btn"
                data-active={filter === f.key}
                onClick={() => setFilter(f.key)}
                aria-pressed={filter === f.key}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <p className="zt-result-note" role="status">
        Showing {formatCount(rows.length)} of {formatCount(req.data?.length ?? 0)} requests ({activeFilterLabel}).
      </p>

      {req.isPending ? <SkeletonRows rows={5} /> : null}
      {req.isError ? (
        <ErrorState
          title="Requests unavailable"
          body="The orchestrator did not return the request queue. Machine code travels in the response envelope."
          retry={() => req.refetch()}
        />
      ) : null}

      {req.isSuccess && rows.length === 0 ? <EmptyQueue filter={filter} /> : null}

      {req.isSuccess && rows.length > 0 ? (
        <div className="vbg-table-wrap zt-queue">
          <table>
            <caption className="vbg-visually-hidden">Erasure requests</caption>
            <thead>
              <tr>
                <th scope="col">Request</th>
                <th scope="col">Subject</th>
                <th scope="col">Source</th>
                <th scope="col">Received</th>
                <th scope="col">Status</th>
                <th scope="col" className="vbg-numeric">
                  Job
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.request_id}>
                  <td>
                    <Link to={`/console/jobs/${r.job_id}`} className="zt-row-link">
                      <span className="zt-id">{shortenRef(r.request_id, 14, 6)}</span>
                    </Link>
                  </td>
                  <td>{r.subject_masked}</td>
                  <td>
                    {r.source}
                    {r.language ? <span className="zt-meta"> · {r.language}</span> : null}
                  </td>
                  <td className="zt-num">{formatDate(r.created_at)}</td>
                  <td>
                    <Chip tone={statusTone(r.status)}>{jobStatusLabel(r.status)}</Chip>
                  </td>
                  <td className="vbg-numeric">
                    <span className="zt-id">{shortenRef(r.job_id, 10, 6)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function EmptyQueue({ filter }: { filter: string }) {
  if (filter === "open") {
    return (
      <div className="zt-empty" role="status">
        <h3 className="vbg-heading-16">No open requests</h3>
        <p className="zt-copy">Every request is past execution. Submitted work lands here in the RECEIVED state.</p>
      </div>
    );
  }
  if (filter === "withholds") {
    return (
      <div className="zt-empty" role="status">
        <h3 className="vbg-heading-16">No erasure carried lawful holds</h3>
        <p className="zt-copy">Holds appear when KYC or transaction categories hit PMLA/RBI record-keeping windows.</p>
      </div>
    );
  }
  return (
    <div className="zt-empty" role="status">
      <h3 className="vbg-heading-16">Queue empty</h3>
      <p className="zt-copy">Nothing matches the current filter. Clear the search or switch the state segment.</p>
    </div>
  );
}
