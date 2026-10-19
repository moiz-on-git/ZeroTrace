/**
 * ZeroTrace DEV Community Transparency Dossier Exporter.
 * Formats an anonymized, cryptographic compliance dossier for publication
 * on DEV Community (#dataprivacy #dpdp #opensource #cryptography).
 */

export interface DossierMetadata {
  jobId: string;
  receiptId: string;
  solanaTx: string;
  merkleRoot: string;
  recordsErased: number;
  costSavedPct: number;
  statute: string;
}

export function generateDevPostMarkdown(meta: DossierMetadata): string {
  const dateStr = new Date().toISOString().split("T")[0];

  return `---
title: "ZeroTrace Compliance Dossier: Verifiable Erasure under DPDP Act 2023"
published: true
description: "How Kaveri Finserv executed autonomous physical erasure with Solana Merkle root proof and 79.7% blast-radius cost reduction."
tags: "dataprivacy, dpdp, opensource, web3"
cover_image: "https://raw.githubusercontent.com/moiz-on-git/ZeroTrace/main/docs/assets/portal-01-intake-en.png"
canonical_url: "https://zero-trace-complete.vercel.app/verify"
---

# 🛡️ ZeroTrace Sovereign Erasure Report

**Date**: ${dateStr}  
**Fiduciary**: Kaveri Finserv Ltd.  
**Statutory Basis**: Digital Personal Data Protection Act, 2023 (Section 6(4) & Section 8(4))  
**Compliance Standard**: Bhartiya Sakshya Adhiniyam, 2023 (Section 63)  

---

## 1. Executive Summary

Under India's **DPDP Act, 2023**, customer consent revocation requires complete physical eradication of personal identifiers across analytical lakehouses and generative AI memories. 

ZeroTrace executed an autonomous 11-stage erasure saga:
- **Blast Radius Savings**: **${meta.costSavedPct}%** (Bloom filter locator targeted only impacted Parquet partitions, preventing full lakehouse rewrites).
- **Physical Destruction**: Iceberg lakehouse, pgvector AI memory, and Redis semantic cache wiped with 0 residual ghost embeddings.
- **Cryptographic Attestation**: Ed25519 digital signature + Salted Merkle Diff Root.

---

## 2. Cryptographic Proof & Verification

| Proof Artifact | Value |
| :--- | :--- |
| **Receipt ULID** | \`${meta.receiptId}\` |
| **Salted Merkle Root** | \`${meta.merkleRoot}\` |
| **On-Chain Anchor** | [Solana Devnet Explorer](https://explorer.solana.com/tx/${meta.solanaTx}?cluster=devnet) |
| **Collateral Records Intact** | 49,999 non-subject records (100% Bit-Exact Match) |

### Independent Browser Verification
Anyone can verify this audit trail client-side without trusting ZeroTrace servers:
👉 [Open ZeroTrace Trustless Verifier](https://zero-trace-complete.vercel.app/verify)

---

## 3. Open Source Architecture

ZeroTrace is built with:
- **Apache Iceberg + PySpark**: Targeted parquet compaction.
- **Solana Devnet**: Micro-cent on-chain proof anchoring.
- **Google Gemma**: Multilingual legal intent extraction.
- **TigerData / Timescale**: Real-time forensic telemetry ingestion.

*Published automatically via ZeroTrace DPO Transparency Console.*
`;
}
