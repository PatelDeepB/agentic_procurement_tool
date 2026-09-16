"""Deterministic scoring, ranking, and deduplication agent.

Computes multi-criteria confidence scores, ranks candidates within geographic
tiers, deduplicates multi-channel leads, and explains inclusion rationale.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.domain.models import (
    EvaluatedVendor,
    MatchCategory,
    NormalizedSpecification,
    VendorTier,
    VendorType,
)


class ScorerAgent:
    """Agent responsible for deterministic confidence scoring, deduplication, and ranking."""

    def score_and_rank(
        self,
        evaluated_candidates: List[Dict[str, Any]],
        spec: NormalizedSpecification,
    ) -> List[EvaluatedVendor]:
        """Deduplicate, calculate composite scores, and sort candidates by rank."""
        deduplicated = self._deduplicate_candidates(evaluated_candidates)
        scored_list: List[EvaluatedVendor] = []

        for item in deduplicated:
            vendor = item["raw_vendor"]
            match_cat: MatchCategory = item["match_category"]
            score, breakdown = self._calculate_confidence_score(vendor, match_cat, spec)

            evaluated_vendor = EvaluatedVendor(
                vendor_name=vendor.get("vendor_name", "Unknown Vendor"),
                tier=VendorTier(vendor.get("tier")),
                location=vendor.get("location", ""),
                country=vendor.get("country", "India"),
                vendor_type=VendorType(vendor.get("vendor_type")),
                match_category=match_cat,
                confidence_score=round(score, 1),
                score_breakdown=breakdown,
                evidence=item["evidence"],
                unresolved_issues=item["unresolved_issues"],
                recommended_next_step=item["recommended_next_step"],
                rank=1,
            )
            scored_list.append(evaluated_vendor)

        scored_list.sort(key=lambda vendor: vendor.confidence_score, reverse=True)
        for index, vendor in enumerate(scored_list, start=1):
            vendor.rank = index

        return scored_list

    def _deduplicate_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate vendor entries based on normalized vendor name."""
        seen_names = set()
        deduped: List[Dict[str, Any]] = []
        for cand in candidates:
            name = cand["raw_vendor"].get("vendor_name", "").strip().lower()
            if name not in seen_names:
                seen_names.add(name)
                deduped.append(cand)
        return deduped

    def _calculate_confidence_score(
        self,
        vendor: Dict[str, Any],
        match_cat: MatchCategory,
        spec: NormalizedSpecification,
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate composite confidence score out of 100 points."""
        breakdown: Dict[str, float] = {
            "technical_fit": self._score_technical_fit(match_cat),
            "certifications": self._score_certifications(vendor.get("certifications", [])),
            "capacity_feasibility": self._score_capacity(vendor.get("vendor_type")),
            "geographic_logistics": self._score_geography(
                vendor.get("tier"),
                vendor.get("delivery_evidence", "").lower(),
            ),
            "traceability": self._score_traceability(vendor),
        }
        return sum(breakdown.values()), breakdown

    @staticmethod
    def _score_technical_fit(match_cat: MatchCategory) -> float:
        """Score technical alignment (35 points max)."""
        if match_cat == MatchCategory.EXACT_MATCH:
            return 35.0
        if match_cat == MatchCategory.NEAR_MATCH:
            return 27.0
        if match_cat == MatchCategory.CATEGORY_LEVEL_LEAD:
            return 18.0
        return 8.0

    @staticmethod
    def _score_certifications(certs: List[str]) -> float:
        """Score recognized quality and standard certifications (25 points max)."""
        cert_text = " ".join(certs).upper()
        if "IS 1239" in cert_text and "ISO" in cert_text:
            return 25.0
        if any(std in cert_text for std in ["ISO", "ASTM", "API"]):
            return 20.0
        if certs:
            return 15.0
        return 5.0

    @staticmethod
    def _score_capacity(vendor_type: Optional[str]) -> float:
        """Score production volume and order fulfillment capacity (20 points max)."""
        if vendor_type == VendorType.PRIMARY_MANUFACTURER.value:
            return 20.0
        if vendor_type == VendorType.AUTHORIZED_DISTRIBUTOR.value:
            return 17.0
        if vendor_type == VendorType.STOCKIST_TRADER.value:
            return 14.0
        return 10.0

    @staticmethod
    def _score_geography(tier: Optional[str], delivery_text: str) -> float:
        """Score transit distance and warehouse proximity (15 points max)."""
        if tier == VendorTier.AHMEDABAD.value:
            return 15.0
        if tier == VendorTier.INDIA_OUTSIDE_AHMEDABAD.value:
            if any(hub in delivery_text for hub in ["changodar", "sarkhej", "ahmedabad"]):
                return 14.0
            return 11.0
        return 8.0

    @staticmethod
    def _score_traceability(vendor: Dict[str, Any]) -> float:
        """Score verifiable digital and physical contact footprint (5 points max)."""
        has_email = bool(vendor.get("contact_email"))
        has_phone = bool(vendor.get("contact_phone"))
        has_url = bool(vendor.get("source_url"))
        contact_score = 2.0 + (1.5 if has_email and has_phone else 0.5) + (1.5 if has_url else 0.0)
        return min(5.0, contact_score)
