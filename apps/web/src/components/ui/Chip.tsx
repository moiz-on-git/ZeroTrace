import type { ReactNode } from "react";
import type { Tone } from "@/lib/tone";

/** Status/verdict chip. The visible text is the primary cue; tone colours it. */
export function Chip({
  tone = "neutral",
  children,
  mono,
}: {
  tone?: Tone;
  children: ReactNode;
  mono?: boolean;
}) {
  return (
    <span className="zt-chip" data-tone={tone} aria-label={undefined}>
      {mono ? <span className="zt-id">{children}</span> : children}
    </span>
  );
}

/** Stage dot for timelines (colour + adjacent text carry the state). */
export function Dot({ tone }: { tone: Tone }) {
  return <span className="zt-tl-dot" data-tone={tone} aria-hidden="true" />;
}
