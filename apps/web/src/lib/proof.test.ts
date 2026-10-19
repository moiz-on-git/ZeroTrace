/**
 * Proof-lockstep tests. The fixture generator (scripts/generate-fixtures.mjs)
 * signs receipts with the INTERIM derivations documented in src/lib/proof.ts.
 * These vectors prove the browser verifier recomputes the same values on the
 * shipped fixtures — the app's own test corpus unless the
 * contracts/fixtures/proof-test-vectors.json vectors are adopted.
 */
import { describe, expect, it } from "vitest";
import {
  canonicalReceiptBytes,
  computeDiffRoot,
  subjectCommitmentFromSecret,
  verifyEd25519Hex,
} from "./proof";
import successFx from "../mocks/fixtures/success.json";
import ghostFx from "../mocks/fixtures/ghost.json";
import holdsFx from "../mocks/fixtures/holds.json";

interface FixtureRe {
  receipt: Record<string, unknown>;
  manifest: { algorithm: string; leaves: Array<{ layer: string; object_id: string; content_hash: string }> };
  demo_secret: { receipt_secret: string; otp_code: string };
}

const FIXTURES: Record<"success" | "ghost" | "holds", FixtureRe> = {
  success: successFx as unknown as FixtureRe,
  ghost: ghostFx as unknown as FixtureRe,
  holds: holdsFx as unknown as FixtureRe,
};

describe("interim proof derivations", () => {
  it.concurrent.each(["success", "ghost", "holds"] as const)("fixture %s carries a genuine ed25519 signature", (name) => {
    const receipt = FIXTURES[name].receipt;
    expect(receipt.receipt_id).toMatch(/^rcpt_/);
    const bytes = canonicalReceiptBytes(receipt);
    const result = verifyEd25519Hex(String(receipt.signature), bytes, String(receipt.signer_public_key));
    expect(result).toEqual({ ok: true });
  });

  it.concurrent.each(["success", "ghost", "holds"] as const)("fixture %s diff root recomputes from the pack manifest", (name) => {
    const { receipt, manifest } = FIXTURES[name];
    expect(computeDiffRoot(manifest.leaves)).toBe(String(receipt.diff_root));
    expect(manifest.leaves.length).toBeGreaterThan(400);
  });

  it.concurrent.each(["success", "ghost", "holds"] as const)("fixture %s commitment equals sha256 of the one-time secret", (name) => {
    const { receipt, demo_secret } = FIXTURES[name];
    expect(subjectCommitmentFromSecret(demo_secret.receipt_secret)).toBe(String(receipt.subject_commitment));
    expect(demo_secret.otp_code).toMatch(/^\d{6}$/);
  });
});

describe("tamper behaviour (walks byte changes to their exact failing check)", () => {
  const { receipt, manifest } = FIXTURES.success;

  it("canon bytes exclude the signature field but keep the signer covered", () => {
    const bytes = canonicalReceiptBytes(receipt);
    const parsed = JSON.parse(new TextDecoder().decode(bytes)) as Record<string, unknown>;
    expect(parsed).not.toHaveProperty("signature");
    expect(parsed.algorithms).toHaveProperty("signature");
    expect(new TextDecoder().decode(bytes)).toContain(String(receipt.signer_public_key));
  });

  it("editing a covered field (policy_version) breaks the signature alone", () => {
    const tampered = { ...receipt, policy_version: "2026.10.2" };
    const result = verifyEd25519Hex(String(receipt.signature), canonicalReceiptBytes(tampered), String(receipt.signer_public_key));
    expect(result.ok).toBe(false);
  });

  it("editing diff_root breaks both recomputation and signature", () => {
    const tampered = { ...receipt, diff_root: "0".repeat(64) };
    expect(computeDiffRoot(manifest.leaves)).not.toBe(String(tampered.diff_root));
    const result = verifyEd25519Hex(String(receipt.signature), canonicalReceiptBytes(tampered), String(receipt.signer_public_key));
    expect(result.ok).toBe(false);
  });

  it("tampering a manifest leaf breaks only the diff recomputation (receipt bytes untouched)", () => {
    const leaves = manifest.leaves.map((l, i) => (i === 0 ? { ...l, content_hash: "0".repeat(64) } : l));
    expect(computeDiffRoot(leaves)).not.toBe(String(receipt.diff_root));
  });

  it("bad signature length formats are rejected with a readable reason", () => {
    const r = verifyEd25519Hex("ff", canonicalReceiptBytes(receipt), String(receipt.signer_public_key));
    expect(r.ok).toBe(false);
    expect(r.reason).toMatch(/64 bytes/);
  });
});
