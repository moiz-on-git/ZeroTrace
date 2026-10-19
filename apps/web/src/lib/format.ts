/** Formatting helpers. All numerals render with tabular figures at call sites. */

const inrFmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const numFmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export function formatInr(v: number): string {
  return `₹${inrFmt.format(v)}`;
}

export function formatCount(v: number): string {
  return numFmt.format(v);
}

export function formatPct(v: number, digits = 1): string {
  return `${v.toFixed(digits)}%`;
}

export function formatBytes(v: number): string {
  if (!Number.isFinite(v)) return "—";
  if (v < 1024) return `${v} B`;
  if (v < 1024 ** 2) return `${(v / 1024).toFixed(1)} KB`;
  if (v < 1024 ** 3) return `${(v / 1024 ** 2).toFixed(1)} MB`;
  return `${(v / 1024 ** 3).toFixed(2)} GB`;
}

/** 42_100 -> "42.1 s", 1_900 -> "1.9 s", 480 -> " 480 ms" */
export function formatMs(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  if (v < 1_000) return `${Math.round(v)} ms`;
  const s = v / 1_000;
  return `${s.toFixed(1)} s`;
}

/** elapsed ticking clock */
export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1_000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatTime(ts: string): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  const hh = d.getUTCHours().toString().padStart(2, "0");
  const mm = d.getUTCMinutes().toString().padStart(2, "0");
  const ss = d.getUTCSeconds().toString().padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

export function formatDate(ts: string): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "2-digit", timeZone: "UTC" });
}

/** Shorten hash/id strings but keep them dountable: job_01J8BJ0M…EK9XC */
export function shortenRef(id: string, head = 12, tail = 6): string {
  if (id.length <= head + tail + 1) return id;
  return `${id.slice(0, head)}…${id.slice(-tail)}`;
}
