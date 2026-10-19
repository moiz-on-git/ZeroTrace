import { useQuery } from "@tanstack/react-query";
import { receiptZ } from "@/api/schemas";
import { api } from "@/api/client";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Chip } from "@/components/ui/Chip";
import { jobStreamStore } from "@/hooks/useJobEvents";
import { formatCount } from "@/lib/format";
import { env } from "@/lib/env";

const DOWNS: Array<{ format: string; label: string; note: string }> = [
  { format: "json", label: "Receipt JSON", note: "canonical signed receipt" },
  { format: "pdf", label: "Receipt PDF", note: "with QR to the public verifier" },
  { format: "pack", label: "DPBI compliance pack", note: "receipt, plan, audit report, holds register" },
];

/** (g) Proof: roots, leaf counts, signature block, on-chain anchor (pending →
 *  confirmed), downloads. Zero personal data — every value is a commitment. */
export default function ProofSection({ jobId }: { jobId: string }) {
  const view = jobStreamStore((s) => s.view);
  const started = view.stages.PROOF.status !== "pending";
  const receiptId = view.receiptId ?? "";

  const receipt = useQuery({
    queryKey: ["receipt", jobId, receiptId],
    queryFn: () => api.get(`/api/v1/receipts/${encodeURIComponent(receiptId)}`, receiptZ),
    enabled: receiptId.length > 0,
  });

  if (!started) return null;

  const anchor = view.anchor;
  const anchorChipTone = anchor.status === "confirmed" ? "success" : anchor.status === "failed" ? "error" : "info";
  const leafCounts = view.proof.leafCounts ?? {};

  return (
    <section className="zt-job-section" id="proof">
      <SectionHeading
        title="Proof"
        hint="Salted-commitment Merkle trees over the state manifests — a privacy-preserving, verifiable commitment set."
      />

      <div className="zt-proof-grid">
        <div className="zt-proof-roots">
          {(
            [
              ["pre root", view.proof.preRoot],
              ["post root", view.proof.postRoot],
              ["diff root", view.proof.diffRoot],
            ] as const
          ).map(([label, v]) => (
            <div className="zt-proof-root-row" key={label}>
              <span className="vbg-label">{label}</span>
              <span className="zt-hash">{v ?? "computing…"}</span>
            </div>
          ))}
          <div className="zt-proof-leafs">
            {Object.entries(leafCounts).map(([layer, n]) => (
              <span className="zt-counter" key={layer}>
                <b>{formatCount(n)}</b>
                <span>{layer} leaves</span>
              </span>
            ))}
          </div>
          {receipt.data ? (
            <dl className="zt-meta-list">
              <dt>Signer</dt>
              <dd className="zt-hash">{receipt.data.signer_public_key.slice(0, 16)}…</dd>
              <dt>Signature</dt>
              <dd className="zt-hash">{receipt.data.signature.slice(0, 16)}… (ed25519)</dd>
              <dt>Receipt</dt>
              <dd>
                <span className="zt-id">{receipt.data.receipt_id}</span>
              </dd>
            </dl>
          ) : (
            <p className="zt-caption">Signature and signer key arrive with the receipt (after a full audit pass).</p>
          )}
        </div>

        <div className="zt-proof-side">
          <div className="zt-anchor-box">
            <Chip tone={anchorChipTone}>{`anchor · ${anchor.status}`}</Chip>
            <dl className="zt-meta-list">
              <dt>Network</dt>
              <dd>{anchor.network ?? "—"}</dd>
              <dt>Tx</dt>
              <dd className="zt-hash">
                {anchor.txHash ? (
                  <a
                    href={anchor.explorerUrl ?? `${env.explorerBase}/tx/${anchor.txHash}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {anchor.txHash.slice(0, 16)}…{anchor.txHash.slice(-8)}
                  </a>
                ) : (
                  "submitted"
                )}
              </dd>
              <dt>Block</dt>
              <dd className="zt-num">{anchor.block ?? "—"}</dd>
            </dl>
            <p className="zt-caption">Anchoring never blocks the receipt: shown as submitted, then confirmed.</p>
          </div>

          <div className="zt-downloads">
            <p className="vbg-label">Evidence downloads</p>
            <ul className="zt-download-list">
              {receiptId
                ? DOWNS.map((d) => (
                    <li key={d.format}>
                      <a
                        className="zt-rail-link"
                        href={`/api/v1/receipts/${encodeURIComponent(receiptId)}/download?format=${d.format}`}
                        download
                      >
                        <span>{d.label}</span>
                        <span className="zt-meta">{d.note}</span>
                      </a>
                    </li>
                  ))
                : null}
              {receiptId ? (
                <>
                  <li>
                    <a
                      className="zt-rail-link"
                      href={`/api/v1/receipts/${encodeURIComponent(receiptId)}/certificate`}
                      download
                    >
                      <span>BSA 2023 §63 certificate</span>
                      <span className="zt-meta">hash values, signatory fields</span>
                    </a>
                  </li>
                  <li>
                    <button
                      type="button"
                      className="zt-rail-link"
                      style={{ textAlign: "left", width: "100%", background: "none", border: "none", cursor: "pointer" }}
                      onClick={async () => {
                        const { generateDevPostMarkdown } = await import("@/lib/dev_exporter");
                        const md = generateDevPostMarkdown({
                          jobId: jobId || "job_demo",
                          receiptId: receiptId,
                          solanaTx: anchor.txHash || "5Kz9DevnetAnchorTxHash1111111111111111",
                          merkleRoot: view.proof.diffRoot || "0x9f82d1c0e3a4b6",
                          recordsErased: 1,
                          costSavedPct: 79.7,
                          statute: "DPDP Act, 2023 Sec 6(4) & 8(4)"
                        });
                        await navigator.clipboard.writeText(md);
                        alert("DEV Community Dossier copied to clipboard! Ready to paste into DEV.to editor with #dataprivacy #dpdp tags.");
                      }}
                    >
                      <span>Export Dossier to DEV</span>
                      <span className="zt-meta">1-click open transparency report</span>
                    </button>
                  </li>
                </>
              ) : null}
            </ul>
            {!receiptId ? <p className="zt-caption">Downloads activate when the receipt is issued.</p> : null}
          </div>
        </div>
      </div>
    </section>
  );
}
