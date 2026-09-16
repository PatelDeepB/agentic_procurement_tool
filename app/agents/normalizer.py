"""Specification normalizer and ambiguity detection agent with unified single-call LLM reasoning.

Combines prompt-driven language understanding in a single cost-optimized LLM call
with deterministic physical mathematics (ReAct) to extract specifications and
diagnose quantity and technical ambiguities.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

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

    SYSTEM_PROMPT = (
        "You are an expert Senior Industrial Piping Procurement Engineer. "
        "Analyze the procurement requisition in one pass. "
        "Extract physical parameters and diagnose ambiguities in a single JSON output.\n\n"
        "ENGINEERING REFERENCE (IS 1239 Part 1: 2004 Standard Schedules):\n"
        "- DN 15 (1/2 in NB): OD 21.3 mm (Class A 2.0 mm, Class B 2.65 mm, Class C 3.25 mm)\n"
        "- DN 20 (3/4 in NB): OD 26.9 mm (Class A 2.3 mm, Class B 2.65 mm, Class C 3.25 mm)\n"
        "- DN 25 (1 in NB): OD 33.7 mm (Class A 2.6 mm, Class B 3.25 mm, Class C 4.05 mm)\n"
        "- DN 32 (1.25 in NB): OD 42.4 mm (Class A 2.6 mm, Class B 3.25 mm, Class C 4.05 mm)\n"
        "- DN 40 (1.5 in NB): OD 48.3 mm (Class A 2.9 mm, Class B 3.25 mm, Class C 4.05 mm)\n"
        "- DN 50 (2 in NB): OD 60.3 mm (Class A 2.9 mm, Class B 3.65 mm, Class C 4.50 mm)\n"
        "- DN 65 (2.5 in NB): OD 76.1 mm (Class A 3.25 mm, Class B 3.65 mm, Class C 4.50 mm)\n"
        "- DN 80 (3 in NB): OD 88.9 mm (Class A 3.25 mm, Class B 4.05 mm, Class C 4.85 mm, max OD 89.5 mm)\n"
        "- DN 100 (4 in NB): OD 114.3 mm (Class A 3.65 mm, Class B 4.50 mm, Class C 5.40 mm)\n"
        "- DN 125 (5 in NB): OD 139.7 mm (Class A 4.50 mm, Class B 4.85 mm, Class C 5.40 mm)\n"
        "- DN 150 (6 in NB): OD 165.1 mm (Class A 4.50 mm, Class B 4.85 mm, Class C 5.40 mm)\n\n"
        "DOMAIN RULES TO ENFORCE:\n"
        "1. Quantity Unit Check: Detect if an explicit physical unit is given (meters, m, mtr, MT, tonnes, pieces, pcs). "
        "If ambiguous, explain industrial convention, state assumption (linear meters), and draft clarification prompt.\n"
        "2. Nominal Bore (NB) vs Outside Diameter (OD): '40 mm' or similar often designates Nominal Bore (DN 40 / 1.5 in NB, OD 48.3 mm) "
        "rather than strict 40 mm OD (which does not exist in IS 1239). Flag NOMINAL_BORE_VS_OUTSIDE_DIAMETER if ambiguity exists.\n"
        "3. Wall Thickness Check: Compare against standard classes. If wall thickness exceeds Heavy Class C (e.g. 5.5 mm for DN 50 where max Class C is 4.5 mm), "
        "flag NON_STANDARD_WALL_THICKNESS and suggest custom rolling or ASTM A53 Schedule 80.\n"
        "4. Steel Grade Check: If MS ERW pipe material does not specify tensile grade (e.g. Fe 330 vs Fe 410 per IS 1239), "
        "flag UNSPECIFIED_STEEL_GRADE (severity INFO) and state commercial default (Fe 330 for general distribution).\n"
        "5. Pipe Class & Wall Thickness Check: If neither class (Class A/B/C) nor wall thickness is specified, "
        "note the standard commercial convention (Class B Medium wall) and prompt for buyer confirmation.\n"
        "6. Output valid JSON matching the schema."
    )

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """Initialize agent with LLM client."""
        self.llm = llm_client or get_llm_client()

    def normalize(self, raw_input: MaterialInput) -> NormalizedSpecification:
        """Analyze raw material request in a single LLM call, invoke tools, and return normalized spec."""
        # Step 1: Execute single unified LLM call for extraction and ambiguity detection
        llm_data = self._execute_unified_llm_call(raw_input)

        # Step 2: Build ambiguities from LLM analysis with safe parsing
        ambiguities = self._build_ambiguities_from_llm(llm_data, raw_input)

        # Step 3: Resolve effective dimensions using deterministic tools
        dn = llm_data.parsed_dn_mm
        od = llm_data.parsed_od_mm
        wall = llm_data.parsed_wall_thickness_mm
        pipe_class = llm_data.parsed_class

        eff_dn, eff_od, eff_wall, is_class_assumed = self._determine_effective_dimensions(
            dn, od, wall, pipe_class
        )

        # Step 4: If class and wall thickness were unspecified and defaulted to Class B, record assumption
        if is_class_assumed and eff_wall > 0.0:
            already_has_class_amb = any(
                "class" in a.description.lower() for a in ambiguities
            )
            if not already_has_class_amb:
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

        # Step 5: Bidirectional wall thickness check on resolved effective dimensions
        if eff_dn and eff_wall:
            self._verify_wall_thickness_via_tool(eff_dn, eff_wall, ambiguities)

        # Step 6: Grounded ReAct tool call for mass and piece calculations
        calc_result = tool_calculate_steel_tonnage(eff_od, eff_wall, raw_input.quantity)

        # Step 7: Inject physical conversions into quantity ambiguity item if present
        for amb in ambiguities:
            if amb.ambiguity_type == AmbiguityType.UNSPECIFIED_QUANTITY_UNIT:
                self._populate_quantity_conversions(amb, raw_input, calc_result)

        unit = llm_data.detected_unit if llm_data.has_quantity_unit else "meters"

        return NormalizedSpecification(
            raw_input=raw_input,
            parsed_dn_mm=eff_dn or dn,
            parsed_od_mm=eff_od if eff_od > 0 else None,
            parsed_wall_thickness_mm=eff_wall if eff_wall > 0 else None,
            parsed_standard=llm_data.parsed_standard,
            parsed_class=pipe_class,
            parsed_steel_grade=llm_data.parsed_steel_grade,
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
            "parsed_standard, parsed_class, parsed_steel_grade, is_erw, has_quantity_unit, detected_unit, "
            "quantity_ambiguity_description, quantity_stated_assumption, quantity_clarification_prompt, "
            "technical_ambiguities (list of {field, ambiguity_type, severity, description, stated_assumption, clarification_prompt})."
        )
        try:
            raw_dict = self.llm.generate_structured_json(self.SYSTEM_PROMPT, user_prompt)
            return UnifiedNormalizerLLMResponse.model_validate(raw_dict)
        except Exception as err:
            logger.warning(f"Unified LLM parsing encountered error: {err}. Using generalized fallback.")
            return self._fallback_deterministic_parse(raw_input)

    def _build_ambiguities_from_llm(
        self,
        llm_data: UnifiedNormalizerLLMResponse,
        raw_input: MaterialInput,
    ) -> List[AmbiguityItem]:
        """Convert LLM ambiguity output into typed domain AmbiguityItem models with safe coercion."""
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

        # Technical ambiguities identified by LLM with safe type and severity parsing
        for tech in llm_data.technical_ambiguities:
            amb_type = self._safe_parse_ambiguity_type(tech.get("ambiguity_type"))
            severity = self._safe_parse_severity(tech.get("severity"))
            ambiguities.append(
                AmbiguityItem(
                    field=tech.get("field", "material"),
                    ambiguity_type=amb_type,
                    severity=severity,
                    description=tech.get("description", ""),
                    stated_assumption=tech.get("stated_assumption", ""),
                    clarification_prompt=tech.get("clarification_prompt", ""),
                    unit_conversions={},
                )
            )

        return ambiguities

    @staticmethod
    def _safe_parse_ambiguity_type(val: Any) -> AmbiguityType:
        """Safely parse ambiguity type string into AmbiguityType enum with synonym mapping."""
        if not val or not isinstance(val, str):
            return AmbiguityType.OTHER
        cleaned = re.sub(r"[^A-Za-z0-9_]", "", val.upper().strip())
        try:
            return AmbiguityType(cleaned)
        except ValueError:
            pass

        # Synonym and partial keyword mappings
        if "UNIT" in cleaned or "QUANTITY" in cleaned:
            return AmbiguityType.UNSPECIFIED_QUANTITY_UNIT
        if "BORE" in cleaned or "OD" in cleaned or "NB" in cleaned or "DIAMETER" in cleaned:
            return AmbiguityType.NOMINAL_BORE_VS_OUTSIDE_DIAMETER
        if "WALL" in cleaned or "THICKNESS" in cleaned:
            return AmbiguityType.NON_STANDARD_WALL_THICKNESS
        if "GRADE" in cleaned or "STEEL" in cleaned:
            return AmbiguityType.UNSPECIFIED_STEEL_GRADE
        return AmbiguityType.OTHER

    @staticmethod
    def _safe_parse_severity(val: Any) -> AmbiguitySeverity:
        """Safely parse severity string into AmbiguitySeverity enum with fallback."""
        if not val or not isinstance(val, str):
            return AmbiguitySeverity.WARNING
        cleaned = str(val).upper().strip()
        if "CRIT" in cleaned or "ERR" in cleaned or "HIGH" in cleaned:
            return AmbiguitySeverity.CRITICAL
        if "INFO" in cleaned or "LOW" in cleaned:
            return AmbiguitySeverity.INFO
        return AmbiguitySeverity.WARNING

    def _verify_wall_thickness_via_tool(
        self,
        dn: Optional[int],
        wall: Optional[float],
        ambiguities: List[AmbiguityItem],
    ) -> None:
        """Ground wall thickness check against IS 1239 standard using deterministic tool (bidirectional)."""
        if not dn or not wall:
            return

        compliance = tool_evaluate_wall_thickness(dn, wall)
        is_standard = compliance.get("is_standard", True)

        existing_indices = [
            i for i, a in enumerate(ambiguities)
            if a.ambiguity_type == AmbiguityType.NON_STANDARD_WALL_THICKNESS
        ]

        if is_standard and existing_indices:
            # LLM hallucinated non-standard wall thickness on a standard pipe; dismiss false positive
            for idx in reversed(existing_indices):
                ambiguities.pop(idx)
        elif not is_standard and not existing_indices:
            # LLM missed non-standard wall thickness; add deterministic ground truth
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
        """Resolve DN, OD, and wall thickness using tool lookup if omitted.

        Returns:
            Tuple of (effective_dn, effective_od, effective_wall, is_class_assumed)
        """
        effective_dn = dn
        effective_od = od or 0.0
        effective_wall = wall or 0.0
        is_class_assumed = False

        # If DN is missing but OD is given, reverse lookup DN from standard table
        if not effective_dn and effective_od > 0.0:
            effective_dn = find_is1239_dn_by_od(effective_od)

        # Lookup standard specifications if DN is resolved
        if effective_dn:
            spec_info = tool_lookup_is1239_spec(effective_dn)
            if spec_info.get("found"):
                # Decoupled OD resolution
                if effective_od == 0.0:
                    effective_od = spec_info["nominal_od_mm"]

                # Decoupled Wall Thickness resolution
                if effective_wall == 0.0:
                    if pipe_class:
                        if "Class A" in pipe_class:
                            effective_wall = spec_info["class_a_light_wall_mm"]
                        elif "Class C" in pipe_class:
                            effective_wall = spec_info["class_c_heavy_wall_mm"]
                        else:
                            effective_wall = spec_info["class_b_medium_wall_mm"]
                    else:
                        # Standard Indian supply convention: default to Class B (Medium)
                        effective_wall = spec_info["class_b_medium_wall_mm"]
                        is_class_assumed = True

        return effective_dn, effective_od, effective_wall, is_class_assumed

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

    @staticmethod
    def _detect_explicit_unit(text: str) -> Tuple[bool, Optional[str]]:
        """Detect whether text contains an explicit industrial physical unit."""
        unit_pattern = (
            r"\b(m|mtr|mtrs|meter|meters|metre|metres|"
            r"ft|feet|pcs|piece|pieces|nos|numbers|"
            r"mt|tonne|tonnes|ton|tons|bundle|bundles|length|lengths|kg)\b"
        )
        match = re.search(unit_pattern, text.lower())
        if not match:
            return False, None

        raw_unit = match.group(1)
        if raw_unit in ["m", "mtr", "mtrs", "meter", "meters", "metre", "metres"]:
            return True, "meters"
        if raw_unit in ["pcs", "piece", "pieces", "nos", "numbers"]:
            return True, "pieces"
        if raw_unit in ["mt", "tonne", "tonnes", "ton", "tons"]:
            return True, "metric_tons"
        return True, raw_unit

    def _fallback_deterministic_parse(self, raw_input: MaterialInput) -> UnifiedNormalizerLLMResponse:
        """Generalized regex and table-lookup fallback covering all pipe sizes."""
        text = raw_input.material.lower()

        # Step A: Detect explicit unit
        has_unit, detected_unit = self._detect_explicit_unit(f"{raw_input.material} {raw_input.quantity}")

        # Step B: Parse standard and class
        pipe_class = None
        if "class a" in text:
            pipe_class = "Class A"
        elif "class c" in text:
            pipe_class = "Class C"
        elif "class b" in text:
            pipe_class = "Class B"

        standard = "IS 1239" if "1239" in text else ("ASTM A53" if "a53" in text else None)

        # Step C: Parse steel grade
        steel_grade = None
        grade_match = re.search(r"\b(fe\s*330|fe\s*410|grade\s*[ab]|e250)\b", text)
        if grade_match:
            steel_grade = grade_match.group(1).upper()

        # Step D: Generalized dimension extraction
        dn: Optional[int] = None
        od: Optional[float] = None
        wall: Optional[float] = None

        # Check for explicit OD x Wall pattern (e.g. 60.3 x 5.5 mm or 89.5 x 4.8 mm)
        dim_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*[xX*]\s*(\d+(?:\.\d+)?)\s*mm", text)
        if dim_match:
            od = float(dim_match.group(1))
            wall = float(dim_match.group(2))

        # Check for explicit DN pattern (e.g. DN 50, DN 80, DN 100)
        dn_match = re.search(r"\b(?:dn|nb)\s*(\d+)\b", text)
        if dn_match:
            dn = int(dn_match.group(1))
        elif od:
            # Reverse lookup DN from OD
            dn = find_is1239_dn_by_od(od)
            if not dn:
                for candidate_dn in [15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150]:
                    s = tool_lookup_is1239_spec(candidate_dn)
                    if s.get("found") and abs(s["nominal_od_mm"] - od) < 1.5:
                        dn = candidate_dn
                        break

        # Check for standalone "X mm" (e.g. "40 mm MS ERW" or "60.3 mm MS pipe")
        tech_ambiguities: List[Dict[str, Any]] = []
        if not dn and not od:
            size_match = re.search(r"\b(\d+(?:\.\d+)?)\s*mm\b", text)
            if size_match:
                size_num = float(size_match.group(1))
                spec_cand = tool_lookup_is1239_spec(int(size_num)) if size_num.is_integer() else {"found": False}
                if spec_cand.get("found"):
                    dn = int(size_num)
                    # "X mm" used as nominal diameter when IS 1239 OD differs
                    if spec_cand["nominal_od_mm"] != size_num:
                        tech_ambiguities.append({
                            "field": "material",
                            "ambiguity_type": "NOMINAL_BORE_VS_OUTSIDE_DIAMETER",
                            "severity": "WARNING",
                            "description": (
                                f"Requirement specifies '{int(size_num)} mm'. In piping terminology, "
                                f"'{int(size_num)} mm' can refer to Nominal Bore (DN {int(size_num)}, actual OD {spec_cand['nominal_od_mm']} mm) "
                                f"or strict Outside Diameter ({int(size_num)} mm OD). Standard IS 1239 Part 1 does not "
                                f"specify an OD of {int(size_num)} mm; DN {int(size_num)} pipes have an OD of {spec_cand['nominal_od_mm']} mm."
                            ),
                            "stated_assumption": (
                                f"Assumed DN {int(size_num)} Nominal Bore (OD {spec_cand['nominal_od_mm']} mm, "
                                f"{pipe_class or 'Class B'} wall thickness) in accordance with standard Indian manufacturing conventions."
                            ),
                            "clarification_prompt": (
                                f"Please confirm whether '{int(size_num)} mm' denotes Nominal Bore (DN {int(size_num)}, actual OD {spec_cand['nominal_od_mm']} mm) "
                                f"or a non-standard {int(size_num)} mm outside diameter."
                            ),
                        })
                else:
                    matched_dn = find_is1239_dn_by_od(size_num)
                    if matched_dn:
                        od = size_num
                        dn = matched_dn

        # Step E: Verify wall thickness against standard if both DN and wall are present
        if dn and wall:
            comp = tool_evaluate_wall_thickness(dn, wall)
            if not comp.get("is_standard", True):
                tech_ambiguities.append({
                    "field": "material",
                    "ambiguity_type": "NON_STANDARD_WALL_THICKNESS",
                    "severity": "WARNING",
                    "description": (
                        f"Specified wall thickness {wall} mm for DN {dn} is non-standard under IS 1239 Part 1. "
                        f"{comp.get('deviation_note', '')}"
                    ),
                    "stated_assumption": (
                        f"Assumed buyer requires custom heavy-wall ERW pipe ({wall} mm). "
                        "Evaluating manufacturers capable of custom rolling or ASTM A53 Schedule 80."
                    ),
                    "clarification_prompt": (
                        f"Please confirm if {wall} mm wall is mandatory (requiring custom mill run "
                        f"or ASTM A53 Schedule 80) or if standard IS 1239 Class C is acceptable."
                    ),
                })

        return UnifiedNormalizerLLMResponse(
            parsed_dn_mm=dn,
            parsed_od_mm=od,
            parsed_wall_thickness_mm=wall,
            parsed_standard=standard,
            parsed_class=pipe_class,
            parsed_steel_grade=steel_grade,
            is_erw="erw" in text,
            has_quantity_unit=has_unit,
            detected_unit=detected_unit,
            quantity_ambiguity_description=None if has_unit else (
                f"Quantity '{raw_input.quantity}' lacks a physical unit of measure. "
                "In industrial steel piping, quantities are typically specified in linear meters, "
                "metric tons (MT), or commercial 6-meter pipe lengths/pieces."
            ),
            quantity_stated_assumption=None if has_unit else (
                "Assumed quantity represents linear meters (standard Indian piping contract convention). "
                "Commercial lengths are assumed to be 6.0 meters."
            ),
            quantity_clarification_prompt=None if has_unit else (
                f"Please confirm whether {raw_input.quantity} is linear meters, metric tons, or pieces."
            ),
            technical_ambiguities=tech_ambiguities,
        )
