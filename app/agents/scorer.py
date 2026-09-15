"""Deterministic scoring, ranking, and deduplication agent.

Computes multi-criteria confidence scores, ranks candidates within geographic
tiers, deduplicates multi-channel leads, and explains inclusion rationale.
"""

from typing import Any, Dict, List

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
            evidence = item["evidence"]
            unresolved = item["unresolved_issues"]
            next_step = item["recommended_next_step"]

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
                evidence=evidence,
                unresolved_issues=unresolved,
                recommended_next_step=next_step,
                rank=1,
            )
            scored_list.append(evaluated_vendor)

        # Sort descending by confidence score
        scored_list.sort(key=lambda v: v.confidence_score, reverse=True)

        # Assign ranks
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
    ) -> (float, Dict[str, float]):
        """Calculate composite confidence score out of 100 points."""
        breakdown: Dict[str, float] = {}

        # 1. Technical Fit (35 points max)
        if match_cat == MatchCategory.EXACT_MATCH:
            breakdown["technical_fit"] = 35.0
        elif match_cat == MatchCategory.NEAR_MATCH:
            breakdown["technical_fit"] = 27.0
        elif match_cat == MatchCategory.CATEGORY_LEVEL_LEAD:
            breakdown["technical_fit"] = 18.0
        else:
            breakdown["technical_fit"] = 8.0

        # 2. Standards & Certifications (25 points max)
        certs = vendor.get("certifications", [])
        cert_text = " ".join(certs).upper()
        if "IS 1239" in cert_text and "ISO" in cert_text:
            breakdown["certifications"] = 25.0
        elif "ISO" in cert_text or "ASTM" in cert_text or "API" in cert_text:
            breakdown["certifications"] = 20.0
        elif len(certs) > 0:
            breakdown["certifications"] = 15.0
        else:
            breakdown["certifications"] = 5.0

        # 3. Capacity & Bulk-Order Feasibility (20 points max)
        v_type = vendor.get("vendor_type")
        if v_type == VendorType.PRIMARY_MANUFACTURER.value:
            breakdown["capacity_feasibility"] = 20.0
        elif v_type == VendorType.AUTHORIZED_DISTRIBUTOR.value:
            breakdown["capacity_feasibility"] = 17.0
        elif v_type == VendorType.STOCKIST_TRADER.value:
            breakdown["capacity_feasibility"] = 14.0
        else:
            breakdown["capacity_feasibility"] = 10.0

        # 4. Geographic Delivery Feasibility (15 points max)
        tier = vendor.get("tier")
        if tier == VendorTier.AHMEDABAD.value:
            breakdown["geographic_logistics"] = 15.0
        elif tier == VendorTier.INDIA_OUTSIDE_AHMEDABAD.value:
            # Check if vendor has local depot or fast corridor
            delivery_text = vendor.get("delivery_evidence", "").lower()
            if "changodar" in delivery_text or "sarkhej" in delivery_text or "ahmedabad" in delivery_text:
                breakdown["geographic_logistics"] = 14.0
            else:
                breakdown["geographic_logistics"] = 11.0
        else:
            # Global tier
            breakdown["geographic_logistics"] = 8.0

        # 5. Evidence & Contact Traceability (5 points max)
        has_email = bool(vendor.get("contact_email"))
        has_phone = bool(vendor.get("contact_phone"))
        has_url = bool(vendor.get("source_url"))
        contact_score = 2.0 + (1.5 if has_email and has_phone else 0.5) + (1.5 if has_url else 0.0)
        breakdown["traceability"] = min(5.0, contact_score)

        total_score = sum(breakdown.values())
        return total_score, breakdown
