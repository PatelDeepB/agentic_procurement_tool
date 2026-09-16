"""Deterministic scoring, ranking, and deduplication agent.

Computes multi-criteria confidence scores, ranks candidates within geographic
tiers, deduplicates multi-channel leads, and explains inclusion rationale.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.domain.models import (
    EvaluatedVendor,
    MatchCategory,
    NormalizedSpecification,
    VendorEvidence,
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
        """Deduplicate, calculate composite scores, and assign intra-tier and global ranks."""
        deduplicated = self._deduplicate_candidates(evaluated_candidates)
        scored_list = [self._build_evaluated_vendor(item, spec) for item in deduplicated]

        scored_list.sort(
            key=lambda candidate: (
                -candidate.confidence_score,
                -candidate.score_breakdown.get("technical_fit", 0.0),
                -candidate.score_breakdown.get("certifications", 0.0),
                candidate.vendor_name,
            )
        )

        return self._assign_tier_and_global_ranks(scored_list)

    def _build_evaluated_vendor(
        self,
        item: Dict[str, Any],
        spec: NormalizedSpecification,
    ) -> EvaluatedVendor:
        """Construct EvaluatedVendor instance with calculated composite score."""
        vendor = item.get("raw_vendor", item)
        match_cat = item.get("match_category", MatchCategory.EXACT_MATCH)
        if isinstance(match_cat, str):
            try:
                match_cat = MatchCategory(match_cat)
            except ValueError:
                match_cat = MatchCategory.CATEGORY_LEVEL_LEAD

        score, breakdown = self._calculate_confidence_score(vendor, match_cat, spec)
        tier = self._parse_vendor_tier(vendor.get("tier"))
        vendor_type = self._parse_vendor_type(vendor.get("vendor_type"))
        evidence = item.get("evidence") or self._synthesize_evidence(vendor)

        return EvaluatedVendor(
            vendor_name=vendor.get("vendor_name", "Unknown Vendor"),
            tier=tier,
            location=vendor.get("location", ""),
            country=vendor.get("country", "India"),
            vendor_type=vendor_type,
            match_category=match_cat,
            confidence_score=round(score, 1),
            score_breakdown=breakdown,
            evidence=evidence,
            unresolved_issues=item.get("unresolved_issues", []),
            recommended_next_step=item.get("recommended_next_step", "Issue RFQ"),
            rank=1,
            global_rank=1,
        )

    @staticmethod
    def _synthesize_evidence(vendor: Dict[str, Any]) -> VendorEvidence:
        """Synthesize default evidence model from raw vendor dictionary."""
        return VendorEvidence(
            catalog_spec=vendor.get("catalog_spec", "Catalog reference"),
            source_url=vendor.get("source_url") or vendor.get("website", "https://example.com"),
            address=vendor.get("address", "Registered facility"),
            contact_email=vendor.get("contact_email"),
            contact_phone=vendor.get("contact_phone"),
            certifications=vendor.get("certifications") or [],
            stock_or_capacity_evidence=vendor.get("stock_or_capacity_evidence"),
            delivery_evidence=vendor.get("delivery_evidence"),
        )

    @staticmethod
    def _assign_tier_and_global_ranks(
        scored_list: List[EvaluatedVendor],
    ) -> List[EvaluatedVendor]:
        """Assign sequential global ranks and intra-tier ranks (1..N within each tier)."""
        tier_counters: Dict[VendorTier, int] = {
            VendorTier.AHMEDABAD: 0,
            VendorTier.INDIA_OUTSIDE_AHMEDABAD: 0,
            VendorTier.GLOBAL: 0,
        }

        for global_index, vendor in enumerate(scored_list, start=1):
            vendor.global_rank = global_index
            tier_counters[vendor.tier] = tier_counters.get(vendor.tier, 0) + 1
            vendor.rank = tier_counters[vendor.tier]

        return scored_list

    @staticmethod
    def _parse_vendor_tier(tier_value: Any) -> VendorTier:
        """Safely parse vendor tier with case-insensitive fallback."""
        if isinstance(tier_value, VendorTier):
            return tier_value
        if isinstance(tier_value, str):
            clean_tier = tier_value.strip().upper()
            for tier_member in VendorTier:
                if tier_member.value == clean_tier:
                    return tier_member
        return VendorTier.GLOBAL

    @staticmethod
    def _parse_vendor_type(type_value: Any) -> VendorType:
        """Safely parse vendor type with case-insensitive fallback."""
        if isinstance(type_value, VendorType):
            return type_value
        if isinstance(type_value, str):
            clean_type = type_value.strip().upper()
            for type_member in VendorType:
                if type_member.value == clean_type:
                    return type_member
        return VendorType.STOCKIST_TRADER

    def _deduplicate_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate vendor entries based on normalized vendor name."""
        seen_names = set()
        deduped: List[Dict[str, Any]] = []
        for candidate in candidates:
            raw_vendor = candidate.get("raw_vendor", candidate)
            name = raw_vendor.get("vendor_name", "").strip().lower()
            if name not in seen_names:
                seen_names.add(name)
                deduped.append(candidate)
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
            "certifications": self._score_certifications(vendor.get("certifications")),
            "capacity_feasibility": self._score_capacity(vendor.get("vendor_type"), spec),
            "geographic_logistics": self._score_geography(
                vendor.get("tier"),
                vendor.get("delivery_evidence"),
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
    def _score_certifications(certs: Optional[List[str]]) -> float:
        """Score recognized quality and standard certifications (25 points max)."""
        cert_list = certs or []
        cert_text = " ".join(cert_list).upper()
        if "IS 1239" in cert_text and "ISO" in cert_text:
            return 25.0
        if any(std in cert_text for std in ["ISO", "ASTM", "API"]):
            return 20.0
        if cert_list:
            return 15.0
        return 5.0

    @staticmethod
    def _score_capacity(
        vendor_type: Optional[Any],
        spec: Optional[NormalizedSpecification] = None,
    ) -> float:
        """Score production volume and order fulfillment capacity (20 points max)."""
        clean_type = (
            vendor_type.value if isinstance(vendor_type, VendorType)
            else (str(vendor_type).strip().upper() if vendor_type else "")
        )

        if clean_type == VendorType.PRIMARY_MANUFACTURER.value:
            base_score = 20.0
        elif clean_type == VendorType.AUTHORIZED_DISTRIBUTOR.value:
            base_score = 17.0
        elif clean_type == VendorType.STOCKIST_TRADER.value:
            base_score = 14.0
        elif clean_type == VendorType.EPC_SUPPLIER.value:
            base_score = 12.0
        else:
            base_score = 10.0

        if spec and spec.total_estimated_metric_tons:
            is_heavy_batch = spec.total_estimated_metric_tons > 50.0
            if is_heavy_batch and clean_type in [VendorType.STOCKIST_TRADER.value, VendorType.EPC_SUPPLIER.value]:
                base_score = max(8.0, base_score - 2.0)

        return base_score

    @staticmethod
    def _score_geography(tier: Optional[Any], delivery_text: Optional[str]) -> float:
        """Score transit distance and warehouse proximity (15 points max)."""
        clean_tier = (
            tier.value if isinstance(tier, VendorTier)
            else (str(tier).strip().upper() if tier else "")
        )
        if clean_tier == VendorTier.AHMEDABAD.value:
            return 15.0
        if clean_tier == VendorTier.INDIA_OUTSIDE_AHMEDABAD.value:
            delivery_lower = (delivery_text or "").lower()
            if any(hub in delivery_lower for hub in ["changodar", "sarkhej", "ahmedabad"]):
                return 14.0
            return 11.0
        return 8.0

    @staticmethod
    def _score_traceability(vendor: Dict[str, Any]) -> float:
        """Score verifiable digital and physical contact footprint (5 points max)."""
        has_email = bool(vendor.get("contact_email"))
        has_phone = bool(vendor.get("contact_phone"))
        has_url = bool(vendor.get("source_url") or vendor.get("website"))
        has_address = bool(vendor.get("address"))

        score = 2.0 if has_address else 0.0
        if has_url:
            score += 1.5

        if has_email and has_phone:
            score += 1.5
        elif has_email or has_phone:
            score += 0.75

        return min(5.0, score)

