"""Specification normalizer and ambiguity detection agent with unified single-call LLM reasoning.

Combines prompt-driven language understanding in a single cost-optimized LLM call
with deterministic physical mathematics (ReAct) to extract specifications and
diagnose quantity and technical ambiguities.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

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

    SYSTEM_PROMPT = (
        "You are an expert Senior Industrial Piping Procurement Engineer. "
        "Analyze the procurement requisition in one pass. "
        "Extract physical parameters and diagnose ambiguities in a single JSON output:\n"
        "1. Quantity Unit Check: Detect if quantity or description specifies a unit (meters, MT, pieces) "
        "or if it is unspecified/ambiguous. If ambiguous, explain industrial convention, state assumption "
        "(defaulting to linear meters), and draft a buyer clarification prompt.\n"
        "2. Technical Ambiguity Check: Expose dimensional issues (e.g. 40 mm Nominal Bore NB vs Outside Diameter OD; "
        "note IS 1239 has no 40 mm OD) or non-standard wall thicknesses.\n"
        "3. Output valid JSON matching the schema."
    )

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """Initialize agent with LLM client."""
        self.llm = llm_client or get_llm_client()

    def normalize(self, raw_input: MaterialInput) -> NormalizedSpecification:
        """Analyze raw material request in a single LLM call, invoke tools, and return normalized spec."""
        # Step 1: Execute single unified LLM call for extraction & ambiguity detection
        llm_data = self._execute_unified_llm_call(raw_input)

        # Step 2: Build ambiguities from LLM analysis
        ambiguities = self._build_ambiguities_from_llm(llm_data, raw_input)

        # Step 3: Resolve effective dimensions using deterministic tools
        dn = llm_data.parsed_dn_mm
        od = llm_data.parsed_od_mm
        wall = llm_data.parsed_wall_thickness_mm
        pipe_class = llm_data.parsed_class

        effective_od, effective_wall = self._determine_effective_dimensions(dn, od, wall, pipe_class)

        # Step 4: Grounded ReAct tool call for mass and piece calculations
        calc_result = tool_calculate_steel_tonnage(effective_od, effective_wall, raw_input.quantity)

        # Step 5: Inject physical conversions into quantity ambiguity item if present
        for amb in ambiguities:
            if amb.ambiguity_type == AmbiguityType.UNSPECIFIED_QUANTITY_UNIT:
                self._populate_quantity_conversions(amb, raw_input, calc_result)

        unit = llm_data.detected_unit if llm_data.has_quantity_unit else "meters"

        return NormalizedSpecification(
            raw_input=raw_input,
            parsed_dn_mm=dn,
            parsed_od_mm=effective_od if effective_od > 0 else None,
            parsed_wall_thickness_mm=effective_wall if effective_wall > 0 else None,
            parsed_standard=llm_data.parsed_standard,
            parsed_class=pipe_class,
            is_erw=llm_data.is_erw,
            assumed_quantity_unit=unit or "meters",
            estimated_linear_weight_kg_m=calc_result["linear_weight_kg_per_meter"] or None,
            total_estimated_metric_tons=calc_result["total_metric_tons"] or None,
            total_estimated_pieces_6m=calc_result["estimated_pieces_6m"] or None,
            ambiguities=ambiguities,
        )

    def _execute_unified_llm_call(self, raw_input: MaterialInput) -> UnifiedNormalizerLLMResponse:
        """Call LLM once to extract parameters and diagnose ambiguities with schema validation."""
        user_prompt = (
            f"Procurement Requisition:\n"
            f"- Material: {raw_input.material}\n"
            f"- Quantity: {raw_input.quantity}\n"
            f"- Destination: {raw_input.location}\n\n"
            "Return a single JSON object with keys: parsed_dn_mm, parsed_od_mm, parsed_wall_thickness_mm, "
            "parsed_standard, parsed_class, is_erw, has_quantity_unit, detected_unit, "
            "quantity_ambiguity_description, quantity_stated_assumption, quantity_clarification_prompt, "
            "technical_ambiguities (list of {field, ambiguity_type, severity, description, stated_assumption, clarification_prompt})."
        )
        try:
            raw_dict = self.llm.generate_structured_json(self.SYSTEM_PROMPT, user_prompt)
            return UnifiedNormalizerLLMResponse.model_validate(raw_dict)
        except Exception as err:
            logger.warning(f"Unified LLM parsing encountered error: {err}. Using deterministic fallback.")
            return self._fallback_deterministic_parse(raw_input)

    def _build_ambiguities_from_llm(
        self,
        llm_data: UnifiedNormalizerLLMResponse,
        raw_input: MaterialInput,
    ) -> List[AmbiguityItem]:
        """Convert LLM ambiguity output into typed domain AmbiguityItem models."""
        ambiguities: List[AmbiguityItem] = []

        # Quantity ambiguity (only added if unit is missing)
        if not llm_data.has_quantity_unit:
            desc = llm_data.quantity_ambiguity_description or (
                f"Quantity '{raw_input.quantity}' lacks a physical unit (meters, MT, pieces)."
            )
            assump = llm_data.quantity_stated_assumption or (
                f"Assumed '{raw_input.quantity}' represents linear meters."
            )
            prompt = llm_data.quantity_clarification_prompt or (
                f"Please confirm whether {raw_input.quantity} is linear meters, metric tons, or pieces."
            )
            ambiguities.append(
                AmbiguityItem(
                    field="quantity",
                    ambiguity_type=AmbiguityType.UNSPECIFIED_QUANTITY_UNIT,
                    severity=AmbiguitySeverity.WARNING,
                    description=desc,
                    stated_assumption=assump,
                    clarification_prompt=prompt,
                    unit_conversions={},
                )
            )

        # Technical ambiguities identified by LLM
        for tech in llm_data.technical_ambiguities:
            amb_type = tech.get("ambiguity_type", "NOMINAL_BORE_VS_OUTSIDE_DIAMETER")
            ambiguities.append(
                AmbiguityItem(
                    field=tech.get("field", "material"),
                    ambiguity_type=AmbiguityType(amb_type),
                    severity=AmbiguitySeverity(tech.get("severity", "WARNING")),
                    description=tech.get("description", ""),
                    stated_assumption=tech.get("stated_assumption", ""),
                    clarification_prompt=tech.get("clarification_prompt", ""),
                    unit_conversions={},
                )
            )

        # Tool verification check for non-standard wall thickness
        if llm_data.parsed_dn_mm and llm_data.parsed_wall_thickness_mm:
            self._verify_wall_thickness_via_tool(llm_data, ambiguities)

        return ambiguities

    def _verify_wall_thickness_via_tool(
        self,
        llm_data: UnifiedNormalizerLLMResponse,
        ambiguities: List[AmbiguityItem],
    ) -> None:
        """Ground wall thickness check against IS 1239 standard using deterministic tool."""
        dn = llm_data.parsed_dn_mm
        wall = llm_data.parsed_wall_thickness_mm
        if not dn or not wall:
            return

        already_flagged = any(a.ambiguity_type == AmbiguityType.NON_STANDARD_WALL_THICKNESS for a in ambiguities)
        if already_flagged:
            return

        compliance = tool_evaluate_wall_thickness(dn, wall)
        if not compliance.get("is_standard", True):
            ambiguities.append(
                AmbiguityItem(
                    field="material",
                    ambiguity_type=AmbiguityType.NON_STANDARD_WALL_THICKNESS,
                    severity=AmbiguitySeverity.WARNING,
                    description=(
                        f"Specified wall thickness {wall} mm for DN {dn} is non-standard under IS 1239 Part 1. "
                        f"Heavy Class C is 4.5 mm for DN 50. {compliance.get('deviation_note', '')}"
                    ),
                    stated_assumption=(
                        f"Assumed buyer requires custom heavy-wall ERW pipe ({wall} mm). "
                        "Evaluating manufacturers capable of custom rolling or ASTM A53 Schedule 80."
                    ),
                    clarification_prompt=(
                        f"Please confirm if {wall} mm wall is mandatory (requiring custom mill run "
                        f"or ASTM A53 Schedule 80) or if standard IS 1239 Class C (4.5 mm) is acceptable."
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
    ) -> Tuple[float, float]:
        """Resolve OD and wall thickness using tool lookup if omitted."""
        effective_od = od or 0.0
        effective_wall = wall or 0.0

        if dn and effective_od == 0.0:
            spec_info = tool_lookup_is1239_spec(dn)
            if spec_info.get("found"):
                effective_od = spec_info["nominal_od_mm"]
                if effective_wall == 0.0 and pipe_class:
                    if "Class A" in pipe_class:
                        effective_wall = spec_info["class_a_light_wall_mm"]
                    elif "Class C" in pipe_class:
                        effective_wall = spec_info["class_c_heavy_wall_mm"]
                    else:
                        effective_wall = spec_info["class_b_medium_wall_mm"]

        return effective_od, effective_wall

    def _populate_quantity_conversions(
        self,
        item: AmbiguityItem,
        raw_input: MaterialInput,
        calc_result: dict,
    ) -> None:
        """Populate physical conversions on ambiguity report."""
        lin_wt = calc_result["linear_weight_kg_per_meter"]
        item.unit_conversions = {
            "linear_weight_kg_per_meter": lin_wt,
            "if_assumed_meters": {
                "total_length_meters": raw_input.quantity,
                "estimated_weight_metric_tons": calc_result["total_metric_tons"],
                "standard_6m_pieces": calc_result["estimated_pieces_6m"],
            },
            "if_assumed_pieces_6m": {
                "total_pieces": int(raw_input.quantity),
                "total_length_meters": raw_input.quantity * 6.0,
                "estimated_weight_metric_tons": round((lin_wt * raw_input.quantity * 6.0) / 1000.0, 3),
            },
        }

    def _fallback_deterministic_parse(self, raw_input: MaterialInput) -> UnifiedNormalizerLLMResponse:
        """Deterministic safety fallback in case LLM network call fails."""
        text = raw_input.material.lower()
        is_40mm = "40 mm" in text
        is_50mm = "50" in text or "60.3" in text
        is_80mm = "80" in text or "89.5" in text

        dn = 40 if is_40mm else (50 if is_50mm else (80 if is_80mm else None))
        od = 60.3 if is_50mm else (89.5 if is_80mm else None)
        wall = 5.5 if (is_50mm and "5.5" in text) else (4.8 if is_80mm else None)

        tech_ambiguities = []
        if is_40mm:
            tech_ambiguities.append({
                "field": "material",
                "ambiguity_type": "NOMINAL_BORE_VS_OUTSIDE_DIAMETER",
                "severity": "WARNING",
                "description": "40 mm can denote DN 40 Nominal Bore (OD 48.3 mm) or non-standard 40 mm OD.",
                "stated_assumption": "Assumed DN 40 Nominal Bore (OD 48.3 mm, Class B wall 3.25 mm).",
                "clarification_prompt": "Please confirm whether 40 mm denotes Nominal Bore or strict outside diameter.",
            })

        return UnifiedNormalizerLLMResponse(
            parsed_dn_mm=dn,
            parsed_od_mm=od,
            parsed_wall_thickness_mm=wall,
            parsed_standard="IS 1239" if "1239" in text else None,
            parsed_class="Class B" if "class b" in text else ("Class C" if "class c" in text else None),
            is_erw="erw" in text,
            has_quantity_unit=False,
            detected_unit=None,
            quantity_ambiguity_description=f"Quantity '{raw_input.quantity}' lacks a physical unit.",
            quantity_stated_assumption=f"Assumed '{raw_input.quantity}' represents linear meters.",
            quantity_clarification_prompt=f"Please confirm whether {raw_input.quantity} is linear meters or pieces.",
            technical_ambiguities=tech_ambiguities,
        )
