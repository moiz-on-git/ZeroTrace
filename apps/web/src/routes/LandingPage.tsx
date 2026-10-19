import { Link } from "react-router-dom";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Chip } from "@/components/ui/Chip";
import { useDocumentTitle } from "@/components/shell/AppShell";

/* ------------------------------------------------------------------ */
/*  SVG diagram: Lakehouse time-travel trap                           */
/* ------------------------------------------------------------------ */
function TrapLakeDiagram() {
  return (
    <svg
      className="zt-trap-svg"
      viewBox="0 0 320 160"
      fill="none"
      aria-label="Diagram: SQL DELETE writes a position-delete file but the original Parquet data remains on disk, reachable from historical snapshots."
      role="img"
    >
      <rect x="16" y="20" width="88" height="48" rx="3" stroke="var(--vbg-border-strong)" strokeWidth="1" fill="var(--vbg-surface-secondary)" />
      <text x="60" y="40" textAnchor="middle" className="zt-trap-svg-label">Parquet file</text>
      <text x="60" y="54" textAnchor="middle" className="zt-trap-svg-sublabel">PII rows intact</text>

      <line x1="108" y1="44" x2="148" y2="44" stroke="var(--vbg-color-error)" strokeWidth="1" strokeDasharray="4 3" />
      <polygon points="146,40 154,44 146,48" fill="var(--vbg-color-error)" />
      <text x="131" y="36" textAnchor="middle" className="zt-trap-svg-tiny">DELETE</text>

      <rect x="156" y="20" width="88" height="48" rx="3" stroke="var(--vbg-color-warning)" strokeWidth="1" fill="var(--vbg-surface-primary)" />
      <text x="200" y="40" textAnchor="middle" className="zt-trap-svg-label">pos-delete</text>
      <text x="200" y="54" textAnchor="middle" className="zt-trap-svg-sublabel">marks rows</text>

      <rect x="156" y="92" width="88" height="40" rx="3" stroke="var(--vbg-border-strong)" strokeWidth="1" fill="var(--vbg-surface-secondary)" />
      <text x="200" y="109" textAnchor="middle" className="zt-trap-svg-label">snapshot v2</text>
      <text x="200" y="123" textAnchor="middle" className="zt-trap-svg-sublabel">time-travel</text>

      <line x1="168" y1="92" x2="80" y2="72" stroke="var(--vbg-color-error)" strokeWidth="1" />
      <polygon points="82,68 76,74 86,74" fill="var(--vbg-color-error)" />

      <text x="104" y="86" textAnchor="middle" className="zt-trap-svg-warn">data still reachable</text>

      <rect x="256" y="92" width="52" height="40" rx="3" stroke="var(--vbg-border-default)" strokeWidth="1" fill="var(--vbg-surface-secondary)" />
      <text x="282" y="109" textAnchor="middle" className="zt-trap-svg-label">S3</text>
      <text x="282" y="123" textAnchor="middle" className="zt-trap-svg-sublabel">versions</text>

      <line x1="244" y1="112" x2="254" y2="112" stroke="var(--vbg-border-strong)" strokeWidth="1" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  SVG diagram: Ghost embedding trap                                 */
/* ------------------------------------------------------------------ */
function TrapVectorDiagram() {
  return (
    <svg
      className="zt-trap-svg"
      viewBox="0 0 320 160"
      fill="none"
      aria-label="Diagram: Deleting primary data leaves embeddings in the vector database. A RAG pipeline can reconstruct PII from them."
      role="img"
    >
      <rect x="16" y="20" width="72" height="44" rx="3" stroke="var(--vbg-border-strong)" strokeWidth="1" fill="var(--vbg-surface-secondary)" />
      <text x="52" y="38" textAnchor="middle" className="zt-trap-svg-label">Primary DB</text>
      <text x="52" y="52" textAnchor="middle" className="zt-trap-svg-sublabel">row deleted</text>

      <line x1="24" y1="45" x2="80" y2="45" stroke="var(--vbg-color-success)" strokeWidth="1" />

      <line x1="52" y1="68" x2="52" y2="88" stroke="var(--vbg-border-strong)" strokeWidth="1" strokeDasharray="3 2" />
      <text x="52" y="82" textAnchor="middle" className="zt-trap-svg-tiny">embed</text>

      <rect x="16" y="92" width="72" height="44" rx="3" stroke="var(--vbg-color-error)" strokeWidth="1" fill="var(--vbg-surface-primary)" />
      <text x="52" y="110" textAnchor="middle" className="zt-trap-svg-label">Vector DB</text>
      <text x="52" y="124" textAnchor="middle" className="zt-trap-svg-warn">embedding lives</text>

      <line x1="92" y1="114" x2="136" y2="114" stroke="var(--vbg-color-error)" strokeWidth="1" />
      <polygon points="134,110 142,114 134,118" fill="var(--vbg-color-error)" />

      <rect x="144" y="92" width="72" height="44" rx="3" stroke="var(--vbg-border-strong)" strokeWidth="1" fill="var(--vbg-surface-secondary)" />
      <text x="180" y="110" textAnchor="middle" className="zt-trap-svg-label">RAG query</text>
      <text x="180" y="124" textAnchor="middle" className="zt-trap-svg-sublabel">retrieves PII</text>

      <rect x="232" y="20" width="72" height="44" rx="3" stroke="var(--vbg-color-warning)" strokeWidth="1" fill="var(--vbg-surface-primary)" />
      <text x="268" y="38" textAnchor="middle" className="zt-trap-svg-label">Redis cache</text>
      <text x="268" y="52" textAnchor="middle" className="zt-trap-svg-sublabel">stale answer</text>

      <line x1="180" y1="92" x2="250" y2="68" stroke="var(--vbg-border-strong)" strokeWidth="1" strokeDasharray="3 2" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  SVG diagram: Audit paradox trap                                   */
/* ------------------------------------------------------------------ */
function TrapAuditDiagram() {
  return (
    <svg
      className="zt-trap-svg"
      viewBox="0 0 320 140"
      fill="none"
      aria-label="Diagram: Traditional audit logs store the subject's identifier, creating a data-minimisation violation. ZeroTrace uses a hash commitment instead."
      role="img"
    >
      <rect x="16" y="16" width="128" height="48" rx="3" stroke="var(--vbg-color-error)" strokeWidth="1" fill="var(--vbg-surface-primary)" />
      <text x="80" y="34" textAnchor="middle" className="zt-trap-svg-label">Audit log</text>
      <text x="80" y="48" textAnchor="middle" className="zt-trap-svg-sublabel">subject: Priya Nair</text>

      <line x1="148" y1="32" x2="164" y2="48" stroke="var(--vbg-color-error)" strokeWidth="1.5" />
      <line x1="164" y1="32" x2="148" y2="48" stroke="var(--vbg-color-error)" strokeWidth="1.5" />

      <text x="80" y="82" textAnchor="middle" className="zt-trap-svg-warn">violates minimisation</text>

      <rect x="180" y="16" width="128" height="48" rx="3" stroke="var(--vbg-color-success)" strokeWidth="1" fill="var(--vbg-surface-primary)" />
      <text x="244" y="34" textAnchor="middle" className="zt-trap-svg-label">ZT receipt</text>
      <text x="244" y="48" textAnchor="middle" className="zt-trap-svg-sublabel">H(secret ‖ id)</text>

      <line x1="312" y1="34" x2="318" y2="42" stroke="var(--vbg-color-success)" strokeWidth="1.5" />
      <line x1="318" y1="42" x2="330" y2="26" stroke="var(--vbg-color-success)" strokeWidth="1.5" />

      <text x="244" y="82" textAnchor="middle" className="zt-trap-svg-ok">no PII in proof</text>

      <rect x="180" y="96" width="128" height="34" rx="3" stroke="var(--vbg-border-default)" strokeWidth="1" fill="var(--vbg-surface-secondary)" />
      <text x="244" y="114" textAnchor="middle" className="zt-trap-svg-label">browser verifies</text>
      <text x="244" y="126" textAnchor="middle" className="zt-trap-svg-sublabel">trustless, client-side</text>

      <line x1="244" y1="68" x2="244" y2="94" stroke="var(--vbg-border-strong)" strokeWidth="1" />
      <polygon points="240,92 244,98 248,92" fill="var(--vbg-border-strong)" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  SVG: Pipeline architecture with clickable stage links             */
/* ------------------------------------------------------------------ */
function PipelineDiagram() {
  const stages = [
    { label: "Intake", sub: "voice / text", to: "/portal", tag: "PORTAL" },
    { label: "Parse", sub: "NLU + Sarvam", to: "/console/jobs/job_01J8BJ0M3Q7W4N8H2RGT6EK9XC#intent", tag: "NLU" },
    { label: "Discover", sub: "lineage graph", to: "/console/jobs/job_01J8BJ0M3Q7W4N8H2RGT6EK9XC#lineage", tag: "GRAPH" },
    { label: "Policy", sub: "DPDP + PMLA", to: "/console/policies", tag: "RULES" },
    { label: "Plan", sub: "blast radius", to: "/console/jobs/job_01J8BJ0M3Q7W4N8H2RGT6EK9XC#plan", tag: "HEATMAP" },
    { label: "Erase", sub: "lake · vec · cache", to: "/console/jobs/job_01J8BJ0M3Q7W4N8H2RGT6EK9XC#execution", tag: "SHRED" },
    { label: "Audit", sub: "adversarial", to: "/adversary", tag: "RED-TEAM" },
    { label: "Proof", sub: "Merkle + chain", to: "/verify", tag: "ED25519" },
  ];

  return (
    <div className="zt-pipe-grid-interactive">
      {stages.map((s, idx) => (
        <Link key={s.label} to={s.to} className="zt-pipe-node-link" title={`Inspect ${s.label} internal structure`}>
          <div className="zt-pipe-node-header">
            <span className="zt-pipe-idx">{String(idx + 1).padStart(2, "0")}</span>
            <span className="zt-pipe-tag">{s.tag}</span>
          </div>
          <strong className="zt-pipe-title">{s.label}</strong>
          <span className="zt-pipe-sublabel">{s.sub}</span>
          <span className="zt-pipe-arrow">Inspect &rarr;</span>
        </Link>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Internal architecture gateways (the transfer hubs)                */
/* ------------------------------------------------------------------ */
interface GatewayCard {
  role: string;
  title: string;
  path: string;
  lede: string;
  highlights: string[];
  badge: string;
  badgeTone: "success" | "warning" | "info" | "neutral";
  cta: string;
}

const INTERNAL_GATEWAYS: GatewayCard[] = [
  {
    role: "DATA PRINCIPAL",
    title: "Citizen Intake & Receipt Portal",
    path: "/portal",
    badge: "Public · Mobile-first",
    badgeTone: "info",
    lede: "Voice recording in 5 Indian languages (Hindi, Kannada, Tamil, Telugu, English) with real-time Web Audio waveform analysis, OTP verification, live pipeline status tracker, and client-held receipt secrets.",
    highlights: [
      "Speech-to-text intake via Sarvam AI & Web Audio API",
      "Live 6-step erasure state tracker over SSE",
      "Cryptographic receipt with zero-knowledge commitment",
      "One-time secret download & QR verification code"
    ],
    cta: "Launch Principal Portal",
  },
  {
    role: "DATA PROTECTION OFFICER",
    title: "DPO Orchestration Console",
    path: "/console",
    badge: "Dense · Desktop-first",
    badgeTone: "neutral",
    lede: "Enterprise control surface with live queue, 15-stage pipeline timeline, NLU intent reasoning, interactive @xyflow lineage graph, 480-file blast radius heat grid, and parallel execution telemetry.",
    highlights: [
      "Live requests queue with SLA countdown & filters",
      "Lineage DAG across Postgres, Iceberg, pgvector, Redis",
      "Blast radius heatmap (3 of 480 targeted Parquet files)",
      "Hold-to-confirm approval & virtualized event stream"
    ],
    cta: "Open DPO Console",
  },
  {
    role: "RED TEAM / EXAMINER",
    title: "Adversary Forensics Console",
    path: "/adversary",
    badge: "Dual-Baseline Split",
    badgeTone: "warning",
    lede: "Side-by-side comparison proving standard SQL DELETE leaves recoverable residue across snapshots, versioned S3 objects, unlinked embeddings, and cached answers, while ZeroTrace leaves zero residue.",
    highlights: [
      "9 live attacks: Iceberg time travel, raw Parquet, S3 versions",
      "RAG prompt injection & Redis semantic cache probes",
      "BEFORE (naive delete) vs AFTER (ZeroTrace) split view",
      "Masked forensic evidence with definitive FOUND/NOT_FOUND verdicts"
    ],
    cta: "Launch Adversary Console",
  },
  {
    role: "INDEPENDENT AUDITOR",
    title: "Trustless Public Verifier",
    path: "/verify",
    badge: "100% Client-Side Crypto",
    badgeTone: "success",
    lede: "Zero-trust verification executed entirely inside the browser using Web Crypto API and Noble Ed25519. Validates digital signatures, recomputes Merkle diff roots, and tests for ledger tampering in real time.",
    highlights: [
      "Ed25519 signature verification without server trust",
      "Client-side Merkle root recomputation from manifest",
      "Live tamper laboratory: mutate any byte to watch checks fail",
      "Data principal secret verification (H(secret || id))"
    ],
    cta: "Open Public Verifier",
  },
  {
    role: "EXECUTIVE / AUDITOR",
    title: "Platform Telemetry & Cost Model",
    path: "/console/impact",
    badge: "Telemetry & ROI",
    badgeTone: "info",
    lede: "Aggregate operational metrics detailing completed erasures, shredded bytes, and measured infrastructure cost reductions achieved through Bloom-filter guided targeted rewriting.",
    highlights: [
      "3,412+ shredded objects across Iceberg, pgvector & Redis",
      "73.4% cost savings over brute-force full table scans",
      "On-chain anchor status & active statutory hold counters",
      "Production-level infrastructure metrics"
    ],
    cta: "View Platform Impact",
  },
  {
    role: "LEGAL & COMPLIANCE",
    title: "Statutory Retention Rulebook",
    path: "/console/policies",
    badge: "DPDP + PMLA + RBI",
    badgeTone: "warning",
    lede: "Configurable compliance matrix governing which data categories are immediately purged upon consent withdrawal and which must be held under statutory anti-money laundering and banking laws.",
    highlights: [
      "DPDP Act 2023 §6(6) & §12(1) immediate erasure mappings",
      "PMLA 2002 §12 & RBI Master Direction 5-year retention holds",
      "Encrypted retention vault scheduling with automated future purge",
      "Mandatory 'requires legal review' compliance citations"
    ],
    cta: "Inspect Policies",
  },
];

/* ------------------------------------------------------------------ */
/*  Main landing component                                            */
/* ------------------------------------------------------------------ */
export default function LandingPage() {
  useDocumentTitle("Overview");

  const traps = [
    {
      title: "Lakehouse time travel",
      body: "A SQL DELETE on Iceberg in merge-on-read mode writes a small position-delete file. The original Parquet file with the person\u2019s data stays on disk, reachable from every historical snapshot, column statistics, and old metadata JSON. S3 versioning preserves every overwritten object.",
      diagram: <TrapLakeDiagram />,
    },
    {
      title: "AI ghost memory",
      body: "Support tickets and call transcripts are embedded into a vector database. Deleting the primary row leaves the embeddings \u2014 a RAG chatbot can still retrieve them and reconstruct PII from the nearest-neighbour results. Semantic-cache entries in Redis keep serving stale answers containing the person\u2019s data.",
      diagram: <TrapVectorDiagram />,
    },
    {
      title: "The audit paradox",
      body: "To prove to the regulator that a person\u2019s data was erased, a company records that person\u2019s identifier in an audit log \u2014 which is itself a data-minimisation violation under Section 8(7). Verification should not require retaining the identifier.",
      diagram: <TrapAuditDiagram />,
    },
  ];

  return (
    <div className="zt-stack-page zt-landing">

      {/* ---- Hero ---- */}
      <header className="zt-page-head zt-landing-hero">
        <p className="vbg-label">ZeroTrace · erasure and proof infrastructure</p>
        <h1 className="zt-landing-headline">
          Deletion that can be proven — without keeping the person.
        </h1>
        <p className="zt-lede">
          ZeroTrace finds every copy of a person&apos;s data across the lakehouse, the vector memory and the LLM cache.
          It destroys the data, attacks its own work to prove nothing is recoverable, and issues a signed cryptographic
          receipt — anchored on-chain — with no personal data in it. Built for DPDP Act 2023 compliance.
        </p>
        <div className="zt-cta-row">
          <Link className="zt-button zt-landing-cta-primary" data-variant="approve" to="/portal">
            Submit an erasure request (Portal)
          </Link>
          <Link className="zt-button" to="/console">
            Open DPO Console
          </Link>
          <Link className="zt-button" to="/adversary">
            Adversary Console (Forensics)
          </Link>
          <Link className="zt-button" to="/verify">
            Public Verifier (Crypto)
          </Link>
        </div>
      </header>

      {/* ---- Context bar ---- */}
      <div className="zt-landing-context">
        <dl className="zt-landing-context-list">
          <dt>Compliance</dt>
          <dd>DPDP Act 2023 · Section 12(3) erasure duty</dd>
          <dt>Demo tenant</dt>
          <dd className="zt-id">Kaveri Finserv (fictional NBFC)</dd>
          <dt>Targeted layers</dt>
          <dd>Apache Iceberg on S3 · Vector DB (pgvector) · Redis semantic cache</dd>
        </dl>
      </div>

      {/* ---- SYSTEM GATEWAYS: Transfer to next internal structures ---- */}
      <section className="zt-landing-section">
        <SectionHeading
          title="Internal System Structures"
          hint="Explore each subsystem independently. ZeroTrace provides dedicated operational interfaces for principals, DPOs, examiners, and auditors."
        />
        <div className="zt-gateway-grid">
          {INTERNAL_GATEWAYS.map((gw) => (
            <div key={gw.path} className="zt-gateway-card">
              <div className="zt-gateway-card-top">
                <span className="zt-gateway-role">{gw.role}</span>
                <Chip tone={gw.badgeTone}>{gw.badge}</Chip>
              </div>
              <h3 className="zt-gateway-title">{gw.title}</h3>
              <p className="zt-copy">{gw.lede}</p>
              <ul className="zt-gateway-list">
                {gw.highlights.map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
              <div className="zt-gateway-actions">
                <Link to={gw.path} className="zt-button zt-gateway-btn">
                  <span>{gw.cta}</span>
                  <span aria-hidden="true">&rarr;</span>
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ---- Interactive Pipeline Transfer Map ---- */}
      <section className="zt-landing-section">
        <SectionHeading
          title="Pipeline Architecture & Stage Deep-Links"
          hint="Click any stage below to inspect the corresponding live data structure in the DPO console, adversary suite, or public verifier."
        />
        <div className="zt-landing-pipeline-interactive-wrap">
          <PipelineDiagram />
        </div>
        <p className="zt-copy">
          Typical wall-clock time for a single-subject erasure across 480 Parquet files, 12 vector namespaces
          and 3 cache keyspaces: <strong className="zt-num">68–94 seconds</strong>. Targeted rewrite touches <strong className="zt-num">3</strong> of <strong className="zt-num">480</strong> files.
          Estimated cost: <strong className="zt-num">&#8377;212</strong> against <strong className="zt-num">&#8377;1,046</strong> for a full-table rewrite — an <strong className="zt-num">80%</strong> measured saving.
        </p>
      </section>

      {/* ---- Three traps ---- */}
      <section className="zt-landing-section">
        <SectionHeading
          title="Why ordinary DELETE fails"
          hint="Three residual-data traps that a naive erasure misses. The adversary console resurrects data from each one, live."
        />
        <div className="zt-landing-traps">
          {traps.map((trap) => (
            <div key={trap.title} className="zt-landing-trap-card">
              <div className="zt-landing-trap-text">
                <h3 className="vbg-heading-16">{trap.title}</h3>
                <p className="zt-copy">{trap.body}</p>
              </div>
              <div className="zt-landing-trap-diagram">
                {trap.diagram}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ---- What gets erased across layers ---- */}
      <section className="zt-landing-section">
        <SectionHeading
          title="Data Plane Layers & Operations"
          hint="Detailed breakdown of destruction operations across five persistent storage layers."
        />
        <div className="zt-landing-layers-wrap">
          <table className="zt-landing-layers">
            <thead>
              <tr>
                <th>Storage layer</th>
                <th>Underlying technology</th>
                <th>Zero-trace destruction operations</th>
                <th>Inspect structure</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="zt-landing-layer-name">Data Lakehouse</td>
                <td>Apache Iceberg on AWS S3</td>
                <td className="zt-copy">Bloom-filtered Parquet rewrite, snapshot expiry, orphan file vacuum, S3 version purge</td>
                <td>
                  <Link to="/console/jobs/job_01J8BJ0M3Q7W4N8H2RGT6EK9XC#plan" className="zt-rail-link">
                    Heat grid &rarr;
                  </Link>
                </td>
              </tr>
              <tr>
                <td className="zt-landing-layer-name">AI Memory</td>
                <td>pgvector (Postgres)</td>
                <td className="zt-copy">Embedding deletion by namespace, cosine-similarity sweep for unlinked ghost embeddings</td>
                <td>
                  <Link to="/console/jobs/job_01J8BJ0M3Q7W4N8H2RGT6EK9XC#execution" className="zt-rail-link">
                    Vector lane &rarr;
                  </Link>
                </td>
              </tr>
              <tr>
                <td className="zt-landing-layer-name">Semantic Cache</td>
                <td>Redis Key-Value Cache</td>
                <td className="zt-copy">Semantic prompt-response pair flush, TTL verification, keyspace pattern invalidation</td>
                <td>
                  <Link to="/console/jobs/job_01J8BJ0M3Q7W4N8H2RGT6EK9XC#execution" className="zt-rail-link">
                    Cache lane &rarr;
                  </Link>
                </td>
              </tr>
              <tr>
                <td className="zt-landing-layer-name">Cryptographic Layer</td>
                <td>Key Management (Envelope)</td>
                <td className="zt-copy">Subject DEK (Data Encryption Key) destruction making any residual block unreadable ciphertext</td>
                <td>
                  <Link to="/verify" className="zt-rail-link">
                    Verifier &rarr;
                  </Link>
                </td>
              </tr>
              <tr>
                <td className="zt-landing-layer-name">Relational Audit</td>
                <td>PostgreSQL App Storage</td>
                <td className="zt-copy">Dead-tuple MVCC vacuum, zero-PII subject commitment replacement, catalog sync</td>
                <td>
                  <Link to="/console/policies" className="zt-rail-link">
                    Policies &rarr;
                  </Link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* ---- Integration ---- */}
      <section className="zt-landing-section">
        <SectionHeading
          title="One-call integration"
          hint="A consent manager posts a signed webhook. ZeroTrace runs the pipeline and streams events."
        />
        <pre className="zt-code zt-landing-code">
          <code>{`POST /api/v1/webhooks/consent
X-Signature: t=173..., v1=hmac...

{
  "request_id": "req_01J8\u2026",
  "type": "consent.withdrawn",
  "subject_identifiers": { /* handled server-side, never logged */ },
  "language": "kn-IN"
}

# \u2192 202 Accepted
# \u2192 job_id: job_01J8\u2026
# \u2192 SSE stream: GET /api/v1/jobs/{job_id}/events
#    \u2192 91 events over ~80 seconds
#    \u2192 stages: INTAKE \u2192 PARSE \u2192 DISCOVERY \u2192 POLICY \u2192 PLAN \u2192 ERASE \u2192 AUDIT \u2192 PROOF \u2192 ANCHOR \u2192 COMPLETE`}</code>
        </pre>
      </section>

      {/* ---- Retention holds ---- */}
      <section className="zt-landing-section">
        <SectionHeading
          title="Statutory Retention Holds"
          hint="Some data must legally stay. ZeroTrace identifies, holds, and schedules it."
        />
        <p className="zt-copy">
          KYC records under PMLA/RBI regulations cannot be erased during their statutory retention period.
          ZeroTrace identifies these records during the policy stage, marks them as <code className="zt-id">HELD</code>,
          records the legal basis (e.g. Prevention of Money Laundering Act, 2002 &sect;12), the retention
          period (e.g. until 14 Oct 2031), and schedules automatic erasure after the hold expires.
          The receipt clearly itemises what was erased and what was held.
        </p>
        <div className="zt-landing-hold-example">
          <dl className="zt-meta-list">
            <dt>Category</dt>
            <dd>KYC records</dd>
            <dt>Legal basis</dt>
            <dd>PMLA 2002, &sect;12; RBI Master Direction 2016</dd>
            <dt>Retention until</dt>
            <dd className="zt-num">14 Oct 2031</dd>
            <dt>Count</dt>
            <dd className="zt-num">2 records</dd>
          </dl>
        </div>
      </section>

      {/* ---- Pricing ---- */}
      <section className="zt-landing-section">
        <SectionHeading
          title="Commercial Model"
          hint="Matched to enterprise data infrastructure stacks. No per-seat or per-query tax."
        />
        <div className="zt-landing-pricing-grid">
          <div className="zt-landing-price-card">
            <p className="zt-landing-price-label">Platform</p>
            <p className="zt-landing-price-amount">
              <span className="zt-num">&#8377;3.5 lakh</span>
              <span className="zt-landing-price-period">/year</span>
            </p>
            <p className="zt-copy">For mid-market data lakes up to 10 TB. Includes the orchestrator, the adversarial auditor, and the proof system. Self-hosted or managed.</p>
          </div>
          <div className="zt-landing-price-card">
            <p className="zt-landing-price-label">Certificates</p>
            <p className="zt-landing-price-amount">
              <span className="zt-num">&#8377;10</span>
              <span className="zt-landing-price-period">/certificate</span>
            </p>
            <p className="zt-copy">Per verifiable on-chain erasure certificate. Includes the Merkle proof, the Ed25519 signature, and the blockchain anchor. BSA Section 63 format available.</p>
          </div>
          <div className="zt-landing-price-card">
            <p className="zt-landing-price-label">Insurance</p>
            <p className="zt-landing-price-amount">
              <span className="zt-landing-price-period">partner programme</span>
            </p>
            <p className="zt-copy">Cyber-insurance partnerships with premium discounts for companies running automated, auditable erasure workflows. Underwriter integration in progress.</p>
          </div>
        </div>
      </section>

      {/* ---- Footer ---- */}
      <footer className="zt-landing-footer">
        <div className="zt-landing-footer-links">
          <Link className="zt-rail-link" to="/portal">Data Principal Portal</Link>
          <Link className="zt-rail-link" to="/console">DPO Console</Link>
          <Link className="zt-rail-link" to="/console/impact">Platform Impact</Link>
          <Link className="zt-rail-link" to="/console/policies">Retention Policies</Link>
          <Link className="zt-rail-link" to="/adversary">Adversary Console</Link>
          <Link className="zt-rail-link" to="/verify">Public Verifier</Link>
          <Link className="zt-rail-link" to="/demo">Demo Director</Link>
        </div>
        <p className="zt-landing-footer-legal">
          ZeroTrace is erasure and proof infrastructure for DPDP Act compliance. All statutory mappings (DPDP Act 2023,
          PMLA 2002, RBI Master Directions) are implemented as configurable policy rules and require
          independent legal review before production use. &ldquo;Kaveri Finserv&rdquo; is a fictional
          entity used for demonstration purposes. No real personal data is processed in the demo environment.
        </p>
      </footer>
    </div>
  );
}
