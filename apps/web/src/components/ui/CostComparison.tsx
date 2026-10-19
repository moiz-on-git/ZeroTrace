import { useId } from "react";
import { formatInr, formatPct } from "@/lib/format";

/**
 * Measured cost comparison: two peer bars on ONE shared scale so the saving
 * is seen, not reconstructed. Length encodes the rupee value; zero baseline.
 */
export function CostComparison({
  naiveInr,
  targetedInr,
  savingPct,
  assumptions,
}: {
  naiveInr: number;
  targetedInr: number;
  savingPct: number;
  assumptions: string[];
}) {
  const id = useId();
  const max = Math.max(naiveInr, targetedInr) || 1;
  const rows: Array<{ label: string; value: number }> = [
    { label: "Naive full-table rewrite", value: naiveInr },
    { label: "Targeted (locator index)", value: targetedInr },
  ];

  return (
    <figure className="zt-cost-comp">
      <figcaption className="vbg-caption">
        Estimated erasure cost. Saving {formatPct(savingPct)} measured against the rewrite-all alternative.
      </figcaption>
      <div className="zt-cost-bars" role="group" aria-labelledby={`cost-${id}`}>
        <span id={`cost-${id}`} className="vbg-visually-hidden">
          Cost comparison in rupees, shared scale
        </span>
        {rows.map((r) => (
          <div className="zt-cost-row" key={r.label}>
            <span className="zt-cost-label">{r.label}</span>
            <span className="zt-cost-track">
              <span
                className="zt-cost-fill"
                data-kind={r.label.startsWith("Naive") ? "naive" : "targeted"}
                style={{ width: `${Math.max(2, (r.value / max) * 100)}%` }}
              />
            </span>
            <span className="zt-cost-value zt-num">{formatInr(r.value)}</span>
          </div>
        ))}
      </div>
      <details className="zt-cost-assumptions">
        <summary className="vbg-label">Cost-model assumptions</summary>
        <ul>
          {assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </details>
    </figure>
  );
}
