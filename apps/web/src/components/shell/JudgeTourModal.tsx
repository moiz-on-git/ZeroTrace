import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

export interface JudgeTourModalProps {
  open: boolean;
  onClose: () => void;
}

interface Step {
  id: number;
  badge: string;
  title: string;
  subtitle: string;
  route: string;
  actionText: string;
  points: string[];
  techSpec: string;
  architectureHighlight: string;
}

const STEPS: Step[] = [
  {
    id: 1,
    badge: "WORKFLOW 01 · INGESTION & CONSENT",
    title: "Citizen Data Principal Portal",
    subtitle: "Constitutional Language Parity under DPDP Act §6(4) / §12(1)",
    route: "/portal",
    actionText: "Open Citizen Portal",
    points: [
      "Select ಕನ್ನಡ (Kannada), हिंदी (Hindi), or English from the language bar.",
      "Record audio via the Microphone or enter sample revocation text.",
      "Enter verification OTP code '230671' to authenticate principal ownership.",
      "Inspect the generated cryptographic receipt with Sarvam 8 kHz telephony audio synthesis.",
    ],
    techSpec: "Sarvam AI Streaming STT/TTS (8 kHz μ-law) · SHA-256 Subject Commitment · Zero PII in Receipt",
    architectureHighlight:
      "Language Parity ensures constitutional compliance. The subject commitment uses HMAC-SHA256(salt, subject_id) so the receipt reveals zero personal data to third parties.",
  },
  {
    id: 2,
    badge: "WORKFLOW 02 · ORCHESTRATION & SAGA",
    title: "DPO Console & Autonomous Saga",
    subtitle: "Two-Speed Erasure & Dynamic Lineage DAG",
    route: "/console",
    actionText: "Open DPO Console",
    points: [
      "Monitor the real-time erasure queue across lakehouse, vector index, and semantic cache.",
      "Click into any job (e.g. Ananya I•••) to inspect the Dagre/XyFlow lineage dependency graph.",
      "Verify Two-Speed Erasure: synchronous cryptographic tombstone in <500ms; asynchronous Apache Iceberg rewrite.",
      "Inspect the 79.7% query pruning cost reduction via partition blast-radius planning.",
    ],
    techSpec: "11-Stage Distributed Saga · Apache Iceberg v2 Delete Vectors · Qdrant HNSW Index · 79.7% Cost Savings",
    architectureHighlight:
      "Unlike naive SQL DELETE which causes lakehouse table locks and downtime, Two-Speed Erasure instantaneously invalidates encryption keys while Parquet files are rewritten in background micro-batches.",
  },
  {
    id: 3,
    badge: "WORKFLOW 03 · RED-TEAM FORENSICS",
    title: "Adversary Forensics Console",
    subtitle: "9 Attack Batteries Testing Residual Data Leakage",
    route: "/adversary",
    actionText: "Open Adversary Console",
    points: [
      "Select 'BEFORE' (standard SQL DELETE) and execute attacks — witness 8 residue leaks across S3 object versions, raw Parquet snapshots, and dead tuples.",
      "Select 'AFTER' (ZeroTrace) and run all 9 batteries again.",
      "Verify 0/9 residue leaks (100% clean verification across lakehouse, vectors, and caches).",
      "Stream live penetration execution logs with sub-millisecond execution timestamps.",
    ],
    techSpec: "S3 Version Scans · Parquet Raw Catalog Bypass · Qdrant Vector Extraction · RAG Prompt Injections",
    architectureHighlight:
      "Standard database erasures leave ghost embeddings in vector databases and historical snapshots in Iceberg metadata. ZeroTrace's 9 forensic sweeps mathematically prove zero residual leakage.",
  },
  {
    id: 4,
    badge: "WORKFLOW 04 · CRYPTOGRAPHIC AUDIT",
    title: "Public Cryptographic Verifier",
    subtitle: "Client-Side RFC 8032 Ed25519 & Solana Devnet Attestation",
    route: "/verify",
    actionText: "Open Public Verifier",
    points: [
      "Click 'Load Demo Receipt' to load a digitally signed compliance certificate.",
      "Observe all 6 cryptographic verification checks execute locally in the browser via WebCrypto.",
      "Validate the Merkle Diff Root recomputed across 2,995 manifest leaves.",
      "Inspect the Solana Devnet SPL Memo block anchor link confirming immutable timestamping.",
    ],
    techSpec: "RFC 8032 Ed25519 Signatures · WebCrypto API · Solana SPL Memo · BSA §63 Evidence Parity",
    architectureHighlight:
      "Full compliance with Bharatiya Sakshya Adhiniyam (BSA) §63 standards for court-admissible electronic records. Verification runs 100% client-side without relying on vendor backend servers.",
  },
  {
    id: 5,
    badge: "WORKFLOW 05 · PRESENTER RUNBOOK",
    title: "Demo Director & Pipeline Orchestration",
    subtitle: "Rapid 60-Second End-to-End System Evaluation",
    route: "/demo",
    actionText: "Open Demo Director",
    points: [
      "Execute pre-seeded end-to-end evaluation scenario with a single click.",
      "Pre-loaded with Kaveri Finserv banking workload data for enterprise evaluation.",
      "Ideal for rapid technical deep-dives and video recording demonstrations.",
    ],
    techSpec: "Kubernetes HPA Orchestration · Helm Chart Deployment · Zero-Copy Rust Data Plane",
    architectureHighlight:
      "Orchestrates all microservices with full observability, synthetic latency benchmarking, and automated preflight checks.",
  },
];

