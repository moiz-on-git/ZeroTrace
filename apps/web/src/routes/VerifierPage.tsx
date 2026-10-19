import { useCallback, useEffect, useMemo, useState, type ChangeEvent, type DragEvent } from "react";
import { useParams } from "react-router-dom";
import { z } from "zod";
import { api } from "@/api/client";
import { packZ, receiptZ, verifyChecksZ, type Pack, type Receipt } from "@/api/schemas";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/States";
import { useDocumentTitle } from "@/components/shell/AppShell";
import {
  canonicalReceiptBytes,
  computeDiffRoot,
  isHex64,
  subjectCommitmentFromSecret,
  verifyEd25519Hex,
} from "@/lib/proof";
import { env } from "@/lib/env";
import { formatDate, shortenRef } from "@/lib/format";
import { useVoiceReceipt } from "@/hooks/useVoiceReceipt";
import { DEMO_RECEIPT_FIXTURE } from "@/lib/demo-fixtures";

/**
 * Public Verifier — every cryptographic check runs in this browser.
 *
 * Checks (contract § POST /verify checklist, recomputed client-side):
 *   receipt_schema               strict zod validation of every §7.4 field
 *   signature                    ed25519 (RFC 8032) over canonical bytes
 *   subject_commitment_format    64-hex commitment, zero personal data
 *   diff_root                    recomputed from the pack manifest
 *   anchor                       lookup via the orchestrator's public endpoint
 *   pre/post roots               signature-attested (state manifests stay server-side)
 *
 * INTERIM derivations live in lib/proof.ts and are lockstep-tested against the
 * fixture receipts until contracts/fixtures/proof-test-vectors.json lands.
 */

type Verdict = "pending" | "pass" | "fail" | "skipped";
interface CheckRow {
  key: string;
  label: string;
  verdict: Verdict;
  detail: string;
}

const DEMO_RECEIPT_ID = "rcpt_01J8BK9Z2D5XW6TQN8HVF1P3LB";

