"""
ZeroTrace Merkle Tree, Salted Proof & Cryptographic Signature Unit Tests.
Verifies mathematical correctness of leaf hashing, tree construction,
diff roots, Ed25519 signatures, and tamper detection.
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from proof.merkle import (
    compute_leaf_hash,
    build_merkle_root,
    compute_manifest_root,
    compute_diff_root,
    compute_subject_commitment,
    LEAF_DOMAIN_SEPARATOR,
    NODE_DOMAIN_SEPARATOR
)
from proof.signer import (
    generate_ed25519_keypair,
    sign_receipt,
    verify_receipt_signature,
    compute_receipt_digest
)


def test_empty_merkle_root():
    root = build_merkle_root([])
    assert root == "0" * 64


def test_odd_node_merkle_tree():
    # 3 leaves -> should duplicate 3rd leaf to make 4, then combine to 2, then 1 root
    leaves = [
        "1111111111111111111111111111111111111111111111111111111111111111",
        "2222222222222222222222222222222222222222222222222222222222222222",
        "3333333333333333333333333333333333333333333333333333333333333333"
    ]
    root = build_merkle_root(leaves)
    assert len(root) == 64
    # Deterministic check
    assert root == build_merkle_root(leaves)


def test_subject_commitment_determinism():
    salt = "a" * 64
    canonical_subject = "phone:+919876543210"
    commitment1 = compute_subject_commitment(salt, canonical_subject)
    commitment2 = compute_subject_commitment(salt, canonical_subject)
    assert commitment1 == commitment2
    assert len(commitment1) == 64

    # Changing phone changes commitment
    commitment3 = compute_subject_commitment(salt, "phone:+919876543211")
    assert commitment1 != commitment3


def test_ed25519_signing_and_tamper_detection():
    priv, pub = generate_ed25519_keypair()
    receipt_data = {
        "version": "1.0.0",
        "receipt_id": "rcpt_01JB0000000000000000000001",
        "job_id": "job_01JB0000000000000000000001",
        "issued_at": "2026-10-17T10:00:00Z",
        "policy_version": "dpdp-2023-v1.4",
        "subject_commitment": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "pre_root": "1" * 64,
        "post_root": "2" * 64,
        "diff_root": "3" * 64,
        "signer_public_key": pub
    }

    sig = sign_receipt(receipt_data, priv)
    receipt_data["signature"] = sig

    # Valid check
    assert verify_receipt_signature(receipt_data) is True

    # Tamper test 1: altering diff_root causes signature verification failure!
    tampered_receipt = dict(receipt_data)
    tampered_receipt["diff_root"] = "4" * 64
    assert verify_receipt_signature(tampered_receipt) is False

    # Tamper test 2: altering signature
    tampered_receipt2 = dict(receipt_data)
    tampered_receipt2["signature"] = "0" * 128
    assert verify_receipt_signature(tampered_receipt2) is False


def test_proof_test_vectors_file():
    vector_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "contracts", "fixtures", "proof-test-vectors.json")
    assert os.path.exists(vector_path), "proof-test-vectors.json must exist"

    with open(vector_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    valid_rcpt = data["receipts"]["valid_receipt"]
    assert verify_receipt_signature(valid_rcpt) is True

    tampered_root = data["receipts"]["tampered_root_receipt"]
    assert verify_receipt_signature(tampered_root) is False

    tampered_sig = data["receipts"]["tampered_signature_receipt"]
    assert verify_receipt_signature(tampered_sig) is False


def test_merkle_inclusion_proof_and_verification():
    from proof.merkle import generate_merkle_proof, verify_merkle_proof

    leaves = [
        "1111111111111111111111111111111111111111111111111111111111111111",
        "2222222222222222222222222222222222222222222222222222222222222222",
        "3333333333333333333333333333333333333333333333333333333333333333",
        "4444444444444444444444444444444444444444444444444444444444444444",
        "5555555555555555555555555555555555555555555555555555555555555555"
    ]
    root = build_merkle_root(leaves)

    for target in leaves:
        proof = generate_merkle_proof(leaves, target)
        assert len(proof) > 0
        assert verify_merkle_proof(target, proof, root) is True

        # Tampering with proof makes verification fail
        corrupt_proof = list(proof)
        corrupt_proof[0] = dict(corrupt_proof[0])
        corrupt_proof[0]["sibling"] = "0" * 64
        assert verify_merkle_proof(target, corrupt_proof, root) is False

