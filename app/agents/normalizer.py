"""Specification normalizer and ambiguity detection agent with unified single-call LLM reasoning.

Combines prompt-driven language understanding in a single cost-optimized LLM call
with deterministic physical mathematics (ReAct) to extract specifications and
diagnose quantity and technical ambiguities.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.agents.normalizer_fallback import (
    detect_explicit_unit,
    fallback_deterministic_parse,
)
from app.agents.normalizer_prompts import (
    NORMALIZER_SYSTEM_PROMPT,
    build_quantity_conversions,
    create_quantity_ambiguity,
    safe_parse_ambiguity_type,
    safe_parse_severity,
)
from app.core.standards import find_is1239_dn_by_od
from app.domain.models import (
    AmbiguityItem,
    AmbiguitySeverity,
    AmbiguityType,
    MaterialInput,
    NormalizedSpecification,
    UnifiedNormalizerLLMResponse,
)
from app.llm.client import BaseLLMClient, get_llm_client
from app.tools.procurement_tools import (
    tool_calculate_steel_tonnage,
    tool_evaluate_wall_thickness,
    tool_lookup_is1239_spec,
)

logger = logging.getLogger(__name__)


class NormalizerAgent:
    """Agent that normalizes material requirements via a single structured LLM call and tools."""

    SYSTEM_PROMPT = NORMALIZER_SYSTEM_PROMPT

    _detect_explicit_unit = staticmethod(detect_explicit_unit)
    _safe_parse_ambiguity_type = staticmethod(safe_parse_ambiguity_type)
    _safe_parse_severity = staticmethod(safe_parse_severity)

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """Initialize agent with LLM client."""
        self.llm = llm_client or get_llm_client()

    def normalize(self, raw_input: MaterialInput) -> NormalizedSpecification:
        """Analyze raw material request in a single LLM call, invoke tools, and return normalized spec."""
        llm_data = self._execute_unified_llm_call(raw_input)
        ambiguities = self._build_ambiguities_from_llm(llm_data, raw_input)

        eff_dn, eff_od, eff_wall, is_class_assumed = self._determine_effective_dimensions(
            llm_data.parsed_dn_mm,
            llm_data.parsed_od_mm,
            llm_data.parsed_wall_thickness_mm,
            llm_data.parsed_class,
        )

        self._record_class_omission_if_needed(is_class_assumed, eff_wall, ambiguities)

        if eff_dn and eff_wall:
            self._verify_wall_thickness_via_tool(eff_dn, eff_wall, ambiguities)

        calc = tool_calculate_steel_tonnage(eff_od, eff_wall, raw_input.quantity)
        self._attach_conversions_to_ambiguities(ambiguities, raw_input, calc)

        return self._create_normalized_spec(raw_input, llm_data, eff_dn, eff_od, eff_wall, calc, ambiguities)

    def _execute_unified_llm_call(self, raw_input: MaterialInput) -> UnifiedNormalizerLLMResponse:
        """Call LLM once to extract parameters and diagnose ambiguities with schema validation."""
        user_prompt = (
            f"Procurement Requisition:\n"
            f"- Material: {raw_input.material}\n"
            f"- Quantity: {raw_input.quantity}\n"
            f"- Destination: {raw_input.location}\n\n"
            "Return a single JSON object with keys: parsed_dn_mm, parsed_od_mm, parsed_wall_thickness_mm, "
            "parsed_standard, parsed_class, parsed_steel_grade, is_erw, has_quantity_unit, detected_unit, "
            "quantity_ambiguity_description, quantity_stated_assumption, quantity_clarification_prompt, "
            "technical_ambiguities (list of {field, ambiguity_type, severity, description, stated_assumption, clarification_prompt})."
        )
        try:
            raw_dict = self.llm.generate_structured_json(self.SYSTEM_PROMPT, user_prompt)
            return UnifiedNormalizerLLMResponse.model_validate(raw_dict)
        except Exception as err:
            logger.warning(f"Unified LLM parsing encountered error: {err}. Using generalized fallback.")
            return fallback_deterministic_parse(raw_input)

    def _fallback_deterministic_parse(self, raw_input: MaterialInput) -> UnifiedNormalizerLLMResponse:
        """Generalized regex and table-lookup fallback covering all pipe sizes."""
        return fallback_deterministic_parse(raw_input)

    def _build_ambiguities_from_llm(
        self,
        llm_data: UnifiedNormalizerLLMResponse,
        raw_input: MaterialInput,
    ) -> List[AmbiguityItem]:
        """Convert LLM ambiguity output into typed domain AmbiguityItem models with safe coercion."""
        ambiguities: List[AmbiguityItem] = []

        if not llm_data.has_quantity_unit:
            ambiguities.append(create_quantity_ambiguity(llm_data, raw_input))

        for tech in llm_data.technical_ambiguities:
            ambiguities.append(
                AmbiguityItem(
                    field=tech.get("field", "material"),
                    ambiguity_type=safe_parse_ambiguity_type(tech.get("ambiguity_type")),
                    severity=safe_parse_severity(tech.get("severity")),
                    description=tech.get("description", ""),
                    stated_assumption=tech.get("stated_assumption", ""),
                    clarification_prompt=tech.get("clarification_prompt", ""),
                    unit_conversions={},
                )
            )
        return ambiguities

    def _verify_wall_thickness_via_tool(
        self,
        dn: int,
        wall: float,
        ambiguities: List[AmbiguityItem],
    ) -> None:
        """Verify wall thickness using deterministic IS 1239 standard table tool."""
        compliance = tool_evaluate_wall_thickness(dn, wall)
        is_standard = compliance.get("is_standard", True)
        indices = [
            i for i, a in enumerate(ambiguities)
            if a.ambiguity_type == AmbiguityType.NON_STANDARD_WALL_THICKNESS
        ]

        if is_standard and indices:
            for idx in reversed(indices):
                ambiguities.pop(idx)
        elif not is_standard and not indices:
            ambiguities.append(
                AmbiguityItem(
                    field="material",
                    ambiguity_type=AmbiguityType.NON_STANDARD_WALL_THICKNESS,
                    severity=AmbiguitySeverity.WARNING,
                    description=(
                        f"Specified wall thickness {wall} mm for DN {dn} is non-standard under IS 1239 Part 1. "
                        f"{compliance.get('deviation_note', '')}"
                    ),
                    stated_assumption=(
                        f"Assumed buyer requires custom heavy-wall ERW pipe ({wall} mm). "
                        "Evaluating manufacturers capable of custom rolling or ASTM A53 Schedule 80."
                    ),
                    clarification_prompt=(
                        f"Please confirm if {wall} mm wall is mandatory (requiring custom mill run "
                        f"or ASTM A53 Schedule 80) or if standard IS 1239 Class C is acceptable."
                    ),
                    unit_conversions={},
                )
            )

    def _determine_effective_dimensions(
        self,
        dn: Optional[int],
        od: Optional[float],
        wall: Optional[float],
        pipe_class: Optional[str],
    ) -> Tuple[Optional[int], float, float, bool]:
        """Resolve DN, OD, and wall thickness using tool lookup if omitted."""
        effective_dn = dn
        effective_od = od or 0.0
        effective_wall = wall or 0.0
        is_class_assumed = False

        if not effective_dn and effective_od > 0.0:
            effective_dn = find_is1239_dn_by_od(effective_od)

        if effective_dn:
            spec = tool_lookup_is1239_spec(effective_dn)
            if spec.get("found"):
                if effective_od == 0.0:
                    effective_od = spec["nominal_od_mm"]
                if effective_wall == 0.0:
                    effective_wall, is_class_assumed = self._resolve_wall_from_spec(spec, pipe_class)

        return effective_dn, effective_od, effective_wall, is_class_assumed

    @staticmethod
    def _resolve_wall_from_spec(spec: Dict[str, Any], pipe_class: Optional[str]) -> Tuple[float, bool]:
        """Resolve wall thickness from standard schedule or default to Class B."""
        if not pipe_class:
            return spec["class_b_medium_wall_mm"], True
        if "Class A" in pipe_class:
            return spec["class_a_light_wall_mm"], False
        if "Class C" in pipe_class:
            return spec["class_c_heavy_wall_mm"], False
        return spec["class_b_medium_wall_mm"], False

    @staticmethod
    def _record_class_omission_if_needed(
        is_class_assumed: bool,
        eff_wall: float,
        ambiguities: List[AmbiguityItem],
    ) -> None:
        """Append assumption and prompt when pipe class is omitted and defaulted to Class B."""
        if not (is_class_assumed and eff_wall > 0.0):
            return
        already_flagged = any("class" in a.description.lower() for a in ambiguities)
        if already_flagged:
            return
        ambiguities.append(
            AmbiguityItem(
                field="material",
                ambiguity_type=AmbiguityType.OTHER,
                severity=AmbiguitySeverity.INFO,
                description="Pipe class and wall thickness were unspecified in the requisition.",
                stated_assumption=(
                    f"Assumed standard IS 1239 Class B Medium wall thickness ({eff_wall} mm) "
                    "in accordance with standard commercial supply convention."
                ),
                clarification_prompt=(
                    "Please confirm whether Class A (Light), Class B (Medium), or Class C (Heavy) is required."
                ),
                unit_conversions={},
            )
        )

    @staticmethod
    def _attach_conversions_to_ambiguities(
        ambiguities: List[AmbiguityItem],
        raw_input: MaterialInput,
        calc: dict,
    ) -> None:
        """Inject physical conversions into quantity ambiguity item if present."""
        for amb in ambiguities:
            if amb.ambiguity_type == AmbiguityType.UNSPECIFIED_QUANTITY_UNIT:
                amb.unit_conversions = build_quantity_conversions(raw_input, calc)

    @staticmethod
    def _create_normalized_spec(
        raw_input: MaterialInput,
        llm_data: UnifiedNormalizerLLMResponse,
        eff_dn: Optional[int],
        eff_od: float,
        eff_wall: float,
        calc: dict,
        ambiguities: List[AmbiguityItem],
    ) -> NormalizedSpecification:
        """Construct NormalizedSpecification domain object."""
        unit = llm_data.detected_unit if llm_data.has_quantity_unit else "meters"
        return NormalizedSpecification(
            raw_input=raw_input,
            parsed_dn_mm=eff_dn or llm_data.parsed_dn_mm,
            parsed_od_mm=eff_od if eff_od > 0 else None,
            parsed_wall_thickness_mm=eff_wall if eff_wall > 0 else None,
            parsed_standard=llm_data.parsed_standard,
            parsed_class=llm_data.parsed_class,
            parsed_steel_grade=llm_data.parsed_steel_grade,
            is_erw=llm_data.is_erw,
            assumed_quantity_unit=unit or "meters",
            estimated_linear_weight_kg_m=calc["linear_weight_kg_per_meter"] or None,
            total_estimated_metric_tons=calc["total_metric_tons"] or None,
            total_estimated_pieces_6m=calc["estimated_pieces_6m"] or None,
            ambiguities=ambiguities,
        )
