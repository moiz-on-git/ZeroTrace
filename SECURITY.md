# ZeroTrace Security Policy & Threat Model

## 1. Security Overview

ZeroTrace is an autonomous erasure and cryptographic proof engine engineered for high-assurance compliance under India's **Digital Personal Data Protection (DPDP) Act, 2023** and **GDPR Article 17**. 

Because ZeroTrace operates directly on enterprise Lakehouses (Apache Iceberg), Vector Databases (pgvector), and Redis Semantic Memory, security is our primary design constraint.

---

## 2. Supported Versions

| Version | Supported          | Security Patches |
| ------- | ------------------ | ---------------- |
| 1.2.x   | :white_check_mark: | Active           |
| 1.1.x   | :white_check_mark: | Critical Only    |
| < 1.0   | :x:                | Deprecated       |

---

## 3. Cryptographic Threat Model & Guarantees

### 3.1 Trustless Public Verifier (Merkle Diff Proofs)
- **Zero Knowledge of Subject Identifiers**: The public verification receipt (`/receipts/verify`) contains domain-separated salted hashes (`H(salt || value)`). Plaintext emails, names, or phone numbers are **never** published to the public ledger or blockchain anchor.
- **Collateral Non-Impact**: Row-level Merkle roots prove mathematically that untouched data records ($N-k$) maintained bit-exact integrity during targeted parquet compaction.

### 3.2 Non-Repudiation (Ed25519 & BSA 2023 Section 63)
- All compliance certificates are digitally signed using an Ed25519 institutional key (`0x9d61...`).
- Electronic evidence certificates conform to the **Bhartiya Sakshya Adhiniyam, 2023 (Section 63)** standards for legal admissibility in Indian judicial proceedings.

### 3.3 Blockchain Anchoring (ShipRite / Sealed Ledger)
- State root transitions are anchored to immutable distributed ledgers. Once an erasure receipt is anchored, neither ZeroTrace nor the data fiduciary can alter or retroactively fabricate audit trails.

---

## 4. Reporting a Vulnerability

We maintain a responsible disclosure program. If you discover a security vulnerability:

1. **Email**: Send encrypted disclosures to `security@zerotrace.dev`.
2. **Response SLA**:
   - Initial triage acknowledgement: < 12 hours.
   - Severity classification & repro: < 48 hours.
   - Patch release: < 7 days for Critical/High vulnerabilities.
3. **Public Disclosure**: We coordinate responsible public disclosures 30 days after the fix is deployed to enterprise clusters.

---

## 5. DevSecOps Standards
- Container images scanned weekly with **Aqua Security Trivy**.
- Static AST security analysis enforced via **Bandit** and **Semgrep**.
- Kubernetes deployments enforce restricted Pod Security Standards (`runAsNonRoot: true`, `drop: ["ALL"]`).
