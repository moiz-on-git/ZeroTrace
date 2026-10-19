# ZeroTrace: Founder Pitch & Evaluation Cheatsheet

---

## 1. The 60-Second Elevator Pitch

> "Under India's **DPDP Act 2023**, withdrawing consent must be as effortless as giving it, and failure to completely erase data carries statutory penalties up to **₹250 Crore**. 
>
> Today, enterprise customer data is fragmented across Iceberg Lakehouses, Vector AI memory, and Redis caches. When a customer says 'forget me', engineering teams have to manually run expensive full-table rewrites, and they have **zero mathematical proof** that AI memory was eradicated.
>
> **ZeroTrace is India's first sovereign autonomous erasure and cryptographic proof engine.** 
> We intake consent revocations via voice in 5 Indic languages, target physical file compaction with Bloom filters (reducing compute costs by **79.7%**), eradicate LLM ghost embeddings, and issue a digitally signed, **Bhartiya Sakshya Adhiniyam (Section 63)** compliant electronic evidence certificate with salted Merkle proofs anchored to the blockchain."

---

## 2. Competitive Moat: Why We Beat Everyone Else

| Capability | Legacy Solutions (OneTrust, BigID, Transcend) | **ZeroTrace** |
| :--- | :--- | :--- |
| **Erasure Method** | Sends Jira tickets or API webhooks to data owners | **Autonomous 11-stage physical erasure saga across Lakehouse, pgvector, and Redis** |
| **Proof of Erasure** | An email saying "we deleted it" (Self-attestation) | **Salted Merkle Diff Trees & Ed25519 digital signatures (Trustless Math)** |
| **Courtroom Admissibility** | None (Inadmissible in Indian courts) | **Section 63 BSA 2023 Electronic Evidence Certificate** |
| **LLM Memory Scrubbing**| Completely ignores vector databases & embeddings | **Active semantic vector sweeps and ghost embedding remediation** |
| **Compute Cost** | Rewrites entire TB-scale parquet tables | **Bloom filter Subject Locator targeting only impacted partitions (79.7% savings)** |
| **Accessibility** | English-only web forms | **Voice-first Indic intake (Kannada, Hindi, Tamil, Telugu, English) powered by Sarvam AI** |

---

## 3. Tough Technical Questions & Your Winning Answers

### Q1: *"How do you prove you deleted the data without leaking the person's identity in the proof?"*
> **Your Answer**: *"We use **Domain-Separated Salted Merkle Trees**. Every leaf is computed as `H(domain_tag || salt || row_checksum)`. The raw PII is never included in the proof or published on the blockchain. The data principal holds their private sovereign secret (`0x...`), allowing them—and only them—to mathematically verify their record was purged without revealing their identity to anyone else."*

### Q2: *"What if the person has loans or KYC documents that the law requires the bank to keep?"*
> **Your Answer**: *"ZeroTrace has an automated **Retention Policy Engine** complying with Section 8(7) of the DPDP Act. When PMLA 2002 or RBI 5-year statutory retention mandates apply, our engine automatically segregates and quarantines those records into an encrypted retention vault with a statutory release date, while still safely pruning marketing and interaction history."*

### Q3: *"How does this deploy in a real bank or telecommunications company?"*
> **Your Answer**: *"We use a two-tier architecture:
> 1. Our public portal and trustless verifier runs at `https://zero-trace-complete.vercel.app/`.
> 2. For enterprise deployments where PII cannot touch public serverless nodes, our entire brain plane, data plane, and lakehouse engine deploys into the bank's sovereign private VPC via our **production Kubernetes Helm Chart** (`deploy/helm/zerotrace`) with strict **NetworkPolicy container isolation**."*
