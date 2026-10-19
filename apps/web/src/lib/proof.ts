/**
 * Client-side proof verification (§7.4 interim spec).
 *
 * The proof-spec.md / fixtures/proof-test-vectors.json are not published
 * yet, so this module implements the contract's described checks with our own
 * derivations, documented here and in CONTRACT_REQUESTS.md. When the real spec
 * lands, replace the INTERIM blocks below and re-run the fixture generator —
 * every derivation lives in exactly one function, nothing else reaches into
 * bytes or hashes.
 *
 * Interim derivations:
 * - canonical bytes  stable JSON, recursive key sort, compact separators,
 *                    `signature` field excluded.
 * - signature        ed25519 (RFC 8032) over the canonical bytes.
 * - subject_commitment  sha256 hex of the one-time receipt secret (UTF-8).
 * - diff_root        fold of leaf lines `layer \t object_id \t content_hash \n`
 *                    sorted lexicographically: h = sha256(h || line), seeded
 *                    with sha256("ZT-DIFF-V1").
 * - pre/post roots   computed by the orchestrator over full state manifests;
 *                    the browser carries no baseline, so these are attested by
 *                    the signature (any edit breaks it) and by the anchor.
 */

import { ed25519 } from "@noble/curves/ed25519.js";
import { sha256 } from "@noble/hashes/sha2.js";

const encoder = new TextEncoder();

function toHex(bytes: Uint8Array): string {
  let out = "";
  for (const b of bytes) out += b.toString(16).padStart(2, "0");
  return out;
}

/** Canonical JSON: recursive key sort, compact separators, no undefined. */
export function canonicalize(value: unknown): string {
  if (value === null || typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(",")}]`;
  if (typeof value === "object") {
    const keys = Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => v !== undefined)
      .map(([k]) => k)
      .sort();
    const body = keys.map((k) => `${JSON.stringify(k)}:${canonicalize((value as Record<string, unknown>)[k])}`).join(",");
    return `{${body}}`;
  }
  throw new TypeError(`canonicalize: unsupported value ${String(value)}`);
}

/** Canonical bytes of a receipt: every field except `signature`. */
export function canonicalReceiptBytes(receipt: Record<string, unknown>): Uint8Array {
  const body = { ...receipt } as Record<string, unknown>;
  delete body.signature;
  return encoder.encode(canonicalize(body));
}

export function sha256Hex(data: string | Uint8Array): string {
  const bytes = typeof data === "string" ? encoder.encode(data) : data;
  return toHex(sha256(bytes));
}

/** INTERIM: the one-time secret commits via plain sha256 hex. */
export function subjectCommitmentFromSecret(secret: string): string {
  return sha256Hex(encoder.encode(secret));
}

/* ---------------- ed25519 signature ---------------- */

export function verifyEd25519Hex(signatureHex: string, message: Uint8Array, publicKeyHex: string): { ok: boolean; reason?: string } {
  const parse = (h: string, want: number): Uint8Array | null => {
    if (!/^[0-9a-fA-F]+$/.test(h)) return null;
    if (h.length !== want * 2) return null;
    return Uint8Array.from(h.match(/.{2}/g)!.map((p) => parseInt(p, 16)));
  };
  const sig = parse(signatureHex, 64);
  const pub = parse(publicKeyHex, 32);
  if (!sig) return { ok: false, reason: `signature must be 64 bytes of hex (got ${signatureHex.length / 2})` };
  if (!pub) return { ok: false, reason: `public key must be 32 bytes of hex (got ${publicKeyHex.length / 2})` };
  try {
    return { ok: ed25519.verify(sig, message, pub) };
  } catch (e) {
    return { ok: false, reason: e instanceof Error ? e.message : "verification threw" };
  }
}

/* ---------------- diff-root recomputation ---------------- */

export interface ManifestLeaf {
  layer: string;
  object_id: string;
  content_hash: string;
}

export const DIFF_SEED = sha256Hex(encoder.encode("ZT-DIFF-V1"));

function leafLine(leaf: ManifestLeaf): string {
  return `${leaf.layer}\t${leaf.object_id}\t${leaf.content_hash}\n`;
}

export function leafListCanonicalOrder(leaves: ManifestLeaf[]): string[] {
  return leaves.map(leafLine).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
}

/** INTERIM: linear sha256 fold over the sorted leaf lines. */
export function computeDiffRoot(leaves: Array<{ layer: string; object_id: string; content_hash: string }>): string {
  let roll = DIFF_SEED;
  for (const line of leafListCanonicalOrder(leaves)) {
    roll = sha256Hex(roll + line);
  }
  return roll;
}

/* ---------------- shared check helpers ---------------- */

const HEX64 = /^[0-9a-f]{64}$/;

export function isHex64(v: unknown): boolean {
  return typeof v === "string" && HEX64.test(v);
}

export interface ProofCheck {
  check: string;
  verdict: "pass" | "fail" | "skipped";
  detail: string;
}

/** Reveal one character substitution for the demo tamper test. */
export function rebukeOneChar(s: string, index: number, replacement: string): string {
  return index < 0 || index >= s.length ? s : s.slice(0, index) + replacement + s.slice(index + 1);
}
