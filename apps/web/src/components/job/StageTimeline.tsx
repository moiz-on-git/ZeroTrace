import { STAGE_ORDER, type JobEventView, type StageView } from "@/lib/event-view";
import { formatMs } from "@/lib/format";
import { Dot } from "@/components/ui/Chip";
import type { Tone } from "@/lib/tone";

function stageTone(s: StageView): Tone {
  switch (s.status) {
    case "done":
      return "success";
    case "failed":
      return "error";
    case "running":
      return "info";
    default:
      return "neutral";
  }
}

/** Pipeline timeline: the 15 §7.2 stages with status, duration and the running
 *  stage anchored in view. Pattern follows CI run views (Actions / Temporal). */
export default function StageTimeline({ view }: { view: JobEventView }) {
  const lastRound = view.auditRounds[view.auditRounds.length - 1];

  return (
    <section aria-label="Stage timeline" className="zt-tl-wrap">
      <div className="zt-tl" role="list" tabIndex={0} aria-live="polite">
        {STAGE_ORDER.map((stage) => {
          const s = view.stages[stage];
          const touched = s.status !== "pending" || stage === "INTAKE";
          if (!touched) return null;
          return (
            <div className="zt-tl-stage" data-active={s.status === "running"} role="listitem" key={stage}>
              <span className="zt-tl-marker">
                <Dot tone={stageTone(s)} />
                <span className="zt-tl-name">{stage.replace(/^ERASE_/, "").replace(/_/g, " ").toLowerCase()}</span>
              </span>
              <span className="zt-tl-duration zt-num">
                {s.durationMs ? formatMs(s.durationMs) : s.status === "running" ? "running" : ""}
              </span>
            </div>
          );
        })}
      </div>
      {view.stages.AUDIT.status === "running" && lastRound ? (
        <p className="zt-caption">
          Audit round {lastRound.round} running — earlier rounds remain visible in the audit section.
        </p>
      ) : null}
    </section>
  );
}
