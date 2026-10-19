import { useQuery } from "@tanstack/react-query";
import { auditViewZ, type AuditView } from "@/api/schemas";
import { api } from "@/api/client";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { ErrorState, SkeletonRows } from "@/components/ui/States";
import { Chip } from "@/components/ui/Chip";
import { jobStreamStore } from "@/hooks/useJobEvents";
import { attackTone } from "@/lib/tone";
import { formatCount } from "@/lib/format";
import type { AuditRound } from "@/lib/event-view";

/* server audit report → the reduced round shape produced by the stream */
function toAuditRound(sv: AuditView["rounds"][number]): AuditRound {
  return {
    round: sv.round,
    verdict: sv.verdict,
    attacks: sv.findings.map((f) => ({
      attack: f.attack,
      verdict: f.verdict,
      checked: f.checked,
      matches: f.matches,
      round: sv.round,
      message: f.description,
    })),
    collateral: sv.collateral_integrity,
    residualLocations: sv.residual_locations,
  };
}

const ATTACK_LABELS: Record<string, string> = {
  time_travel: "time travel",
  raw_parquet: "raw Parquet",
  bucket_grep: "bucket grep",
  s3_versions: "S3 versions",
  vector_lookup: "vector lookup",
  rag_prompt_injection: "RAG prompt injection",
  cache_probe: "cache probe",
  dead_tuples: "dead tuples",
  collateral: "collateral integrity",
};

/**
 * (f) Adversarial self-audit: attacks with verdict chips, masked evidence,
 * the collateral-integrity result, and remediation rounds in order — the
 * demo's fail-then-self-heal must read clearly as a sequence.
 */
export default function AuditSection({ jobId }: { jobId: string }) {
  const view = jobStreamStore((s) => s.view);
  const rounds: AuditRound[] = view.auditRounds;

  const serverAudit = useQuery({
    queryKey: ["audit", jobId],
    queryFn: () => api.get(`/api/v1/jobs/${encodeURIComponent(jobId)}/audit`, auditViewZ),
    enabled: rounds.length === 0,
  });

  if (!view.lastSeq && serverAudit.isPending) {
    return (
      <section className="zt-job-section" id="audit">
        <SectionHeading title="Audit" hint="The engine attacks its own erasure like a red team." />
        <SkeletonRows rows={3} />
      </section>
    );
  }

  const showServer = rounds.length === 0 && serverAudit.data;

  return (
    <section className="zt-job-section" id="audit">
      <SectionHeading
        title="Audit"
        hint={
          rounds.length > 0
            ? `${rounds.length} round${rounds.length === 1 ? "" : "s"} · first-class verdicts per attack`
            : "Verdicts arrive as finding events; the server view fills in the full report."
        }
      />

      {serverAudit.isError && rounds.length === 0 ? <ErrorState title="Audit unavailable" retry={() => serverAudit.refetch()} /> : null}

      {showServer && serverAudit.data
        ? (() => {
            const last = serverAudit.data.rounds.at(-1);
            return last ? <RoundTable round={toAuditRound(last)} /> : null;
          })()
        : null}

      {rounds.map((r) => (
        <article className="zt-audit-round" key={r.round}>
          <header className="zt-audit-round-head">
            <Chip tone={attackTone(r.verdict)}>{`round ${r.round} · ${r.verdict}`}</Chip>
            {r.residualLocations.length > 0 && r.verdict === "FAIL" ? (
              <span className="zt-residual-note">Residual locations: {r.residualLocations.map((l) => `${l.layer}:${l.object_id ?? "?"}`).join(" · ")}</span>
            ) : null}
          </header>
          <RoundTable round={r} />
        </article>
      ))}

      {view.remediationCount > 0 ? (
        <p className="zt-caption">
          Self-heal ran {formatCount(view.remediationCount)} round and the system re-audited before signing anything.
        </p>
      ) : null}
    </section>
  );
}

function RoundTable({ round }: { round: AuditRound | undefined }) {
  if (!round) return null;
  const rows = round.attacks.filter((a) => a.attack !== "collateral");
  const collateral = round.collateral;
  const ghost = rows.find((a) => a.special === true || a.verdict === "FOUND") ?? null;

  return (
    <div className="vbg-table-wrap zt-audit-table">
      <table>
        <caption className="vbg-visually-hidden">{`Audit round ${round.round} attack results`}</caption>
        <thead>
          <tr>
            <th scope="col">Attack</th>
            <th scope="col">Verdict</th>
            <th scope="col" className="vbg-numeric">
              Checked
            </th>
            <th scope="col" className="vbg-numeric">
              Matches
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a, i) => (
            <tr key={`${a.attack}-${i}`}>
              <td>{ATTACK_LABELS[a.attack] ?? a.attack}</td>
              <td>
                <Chip tone={attackTone(a.verdict)}>{a.verdict}</Chip>
              </td>
              <td className="vbg-numeric zt-num">{a.checked !== undefined && a.checked !== null ? formatCount(a.checked) : "—"}</td>
              <td className="vbg-numeric zt-num">{a.matches ?? 0}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>
              <strong>Collateral integrity</strong>
            </td>
            <td>
              {collateral ? (
                <Chip tone={collateral.checksum_match ? "success" : "error"}>
                  {collateral.checksum_match ? "PASS" : "MISMATCH"}
                </Chip>
              ) : (
                <span className="zt-meta">pending</span>
              )}
            </td>
            <td className="vbg-numeric zt-num">{collateral?.rows_compared !== undefined && collateral?.rows_compared !== null ? formatCount(collateral.rows_compared) : "—"}</td>
            <td className="vbg-numeric zt-num">{collateral?.other_subjects_affected ?? "—"}</td>
          </tr>
        </tfoot>
      </table>
      {ghost && ghost.verdict === "FOUND" && ghost.message ? (
        <p className="zt-ghost-note" role="status">
          <strong>Found:</strong> {ghost.message}
        </p>
      ) : null}
      {round.verdict === "FAIL" ? (
        <p className="zt-caption">No receipt is issued on a fail verdict. Remediation targets the exact residual location, then the audit re-runs.</p>
      ) : null}
    </div>
  );
}
