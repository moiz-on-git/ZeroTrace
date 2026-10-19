"""
ZeroTrace Retention Policy & Legal Hold Engine.
Evaluates category-level actions (ERASE_NOW vs HOLD_THEN_ERASE) against DPDP Act, 2023,
PMLA 2002, and RBI KYC Master Direction regulations.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
import os
from typing import Any, Dict, List, Tuple
import yaml
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import settings
from core.logging import logger
from models.entities import RetentionHoldRecord

POLICY_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "infra", "retention_policies.yaml")


class PolicyEngine:
    def __init__(self, policy_path: str = POLICY_FILE):
        self.policy_path = policy_path
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, Dict[str, Any]]:
        default_rules = {
            "kyc": {
                "action": "HOLD_THEN_ERASE",
                "duration_years": 5,
                "legal_basis": "PMLA 2002 Section 12 & RBI KYC Master Direction, 2016 (5-year lock)",
                "requires_legal_review": True
            },
            "financial": {
                "action": "HOLD_THEN_ERASE",
                "duration_years": 5,
                "legal_basis": "Companies Act, 2013 (Section 128) & RBI NBFC Account Books Preservation Guidelines",
                "requires_legal_review": True
            },
            "identity": {
                "action": "ERASE_NOW",
                "duration_years": 0,
                "legal_basis": "DPDP Act, 2023 (Section 12(1) & 6(4))",
                "requires_legal_review": True
            },
            "marketing": {
                "action": "ERASE_NOW",
                "duration_years": 0,
                "legal_basis": "DPDP Act, 2023 (Section 8(7) Purpose Limitation)",
                "requires_legal_review": True
            },
            "embedding": {
                "action": "ERASE_NOW",
                "duration_years": 0,
                "legal_basis": "DPDP Act, 2023 & Indian AI Privacy Safeguards",
                "requires_legal_review": True
            },
            "cache": {
                "action": "ERASE_NOW",
                "duration_years": 0,
                "legal_basis": "DPDP Act, 2023 Data Minimisation",
                "requires_legal_review": True
            }
        }
        if os.path.exists(self.policy_path):
            try:
                with open(self.policy_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    rules_map = {}
                    for item in data.get("policies", []):
                        rules_map[item["category"]] = item
                    return rules_map
            except Exception as e:
                logger.warn("failed_to_load_policy_yaml_using_defaults", error=str(e))
        return default_rules

    async def evaluate_holds(
        self,
        session: AsyncSession,
        job_id: str,
        locations: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Evaluates locations, returns list of holds to pass to Data Plane and records them in retention_holds.
        Returns: (holds_list, has_holds)
        """
        now = datetime.now(timezone.utc)
        holds_list: List[Dict[str, Any]] = []

        # Find categories present in locations
        categories = {loc.get("data_category", "general") for loc in locations}

        for cat in categories:
            rule = self.rules.get(cat)
            if rule and rule.get("action") == "HOLD_THEN_ERASE":
                years = rule.get("duration_years", 5)
                release_date = now + timedelta(days=365 * years)
                legal_basis = rule.get("legal_basis", "Statutory preservation")

                hold_dict = {
                    "category": cat,
                    "legal_basis": legal_basis,
                    "release_date": release_date.isoformat(),
                    "count": 1
                }
                holds_list.append(hold_dict)

                # Persist in DB
                hold_record = RetentionHoldRecord(
                    job_id=job_id,
                    category=cat,
                    legal_basis=legal_basis,
                    release_date=release_date,
                    count=1,
                    status="ACTIVE"
                )
                session.add(hold_record)

        await session.commit()
        has_holds = len(holds_list) > 0
        return holds_list, has_holds
