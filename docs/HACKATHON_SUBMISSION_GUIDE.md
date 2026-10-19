# Hacktober Hackathon 2026 — Ready-to-Submit Guide

Use this document to copy-paste directly into your Devpost / Devfolio / Hack2skill submission portal.

---

### Project Title
**ZeroTrace: Autonomous Data Destruction & Cryptographic Proof Infrastructure**

### Short Elevator Pitch (Tagline)
*Stripe for Data Destruction: Solving the ₹250 Crore DPDP Act 2023 compliance trap across Lakehouses, AI Agent Memory, and Semantic Caches.*

### Project Links
- **Live Frontend**: [https://zero-trace-complete.vercel.app/](https://zero-trace-complete.vercel.app/)
- **Live Orchestrator Backend**: [https://zerotrace-orchestrator.onrender.com/](https://zerotrace-orchestrator.onrender.com/)
- **Interactive Swagger Documentation**: [https://zerotrace-orchestrator.onrender.com/docs](https://zerotrace-orchestrator.onrender.com/docs)
- **GitHub Repository**: [https://github.com/moiz-on-git/ZeroTrace](https://github.com/moiz-on-git/ZeroTrace)

---

### Inspiration
Under India's Digital Personal Data Protection Act, 2023 (DPDP Act), when a citizen revokes consent, companies face fines up to ₹250 Crore if they fail to erase the citizen's personal data. But modern architectures make real deletion nearly impossible:
1. **Snowflake Time-Travel** keeps deleted records queryable for 90 days.
2. **AI conversational agents** retain chat logs and vector embeddings indefinitely in memory threads.
3. Traditional audit logs that record *"User X was deleted"* ironically violate privacy laws by storing User X's identifier in the audit log.

We built ZeroTrace to make true, verifiable data destruction as simple as integrating Stripe.

---

### What It Does
1. **Voice-First Indic Intake**: Rural or non-English speaking citizens can revoke consent in Kannada, Hindi, Tamil, Telugu, or English using Sarvam AI's sovereign speech engine.
2. **Two-Speed Erasure**: Sub-second envelope key shredding followed by verified physical Parquet compaction (saving 79.7% on cloud compute via Bloom filter indexing).
3. **Snowflake & AI Memory Scrub**: Enforces `DATA_RETENTION_TIME_IN_DAYS = 0` on Snowflake and runs an "Amnesia Probe" across Backboard AI memory threads (proving a 0.000 cosine similarity).
4. **Trustless Cryptographic Proof**: Issues Ed25519-signed privacy-preserving receipts anchored on Solana Devnet for ₹0.02 using SPL Memos. The citizen's browser recomputes the Merkle tree math locally.
5. **Regulator Artifacts**: Generates Section 63 Bharatiya Sakshya Adhiniyam (BSA) 2023 electronic evidence certificates and provides a 1-click exporter to DEV Community.

---

### Sponsor Tracks & Bounties Targeted
- **Sarvam AI**: Integrated `saaras:v4` STT and `bulbul:v4-flash` TTS (speaker: `shubh_enhi_ads`) with production dual-key failover for Indian scheduled languages.
- **Solana**: Sub-second, ₹0.02 SPL Memo transactions anchoring Merkle diff roots.
- **Google AI / Gemma**: DPDP Section 6(4) intent extraction with prompt-injection defense pipeline.
- **Snowflake**: Solves the Time-Travel compliance trap by programmatically collapsing retention buffers.
- **Backboard.io**: AI agent conversational memory thread scrubbing with mathematical amnesia verification.
- **Prior Labs**: TabPFN-3.5 zero-shot tabular AI predicting compaction runtime and cloud compute savings.
- **DEV Community**: 1-click DPO console exporter publishing transparency dossiers to DEV.to.
- **Render & Vercel**: Live cloud deployments powering high-throughput compliance endpoints.

---

### How We Built It
- **Frontend**: Vite, React, TypeScript, TanStack Query, Native CSS (Zero Tailwind), Web Speech API.
- **Backend**: FastAPI, Python 3.11, Pydantic v2, PyArrow, SQLite / PostgreSQL pgvector, Redis.
- **Enterprise DevOps**: Multi-stage Dockerfiles, Docker Compose, Kubernetes Helm Charts with HPA, AWS Terraform modules (`ap-south-1`), Prometheus/Grafana SRE dashboard.
- **Testing**: 156 automated test suites (57 orchestrator, 61 data plane, 38 vitest web tests).
