/** Semantic tones. Colour always carries meaning; chips pair tone with text. */
import type { JobStatus } from "@/api/schemas";

export type Tone = "success" | "warning" | "error" | "info" | "neutral";

export function statusTone(status: string): Tone {
  switch (status) {
    case "COMPLETED":
      return "success";
    case "COMPLETED_WITH_HOLDS":
      return "warning";
    case "FAILED":
    case "REJECTED":
      return "error";
    case "AWAITING_APPROVAL":
      return "warning";
    case "EXECUTING":
    case "AUDITING":
    case "REMEDIATING":
    case "PROVING":
    case "ANCHORING":
      return "info";
    default:
      return "neutral";
  }
}

export function jobStatusLabel(s: JobStatus | string): string {
  switch (s) {
    case "COMPLETED_WITH_HOLDS":
      return "Completed · holds";
    case "AWAITING_APPROVAL":
      return "Awaiting approval";
    case "ERASE":
      return "Erasing";
    default:
      return s.charAt(0) + s.slice(1).replace(/_/g, " ").toLowerCase();
  }
}

export function attackTone(verdict: string): Tone {
  if (verdict === "FOUND" || verdict === "FAIL") return "error";
  if (verdict === "NOT_FOUND" || verdict === "PASS") return "success";
  return "neutral";
}
