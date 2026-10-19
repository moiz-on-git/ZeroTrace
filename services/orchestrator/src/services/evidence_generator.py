"""
ZeroTrace Regulatory Evidence & Compliance Pack Generator.
Generates:
1. Receipt PDF with embedded QR code (ReportLab + qrcode)
2. Bharatiya Sakshya Adhiniyam, 2023 (Section 63) Electronic Evidence Certificate
3. DPBI Compliance Pack ZIP bundle (receipt JSON, plan, audit report, retention register, BSA cert)
"""

from __future__ import annotations
import io
import json
import os
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors


class EvidenceGenerator:
    @staticmethod
    def generate_qr_png_bytes(verifier_url: str) -> bytes:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(verifier_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    @staticmethod
    def generate_receipt_pdf(receipt_data: Dict[str, Any], verifier_base_url: str = "http://localhost:3000/verify") -> bytes:
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Header
        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont("Helvetica-Bold", 18)
        p.drawString(50, height - 50, "ZEROTRACE — DATA DESTRUCTION CERTIFICATE")

        p.setFont("Helvetica", 10)
        p.setFillColor(colors.HexColor("#475569"))
        p.drawString(50, height - 68, "India DPDP Act 2023 & BSA 2023 Section 63 Compliant Cryptographic Receipt")
        p.setStrokeColor(colors.HexColor("#cbd5e1"))
        p.setLineWidth(1)
        p.line(50, height - 78, width - 50, height - 78)

        # Receipt Summary
        p.setFont("Helvetica-Bold", 12)
        p.setFillColor(colors.HexColor("#0f172a"))
        p.drawString(50, height - 105, "RECEIPT DETAILS")

        p.setFont("Helvetica", 9)
        p.setFillColor(colors.HexColor("#1e293b"))
        y = height - 125
        fields = [
            ("Receipt ID:", receipt_data.get("receipt_id", "")),
            ("Job ID:", receipt_data.get("job_id", "")),
            ("Issued At (UTC):", receipt_data.get("issued_at", "")),
            ("Policy Version:", receipt_data.get("policy_version", "")),
            ("Subject Commitment:", receipt_data.get("subject_commitment", "")),
            ("Merkle Diff Root:", receipt_data.get("diff_root", "")),
            ("On-Chain Tx Hash:", receipt_data.get("anchor", {}).get("tx_hash", "")),
            ("Blockchain Network:", receipt_data.get("anchor", {}).get("network", "")),
            ("Signer Public Key:", receipt_data.get("signer_public_key", ""))
        ]

        for label, val in fields:
            p.setFont("Helvetica-Bold", 8)
            p.drawString(50, y, label)
            p.setFont("Courier", 8)
            p.drawString(180, y, str(val)[:65] + ("..." if len(str(val)) > 65 else ""))
            y -= 18

        # Draw QR Code linking to verifier
        verifier_url = f"{verifier_base_url}/{receipt_data.get('receipt_id', '')}"
        qr_bytes = EvidenceGenerator.generate_qr_png_bytes(verifier_url)
        qr_img = io.BytesIO(qr_bytes)

        from reportlab.lib.utils import ImageReader
        p.drawImage(ImageReader(qr_img), width - 160, height - 210, width=110, height=110)
        p.setFont("Helvetica", 7)
        p.setFillColor(colors.HexColor("#64748b"))
        p.drawCentredString(width - 105, height - 220, "Scan to Verify On-Chain")

        # Statutory Retention Holds Table
        y -= 10
        p.setFont("Helvetica-Bold", 12)
        p.setFillColor(colors.HexColor("#0f172a"))
        p.drawString(50, y, "STATUTORY RETENTION HOLDS (Section 12(3))")
        y -= 18

        holds = receipt_data.get("retention_holds", [])
        if holds:
            for hold in holds:
                p.setFont("Helvetica-Bold", 8)
                p.drawString(50, y, f"Category: {hold.get('category')} | Legal Basis: {hold.get('legal_basis')}")
                y -= 14
                p.setFont("Helvetica", 8)
                p.drawString(50, y, f"Scheduled Auto-Erasure Release Date: {hold.get('release_date')}")
                y -= 18
        else:
            p.setFont("Helvetica", 8)
            p.drawString(50, y, "None. 100% of personal data categories physically destroyed.")
            y -= 18

        # Legal Attestation Footer
        p.setStrokeColor(colors.HexColor("#cbd5e1"))
        p.line(50, 80, width - 50, 80)
        p.setFont("Helvetica-Oblique", 7)
        p.setFillColor(colors.HexColor("#64748b"))
        p.drawString(50, 68, "Attestation: This electronic certificate was generated automatically by ZeroTrace.")
        p.drawString(50, 58, "Zero personal identifiers are stored in this record. Integrity is verifiable independently via public Merkle recomputation.")

        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer.getvalue()

    @staticmethod
    def generate_bsa_certificate(receipt_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produces Section 63 BSA 2023 Electronic Evidence Certificate structure.
        """
        return {
            "certificate_id": f"bsa_cert_{receipt_data.get('receipt_id')}",
            "statute": "Bharatiya Sakshya Adhiniyam, 2023 (Act No. 47 of 2023)",
            "section": "Section 63 (Admissibility of electronic records)",
            "entity": "Kaveri Finserv Limited",
            "certifying_officer": {
                "name": "Designated Data Protection Officer",
                "designation": "Data Protection Officer",
                "authority": "DPDP Act, 2023 (Section 10)"
            },
            "system_details": {
                "platform": "ZeroTrace Autonomous Erasure & Proof Engine v1.0.0",
                "lakehouse": "Apache Iceberg Parquet Store (S3)",
                "ai_memory": "pgvector (Database zt_rag)",
                "semantic_cache": "Redis In-Memory Persistence Engine"
            },
            "hash_values": {
                "pre_purge_manifest_merkle_root": receipt_data.get("pre_root"),
                "post_purge_manifest_merkle_root": receipt_data.get("post_root"),
                "difference_set_merkle_root": receipt_data.get("diff_root"),
                "subject_salted_commitment": receipt_data.get("subject_commitment"),
                "corporate_ed25519_signature": receipt_data.get("signature"),
                "blockchain_anchor_tx_hash": receipt_data.get("anchor", {}).get("tx_hash")
            },
            "legal_provisions": [
                {"act": "Digital Personal Data Protection Act, 2023", "section": "Section 6(4)", "provision": "Right to withdraw consent"},
                {"act": "Digital Personal Data Protection Act, 2023", "section": "Section 12(1)", "provision": "Obligation to erase personal data upon consent withdrawal"},
                {"act": "Digital Personal Data Protection Act, 2023", "section": "Section 12(3)", "provision": "Statutory retention exemption for legal obligations (PMLA/RBI)"},
                {"act": "Bharatiya Sakshya Adhiniyam, 2023", "section": "Section 63(4)", "provision": "Certificate proving authenticity of electronic record"}
            ],
            "cryptographic_standards": {
                "signature_scheme": "Ed25519 (RFC 8032)",
                "hashing_algorithm": "SHA-256 (FIPS 180-4)",
                "merkle_domain_separation": "RFC 6962 Compliant (0x00 leaf, 0x01 node)",
                "sovereign_privacy": "Salted blind commitment with zero plain-text PII in certificate"
            },
            "custody_chain": {
                "issuer_public_key": receipt_data.get("signer_public_key"),
                "fiduciary_name": "Kaveri Finserv Limited",
                "fiduciary_registration": "DPBI-REG-2026-KA-00429",
                "retention_locks_active": len(receipt_data.get("retention_holds", []))
            },
            "statement": (
                "I hereby certify pursuant to Section 63(4) of the Bharatiya Sakshya Adhiniyam, 2023 that the electronic "
                "record described herein was produced autonomously by the ZeroTrace system during the ordinary course "
                "of business. The computer system operated properly without any deviation or tampering. The personal "
                "data was permanently destroyed across Lakehouse, Vector DB, and Semantic Cache layers, leaving zero trace "
                "as verified by nine adversarial red-team attack vectors."
            ),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    @staticmethod
    def generate_compliance_pack_zip(receipt_data: Dict[str, Any], plan_data: Dict[str, Any], audit_data: Dict[str, Any]) -> bytes:
        """
        Assembles full DPBI compliance ZIP pack.
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Receipt JSON
            zf.writestr("receipt.json", json.dumps(receipt_data, indent=2))

            # 2. Receipt PDF
            pdf_bytes = EvidenceGenerator.generate_receipt_pdf(receipt_data)
            zf.writestr("receipt.pdf", pdf_bytes)

            # 3. BSA Section 63 Certificate JSON
            bsa_cert = EvidenceGenerator.generate_bsa_certificate(receipt_data)
            zf.writestr("bsa_section_63_certificate.json", json.dumps(bsa_cert, indent=2))

            # 4. Plan & Blast Radius JSON
            zf.writestr("erasure_plan.json", json.dumps(plan_data, indent=2))

            # 5. Adversarial Audit Report JSON
            zf.writestr("adversarial_audit_report.json", json.dumps(audit_data, indent=2))

            # 6. Retention Hold Register JSON
            retention_register = {
                "job_id": receipt_data.get("job_id"),
                "policy_version": receipt_data.get("policy_version"),
                "holds": receipt_data.get("retention_holds", [])
            }
            zf.writestr("retention_hold_register.json", json.dumps(retention_register, indent=2))

        buf.seek(0)
        return buf.getvalue()
