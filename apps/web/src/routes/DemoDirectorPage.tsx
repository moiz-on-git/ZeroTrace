import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/api/client";
import { preflightZ } from "@/api/schemas";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Chip, Dot } from "@/components/ui/Chip";
import { ErrorState, SkeletonRows } from "@/components/ui/States";
import { useDocumentTitle } from "@/components/shell/AppShell";
import type { Tone } from "@/lib/tone";

const okZ = z.object({ ok: z.boolean() }).passthrough();

const lightTone: Record<string, Tone> = { green: "success", amber: "warning", red: "error" };

/** Presenter control surface (full keyboard shortcuts + stopwatch land at M9).
 *  Everything here already runs against the mock orchestrator: preflight
 *  lights, scenario seeding and the reset switch. */
export default function DemoDirectorPage() {
  useDocumentTitle("Demo Director");
  const qc = useQueryClient();
  const [scenario, setScenario] = useState("success");

  const preflight = useQuery({
    queryKey: ["preflight"],
    queryFn: () => api.get("/api/v1/system/preflight", preflightZ),
    refetchInterval: 15_000,
  });

  const seed = useMutation({
    mutationFn: (scenario: string) => api.post("/api/v1/demo/seed", okZ, { profile: "showtime", scenario }),
    onSuccess: () => {
      void qc.invalidateQueries();
    },
  });
  const reset = useMutation({
    mutationFn: () => api.post("/api/v1/demo/reset", okZ),
    onSuccess: () => {
      void qc.invalidateQueries();
    },
  });

  return (
    <div className="zt-stack-page">
      <header className="zt-page-head">
        <h1 className="vbg-title">Demo Director</h1>
        <p className="zt-lede">
          Presenters only: preflight gates before the demo starts, scenario seeding, and the reset switch. Destructive
          actions ask twice on the real backend (hold-to-confirm): never mid-demo.
        </p>
      </header>

      <section>
        <SectionHeading title="Preflight" hint="Auto-refreshes every 15 s. Red or amber gates the story." />
        {preflight.isPending ? <SkeletonRows rows={6} /> : null}
        {preflight.isError ? (
          <ErrorState title="Preflight unavailable" retry={() => preflight.refetch()} />
        ) : null}
        {preflight.data ? (
          <ul className="zt-preflight">
            {preflight.data.map((c) => (
              <li key={c.component}>
                <Dot tone={lightTone[c.status] ?? "neutral"} />
                <span className="zt-preflight-name">{c.component}</span>
                <Chip tone={lightTone[c.status] ?? "neutral"}>{c.status}</Chip>
                <span className="zt-preflight-detail">{c.detail}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section>
        <SectionHeading title="Scenario" hint="Seeds the story the stream tells: A fails-then-heals, B carries holds." />
        <div className="zt-director-actions">
          <label className="zt-director-field">
            <span className="vbg-label">Scenario</span>
            <select className="zt-select" value={scenario} onChange={(e) => setScenario(e.target.value)}>
              <option value="success">A · clean erasure</option>
              <option value="ghost">B · audit fail, self-heal</option>
              <option value="holds">C · retention holds (PMLA)</option>
            </select>
          </label>
          <button type="button" className="zt-button" onClick={() => seed.mutate(scenario)} disabled={seed.isPending}>
            Seed showtime profile
          </button>
          <button
            type="button"
            className="zt-button"
            data-variant="danger"
            onClick={() => {
              if (window.confirm("Reset demo state? (Ask twice on the real backend.)")) reset.mutate();
            }}
            disabled={reset.isPending}
          >
            Reset
          </button>
        </div>
        <p className="zt-caption">
          After seeding, open the DPO console queue — the seeded scenario's job streams live from INTAKE to COMPLETE.
        </p>
      </section>
    </div>
  );
}
