# ZeroTrace Privacy-Preserving Audit Proof Specification (v1.0.0)

## 1. Overview
ZeroTrace generates cryptographic erasure receipts that prove physical data destruction across lakehouse, vector, and cache systems without retaining any personal identifiers in the audit log or on-chain.

This specification describes the exact cryptographic algorithms, domain separators, and data canonicalization rules required to build and verify receipts.

---

## 2. Core Cryptographic Primitives

| Primitive | Standard / Detail | Purpose |
|---|---|---|
| **Hash Function** | SHA-256 (FIPS 180-4) | Merkle node hashing, digests, commitments |
| **MAC** | HMAC-SHA256 (RFC 2104) | Domain-separated salted leaf commitment |
| **Signature Scheme** | Ed25519 (EdDSA over Curve25519, RFC 8032) | Issuer digital signature |
| **Domain Separators** | `0x00` (Leaf), `0x01` (Internal Node) | Prevents second-preimage attacks |

---

## 3. Data Structures & Salted Merkle Trees

### 3.1 State Manifest Item
A state manifest captures storage items at a point in time (pre-purge or post-purge).
Each item contains:
- `layer`: `"iceberg"` | `"vector"` | `"cache"` | `"relational"`
- `object_id`: Stable identifier containing NO personal data (e.g., `iceberg:customers:part-00042.parquet`, `vector:rag_chunks:chunk_9942`, `cache:rag_query:q_hash_8a2b`)
- `content_hash`: SHA-256 hex string (64 characters) of the object's raw bytes or canonical rows.
- `in_scope`: boolean (whether item was eligible for erasure)
- `held`: boolean (whether item was placed in retention vault)

### 3.2 Salted Leaf Hash Calculation
Each item is hashed using HMAC-SHA256 with the job's unique ephemeral salt (`job_salt`):
```text
payload = b"\x00" + UTF8(layer + ":" + object_id + ":" + content_hash)
leaf_hash = HMAC-SHA256(job_salt_bytes, payload).hexdigest()
```
`job_salt` is a 32-byte cryptographically secure random value encoded as a 64-character hex string.

### 3.3 Canonical Sorting & Odd-Node Handling
1. **Canonical Ordering**: All leaf hashes are sorted in standard lexicographical order (ASCII hex sort).
2. **Empty Tree**: If the leaf set is empty, the root is defined as 64 hex zeros (`"0" * 64`).
3. **Odd-Node Level Duplication**: At each level of the tree, if the number of nodes is odd, the final node is duplicated to form a complete pair:
   ```text
   level = [H0, H1, H2] -> [H0, H1, H2, H2]
   ```
4. **Parent Node Hashing**:
   For each adjacent pair `(left_hex, right_hex)`:
   ```text
   parent_bytes = SHA-256(b"\x01" + bytes.fromhex(left_hex) + bytes.fromhex(right_hex))
   parent_hex = parent_bytes.hex()
   ```
5. Repeat iteratively until a single 32-byte (64 hex characters) Merkle root remains.

---

## 4. State-Diff Root Calculation

The difference set `D` is computed as:
1. All items present in `pre_manifest` that are absent from `post_manifest` (action: `ERASED`).
2. All items in `post_manifest` with `held == true` (action: `HELD`).

For each diff item:
```text
diff_payload = b"\x00" + UTF8(action + ":" + layer + ":" + object_id + ":" + content_hash)
diff_leaf_hash = HMAC-SHA256(job_salt_bytes, diff_payload).hexdigest()
```
The diff leaf hashes are canonically sorted and passed through the Merkle tree algorithm described in Section 3.3 to yield `diff_root`.

---

## 5. Subject Commitment (Sovereign Ownership Proof)

To solve the Audit Compliance Paradox, ZeroTrace never stores the Data Principal's identifier in the receipt or database:
1. At intake, a cryptographically secure 32-byte `subject_salt` is generated.
2. The canonical identifier string is prepared (e.g. `phone:+919876543210` or `email:user@example.com`).
3. The commitment is computed:
   ```text
   subject_commitment = SHA-256(bytes.fromhex(subject_salt) + UTF8(canonical_subject)).hex()
   ```
4. The `subject_salt` is returned **only once** to the Data Principal as part of their `receipt_secret`:
   ```json
   {
     "receipt_id": "rcpt_...",
     "subject_salt": "...",
     "canonical_subject": "phone:+919876543210"
   }
   ```
5. In the public verifier, the Data Principal can paste their secret. The browser computes `SHA-256(subject_salt || canonical_subject)` and confirms it matches `receipt.subject_commitment`. This proves ownership to any auditor or regulator without publishing identity.

---

## 6. Ed25519 Signing & Canonical Receipt Digest

### 6.1 Canonical JSON Serialization
To sign or verify a receipt:
1. Take all fields of the receipt **except** `signature`.
2. Serialize to JSON with sorted keys, UTF-8 encoding, and no whitespace (`separators=(',', ':')`).
3. Compute the 32-byte digest:
   ```text
   digest = SHA-256(canonical_json_bytes)
   ```

### 6.2 Signing & Verification
- **Signing**:
  `signature = Ed25519_Sign(private_key, digest).hex()` (128 hex chars)
- **Verification**:
  `Ed25519_Verify(public_key, digest, signature) == True`

---

## 7. In-Browser Trustless Verification Workflow
Any client browser (the Public Verifier) performs the following checklist client-side:
1. **Schema Check**: Validates receipt JSON against `receipt.schema.json`.
2. **Signature Verification**: Verifies Ed25519 signature over canonical receipt digest using `signer_public_key`.
3. **Subject Commitment Format**: Verifies format is valid 64-char hex SHA-256. (If secret provided, verifies match).
4. **State Roots Format**: Verifies `pre_root`, `post_root`, `diff_root` are valid 64-char hex strings.
5. **On-Chain Anchor Check**: Queries public explorer / testnet contract to verify `diff_root` or `receipt_id` exists in confirmed transaction.