export default function JudgeTourModal({ open, onClose }: JudgeTourModalProps) {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [dontShowAgain, setDontShowAgain] = useState(false);

  useEffect(() => {
    if (dontShowAgain) {
      localStorage.setItem("zt_judge_tour_dismissed", "true");
    }
  }, [dontShowAgain]);

  if (!open) return null;

  const step: Step = STEPS[currentStep] ?? (STEPS[0] as Step);

  const handleActionClick = () => {
    navigate(step.route);
    onClose();
  };

  const handleNext = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep((prev) => prev + 1);
    } else {
      onClose();
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  return (
    <div className="zt-tour-backdrop" role="dialog" aria-modal="true" aria-labelledby="zt-tour-title">
      <div className="zt-tour-modal">
        {/* Header bar */}
        <div className="zt-tour-header">
          <div className="zt-tour-mascot-container">
            <div className="zt-tour-avatar">
              <span aria-hidden="true">🛡️</span>
            </div>
            <div>
              <div className="zt-tour-agent-name">
                <span>Technical Architecture Runbook</span>
                <span className="zt-tour-badge">DPDP §6(4) / §12(1)</span>
              </div>
              <p className="zt-tour-agent-sub">Interactive walkthrough for statutory compliance verification</p>
            </div>
          </div>
          <button
            type="button"
            className="zt-tour-close-btn"
            onClick={onClose}
            aria-label="Close Evaluation Guide"
          >
            ✕
          </button>
        </div>

        {/* Card Content */}
        <div className="zt-tour-content">
          <div className="zt-tour-step-meta">
            <span className="zt-tour-step-pill">{step.badge}</span>
            <span className="zt-tour-progress-text">Stage {step.id} of {STEPS.length}</span>
          </div>

          <h2 id="zt-tour-title" className="zt-tour-title">{step.title}</h2>
          <p className="zt-tour-subtitle">{step.subtitle}</p>

          <div className="zt-tour-instructions">
            <p className="zt-tour-instructions-heading">Evaluation Checklist:</p>
            <ul className="zt-tour-points">
              {step.points.map((pt, i) => (
                <li key={i} className="zt-tour-point-item">
                  <span className="zt-tour-point-bullet">{i + 1}</span>
                  <span>{pt}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="zt-tour-protip">
            <span className="zt-tour-protip-icon">⚙️</span>
            <p className="zt-tour-protip-text">
              <strong>Architecture Highlight:</strong> {step.architectureHighlight}
            </p>
          </div>
        </div>

        {/* Action Row */}
        <div className="zt-tour-action-row">
          <button
            type="button"
            className="zt-tour-jump-btn"
            onClick={handleActionClick}
          >
            {step.actionText} →
          </button>
        </div>

        {/* Footer with Step Dots & Controls */}
        <div className="zt-tour-footer">
          <label className="zt-tour-checkbox-label">
            <input
              type="checkbox"
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
            />
            <span>Don't auto-launch on startup</span>
          </label>

          <div className="zt-tour-dots" aria-label="Evaluation steps">
            {STEPS.map((s, idx) => (
              <button
                key={s.id}
                type="button"
                className={`zt-tour-dot ${idx === currentStep ? "active" : ""}`}
                onClick={() => setCurrentStep(idx)}
                aria-label={`Jump to stage ${s.id}: ${s.title}`}
              />
            ))}
          </div>

          <div className="zt-tour-nav-buttons">
            <button
              type="button"
              className="zt-tour-nav-btn zt-tour-prev"
              onClick={handleBack}
              disabled={currentStep === 0}
            >
              ← Back
            </button>
            <button
              type="button"
              className="zt-tour-nav-btn zt-tour-next"
              onClick={handleNext}
            >
              {currentStep === STEPS.length - 1 ? "Complete Guide ✓" : "Next Stage →"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
