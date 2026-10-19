"""
ZeroTrace Contract Fixture & Proof Test Vector Generator.
Generates deterministic proof test vectors, sample receipts, and NDJSON event streams.
"""

import json
import hashlib
from datetime import datetime, timezone
import sys
import os

# Add orchestrator src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "orchestrator", "src")))

from proof.merkle import (
    compute_manifest_root,
    compute_diff_root,
    compute_subject_commitment
)
from proof.signer import (
    sign_receipt,
    verify_receipt_signature
)


def generate_proof_test_vectors():
    # Deterministic keys
    # Use deterministic seed for Ed25519
    private_key_hex = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
    from cryptography.hazmat.primitives.asymmetric import ed25519
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    public_key_hex = priv.public_key().public_bytes_raw().hex()

    job_salt_hex = "a0a1a2a3a4a5a6a7a8a9aaabacadaeafb0b1b2b3b4b5b6b7b8b9babbbcbdbebf"
    subject_salt_hex = "f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff00112233445566778899aabbccddeeff"
    canonical_subject = "phone:+919876543210"
    subject_commitment = compute_subject_commitment(subject_salt_hex, canonical_subject)

    # Pre-manifest items (simulating lake, vector, cache, relational)
    pre_items = [
        {"layer": "iceberg", "object_id": "iceberg:customers:part-0001.parquet", "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "in_scope": True, "held": False},
        {"layer": "iceberg", "object_id": "iceberg:marketing:part-0012.parquet", "content_hash": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb", "in_scope": True, "held": False},
        {"layer": "vector", "object_id": "vector:support_tickets:emb_001", "content_hash": "4e07408562bedb8b60ce05c1decfe3ad16b72230967de01f640b7e4729b49fce", "in_scope": True, "held": False},
        {"layer": "cache", "object_id": "cache:semantic:q_loan_status", "content_hash": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a", "in_scope": True, "held": False},
        {"layer": "relational", "object_id": "relational:kyc_documents:row_9942", "content_hash": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d", "in_scope": True, "held": True}
    ]

    # Post-manifest items (iceberg, vector, cache destroyed; relational held in vault)
    post_items = [
        {"layer": "relational", "object_id": "relational:kyc_documents:row_9942", "content_hash": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d", "in_scope": True, "held": True}
    ]

    pre_root, pre_leaves = compute_manifest_root(pre_items, job_salt_hex)
    post_root, post_leaves = compute_manifest_root(post_items, job_salt_hex)
    diff_root, diff_leaves = compute_diff_root(pre_items, post_items, job_salt_hex)

    receipt_base = {
        "version": "1.0.0",
        "receipt_id": "rcpt_01JB0000000000000000000001",
        "job_id": "job_01JB0000000000000000000001",
        "issued_at": "2026-10-17T10:00:00Z",
        "policy_version": "dpdp-2023-v1.4",
        "subject_commitment": subject_commitment,
        "pre_root": pre_root,
        "post_root": post_root,
        "diff_root": diff_root,
        "leaf_counts": {
            "iceberg": 2,
            "vector": 1,
            "cache": 1,
            "relational": 1,
            "total": 5
        },
        "items_erased_counts": {
            "iceberg": 2,
            "vector": 1,
            "cache": 1,
            "relational": 0,
            "total": 4
        },
        "retention_holds": [
            {
                "category": "kyc_documents",
                "legal_basis": "PMLA 2002 / RBI KYC Master Direction 2016 (5-year statutory lock)",
                "release_date": "2031-10-17T10:00:00Z",
                "count": 1
            }
        ],
        "audit_summary": {
            "attacks_run": 9,
            "attacks_passed": 9,
            "remediation_rounds": 1,
            "collateral_integrity": True
        },
        "algorithm_descriptors": {
            "hash_func": "SHA-256",
            "leaf_domain_separator": "0x00",
            "node_domain_separator": "0x01",
            "signature_scheme": "Ed25519"
        },
        "anchor": {
            "network": "ShipRite-AnchorNet",
            "tx_hash": "0x4f83b128562d965e648b712b774d02633091df05c2a07c244b7d510df1ca7a20",
            "block": 4829104,
            "target": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "explorer_url": "https://explorer.shiprite.io/tx/0x4f83b128562d965e648b712b774d02633091df05c2a07c244b7d510df1ca7a20",
            "status": "CONFIRMED"
        },
        "signer_public_key": public_key_hex
    }

    sig = sign_receipt(receipt_base, private_key_hex)
    receipt_valid = dict(receipt_base)
    receipt_valid["signature"] = sig

    # Ensure validity
    assert verify_receipt_signature(receipt_valid) is True

    # Tampered receipts for testing
    receipt_tampered_root = dict(receipt_valid)
    # Flip last char of diff_root
    alt_char = "1" if receipt_tampered_root["diff_root"][-1] == "0" else "0"
    receipt_tampered_root["diff_root"] = receipt_tampered_root["diff_root"][:-1] + alt_char

    receipt_tampered_sig = dict(receipt_valid)
    alt_char_sig = "1" if receipt_tampered_sig["signature"][-1] == "0" else "0"
    receipt_tampered_sig["signature"] = receipt_tampered_sig["signature"][:-1] + alt_char_sig

    test_vectors = {
        "title": "ZeroTrace Cryptographic Proof Reference Test Vectors",
        "description": "Standard test vectors for browser-side verification and cross-language compatibility",
        "keys": {
            "private_key_hex": private_key_hex,
            "public_key_hex": public_key_hex
        },
        "salts": {
            "job_salt_hex": job_salt_hex,
            "subject_salt_hex": subject_salt_hex
        },
        "subject": {
            "canonical_subject": canonical_subject,
            "expected_commitment": subject_commitment
        },
        "merkle_fixtures": {
            "pre_items": pre_items,
            "pre_leaves": pre_leaves,
            "pre_root": pre_root,
            "post_items": post_items,
            "post_leaves": post_leaves,
            "post_root": post_root,
            "diff_leaves": diff_leaves,
            "diff_root": diff_root
        },
        "receipts": {
            "valid_receipt": receipt_valid,
            "tampered_root_receipt": receipt_tampered_root,
            "tampered_signature_receipt": receipt_tampered_sig
        }
    }

    # Save to contracts/fixtures/proof-test-vectors.json
    out_path = os.path.join(os.path.dirname(__file__), "..", "contracts", "fixtures", "proof-test-vectors.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(test_vectors, f, indent=2)
    print(f"Wrote test vectors to {out_path}")

    # Save sample receipt
    sample_path = os.path.join(os.path.dirname(__file__), "..", "contracts", "fixtures", "sample-receipt.json")
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(receipt_valid, f, indent=2)
    print(f"Wrote sample receipt to {sample_path}")

    return receipt_valid


def generate_event_streams():
    job_id = "job_01JB0000000000000000000001"
    base_ts = "2026-10-17T10:00:"

    # 1. Golden Path Job Events (90-second successful run)
    golden_events = [
        {"seq": 1, "ts": f"{base_ts}00.100Z", "job_id": job_id, "stage": "INTAKE", "kind": "started", "layer": "intake", "message": "Voice erasure request received via portal in Kannada (kn-IN)", "data": {"step_name": "voice_received"}},
        {"seq": 2, "ts": f"{base_ts}01.200Z", "job_id": job_id, "stage": "INTAKE", "kind": "progress", "layer": "intake", "message": "Transcoding audio stream to 16 kHz mono WAV", "data": {"progress_pct": 20}},
        {"seq": 3, "ts": f"{base_ts}02.500Z", "job_id": job_id, "stage": "PARSE", "kind": "started", "layer": "discovery", "message": "Sarvam AI transcribed audio with language confidence 0.98", "data": {"step_name": "sarvam_stt"}},
        {"seq": 4, "ts": f"{base_ts}04.100Z", "job_id": job_id, "stage": "PARSE", "kind": "progress", "layer": "discovery", "message": "Gemma extracted legal intent: WITHDRAW_CONSENT under DPDP Act Section 6", "data": {"intent": "withdraw_consent", "confidence": 0.99}},
        {"seq": 5, "ts": f"{base_ts}05.300Z", "job_id": job_id, "stage": "PARSE", "kind": "completed", "layer": "discovery", "message": "Identifier variants generated across phone (+91 98765 43210), email and scripts", "data": {"variants_count": 8}},
        {"seq": 6, "ts": f"{base_ts}06.000Z", "job_id": job_id, "stage": "DISCOVERY", "kind": "started", "layer": "discovery", "message": "Agentic lineage discovery loop initiated across lakehouse, vector index and cache", "data": {"step_name": "lineage_agent"}},
        {"seq": 7, "ts": f"{base_ts}08.200Z", "job_id": job_id, "stage": "DISCOVERY", "kind": "finding", "layer": "iceberg", "message": "Subject found in 3 of 480 Parquet data files across customers & marketing tables", "data": {"files_targeted": 3, "files_total": 480}},
        {"seq": 8, "ts": f"{base_ts}09.400Z", "job_id": job_id, "stage": "DISCOVERY", "kind": "finding", "layer": "vector", "message": "Subject found in 4 vector chunks in support_transcripts namespace", "data": {"vectors_found": 4}},
        {"seq": 9, "ts": f"{base_ts}10.100Z", "job_id": job_id, "stage": "DISCOVERY", "kind": "finding", "layer": "cache", "message": "Subject found in 2 cached LLM query answers in Redis", "data": {"cache_keys_found": 2}},
        {"seq": 10, "ts": f"{base_ts}11.500Z", "job_id": job_id, "stage": "POLICY", "kind": "started", "layer": "policy", "message": "Applying DPDP & statutory retention policies", "data": {"policy_version": "dpdp-2023-v1.4"}},
        {"seq": 11, "ts": f"{base_ts}12.200Z", "job_id": job_id, "stage": "POLICY", "kind": "progress", "layer": "policy", "message": "KYC document tagged HOLD_THEN_ERASE under PMLA 2002 / RBI KYC Direction (5-yr lock)", "data": {"held_categories": ["kyc_documents"]}},
        {"seq": 12, "ts": f"{base_ts}13.000Z", "job_id": job_id, "stage": "PLAN", "kind": "started", "layer": "system", "message": "Calculating blast-radius compaction using Subject Locator Index", "data": {"step_name": "blast_radius_plan"}},
        {"seq": 13, "ts": f"{base_ts}14.500Z", "job_id": job_id, "stage": "PLAN", "kind": "metric", "layer": "system", "message": "Targeted rewrite estimated at ₹212 vs ₹1,046 for full-table rewrite (79.7% saving)", "data": {"cost_naive_inr": 1046.0, "cost_targeted_inr": 212.0, "saving_pct": 79.7, "files_targeted": 3, "files_total": 480}},
        {"seq": 14, "ts": f"{base_ts}15.000Z", "job_id": job_id, "stage": "APPROVAL", "kind": "started", "layer": "system", "message": "Awaiting DPO confirmation or auto-approve trigger", "data": {"step_name": "dpo_approval"}},
        {"seq": 15, "ts": f"{base_ts}16.000Z", "job_id": job_id, "stage": "APPROVAL", "kind": "completed", "layer": "system", "message": "DPO approval granted. Initiating execution pipeline.", "data": {"approver": "dpo@kaveri-finserv.internal"}},
        {"seq": 16, "ts": f"{base_ts}17.000Z", "job_id": job_id, "stage": "ERASE_CRYPTO", "kind": "started", "layer": "crypto", "message": "Speed 1: Shredding per-subject envelope encryption data key in KMS", "data": {"step_name": "crypto_killswitch"}},
        {"seq": 17, "ts": f"{base_ts}18.100Z", "job_id": job_id, "stage": "ERASE_CRYPTO", "kind": "metric", "layer": "crypto", "message": "Subject data key destroyed. Readability extinguished instantly across historical snapshots.", "data": {"duration_ms": 1100, "bytes_shredded": 256}},
        {"seq": 18, "ts": f"{base_ts}19.000Z", "job_id": job_id, "stage": "ERASE_ICEBERG", "kind": "started", "layer": "iceberg", "message": "Speed 2: Rewriting targeted 3 Parquet files with position deletes folded", "data": {"step_name": "lake_rewrite"}},
        {"seq": 19, "ts": f"{base_ts}22.000Z", "job_id": job_id, "stage": "ERASE_ICEBERG", "kind": "progress", "layer": "iceberg", "message": "Expiring Iceberg historical snapshots referencing obsolete data files", "data": {"snapshots_expired": 4}},
        {"seq": 20, "ts": f"{base_ts}25.000Z", "job_id": job_id, "stage": "ERASE_ICEBERG", "kind": "progress", "layer": "iceberg", "message": "Removing orphan Parquet files and purging old metadata versions", "data": {"orphan_files_removed": 3, "metadata_files_removed": 2}},
        {"seq": 21, "ts": f"{base_ts}28.000Z", "job_id": job_id, "stage": "ERASE_ICEBERG", "kind": "completed", "layer": "iceberg", "message": "Purged non-current S3 versions and scrubbed column min/max statistics", "data": {"object_versions_deleted": 6, "files_rewritten": 3, "bytes_rewritten": 4194304}},
        {"seq": 22, "ts": f"{base_ts}20.000Z", "job_id": job_id, "stage": "ERASE_VECTOR", "kind": "started", "layer": "vector", "message": "Speed 2: Erasing vector embeddings and performing semantic sweep", "data": {"step_name": "vector_purge"}},
        {"seq": 23, "ts": f"{base_ts}24.000Z", "job_id": job_id, "stage": "ERASE_VECTOR", "kind": "progress", "layer": "vector", "message": "Executing VACUUM FULL & REINDEX on pgvector to physically eliminate dead tuples", "data": {"vectors_deleted": 4, "dead_tuples_vacuumed": 18}},
        {"seq": 24, "ts": f"{base_ts}21.000Z", "job_id": job_id, "stage": "ERASE_CACHE", "kind": "started", "layer": "cache", "message": "Speed 2: Flushing Redis semantic cache keys and triggering AOF persistence rewrite", "data": {"step_name": "cache_flush"}},
        {"seq": 25, "ts": f"{base_ts}26.000Z", "job_id": job_id, "stage": "ERASE_CACHE", "kind": "completed", "layer": "cache", "message": "Redis persistence rewritten. In-memory and disk cache purged.", "data": {"cache_keys_deleted": 2}},
        {"seq": 26, "ts": f"{base_ts}30.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "started", "layer": "audit", "message": "Adversarial Red Team Audit initiated: attacking lake, vector, cache and collateral integrity", "data": {"attacks_planned": 9}},
        {"seq": 27, "ts": f"{base_ts}33.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "progress", "layer": "audit", "message": "Attack 1/9 (time_travel): NOT_FOUND. Historical snapshot queries return zero records.", "data": {"attack": "time_travel", "verdict": "NOT_FOUND"}},
        {"seq": 28, "ts": f"{base_ts}36.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "progress", "layer": "audit", "message": "Attack 2/9 (raw_parquet): NOT_FOUND. Direct pyarrow scan across all bucket files clean.", "data": {"attack": "raw_parquet", "verdict": "NOT_FOUND"}},
        {"seq": 29, "ts": f"{base_ts}39.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "progress", "layer": "audit", "message": "Attack 3/9 (bucket_grep): NOT_FOUND. Byte-level regex across S3 metadata and data clean.", "data": {"attack": "bucket_grep", "verdict": "NOT_FOUND"}},
        {"seq": 30, "ts": f"{base_ts}42.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "progress", "layer": "audit", "message": "Attack 4/9 (s3_versions): NOT_FOUND. Zero non-current object versions remain.", "data": {"attack": "s3_versions", "verdict": "NOT_FOUND"}},
        {"seq": 31, "ts": f"{base_ts}45.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "progress", "layer": "audit", "message": "Attack 5/9 (vector_lookup): NOT_FOUND. Semantic similarity search returns zero matches.", "data": {"attack": "vector_lookup", "verdict": "NOT_FOUND"}},
        {"seq": 32, "ts": f"{base_ts}48.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "progress", "layer": "audit", "message": "Attack 6/9 (rag_prompt_injection): NOT_FOUND. Support Copilot prompt injections deflected.", "data": {"attack": "rag_prompt_injection", "verdict": "NOT_FOUND"}},
        {"seq": 33, "ts": f"{base_ts}51.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "progress", "layer": "audit", "message": "Attack 7/9 (cache_probe): NOT_FOUND. Paraphrased cache queries return cache miss.", "data": {"attack": "cache_probe", "verdict": "NOT_FOUND"}},
        {"seq": 34, "ts": f"{base_ts}54.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "progress", "layer": "audit", "message": "Attack 8/9 (dead_tuples): NOT_FOUND. Postgres heap and Redis persistence clear.", "data": {"attack": "dead_tuples", "verdict": "NOT_FOUND"}},
        {"seq": 35, "ts": f"{base_ts}57.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "progress", "layer": "audit", "message": "Attack 9/9 (collateral): NOT_FOUND. 49,999 non-subject records checksum match 100%.", "data": {"attack": "collateral", "verdict": "NOT_FOUND", "rows_compared": 49999, "checksum_match": True}},
        {"seq": 36, "ts": f"{base_ts}58.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "completed", "layer": "audit", "message": "Adversarial self-audit PASSED all 9 security vectors.", "data": {"verdict": "PASS"}},
        {"seq": 37, "ts": f"{base_ts}60.000Z", "job_id": job_id, "stage": "PROOF", "kind": "started", "layer": "proof", "message": "Generating privacy-preserving salted Merkle trees and state diff root", "data": {"step_name": "merkle_proof"}},
        {"seq": 38, "ts": f"{base_ts}62.000Z", "job_id": job_id, "stage": "PROOF", "kind": "metric", "layer": "proof", "message": "Pre-root, post-root, and diff-root calculated with zero PII in audit log", "data": {"leaf_count": 5}},
        {"seq": 39, "ts": f"{base_ts}63.000Z", "job_id": job_id, "stage": "PROOF", "kind": "completed", "layer": "proof", "message": "Receipt signed with Ed25519 corporate identity key", "data": {"receipt_id": "rcpt_01JB0000000000000000000001"}},
        {"seq": 40, "ts": f"{base_ts}64.000Z", "job_id": job_id, "stage": "ANCHOR", "kind": "started", "layer": "chain", "message": "Anchoring diff root to ShipRite AnchorNet / EVM ledger", "data": {"step_name": "blockchain_anchor"}},
        {"seq": 41, "ts": f"{base_ts}66.000Z", "job_id": job_id, "stage": "ANCHOR", "kind": "completed", "layer": "chain", "message": "Proof anchored on-chain in block 4829104 (tx: 0x4f83b1...)", "data": {"block": 4829104, "tx_hash": "0x4f83b128562d965e648b712b774d02633091df05c2a07c244b7d510df1ca7a20"}},
        {"seq": 42, "ts": f"{base_ts}67.000Z", "job_id": job_id, "stage": "COMPLETE", "kind": "completed", "layer": "system", "message": "Erasure pipeline COMPLETED WITH HOLDS under DPDP Section 12(3)", "data": {"status": "COMPLETED_WITH_HOLDS", "receipt_id": "rcpt_01JB0000000000000000000001"}}
    ]

    out_golden = os.path.join(os.path.dirname(__file__), "..", "contracts", "fixtures", "golden-job-events.ndjson")
    with open(out_golden, "w", encoding="utf-8") as f:
        for ev in golden_events:
            f.write(json.dumps(ev) + "\n")
    print(f"Wrote golden events to {out_golden}")

    # 2. Planted Ghost Embedding Self-Healing Stream
    ghost_events = list(golden_events[:26]) # Up to start of audit
    ghost_events.extend([
        {"seq": 27, "ts": f"{base_ts}32.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "finding", "layer": "audit", "message": "Attack vector_lookup: FOUND planted ghost embedding in transcript chunk chunk_trans_9921 without metadata link", "data": {"attack": "vector_lookup", "verdict": "FOUND", "residual_locations": [{"layer": "vector", "resource": "support_transcripts", "location_id": "chunk_trans_9921"}]}},
        {"seq": 28, "ts": f"{base_ts}33.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "failed", "layer": "audit", "message": "Adversarial audit round 1 FAILED: 1 residual location detected. Entering self-healing remediation.", "data": {"verdict": "FAIL", "residuals_count": 1}},
        {"seq": 29, "ts": f"{base_ts}34.000Z", "job_id": job_id, "stage": "REMEDIATE", "kind": "started", "layer": "system", "message": "Remediation Round 1: Targeting identified ghost chunk chunk_trans_9921 via deep semantic sweep", "data": {"step_name": "remediate_target"}},
        {"seq": 30, "ts": f"{base_ts}36.000Z", "job_id": job_id, "stage": "REMEDIATE", "kind": "progress", "layer": "vector", "message": "Ghost embedding chunk_trans_9921 purged and pgvector reindexed", "data": {"vectors_deleted": 1}},
        {"seq": 31, "ts": f"{base_ts}37.000Z", "job_id": job_id, "stage": "REMEDIATE", "kind": "completed", "layer": "system", "message": "Targeted remediation complete. Re-triggering adversarial audit.", "data": {"step_name": "remediation_complete"}},
        {"seq": 32, "ts": f"{base_ts}38.000Z", "job_id": job_id, "stage": "AUDIT", "kind": "started", "layer": "audit", "message": "Audit Round 2: Re-executing full attack suite against all layers", "data": {"round": 2}}
    ])
    # Add remaining passed events with incremented sequence
    for i, ev in enumerate(golden_events[26:], start=33):
        ev_copy = dict(ev)
        ev_copy["seq"] = i
        ghost_events.append(ev_copy)

    out_ghost = os.path.join(os.path.dirname(__file__), "..", "contracts", "fixtures", "audit-fail-self-heal.ndjson")
    with open(out_ghost, "w", encoding="utf-8") as f:
        for ev in ghost_events:
            f.write(json.dumps(ev) + "\n")
    print(f"Wrote self-heal events to {out_ghost}")

    # 3. Retention Hold Event Stream (Clean hold case)
    out_hold = os.path.join(os.path.dirname(__file__), "..", "contracts", "fixtures", "retention-hold.ndjson")
    with open(out_hold, "w", encoding="utf-8") as f:
        for ev in golden_events:
            f.write(json.dumps(ev) + "\n")
    print(f"Wrote retention hold events to {out_hold}")


if __name__ == "__main__":
    generate_proof_test_vectors()
    generate_event_streams()
    print("All fixtures and test vectors generated successfully.")
