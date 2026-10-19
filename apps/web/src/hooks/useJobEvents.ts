import { useEffect, useRef } from "react";
import { create } from "zustand";
import { jobEventZ, type JobEvent } from "@/api/schemas";
import { applyEvent, initialView, isTerminal, statusFromView, type JobEventView } from "@/lib/event-view";
import { env } from "@/lib/env";

export type StreamStatus = "idle" | "connecting" | "live" | "reconnecting" | "ended" | "error";

interface JobStreamState {
  jobId: string | null;
  status: StreamStatus;
  error?: string;
  view: JobEventView;
  events: JobEvent[];
  open: (jobId: string) => void;
  reset: () => void;
  ingest: (events: JobEvent[]) => void;
  setStatus: (s: StreamStatus, error?: string) => void;
}

/**
 * One stream per page load; events merge into the view idempotently by seq.
 * The raw list is kept for the log viewer. Derived views are pure reducer
 * output (see lib/event-view.ts), never ad-hoc counters in the UI.
 */
export const jobStreamStore = create<JobStreamState>((set) => ({
  jobId: null,
  status: "idle",
  view: initialView(),
  events: [],
  open: (jobId) => set({ jobId, status: "connecting", error: undefined, view: initialView(), events: [] }),
  reset: () => set({ jobId: null, status: "idle", view: initialView(), events: [], error: undefined }),
  ingest: (incoming) =>
    set((s) => {
      const draft = structuredClone(s.view) as JobEventView;
      const events: JobEvent[] = [...s.events];
      const fresh: JobEvent[] = [];
      for (const ev of incoming) {
        if (ev.seq <= s.view.lastSeq) continue;
        events.push(ev);
        fresh.push(ev);
        applyEvent(draft, ev);
      }
      if (fresh.length === 0) return {};
      return { events, view: draft };
    }),
  setStatus: (status, error) =>
    set((s) => {
      if (isTerminal(s.view) && (status === "ended" || status === "reconnecting")) return { status: "ended" };
      return { status, error };
    }),
}));

/**
 * Subscribes to GET /jobs/{id}/events (SSE, Last-Event-ID §7.1) and merges
 * merged batches once per animation frame so a burst of events never thrashes
 * layout. Reconnects carry ?from=<seq> for replay (the orchestrator honours
 * Last-Event-ID; the query param is additive and ignored by fresh streams).
 */
export function useJobEvents(jobId: string): StreamStatus {
  const open = jobStreamStore((s) => s.open);
  const ingest = jobStreamStore((s) => s.ingest);
  const setStatus = jobStreamStore((s) => s.setStatus);
  const counters = useRef<{ reconnects: number; from: number }>({ reconnects: 0, from: 0 });

  useEffect(() => {
    if (!jobId) return;
    open(jobId);
    let closed = false;
    let buf: JobEvent[] = [];
    let raf = 0;
    let es: EventSource | null = null;

    const flush = () => {
      raf = 0;
      if (buf.length === 0) return;
      const batched = buf;
      buf = [];
      ingest(batched);
    };

    const enqueue = (raw: MessageEvent) => {
      let json: unknown;
      try {
        json = JSON.parse(raw.data as string);
      } catch {
        return;
      }
      const parsed = jobEventZ.safeParse(json);
      if (!parsed.success) return;
      buf.push(parsed.data);
      if (raf === 0) raf = requestAnimationFrame(flush);
    };

    const connect = () => {
      if (closed) return;
      const from = counters.current.from;
      const url = `/api/v1/jobs/${encodeURIComponent(jobId)}/events${from ? `?from=${from}` : ""}`;
      es = new EventSource(url);

      es.onopen = () => {
        setStatus(counters.current.reconnects > 0 ? "reconnecting" : "live");
      };
      es.onmessage = (m) => {
        enqueue(m);
      };
      es.addEventListener("complete", () => {
        flush();
        setStatus("ended");
        es?.close();
        es = null;
      });
      es.onerror = () => {
        flush();
        if (closed) {
          es?.close();
          return;
        }
        const s = jobStreamStore.getState();
        if (isTerminal(s.view)) {
          setStatus("ended");
          es?.close();
          return;
        }
        // Streams can end mid-job (mock fixture finalize, proxy restart, deploy).
        // Retry bounded: 6 attempts in a session, backoff 700ms * 2^n capped 5s.
        if (counters.current.reconnects >= 6) {
          setStatus("error", "Event stream lost. Reconnect attempts exhausted; data may be stale.");
          es?.close();
          return;
        }
        counters.current.reconnects += 1;
        setStatus("reconnecting");
        es?.close();
        window.setTimeout(
          () => {
            counters.current.from = jobStreamStore.getState().view.lastSeq;
            connect();
          },
          Math.min(5_000, 700 * 2 ** Math.min(counters.current.reconnects, 3))
        );
      };
    };

    connect();

    return () => {
      closed = true;
      if (raf) cancelAnimationFrame(raf);
      es?.close();
    };
  }, [jobId, open, ingest, setStatus]);

  return jobStreamStore((s) => s.status);
}

export function useJobCurrentStatus(): string {
  return jobStreamStore((s) => (s.jobId ? statusFromView(s.view) : "RECEIVED"));
}

export const streamFollowEnv = env;
