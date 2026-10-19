import type { ReactNode } from "react";

/** Section header: heading + optional lede + optional trailing control. */
export function SectionHeading({
  title,
  hint,
  trailing,
  id,
}: {
  title: string;
  hint?: string;
  trailing?: ReactNode;
  id?: string;
}) {
  return (
    <div className="zt-section-head" id={id}>
      <div className="zt-section-head-text">
        <h2 className="vbg-heading-20">{title}</h2>
        {hint ? <p className="zt-section-hint">{hint}</p> : null}
      </div>
      {trailing ? <div className="zt-section-trailing">{trailing}</div> : null}
    </div>
  );
}
