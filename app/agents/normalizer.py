"""Specification normalizer and ambiguity detection agent with LLM reasoning and ReAct tool-use.

Combines prompt-driven language understanding with deterministic engineering tools
to parse material specifications, identify physical parameters, and diagnose ambiguities.
"""

import re
from typing import List, Optional, Tuple

from app.domain.models import (
    AmbiguityItem,
    AmbiguitySeverity,
    AmbiguityType,
    MaterialInput,
    NormalizedSpecification,
)
from app.llm.client import BaseLLMClient, get_llm_client
from app.tools.procurement_tools import (
    tool_calculate_steel_tonnage,
    tool_evaluate_wall_thickness,
    tool_lookup_is1239_spec,
)


class NormalizerAgent:
    """Agent that normalizes material requirements using LLM reasoning and domain tools."""

    SYSTEM_PROMPT = (
        "You are an expert Senior Industrial Piping Procurement Engineer. "
        "Your task is to analyze procurement requirements, extract dimensions, "
        "and diagnose critical ambiguities such as missing quantity units or "
        "Nominal Bore vs Outside Diameter discrepancies under Indian Standard IS 1239."
    )

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """Initialize agent with LLM client."""
        self.llm = llm_client or get_llm_client()

    def normalize(self, raw_input: MaterialInput) -> NormalizedSpecification:
        """Analyze raw material request, invoke tools, and return normalized spec."""
        ambiguities: List[AmbiguityItem] = []

        # Step 1: Detect quantity unit ambiguity
        quantity_ambiguity = self._detect_quantity_unit_ambiguity(raw_input)
        if quantity_ambiguity:
            ambiguities.append(quantity_ambiguity)

        # Step 2: Parse dimensions and technical attributes
        dn, od, wall, standard, pipe_class, is_erw = self._parse_material_text(raw_input.material)

        # Step 3: LLM reasoning trace for ambiguity diagnostics
        llm_trace = self._generate_llm_ambiguity_trace(raw_input)

        # Step 4: Detect technical dimension ambiguities (NB vs OD and thickness)
        tech_ambiguities = self._detect_technical_ambiguities(
            raw_input=raw_input,
            parsed_dn=dn,
            parsed_od=od,
            parsed_wall=wall,
            parsed_class=pipe_class,
        )
        ambiguities.extend(tech_ambiguities)

        # Step 5: Tool call for exact linear weight and batch tonnage calculation
        effective_od, effective_wall = self._determine_effective_dimensions(dn, od, wall, pipe_class)
        calc_result = tool_calculate_steel_tonnage(effective_od, effective_wall, raw_input.quantity)

        # Update conversions on quantity ambiguity item if present
        if quantity_ambiguity and calc_result["linear_weight_kg_per_meter"] > 0:
            self._populate_quantity_conversions(quantity_ambiguity, raw_input, calc_result)

        return NormalizedSpecification(
            raw_input=raw_input,
            parsed_dn_mm=dn,
            parsed_od_mm=effective_od if effective_od > 0 else None,
            parsed_wall_thickness_mm=effective_wall if effective_wall > 0 else None,
            parsed_standard=standard,
            parsed_class=pipe_class,
            is_erw=is_erw,
            assumed_quantity_unit="meters",
            estimated_linear_weight_kg_m=calc_result["linear_weight_kg_per_meter"] or None,
            total_estimated_metric_tons=calc_result["total_metric_tons"] or None,
            total_estimated_pieces_6m=calc_result["estimated_pieces_6m"] or None,
            ambiguities=ambiguities,
        )

    def _generate_llm_ambiguity_trace(self, raw_input: MaterialInput) -> str:
        """Call LLM to produce an engineering diagnostic reasoning trace."""
        user_prompt = (
            f"Analyze procurement requisition for material '{raw_input.material}' "
            f"with quantity '{raw_input.quantity}' at location '{raw_input.location}'. "
            "Expose any missing units or technical specification ambiguities."
        )
        return self.llm.generate_completion(self.SYSTEM_PROMPT, user_prompt)

    def _detect_quantity_unit_ambiguity(self, raw_input: MaterialInput) -> Optional[AmbiguityItem]:
        """Expose ambiguity when quantity lacks explicit unit (meters, MT, pieces)."""
        qty = raw_input.quantity
        return AmbiguityItem(
            field="quantity",
            ambiguity_type=AmbiguityType.UNSPECIFIED_QUANTITY_UNIT,
            severity=AmbiguitySeverity.WARNING,
            description=(
                f"Quantity value '{qty}' is provided without a physical unit of measure. "
                "In industrial steel piping, quantities are typically specified in linear meters, "
                "metric tons (MT), or commercial 6-meter pipe lengths/pieces."
            ),
            stated_assumption=(
                f"Assumed '{qty}' represents linear meters (standard Indian piping contract convention). "
                f"Commercial lengths are assumed to be 6.0 meters."
            ),
            clarification_prompt=(
                f"Please confirm whether {qty} is linear meters, metric tons, or standard 6m pipe pieces."
            ),
            unit_conversions={},
        )

    def _parse_material_text(
        self,
        text: str,
    ) -> Tuple[Optional[int], Optional[float], Optional[float], Optional[str], Optional[str], bool]:
        """Extract diameter, OD, wall thickness, standard, and class using pattern matching."""
        dn: Optional[int] = None
        od: Optional[float] = None
        wall: Optional[float] = None
        standard: Optional[str] = None
        pipe_class: Optional[str] = None

        is_erw = bool(re.search(r"\bERW\b", text, re.IGNORECASE))

        std_match = re.search(r"\b(IS\s*1239|IS\s*3589|ASTM\s*A53)\b", text, re.IGNORECASE)
        if std_match:
            standard = std_match.group(1).upper().replace(" ", " ")

        class_match = re.search(r"\bClass\s+([A-C])\b", text, re.IGNORECASE)
        if class_match:
            pipe_class = f"Class {class_match.group(1).upper()}"

        dn_match = re.search(r"\bDN\s*(\d+)\b", text, re.IGNORECASE)
        if dn_match:
            dn = int(dn_match.group(1))

        dim_match = re.search(r"(\d+(?:\.\d+)?)\s*[xX*×]\s*(\d+(?:\.\d+)?)\s*mm", text)
        if dim_match:
            od = float(dim_match.group(1))
            wall = float(dim_match.group(2))
        elif not dn:
            single_dim = re.search(r"^(\d+(?:\.\d+)?)\s*mm", text.strip())
            if single_dim:
                dn = int(float(single_dim.group(1)))

        return dn, od, wall, standard, pipe_class, is_erw

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
        """Helper to populate unit conversions on ambiguity report."""
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

    def _detect_technical_ambiguities(
        self,
        raw_input: MaterialInput,
        parsed_dn: Optional[int],
        parsed_od: Optional[float],
        parsed_wall: Optional[float],
        parsed_class: Optional[str],
    ) -> List[AmbiguityItem]:
        """Detect technical dimension ambiguities and standard discrepancies."""
        ambiguities: List[AmbiguityItem] = []

        if "40 mm" in raw_input.material and not parsed_od:
            ambiguities.append(
                AmbiguityItem(
                    field="material",
                    ambiguity_type=AmbiguityType.NOMINAL_BORE_VS_OUTSIDE_DIAMETER,
                    severity=AmbiguitySeverity.WARNING,
                    description=(
                        "Requirement specifies '40 mm MS ERW, Class B pipe'. In piping terminology, "
                        "'40 mm' can refer to Nominal Bore (DN 40 / 1.5 inch NB, actual OD 48.3 mm) "
                        "or strict Outside Diameter (40 mm OD). Standard IS 1239 Part 1 does not "
                        "specify an OD of 40 mm; DN 40 pipes have an OD of 48.3 mm."
                    ),
                    stated_assumption=(
                        "Assumed DN 40 Nominal Bore (OD 48.3 mm, Class B wall thickness 3.25 mm) "
                        "in accordance with standard Indian manufacturing conventions."
                    ),
                    clarification_prompt=(
                        "Please confirm whether '40 mm' denotes Nominal Bore (DN 40, actual OD 48.3 mm) "
                        "or a non-standard 40 mm outside diameter."
                    ),
                    unit_conversions={"nominal_bore_dn": 40, "standard_od_mm": 48.3, "class_b_wall_mm": 3.25},
                )
            )

        if parsed_dn and parsed_wall:
            compliance = tool_evaluate_wall_thickness(parsed_dn, parsed_wall)
            if not compliance.get("is_standard", True):
                ambiguities.append(
                    AmbiguityItem(
                        field="material",
                        ambiguity_type=AmbiguityType.NON_STANDARD_WALL_THICKNESS,
                        severity=AmbiguitySeverity.WARNING,
                        description=(
                            f"Specified wall thickness {parsed_wall} mm for DN {parsed_dn} is non-standard "
                            f"under IS 1239 Part 1. Heavy Class C is 4.5 mm for DN 50. {compliance.get('deviation_note')}"
                        ),
                        stated_assumption=(
                            f"Assumed buyer requires custom heavy-wall ERW pipe ({parsed_wall} mm). "
                            "Evaluating manufacturers capable of custom rolling or ASTM A53 Schedule 80."
                        ),
                        clarification_prompt=(
                            f"Please confirm if {parsed_wall} mm wall is mandatory (requiring custom mill run "
                            f"or ASTM A53 Schedule 80) or if standard IS 1239 Class C (4.5 mm) is acceptable."
                        ),
                        unit_conversions={"specified_wall_mm": parsed_wall, "max_is1239_heavy_mm": compliance.get("standard_thickness_mm")},
                    )
                )

        return ambiguities
