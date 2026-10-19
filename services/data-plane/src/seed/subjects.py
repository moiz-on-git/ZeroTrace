"""
Hero and decoy subject definitions for Kaveri Finserv demo.
All values are entirely fictional. These are the anchors the adversarial audit hunts for.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Optional

from src.core.config import get_settings


@dataclass
class Subject:
    customer_id: str
    full_name: str
    full_name_devanagari: str   # Hindi transliteration
    full_name_kannada: str
    phone: str                  # canonical: 10 digits, no country code
    email: str
    dob: str                    # YYYY-MM-DD
    pan: str
    aadhaar_last4: str
    is_hero: bool = True
    decoy_note: Optional[str] = None

    @property
    def phone_variants(self) -> list[str]:
        """All phone format variants the audit engine must scan for."""
        p = self.phone
        return [
            p,                              # 9845012345
            f"+91{p}",                      # +919845012345
            f"+91 {p}",                     # +91 9845012345
            f"+91-{p}",                     # +91-9845012345
            f"91{p}",                       # 919845012345
            f"{p[:5]} {p[5:]}",            # 98450 12345
            f"{p[:3]}-{p[3:6]}-{p[6:]}",  # 984-501-2345
            f"0{p}",                        # 09845012345
        ]

    @property
    def email_variants(self) -> list[str]:
        return [self.email, self.email.upper(), self.email.lower()]

    @property
    def name_variants(self) -> list[str]:
        parts = self.full_name.split()
        variants = [
            self.full_name,
            self.full_name.lower(),
            self.full_name.upper(),
            self.full_name_devanagari,
            self.full_name_kannada,
        ]
        if len(parts) >= 2:
            variants.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
        return [v for v in variants if v]

    def subject_ref(self, pepper: str = "") -> str:
        """Pseudonymous reference — HMAC of email+phone with server pepper."""
        cfg = get_settings()
        _pepper = pepper or cfg.service_key
        raw = f"{self.email}|{self.phone}".encode()
        return "sub_" + hmac.new(_pepper.encode(), raw, hashlib.sha256).hexdigest()[:20]


# ── HERO subject — main demo person ──────────────────────────────────────────
HERO = Subject(
    customer_id="KF-CUST-000042",
    full_name="Ananya Krishnamurthy",
    full_name_devanagari="अनन्या कृष्णमूर्ति",
    full_name_kannada="ಅನನ್ಯಾ ಕೃಷ್ಣಮೂರ್ತಿ",
    phone="9845012345",
    email="ananya.krishnamurthy@example.in",
    dob="1991-03-15",
    pan="ABCPK1234F",
    aadhaar_last4="7890",
    is_hero=True,
)

# ── DECOY subjects — same name, different phone/email ────────────────────────
DECOY_1 = Subject(
    customer_id="KF-CUST-001337",
    full_name="Ananya Krishnamurthy",
    full_name_devanagari="अनन्या कृष्णमूर्ति",
    full_name_kannada="ಅನನ್ಯಾ ಕೃಷ್ಣಮೂರ್ತಿ",
    phone="9900112233",
    email="ananya.k.different@example.in",
    dob="1995-07-22",
    pan="XYZPK9999Z",
    aadhaar_last4="1122",
    is_hero=False,
    decoy_note="Same name, different phone/email — must NOT be erased",
)

DECOY_2 = Subject(
    customer_id="KF-CUST-002048",
    full_name="Ananya K",
    full_name_devanagari="अनन्या के",
    full_name_kannada="ಅನನ್ಯಾ ಕೆ",
    phone="8877665544",
    email="ananya.k2@example.in",
    dob="1988-11-01",
    pan="MNOPK5678G",
    aadhaar_last4="3344",
    is_hero=False,
    decoy_note="Similar name, different identifiers — must NOT be erased",
)

ALL_SUBJECTS = [HERO, DECOY_1, DECOY_2]
