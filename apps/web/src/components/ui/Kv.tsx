import type { ReactNode } from "react";

/** Dense key/value rows used in rails and drawers. */
export function Kv({ children }: { children: ReactNode }) {
  return (
    <dl className="zt-meta-list">
      {children}
    </dl>
  );
}

export function KvPair({ k, children, mono }: { k: string; children: ReactNode; mono?: boolean }) {
  return (
    <>
      <dt>{k}</dt>
      <dd className={mono ? "zt-hash" : undefined}>{children}</dd>
    </>
  );
}

/** Stat rail block (foundation stat-strip semantics, app-owned host). */
export function StatStack({ label, value, detail }: { label: string; value: ReactNode; detail?: string }) {
  return (
    <div className="zt-stat">
      <p className="vbg-label">{label}</p>
      <p className="vbg-heading-20 zt-num">{value}</p>
      {detail ? <p className="zt-caption">{detail}</p> : null}
    </div>
  );
}
