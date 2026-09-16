"""Qualification-gated weighted supplier scoring.

This scorer is intentionally separate from ``ScorerAgent`` so the original
assessment model remains available for comparison. It adapts a weighted
1-to-5 supplier framework to industrial pipe procurement.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.domain.models import MatchCategory, NormalizedSpecification, VendorTier, VendorType


@dataclass
class WeightedVendorScore:
    """Explainable result for one vendor under the weighted model."""

    vendor_name: str
    qualified: bool
    weighted_score: float
    criteria_scores: Dict[str, int]
    qualification_failures: List[str] = field(default_factory=list)
    rationale: List[str] = field(default_factory=list)
    rank: int = 0


class WeightedScorerAgent:
    """Score vendors with qualification gates and weighted 1-to-5 rubrics."""

    WEIGHTS: Dict[str, int] = {
        "technical_compliance": 35,
        "quality_certification": 20,
        "capacity_feasibility": 20,
        "logistics": 15,
        "commercial_readiness": 5,
        "evidence_traceability": 5,
    }

    def score_and_rank(self, evaluated_candidates: List[Dict[str, Any]], spec: NormalizedSpecification) -> List[WeightedVendorScore]:
        """Qualify, score, and rank evaluated vendor candidates."""
        results = [self._score_candidate(candidate, spec) for candidate in self._deduplicate(evaluated_candidates)]
        results.sort(key=lambda item: (item.qualified, item.weighted_score), reverse=True)
        for index, result in enumerate(results, start=1):
            result.rank = index
        return results

    def _score_candidate(self, candidate: Dict[str, Any], spec: NormalizedSpecification) -> WeightedVendorScore:
        vendor = candidate["raw_vendor"]
        match_category = candidate.get("match_category", MatchCategory.UNVERIFIED_LEAD)
        criteria_scores = {
            "technical_compliance": self._technical_score(vendor, spec, match_category),
            "quality_certification": self._quality_score(vendor, spec),
            "capacity_feasibility": self._capacity_score(vendor),
            "logistics": self._logistics_score(vendor),
            "commercial_readiness": self._commercial_score(vendor),
            "evidence_traceability": self._evidence_score(vendor),
        }
        failures = self._qualification_failures(vendor, spec)
        weighted_score = sum(criteria_scores[name] * weight / 5 for name, weight in self.WEIGHTS.items())
        if failures:
            weighted_score = 0.0

        rationale = [f"{name}: {score}/5 ({self.WEIGHTS[name]}% weight)" for name, score in criteria_scores.items()]
        if failures:
            rationale.append("Vendor is excluded from qualified ranking until mandatory gaps are resolved.")

        return WeightedVendorScore(
            vendor_name=vendor.get("vendor_name", "Unknown Vendor"),
            qualified=not failures,
            weighted_score=round(weighted_score, 1),
            criteria_scores=criteria_scores,
            qualification_failures=failures,
            rationale=rationale,
        )

    def _qualification_failures(self, vendor: Dict[str, Any], spec: NormalizedSpecification) -> List[str]:
        failures: List[str] = []
        supported_standards = vendor.get("supported_standards", [])
        required_standard = spec.parsed_standard
        if required_standard and required_standard not in supported_standards:
            failures.append(f"Required standard {required_standard} is not listed as supported.")

        required_dn = spec.parsed_dn_mm
        if required_dn:
            lower, upper = vendor.get("supported_dn_range", [0, 0])
            if not lower <= required_dn <= upper:
                failures.append(f"DN {required_dn} is outside the vendor's supported range.")

        required_wall = spec.parsed_wall_thickness_mm
        if required_wall and vendor.get("max_wall_thickness_mm", 0.0) < required_wall:
            failures.append(f"Required wall thickness {required_wall} mm exceeds vendor capability.")
        return failures

    def _technical_score(self, vendor: Dict[str, Any], spec: NormalizedSpecification, match_category: MatchCategory) -> int:
        if match_category == MatchCategory.EXACT_MATCH:
            return 5
        if match_category == MatchCategory.NEAR_MATCH:
            return 4
        if match_category == MatchCategory.CATEGORY_LEVEL_LEAD:
            return 3
        return 1

    def _quality_score(self, vendor: Dict[str, Any], spec: NormalizedSpecification) -> int:
        certifications = " ".join(vendor.get("certifications", [])).upper()
        if spec.parsed_standard and spec.parsed_standard.upper() in certifications and "ISO" in certifications:
            return 5
        if "ISO" in certifications or "BIS" in certifications:
            return 4
        if certifications:
            return 3
        return 1

    def _capacity_score(self, vendor: Dict[str, Any]) -> int:
        vendor_type = vendor.get("vendor_type")
        if vendor_type == VendorType.PRIMARY_MANUFACTURER.value:
            return 5
        if vendor_type == VendorType.AUTHORIZED_DISTRIBUTOR.value:
            return 4
        if vendor_type == VendorType.STOCKIST_TRADER.value:
            return 3
        return 2

    def _logistics_score(self, vendor: Dict[str, Any]) -> int:
        tier = vendor.get("tier")
        evidence = vendor.get("delivery_evidence", "").lower()
        if tier == VendorTier.AHMEDABAD.value:
            return 5
        if tier == VendorTier.INDIA_OUTSIDE_AHMEDABAD.value:
            return 4 if any(term in evidence for term in ("ahmedabad", "changodar", "sarkhej")) else 3
        return 2

    def _commercial_score(self, vendor: Dict[str, Any]) -> int:
        """Score RFQ readiness only; price is intentionally never inferred."""
        return 4 if vendor.get("contact_email") and vendor.get("contact_phone") else 2

    def _evidence_score(self, vendor: Dict[str, Any]) -> int:
        evidence_fields = ("source_url", "address", "stock_or_capacity_evidence", "delivery_evidence")
        present = sum(bool(vendor.get(field)) for field in evidence_fields)
        return min(5, max(1, present + bool(vendor.get("certifications"))))

    def _deduplicate(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        unique = []
        for candidate in candidates:
            name = candidate["raw_vendor"].get("vendor_name", "").strip().lower()
            if name not in seen:
                seen.add(name)
                unique.append(candidate)
        return unique