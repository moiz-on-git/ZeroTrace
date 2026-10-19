# ZeroTrace Regulatory & Compliance Matrix

This document defines the statutory obligations mapped to automated ZeroTrace architectural mechanisms for enterprise audits.

---

## 1. Digital Personal Data Protection (DPDP) Act, 2023 (India)

| Section | Statutory Mandate | ZeroTrace Technical Implementation | Verification Method |
| :--- | :--- | :--- | :--- |
| **Sec 6(4)** | Right to withdraw consent as easily as given | Voice-first multilingual intake in Kannada, Hindi, Tamil, Telugu, and English. Sarvam AI speech-to-text + Gemma legal intent parser. | Tested via `scripts/e2e_golden_path.py` (Intake -> Parse -> Erasure). |
| **Sec 8(4)** | Duty of Data Fiduciary to erase personal data upon consent withdrawal or fulfillment of purpose | Autonomous 11-stage erasure saga targeting Iceberg Lakehouse (S3), Vector Store (pgvector), and Redis Semantic Memory. | Verified by 9-vector adversarial audit engine (`services/data-plane/src/audit/attack_library.py`). |
| **Sec 8(7)** | Exception: Retention required for compliance with any law | Automated Retention Policy Engine (`policy_engine.py`) detects statutory holds (e.g. PMLA 2002 5-year lock, RBI KYC requirements) and segregates records to encrypted retention vault. | Validated in `test_retention_vault.py` and demo scenario `retention_hold`. |
| **Sec 12(1)** | Data Principal Right to Correction and Erasure | Self-service Data Principal Portal (`apps/web/src/routes/PortalPage.tsx`) enabling immediate tracking and cryptographic proof retrieval. | Verified in live browser E2E test. |

---

## 2. General Data Protection Regulation (GDPR) (EU)

| Article | Mandate | ZeroTrace Technical Implementation |
| :--- | :--- | :--- |
| **Art 17** | *Right to erasure ('right to be forgotten')* | Full physical erasure across persistent Parquet storage and AI embeddings, preventing ghost memory reconstitution in LLMs. |
| **Art 32** | *Security of processing* | Domain-separated salted Merkle diff proofs with HMAC-SHA256 privacy shielding. Zero personal identifiers stored in public receipts. |
| **Art 5(2)** | *Accountability principle* | Ed25519 digitally signed compliance receipts anchored to immutable ledgers (ShipRite / EVM). |

---

## 3. Bhartiya Sakshya Adhiniyam, 2023 (BSA) (India)

| Section | Legal Requirement | ZeroTrace Evidence Generator |
| :--- | :--- | :--- |
| **Section 63** | *Admissibility of electronic records in court proceedings* | Automatically compiles tamper-evident PDF/ZIP compliance pack with SHA-256 system hashes, cryptographic signing key fingerprints, and electronic evidence certificates compliant with judicial submission standards. |

---

## 4. SOC 2 Type II Trust Services Criteria

| Criteria | Control Objective | ZeroTrace Enforcement |
| :--- | :--- | :--- |
| **CC6.1** | Logical Access Controls | DPO role-based console with circuit-breakers and drain mode protection. |
| **CC6.6** | Perimeter & Network Defense | Kubernetes `NetworkPolicy` isolating Data Plane and databases from direct public internet access. |
| **CC6.8** | Preventing Unauthorized Execution | Automated DevSecOps pipeline with Trivy container vulnerability scanning and Bandit AST static analysis. |
