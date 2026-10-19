import type { ReactNode } from "react";

/** Designed states for every surface: empty, loading (skeletons), error. */

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="zt-empty" role="status">
      <h3 className="vbg-heading-16">{title}</h3>
      <p className="zt-copy">{body}</p>
      {action}
    </div>
  );
}

export function ErrorState({ title, body, retry }: { title: string; body?: string; retry?: () => void }) {
  return (
    <div className="zt-empty" data-tone="error" role="alert">
      <h3 className="vbg-heading-16" style={{ color: "var(--vbg-color-error)" }}>
        {title}
      </h3>
      <p className="zt-copy">{body ?? "The service did not respond. The machine code is shown in the details line."}</p>
      {retry ? (
        <button type="button" className="zt-button" onClick={retry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="zt-skeleton-rows" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="zt-skeleton" style={{ height: 14, width: `${52 + ((i * 13) % 46)}%` }} />
      ))}
    </div>
  );
}
