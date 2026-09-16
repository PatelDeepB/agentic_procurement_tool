"""Chief Procurement Officer (CPO) executive synthesis agent.

Synthesizes multi-tier vendor evaluations, commercial trade-offs, and technical
ambiguities into strategic procurement recommendations and actionable RFQ plans.
"""

import logging
from typing import List, Optional

from app.domain.models import (
    AmbiguityType,
    EvaluatedVendor,
    NormalizedSpecification,
)
from app.llm.base import BaseLLMClient
from app.llm.client import get_llm_client

logger = logging.getLogger(__name__)


class ExecutiveSynthesizerAgent:
    """Agent that produces executive-level procurement reasoning and strategic RFQ plans."""

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """Initialize synthesizer with unified or dedicated LLM client."""
        self.llm = llm_client or get_llm_client()

    def synthesize(
        self,
        spec: NormalizedSpecification,
        ahmedabad_vendors: List[EvaluatedVendor],
        india_vendors: List[EvaluatedVendor],
        global_vendors: List[EvaluatedVendor],
    ) -> str:
        """Generate high-level CPO executive synthesis with resilient deterministic fallback."""
        if self._should_call_llm():
            try:
                system_prompt = self._build_system_prompt()
                user_prompt = self._build_user_prompt(spec, ahmedabad_vendors, india_vendors, global_vendors)
                completion = self.llm.generate_completion(system_prompt, user_prompt, temperature=0.1)
                if completion and len(completion.strip()) > 50:
                    return completion.strip()
            except Exception as llm_error:
                logger.warning(f"LLM executive synthesis failed, falling back to deterministic CPO model: {llm_error}")

        return self._synthesize_deterministic(spec, ahmedabad_vendors, india_vendors, global_vendors)

    def _should_call_llm(self) -> bool:
        """Determine if active cloud LLM client should be called."""
        if not self.llm:
            return False
        if type(self.llm).__name__ == "MockLLMClient":
            return False
        return getattr(self.llm, "is_service_available", True)

    @staticmethod
    def _build_system_prompt() -> str:
        """Define Chief Procurement Officer persona and reporting structure."""
        return (
            "You are a Chief Procurement Officer (CPO) advising industrial buyers on steel piping requisitions. "
            "Deliver an executive procurement synthesis structured in four sections:\n"
            "1. Executive Feasibility & Technical Viability (IS 1239 compliance and ambiguity diagnosis)\n"
            "2. Strategic Dual-Sourcing Recommendation (balancing local speed vs mill bulk economies)\n"
            "3. Critical Commercial & Logistics Risk Matrix (MOQ, mass tolerance, freight corridors)\n"
            "4. Actionable Buyer RFQ Execution Plan (prioritized sequential next steps)\n"
            "Always include the exact header 'Executive Procurement Recommendation:' at the beginning."
        )

    def _build_user_prompt(
        self,
        spec: NormalizedSpecification,
        ahmedabad: List[EvaluatedVendor],
        india: List[EvaluatedVendor],
        global_vendors: List[EvaluatedVendor],
    ) -> str:
        """Construct rich procurement context prompt for LLM synthesis."""
        tonnage_str = f"{spec.total_estimated_metric_tons} MT" if spec.total_estimated_metric_tons else "Unspecified"
        pieces_str = f"{spec.total_estimated_pieces_6m} pieces" if spec.total_estimated_pieces_6m else "Unspecified"
        ambiguity_descriptions = [ambiguity.description for ambiguity in spec.ambiguities]

        lines = [
            f"Material Requisition: {spec.raw_input.material}",
            f"Target Destination: {spec.raw_input.location}",
            f"Specified Quantity: {spec.raw_input.quantity} ({spec.assumed_quantity_unit})",
            f"Estimated Batch Mass: {tonnage_str} (~{pieces_str})",
            f"Identified Ambiguities: {ambiguity_descriptions}",
            "",
            "Candidate Shortlist Overview:",
            self._build_tier_summary("Ahmedabad Local", ahmedabad),
            self._build_tier_summary("India-Wide Domestic", india),
            self._build_tier_summary("Global Exporters", global_vendors),
        ]
        return "\n".join(lines)

    @staticmethod
    def _format_vendor_line(vendor: EvaluatedVendor) -> str:
        """Format single vendor summary line for prompt context."""
        return (
            f"- Rank {vendor.rank} (Overall #{vendor.global_rank}): {vendor.vendor_name} | "
            f"Score: {vendor.confidence_score}% | Type: {vendor.vendor_type.value} | "
            f"Match: {vendor.match_category.value} | Location: {vendor.location}"
        )

    def _build_tier_summary(self, tier_name: str, vendors: List[EvaluatedVendor]) -> str:
        """Construct prompt section for a geographic tier."""
        if not vendors:
            return f"* {tier_name}: None qualified."
        vendor_lines = [self._format_vendor_line(vendor) for vendor in vendors[:3]]
        return f"* {tier_name} ({len(vendors)} qualified):\n" + "\n".join(vendor_lines)

    def _synthesize_deterministic(
        self,
        spec: NormalizedSpecification,
        ahmedabad: List[EvaluatedVendor],
        india: List[EvaluatedVendor],
        global_vendors: List[EvaluatedVendor],
    ) -> str:
        """Produce rich, material-tailored CPO synthesis deterministically."""
        lines = [
            "Executive Procurement Recommendation:",
            "",
            "### 1. Executive Feasibility & Technical Viability",
            *self._build_deterministic_feasibility(spec),
            "",
            "### 2. Strategic Dual-Sourcing Recommendation",
            *self._build_deterministic_sourcing_strategy(ahmedabad, india, global_vendors),
            "",
            "### 3. Critical Commercial & Logistics Risk Matrix",
            *self._build_deterministic_risk_matrix(spec),
            "",
            "### 4. Actionable Buyer RFQ Execution Plan",
            *self._build_deterministic_action_plan(spec, ahmedabad, india),
        ]
        return "\n".join(lines)

    @staticmethod
    def _build_deterministic_feasibility(spec: NormalizedSpecification) -> List[str]:
        """Synthesize technical feasibility notes for deterministic fallback."""
        feasibility = [
            f"- Requisition for '{spec.raw_input.material}' evaluated against IS 1239 Part 1 standards.",
        ]
        has_non_standard_wall = any(
            ambiguity.ambiguity_type == AmbiguityType.NON_STANDARD_WALL_THICKNESS
            for ambiguity in spec.ambiguities
        )
        has_nb_od = any(
            ambiguity.ambiguity_type == AmbiguityType.NOMINAL_BORE_VS_OUTSIDE_DIAMETER
            for ambiguity in spec.ambiguities
        )

        if has_non_standard_wall:
            feasibility.append(
                f"- Critical Thickness Finding: Specified {spec.parsed_wall_thickness_mm} mm wall exceeds standard "
                "Class C (Heavy) schedules. Standard off-the-shelf stockists cannot fulfill directly from routine inventory."
            )
        elif has_nb_od:
            feasibility.append(
                "- Dimensional Ambiguity Finding: Requirement specifies '40 mm', which standardizes to DN 40 (48.3 mm OD). "
                "Standard commercial supply assumes DN 40 Class B medium wall."
            )
        else:
            feasibility.append(
                "- Standard Compliance: Material dimensions fully align with commercial IS 1239 Class C Heavy schedules."
            )

        return feasibility

    @staticmethod
    def _build_deterministic_sourcing_strategy(
        ahmedabad: List[EvaluatedVendor],
        india: List[EvaluatedVendor],
        global_vendors: List[EvaluatedVendor],
    ) -> List[str]:
        """Construct multi-tier sourcing balance recommendations."""
        top_local = ahmedabad[0].vendor_name if ahmedabad else "Local GIDC Stockists"
        local_score = f" ({ahmedabad[0].confidence_score}%)" if ahmedabad else ""
        top_india = india[0].vendor_name if india else "Primary Domestic Mills"
        india_score = f" ({india[0].confidence_score}%)" if india else ""
        top_global = global_vendors[0].vendor_name if global_vendors else "Global Exporters"
        global_score = f" ({global_vendors[0].confidence_score}%)" if global_vendors else ""

        return [
            f"- Immediate / Emergency Buffer: Engage {top_local}{local_score} for immediate depot dispatch within 24-48 hours.",
            f"- Primary Volume Production: Place main manufacturing contract with {top_india}{india_score} for factory direct dispatch and verified Mill Test Certificates (EN 10204 Type 3.1).",
            f"- Strategic International Hedge: Maintain secondary qualification with {top_global}{global_score} for CIF Mundra Port supply on extended lead schedules.",
        ]

    @staticmethod
    def _build_deterministic_risk_matrix(spec: NormalizedSpecification) -> List[str]:
        """Identify key financial and physical supply chain risks."""
        risks = []
        has_unit_ambiguity = any(
            ambiguity.ambiguity_type == AmbiguityType.UNSPECIFIED_QUANTITY_UNIT
            for ambiguity in spec.ambiguities
        )
        if has_unit_ambiguity and spec.total_estimated_metric_tons:
            risks.append(
                f"- Commercial Volume Exposure: Quantity unit was unspecified; pricing assumes {spec.total_estimated_metric_tons} Metric Tons "
                f"(~{spec.total_estimated_pieces_6m} commercial 6m pieces). A unit mismatch could cause up to 6x billing variance."
            )

        has_non_standard_wall = any(
            ambiguity.ambiguity_type == AmbiguityType.NON_STANDARD_WALL_THICKNESS
            for ambiguity in spec.ambiguities
        )
        if has_non_standard_wall:
            risks.append(
                "- Production Minimum Order Quantity (MOQ): Primary mills mandate custom rolling lot sizes (typically 25-50 MT minimum). "
                "Partial deliveries cannot be sourced off-the-shelf without ASTM A53 Schedule 80 substitutions."
            )
        else:
            risks.append(
                "- Transit and Logistics Buffer: Domestic road haulage from Northern mills to Ahmedabad requires 3-5 business days."
            )

        return risks

    @staticmethod
    def _build_deterministic_action_plan(
        spec: NormalizedSpecification,
        ahmedabad: List[EvaluatedVendor],
        india: List[EvaluatedVendor],
    ) -> List[str]:
        """Generate numbered purchasing officer action plan."""
        top_local = ahmedabad[0].vendor_name if ahmedabad else "local stockists"
        top_india = india[0].vendor_name if india else "primary mill"

        plan = [
            "1. Buyer Clarification: Issue formal acknowledgment verifying assumed quantity unit and nominal bore dimensions.",
            f"2. Urgent Yard Check: Issue RFQ to {top_local} for local yard stock availability and same-day delivery terms.",
            f"3. Mill Tender: Submit binding commercial inquiry to {top_india} requesting factory lead time and EN 10204 3.1 MTC.",
            "4. Quality Assurance: Mandate BIS ISI marking verification and hydrostatic pressure testing before truckload dispatch.",
        ]

        has_non_standard_wall = any(
            ambiguity.ambiguity_type == AmbiguityType.NON_STANDARD_WALL_THICKNESS
            for ambiguity in spec.ambiguities
        )
        if has_non_standard_wall:
            plan.append("5. Technical Exception Review: Request engineering approval for ASTM A53 Schedule 80 equivalent if custom mill MOQ cannot be met.")

        return plan
