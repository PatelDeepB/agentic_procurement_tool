"""Technical evaluation and grounded evidence extraction agent with LLM reasoning.

Evaluates vendor suitability against normalized requirements, determines
match categories, extracts sourced evidence, documents assumptions, and
identifies unresolved RFQ items without hallucinating data.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.domain.models import (
    AmbiguityType,
    MatchCategory,
    NormalizedSpecification,
    VendorEvidence,
    VendorTier,
)
from app.llm.client import BaseLLMClient, get_llm_client


class EvaluatorAgent:
    """Agent that performs grounded technical evaluation and evidence extraction."""

    SYSTEM_PROMPT = (
        "You are an expert Procurement Technical Auditor. Evaluate the vendor profile "
        "against the buyer specification. You must strictly distinguish verified catalog "
        "facts [SOURCED] from inferences [ASSUMPTION] and required inquiries [NEEDS_CONFIRMATION_RFQ]. "
        "Never invent prices, stock numbers, or lead times."
    )

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """Initialize evaluator with LLM client."""
        self.llm = llm_client or get_llm_client()

    def evaluate_vendor(
        self,
        vendor: Dict[str, Any],
        spec: NormalizedSpecification,
    ) -> Tuple[MatchCategory, VendorEvidence, List[str], str]:
        """Evaluate a single vendor against specifications, extracting grounded evidence."""
        match_cat = self._determine_match_category(vendor, spec)
        sourced_facts = self._extract_sourced_facts(vendor, spec)
        assumptions = self._extract_assumptions(vendor, spec)
        rfq_items = self._extract_rfq_items(vendor, spec)
        unresolved_issues = self._identify_unresolved_issues(vendor, spec)
        recommended_next_step = self._formulate_next_step(vendor, spec)

        # Execute LLM reasoning trace for audit
        self._generate_llm_evaluation_trace(vendor, spec)

        evidence = VendorEvidence(
            sourced_facts=sourced_facts,
            assumptions=assumptions,
            needs_confirmation_rfq=rfq_items,
            catalog_spec=vendor.get("catalog_spec", ""),
            source_url=vendor.get("source_url", ""),
            contact_email=vendor.get("contact_email"),
            contact_phone=vendor.get("contact_phone"),
            address=vendor.get("address", ""),
            certifications=vendor.get("certifications", []),
        )

        return match_cat, evidence, unresolved_issues, recommended_next_step

    def _generate_llm_evaluation_trace(
        self,
        vendor: Dict[str, Any],
        spec: NormalizedSpecification,
    ) -> str:
        """Invoke LLM to produce evaluation reasoning."""
        user_prompt = (
            f"Evaluate vendor '{vendor.get('vendor_name')}' ({vendor.get('location')}) "
            f"for supplying '{spec.raw_input.material}'. "
            f"Vendor products: {vendor.get('supported_products')}. "
            f"Certifications: {', '.join(vendor.get('certifications', []))}."
        )
        return self.llm.generate_completion(self.SYSTEM_PROMPT, user_prompt)

    def _determine_match_category(
        self,
        vendor: Dict[str, Any],
        spec: NormalizedSpecification,
    ) -> MatchCategory:
        """Categorize match precision level."""
        supported_standards = vendor.get("supported_standards", [])
        supported_classes = vendor.get("supported_classes", [])
        max_wall = vendor.get("max_wall_thickness_mm", 0.0)
        req_wall = spec.parsed_wall_thickness_mm or 0.0

        has_is1239 = "IS 1239" in supported_standards
        has_intl_equiv = any(s in supported_standards for s in ["ASTM A53", "BS 1387", "EN 10255"])
        has_thickness_capability = max_wall >= req_wall if req_wall > 0 else True

        if has_is1239 and has_thickness_capability:
            if spec.parsed_class and spec.parsed_class not in supported_classes and "Class C" not in supported_classes:
                return MatchCategory.NEAR_MATCH
            return MatchCategory.EXACT_MATCH

        if has_intl_equiv and has_thickness_capability:
            return MatchCategory.NEAR_MATCH

        if has_is1239 or has_intl_equiv:
            return MatchCategory.CATEGORY_LEVEL_LEAD

        return MatchCategory.UNVERIFIED_LEAD

    def _extract_sourced_facts(
        self,
        vendor: Dict[str, Any],
        spec: NormalizedSpecification,
    ) -> List[str]:
        """Extract verified facts directly from registry data."""
        return [
            f"[SOURCED] Operating location: {vendor.get('location')} ({vendor.get('address')}).",
            f"[SOURCED] Vendor type: {vendor.get('vendor_type')}.",
            f"[SOURCED] Supported product scope: {vendor.get('supported_products')}.",
            f"[SOURCED] Verified certifications: {', '.join(vendor.get('certifications', []))}.",
            f"[SOURCED] Capacity / inventory evidence: {vendor.get('stock_or_capacity_evidence')}.",
            f"[SOURCED] Delivery / logistics: {vendor.get('delivery_evidence')}.",
        ]

    def _extract_assumptions(
        self,
        vendor: Dict[str, Any],
        spec: NormalizedSpecification,
    ) -> List[str]:
        """Document engineering inferences made during evaluation."""
        assumptions: List[str] = []
        tier = vendor.get("tier")

        if tier == VendorTier.AHMEDABAD.value:
            assumptions.append("[ASSUMPTION] Vendor can supply standard order quantities from local warehouse.")
        elif tier == VendorTier.INDIA_OUTSIDE_AHMEDABAD.value:
            assumptions.append("[ASSUMPTION] Supply will be routed via Ahmedabad branch depot or direct freight trailer.")
        else:
            assumptions.append(
                "[ASSUMPTION] Requires import customs clearance at Mundra/Kandla port with lead time of 2 to 4 weeks."
            )

        has_non_standard_wall = any(
            a.ambiguity_type == AmbiguityType.NON_STANDARD_WALL_THICKNESS
            for a in spec.ambiguities
        )

        if has_non_standard_wall and spec.parsed_wall_thickness_mm:
            assumptions.append(
                f"[ASSUMPTION] Vendor is evaluated on capability to roll heavy gauge ({spec.parsed_wall_thickness_mm} mm) "
                "or supply ASTM A53 Schedule 80 equivalent."
            )

        return assumptions

    def _extract_rfq_items(
        self,
        vendor: Dict[str, Any],
        spec: NormalizedSpecification,
    ) -> List[str]:
        """Identify critical technical and commercial items requiring RFQ confirmation."""
        rfq_items: List[str] = [
            "[NEEDS_CONFIRMATION_RFQ] Obtain binding price quote and commercial payment terms.",
            "[NEEDS_CONFIRMATION_RFQ] Request Mill Test Certificate (MTC) per EN 10204 Type 3.1.",
        ]

        has_non_standard_wall = any(
            a.ambiguity_type == AmbiguityType.NON_STANDARD_WALL_THICKNESS
            for a in spec.ambiguities
        )

        if has_non_standard_wall and spec.parsed_wall_thickness_mm:
            rfq_items.append(
                f"[NEEDS_CONFIRMATION_RFQ] Confirm minimum order quantity (MOQ) for custom {spec.parsed_wall_thickness_mm} mm wall rolling."
            )

        if vendor.get("tier") == VendorTier.GLOBAL.value:
            rfq_items.append("[NEEDS_CONFIRMATION_RFQ] Confirm CIF Mundra / FOB shipping terms, port handling, and import duty.")

        return rfq_items

    def _identify_unresolved_issues(
        self,
        vendor: Dict[str, Any],
        spec: NormalizedSpecification,
    ) -> List[str]:
        """List unresolved risks or gaps for procurement follow-up."""
        issues: List[str] = []
        if vendor.get("tier") == VendorTier.GLOBAL.value:
            issues.append("International transit time (15-30 days) and currency exchange fluctuations.")

        has_non_standard_wall = any(
            a.ambiguity_type == AmbiguityType.NON_STANDARD_WALL_THICKNESS
            for a in spec.ambiguities
        )

        if has_non_standard_wall and spec.parsed_wall_thickness_mm:
            issues.append(f"Custom rolling lead time required for non-standard {spec.parsed_wall_thickness_mm} mm wall.")
        if not vendor.get("contact_phone"):
            issues.append("Direct phone contact unverified.")
        return issues

    def _formulate_next_step(
        self,
        vendor: Dict[str, Any],
        spec: NormalizedSpecification,
    ) -> str:
        """Formulate recommended next action for the buyer."""
        tier = vendor.get("tier")
        name = vendor.get("vendor_name")
        if tier == VendorTier.AHMEDABAD.value:
            return f"Issue RFQ to {name} for immediate local stock check and same-day depot pickup quote."
        if tier == VendorTier.INDIA_OUTSIDE_AHMEDABAD.value:
            return f"Submit formal inquiry to {name} commercial sales for factory dispatch schedule and MTC review."
        return f"Request international quotation from {name} including CIF Mundra freight, customs HS code, and export lead time."