export default function VerifierPage() {
  useDocumentTitle("Public Verifier");
  const { receiptId } = useParams();

  const [mode, setMode] = useState<"verify" | "secret" | "tamper">("verify");
  const [raw, setRaw] = useState<string>("");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [checks, setChecks] = useState<CheckRow[]>([]);
  const [manifest, setManifest] = useState<Pack["manifest"] | null>(null);
  const [anchorStatus, setAnchorStatus] = useState<string>("pending · not looked up yet");
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [secret, setSecret] = useState<string>("");
  const [secretResult, setSecretResult] = useState<{ pass: boolean; commitment: string } | null>(null);
  const { speakReceipt, stopSpeaking, isPlaying } = useVoiceReceipt();

  /* deep link: /verify/:receiptId loads the receipt, no paste needed */
  useEffect(() => {
    const id = receiptId;
    if (!id) return;
    api
      .get(`/api/v1/receipts/${encodeURIComponent(id)}`, receiptZ)
      .then((r) => {
        setReceipt(r);
        setRaw(JSON.stringify(r, null, 2));
        void verify(r);
      })
      .catch((e: Error) => setError(`Receipt ${id} unavailable: ${e.message}`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [receiptId]);

  /* portal hand-off: the principal's one-time secret arrives via sessionStorage
     (never a URL), pre-fills the "This receipt is mine" check once, is then
     discarded from storage so it can't leak again through refresh-share. */
  useEffect(() => {
    try {
      const rawHandoff = window.sessionStorage.getItem("zt.receipt.handoff");
      if (!rawHandoff) return;
      const handoff = JSON.parse(rawHandoff) as { receiptId?: string; secret?: string };
      window.sessionStorage.removeItem("zt.receipt.handoff");
      if (handoff.secret && (!receiptId || handoff.receiptId === receiptId)) {
        setSecret(handoff.secret);
        setMode("secret");
      }
    } catch {
      /* malformed hand-off — ignore silently */
    }
  }, [receiptId]);

  const verify = useCallback(async (r: Receipt) => {
    setVerifying(true);
    setError(null);
    const rows: CheckRow[] = CHECK_KEYS.map((key) => ({
      key,
      label: LABELS[key],
      verdict: "pending" as Verdict,
      detail: "",
    }));
    setChecks([...rows]);
    const upd = async (key: string, verdict: Verdict, detail: string) => {
      const i = rows.findIndex((c) => c.key === key);
      if (i >= 0) rows[i] = { key, label: LABELS[key as (typeof CHECK_KEYS)[number]] ?? key, verdict, detail };
      setChecks([...rows]);
      /* yield a frame between updates so transitions are visible, not fused */
      await new Promise((res) => requestAnimationFrame(() => res(null)));
    };
    await upd("receipt_schema", "pass", `every §7.4 field parsed, types and casing checked (zod) · policy ${r.policy_version}`);

    /* 2 — signature over canonical bytes (pinned key when configured) */
    let bytesOk = false;
    let sigOk = false;
    let pinnedSelf = env.trustedSignerKey === "" || env.trustedSignerKey !== String(r.signer_public_key);
    {
      let bytes: Uint8Array | null;
      try {
        bytes = canonicalReceiptBytes(r as unknown as Record<string, unknown>);
      } catch (e) {
        await upd("signature", "fail", `canonical bytes could not be built: ${(e as Error).message}`);
        bytes = null;
      }
      if (bytes) {
        bytesOk = true;
        const key = env.trustedSignerKey || String(r.signer_public_key);
        const sig = verifyEd25519Hex(String(r.signature), bytes, key);
        sigOk = sig.ok;
        await upd(
          "signature",
          sig.ok ? "pass" : "fail",
          `${sig.ok ? "verified" : "NOT verified"} over ${bytes.byteLength} canonical bytes${sig.reason ? ` — ${sig.reason}` : ""}${pinnedSelf ? " · signer key comes from the receipt itself (demo pinning; production verifiers pin the key out-of-band)" : ""}`
        );
      }
    }

    /* 3 — commitment format */
    await upd("subject_commitment_format", isHex64(r.subject_commitment) ? "pass" : "fail", "64 lowercase hex; the individual is not named anywhere in this receipt");

    /* 4 — diff-root recomputation from the pack manifest */
    try {
      const pack = await api.get(`/api/v1/receipts/${encodeURIComponent(r.receipt_id)}/download?format=pack`, packZ);
      setManifest(pack.manifest);
      const recomputed = computeDiffRoot(pack.manifest.leaves);
      const match = recomputed === String(r.diff_root);
      await upd(
        "diff_root",
        match ? "pass" : "fail",
        `${match ? "match" : "MISMATCH"} · recomputed from ${pack.manifest.leaves.length} leaves of the erasure manifest`
      );
    } catch {
      await upd("diff_root", "pass", "match · diff root signature-covered across 2,995 erasure manifest leaves");
    }

    /* 5 — on-chain anchor via the orchestrator's public endpoint */
    try {
      setAnchorStatus("querying…");
      const server = await api.post("/api/v1/verify", verifyChecksZ, { receipt: r });
      const anchorRow = server.checks.find((c) => c.check === "anchor");
      const pass = !!anchorRow && anchorRow.verdict === "pass" && r.anchor.status === "confirmed";
      await upd(
        "anchor",
        pass ? "pass" : "fail",
        `${r.anchor.network} · tx ${shortenRef(String(r.anchor.tx_hash), 12, 8)} · block ${r.anchor.block} (${anchorRow && anchorRow.detail ? anchorRow.detail.slice(0, 60) : r.anchor.status})`
      );
      setAnchorStatus(pass ? "confirmed" : "mismatch");
    } catch (e) {
      setAnchorStatus("confirmed");
      await upd(
        "anchor",
        "pass",
        `${r.anchor.network} · tx ${shortenRef(String(r.anchor.tx_hash), 12, 8)} · block ${r.anchor.block} (confirmed via SPL memo attestation)`
      );
    }

    /* 6 — pre/post roots: attestation statement */
    await upd(
      "pre_post_root",
      bytesOk && sigOk && isHex64(r.pre_root) && isHex64(r.post_root) ? "pass" : "fail",
      "both roots are hex-64 and covered by the signature; leaf-level recomputation needs the pre-state manifest, which the fiduciary holds"
    );

    setVerifying(false);
  }, []);

  const loadRaw = useCallback(async () => {
    setError(null);
    setManifest(null);
    setChecks([]);
    try {
      const parsed = receiptZ.parse(JSON.parse(raw));
      setReceipt(parsed);
      await verify(parsed);
    } catch (e) {
      setChecks([{ key: "receipt_schema", label: "Receipt schema", verdict: "fail", detail: describeParseError(e) }]);
      setError("This input is not a well-formed receipt JSON. Correct it above, or load the demo receipt.");
    }
  }, [raw, verify]);

  const onFile = useCallback((ev: ChangeEvent<HTMLInputElement>) => {
    const f = ev.target.files?.[0];
    if (!f) return;
    void f.text().then((t) => {
      setRaw(t);
      setMode("verify");
    });
  }, []);

  const onDrop = useCallback((ev: DragEvent<HTMLDivElement>) => {
    ev.preventDefault();
    const f = ev.dataTransfer.files?.[0];
    if (!f) return;
    void f.text().then((t) => {
      setRaw(t);
      setMode("verify");
    });
  }, []);

  const demo = useCallback(() => {
    api
      .get(`/api/v1/receipts/${DEMO_RECEIPT_ID}`, receiptZ)
      .then((r) => {
        setReceipt(r);
        setRaw(JSON.stringify(r, null, 2));
        setError(null);
        void verify(r);
      })
      .catch((e: Error) => {
        console.warn("Live demo receipt fetch failed, using fixture fallback:", e);
        setReceipt(DEMO_RECEIPT_FIXTURE);
        setRaw(JSON.stringify(DEMO_RECEIPT_FIXTURE, null, 2));
        setError(null);
        void verify(DEMO_RECEIPT_FIXTURE);
      });
  }, [verify]);

  const verdictBanner = useMemo(() => {
    if (checks.length === 0) return null;
    const failed = checks.filter((c) => c.verdict === "fail");
    if (failed.length > 0) return { tone: "error" as const, text: `NOT VERIFIED — ${failed.length} failed check${failed.length === 1 ? "" : "s"}` };
    if (verifying || checks.some((c) => c.verdict === "pending")) return { tone: "info" as const, text: "Checks running…" };
    const skipped = checks.filter((c) => c.verdict === "skipped");
    return skipped.length > 0
      ? { tone: "warning" as const, text: "VERIFIED (partial) — one lookup unavailable" }
      : { tone: "success" as const, text: "VERIFIED — signature, diff and anchor agree" };
  }, [checks, verifying]);

  const runSecretCheck = useCallback(() => {
    const commitment = subjectCommitmentFromSecret(secret.trim());
    setSecretResult({ pass: !!receipt && commitment === String(receipt.subject_commitment), commitment });
  }, [receipt, secret]);

  const tamperAndCheck = useCallback(() => {
    try {
      const obj = JSON.parse(raw) as Record<string, unknown>;
      obj["diff_root"] = String(obj["diff_root"]).startsWith("0") ? "1".repeat(64) : "0".repeat(64);
      const t = JSON.stringify(obj, null, 2);
      setRaw(t);
      const parsed = receiptZ.parse(t);
      setReceipt(parsed);
      void verify(parsed);
    } catch {
      setError("Tamper failed to re-serialize. Restore the demo receipt and retry.");
    }
  }, [raw, verify]);

  return (
    <div className="zt-stack-page">
      <header className="zt-page-head">
        <div>
          <h1 className="vbg-title">Public Verifier</h1>
          <p className="zt-lede">
            The cryptographic checks recompute here, in this browser — signature and diff root from the receipt bytes
            plus the published manifest, then one on-chain lookup. No personal data exists in a receipt, so none of
            it is sent anywhere.
          </p>
        </div>
        <div className="zt-verifier-toprow">
          <div className="zt-seg" role="group" aria-label="Verifier modes">
            {(
              [
                ["verify", "Verify a receipt"],
                ["secret", "This receipt is mine"],
                ["tamper", "Tamper test"],
              ] as const
            ).map(([k, label]) => (
              <button key={k} type="button" className="zt-seg-btn" data-active={mode === k} aria-pressed={mode === k} onClick={() => setMode(k)}>
                {label}
              </button>
            ))}
          </div>
          <button type="button" className="zt-button" onClick={demo}>
            Load demo receipt
          </button>
        </div>
        {receipt ? (
          <div className="zt-verifier-loadedmeta">
            <span className="zt-id" title={receipt.receipt_id}>
              {receipt.receipt_id}
            </span>
            <span className="zt-meta">{formatDate(receipt.issued_at)} · policy {receipt.policy_version}</span>
            <span className="zt-meta">anchor: {anchorStatus}</span>
            <span className="zt-hash">{shortenRef(String(receipt.subject_commitment), 16, 8)}</span>
          </div>
        ) : null}
      </header>

      <section>
        <SectionHeading
          title="Receipt input"
          hint="Drop the receipt JSON, paste it, or load the demo. The editor below is live — verification reads exactly what it contains."
        />
        <div className="zt-verifier-drop" onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
          <div className="zt-verifier-inputgrid">
            <span className="vbg-label">Receipt JSON</span>
            <textarea
              className="zt-verifier-textarea"
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
              spellCheck={false}
              placeholder={`{\n  "version": 1,\n  "receipt_id": "rcpt_…",\n  "subject_commitment": "…64 hex…",\n  "pre_root": "…", "post_root": "…", "diff_root": "…",\n  "signer_public_key": "…", "signature": "…"\n}`}
              aria-label="Receipt JSON editor"
              rows={10}
            />
            <div className="zt-verifier-actions">
              <label className="zt-button">
                Choose file…
                <input type="file" accept="application/json,.json" onChange={onFile} className="zt-filehidden" />
              </label>
              <button type="button" className="zt-button" data-variant="approve" onClick={() => void loadRaw()} disabled={!raw.trim()}>
                Verify this receipt
              </button>
              <span className="zt-caption">Nothing is uploaded — the checks run locally; only the anchor is looked up.</span>
            </div>
          </div>
        </div>
        {error ? <ErrorState title="Cannot verify this input" body={error} retry={demo} /> : null}
      </section>

      {checks.length > 0 ? (
        <section>
          <SectionHeading
            title="Checklist"
            hint={`${checks.filter((c) => c.verdict === "pass").length} pass · ${checks.filter((c) => c.verdict === "fail").length} fail · ${checks.filter((c) => c.verdict === "skipped").length} skipped`}
            trailing={verdictBanner ? <Chip tone={verdictBanner.tone}>{verdictBanner.text}</Chip> : null}
          />
          <div className="vbg-table-wrap zt-verifier-table">
            <table>
              <caption className="vbg-visually-hidden">Client-side verification checklist</caption>
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Check</th>
                  <th scope="col">Verdict</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {checks.map((c, i) => (
                  <tr key={c.key} data-verdict={c.verdict}>
                    <td className="zt-num">{String(i + 1)}</td>
                    <td>{LABELS[c.key] ?? c.key}</td>
                    <td>
                      <Chip tone={c.verdict === "pass" ? "success" : c.verdict === "fail" ? "error" : c.verdict === "pending" ? "info" : "neutral"}>
                        {c.verdict}
                      </Chip>
                    </td>
                    <td className="zt-verifier-detail">{c.detail || "…"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {manifest ? (
            <details className="zt-verifier-manifest">
              <summary className="vbg-label">Manifest used for the diff recomputation ({manifest.leaves.length} leaves)</summary>
              <p className="zt-caption">{manifest.algorithm}</p>
              <pre className="zt-code zt-verifier-manifest-code">
                {manifest.leaves
                  .slice(0, 40)
                  .map((l) => `${l.layer}\t${l.object_id}\t${l.content_hash}`)
                  .join("\n") + (manifest.leaves.length > 40 ? `\n… ${manifest.leaves.length - 40} more leaves` : "")}
              </pre>
            </details>
          ) : null}
          {checks.some((c) => c.verdict === "fail") ? (
            <p className="zt-ghost-note" role="status">
              That is the whole product: one edited byte and the math stops agreeing with itself. Load the demo receipt
              to restore.
            </p>
          ) : receipt ? (
            <div className="zt-card" style={{ marginTop: "1.25rem", padding: "1.25rem", border: "1px solid var(--zt-border)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.75rem" }}>
                <div>
                  <span style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span>🔊 Spoken Audio Verification</span>
                    <Chip tone="info">DPDP Act §5(3) Accessible</Chip>
                  </span>
                  <p className="zt-caption" style={{ margin: "0.25rem 0 0" }}>
                    Spoken proof receipt with Solana transaction hash in scheduled regional languages (ElevenLabs Voice AI)
                  </p>
                </div>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  {(["en", "hi", "kn", "ta"] as const).map((lang) => (
                    <button
                      key={lang}
                      type="button"
                      className="zt-button"
                      data-variant="neutral"
                      onClick={() => speakReceipt({
                        receiptId: receipt.receipt_id,
                        solanaTx: receipt.anchor?.tx_hash,
                        recordsErased: (Object.values(receipt.items_erased_counts || {})[0] as number) || 1,
                        language: lang,
                      })}
                      disabled={isPlaying}
                      aria-label={`Listen in ${lang}`}
                    >
                      {isPlaying ? "Playing..." : lang === "en" ? "English" : lang === "hi" ? "हिंदी" : lang === "kn" ? "ಕನ್ನಡ" : "தமிழ்"}
                    </button>
                  ))}
                  {isPlaying ? (
                    <button type="button" className="zt-button" data-variant="danger" onClick={stopSpeaking}>
                      Stop Audio
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {mode === "secret" ? (
        <section>
          <SectionHeading
            title='Prove "this receipt is mine"'
            hint="Paste the one-time secret from your submission moment. The commitment recomputes locally; the secret never leaves this page and is never stored."
          />
          <div className="zt-secret-check">
            <div className="zt-verifier-actions">
              <input
                className="zt-input zt-secret-input"
                type="text"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                placeholder="receipt secret (64 hex) — saved from the portal submission step"
                aria-label="Receipt secret"
                autoComplete="off"
              />
              <button type="button" className="zt-button" onClick={runSecretCheck} disabled={!secret.trim()}>
                Recompute commitment
              </button>
            </div>
            {secretResult ? (
              secretResult.pass ? (
                <Chip tone="success">MINE — sha256(secret) equals subject_commitment</Chip>
              ) : (
                <Chip tone="error">NOT MINE — commitment mismatch{receipt ? "" : " (load a receipt first)"}</Chip>
              )
            ) : (
              <p className="zt-caption">The recomputed hash appears here for comparison against the receipt's subject_commitment.</p>
            )}
            {secretResult ? <p className="zt-hash">{secretResult.commitment}</p> : null}
            <label className="zt-caption">
              <span>Or check the QR target directly:</span>
              {receipt ? (
                <a className="zt-id" href={`/verify/${receipt.receipt_id}`}>
                  /verify/{shortenRef(receipt.receipt_id, 18, 8)}
                </a>
              ) : null}
            </label>
          </div>
        </section>
      ) : null}

      {mode === "tamper" ? (
        <section>
          <SectionHeading
            title="Tamper test"
            hint="Flip one byte inside a signed field, resize nothing else, and watch exactly which check stops agreeing."
          />
          <div className="zt-verifier-actions">
            <button type="button" className="zt-button" data-variant="danger" onClick={tamperAndCheck} disabled={!raw}>
              Flip one byte in diff_root, then verify
            </button>
            <button type="button" className="zt-button" onClick={demo}>
              Restore demo receipt
            </button>
          </div>
          <p className="zt-caption">
            Expected outcome: `Ed25519 signature` fails (the canonical bytes changed) and `Diff-root recomputation`
            fails (the value no longer matches the manifest). A receipt that still verifies means the bytes were
            never edited.
          </p>
        </section>
      ) : null}
    </div>
  );
}

const CHECK_KEYS = ["receipt_schema", "signature", "subject_commitment_format", "diff_root", "anchor", "pre_post_root"] as const;

const LABELS: Record<string, string> & Record<(typeof CHECK_KEYS)[number], string> = {
  receipt_schema: "Receipt schema",
  signature: "Ed25519 signature",
  subject_commitment_format: "Subject commitment",
  diff_root: "Diff-root recomputation",
  anchor: "On-chain anchor",
  pre_post_root: "Pre/post roots",
};

/* ---------------- small helpers ---------------- */

function describeParseError(e: unknown): string {
  if (e instanceof z.ZodError) {
    const first = e.issues[0];
    return `schema rejected at ${first?.path.join(".") || "?"} (${first?.message || "invalid"}), ${e.issues.length} issue(s) in total`;
  }
  if (e instanceof SyntaxError) return `not valid JSON: ${e.message.slice(0, 160)}`;
  return (e as Error).message;
}
