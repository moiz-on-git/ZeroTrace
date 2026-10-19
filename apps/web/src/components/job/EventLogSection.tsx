import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { EmptyState } from "@/components/ui/States";
import { jobStreamStore } from "@/hooks/useJobEvents";
import { JOB_STAGES, type JobEvent } from "@/api/schemas";
import { formatTime, formatCount } from "@/lib/format";

const ROW_H = 22;

/**
 * (h) Event log: virtualized, monospace, filterable, with follow/pause.
 * One row per §7.2 event; dedupe is upstream (by seq). Handles bursts without
 * layout thrash since ingest batches per animation frame.
 */
export default function EventLogSection() {
  const events = jobStreamStore((s) => s.events);
  const [stageFilter, setStageFilter] = useState<string>("all");
  const [textFilter, setTextFilter] = useState("");
  const [follow, setFollow] = useState(true);
  const [newWhilePaused, setNewWhilePaused] = useState(0);
  const seenCount = useRef(0);

  const filtered = useMemo<JobEvent[]>(() => {
    const q = textFilter.trim().toLowerCase();
    return events.filter((e) => {
      if (stageFilter !== "all" && e.stage !== stageFilter) return false;
      if (!q) return true;
      return `${e.stage} ${e.kind} ${e.layer} ${e.message}`.toLowerCase().includes(q);
    });
  }, [events, stageFilter, textFilter]);

  const scrollRef = useRef<HTMLDivElement | null>(null);

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_H,
    overscan: 14,
  });

  /* follow: keep the tail in view as events land; count missed while paused */
  useEffect(() => {
    if (follow && scrollRef.current) {
      const el = scrollRef.current;
      el.scrollTop = el.scrollHeight;
      seenCount.current = events.length;
      setNewWhilePaused(0);
    } else {
      const missed = events.length - seenCount.current;
      if (missed > 0) setNewWhilePaused(missed);
    }
  }, [events.length, follow]);

  const stats = useMemo(() => {
    const byStage = new Map<string, number>();
    for (const e of events) byStage.set(e.stage, (byStage.get(e.stage) ?? 0) + 1);
    return byStage;
  }, [events]);

  return (
    <section className="zt-job-section" id="events">
      <SectionHeading
        title="Event log"
        hint={`${formatCount(events.length)} events consumed in order; SSE replay resumes from the last sequence number.`}
        trailing={
          <div className="zt-log-tools">
            <input
              className="zt-input"
              type="search"
              value={textFilter}
              onChange={(e) => setTextFilter(e.target.value)}
              placeholder="Filter log text"
              aria-label="Filter event log"
            />
            <select
              className="zt-select"
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              aria-label="Filter by stage"
            >
              <option value="all">all stages</option>
              {JOB_STAGES.filter((s) => stats.has(s)).map((s) => (
                <option key={s} value={s}>
                  {s.toLowerCase()} ({stats.get(s)})
                </option>
              ))}
            </select>
            <button
              type="button"
              className="zt-button"
              data-variant={follow ? "approve" : "neutral"}
              onClick={() => setFollow((v) => !v)}
              aria-pressed={follow}
            >
              {follow ? "Following" : "Paused"}
            </button>
          </div>
        }
      />

      {newWhilePaused > 0 ? (
        <button type="button" className="zt-resume-btn" onClick={() => setFollow(true)}>
          {formatCount(newWhilePaused)} new events — resume follow
        </button>
      ) : null}

      {events.length === 0 ? (
        <EmptyState
          title="No events yet"
          body="The stream opens with INTAKE. If this empty state persists after receiving a request, the orchestrator's event bus is down — check preflight."
        />
      ) : (
        <div className="zt-log">
          <div
            className="zt-log-scroll"
            ref={scrollRef}
            role="log"
            aria-live="off"
            aria-label="Job event stream"
            tabIndex={0}
          >
            <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
              {virtualizer.getVirtualItems().map((vi) => {
                const ev = filtered[vi.index];
                if (!ev) return null;
                return (
                  <div
                    key={ev.seq}
                    className="zt-log-row"
                    style={{ position: "absolute", top: vi.start, height: ROW_H, transform: `translateY(0)` }}
                  >
                    <span className="zt-log-seq">{ev.seq}</span>
                    <time>{formatTime(ev.ts)}</time>
                    <span className="zt-log-stage">{ev.stage.toLowerCase()}</span>
                    <span className="zt-log-kind">{ev.kind}</span>
                    <span className="zt-log-msg" title={ev.message}>
                      {ev.message}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
