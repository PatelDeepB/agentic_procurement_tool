"""Deterministic fallback parser for piping specifications and ambiguities.

Provides regex-driven extraction and standard IS 1239 catalog lookups
when offline or when LLM parsing encounters an error.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.standards import find_is1239_dn_by_od
from app.domain.models import MaterialInput, UnifiedNormalizerLLMResponse
from app.tools.procurement_tools import (
    tool_evaluate_wall_thickness,
    tool_lookup_is1239_spec,
)


def detect_explicit_unit(text: str) -> Tuple[bool, Optional[str]]:
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


def parse_specification_metadata(text: str) -> Tuple[Optional[str], Optional[str], Optional[str], bool]:
    """Parse pipe standard, class, steel grade, and ERW manufacturing flag."""
    pipe_class = None
    if "class a" in text:
        pipe_class = "Class A"
    elif "class c" in text:
        pipe_class = "Class C"
    elif "class b" in text:
        pipe_class = "Class B"

    standard = "IS 1239" if "1239" in text else ("ASTM A53" if "a53" in text else None)

    steel_grade = None
    grade_match = re.search(r"\b(fe\s*330|fe\s*410|grade\s*[ab]|e250)\b", text)
    if grade_match:
        steel_grade = grade_match.group(1).upper()

    is_erw = "erw" in text
    return standard, pipe_class, steel_grade, is_erw


def _extract_bore_ambiguity(size_num: float, pipe_class: Optional[str]) -> Tuple[Optional[int], Optional[float], Optional[Dict[str, Any]]]:
    """Check whether standalone size designates nominal bore or outside diameter."""
    spec_cand = tool_lookup_is1239_spec(int(size_num)) if size_num.is_integer() else {"found": False}
    if spec_cand.get("found"):
        dn = int(size_num)
        nom_od = spec_cand["nominal_od_mm"]
        if nom_od == size_num:
            return dn, None, None
        amb = {
            "field": "material",
            "ambiguity_type": "NOMINAL_BORE_VS_OUTSIDE_DIAMETER",
            "severity": "WARNING",
            "description": (
                f"Requirement specifies '{int(size_num)} mm'. In piping terminology, "
                f"'{int(size_num)} mm' can refer to Nominal Bore (DN {int(size_num)}, actual OD {nom_od} mm) "
                f"or strict Outside Diameter ({int(size_num)} mm OD). Standard IS 1239 Part 1 does not "
                f"specify an OD of {int(size_num)} mm; DN {int(size_num)} pipes have an OD of {nom_od} mm."
            ),
            "stated_assumption": (
                f"Assumed DN {int(size_num)} Nominal Bore (OD {nom_od} mm, "
                f"{pipe_class or 'Class B'} wall thickness) in accordance with standard Indian manufacturing conventions."
            ),
            "clarification_prompt": (
                f"Please confirm whether '{int(size_num)} mm' denotes Nominal Bore (DN {int(size_num)}, actual OD {nom_od} mm) "
                f"or a non-standard {int(size_num)} mm outside diameter."
            ),
        }
        return dn, None, amb

    matched_dn = find_is1239_dn_by_od(size_num)
    if matched_dn:
        return matched_dn, size_num, None
    return None, None, None


def extract_dimensions_and_bore(
    text: str,
    pipe_class: Optional[str],
) -> Tuple[Optional[int], Optional[float], Optional[float], List[Dict[str, Any]]]:
    """Extract DN, OD, wall thickness, and nominal bore ambiguities from text."""
    dn: Optional[int] = None
    od: Optional[float] = None
    wall: Optional[float] = None
    ambiguities: List[Dict[str, Any]] = []

    dim_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*[xX*]\s*(\d+(?:\.\d+)?)\s*mm", text)
    if dim_match:
        od = float(dim_match.group(1))
        wall = float(dim_match.group(2))

    dn_match = re.search(r"\b(?:dn|nb)\s*(\d+)\b", text)
    if dn_match:
        dn = int(dn_match.group(1))
    elif od:
        dn = find_is1239_dn_by_od(od)

    if not dn and not od:
        size_match = re.search(r"\b(\d+(?:\.\d+)?)\s*mm\b", text)
        if size_match:
            size_num = float(size_match.group(1))
            res_dn, res_od, amb = _extract_bore_ambiguity(size_num, pipe_class)
            dn = res_dn or dn
            od = res_od or od
            if amb:
                ambiguities.append(amb)

    return dn, od, wall, ambiguities


def evaluate_wall_deviation(dn: Optional[int], wall: Optional[float]) -> Optional[Dict[str, Any]]:
    """Check wall thickness against standard schedule and return ambiguity dictionary if deviant."""
    if not (dn and wall):
        return None

    comp = tool_evaluate_wall_thickness(dn, wall)
    if comp.get("is_standard", True):
        return None

    return {
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
    }


def _build_fallback_quantity_notes(quantity: float, has_unit: bool) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Build description, stated assumption, and buyer prompt for missing unit."""
    if has_unit:
        return None, None, None
    desc = (
        f"Quantity '{quantity}' lacks a physical unit of measure. "
        "In industrial steel piping, quantities are typically specified in linear meters, "
        "metric tons (MT), or commercial 6-meter pipe lengths/pieces."
    )
    assumption = (
        "Assumed quantity represents linear meters (standard Indian piping contract convention). "
        "Commercial lengths are assumed to be 6.0 meters."
    )
    prompt = f"Please confirm whether {quantity} is linear meters, metric tons, or pieces."
    return desc, assumption, prompt


def fallback_deterministic_parse(raw_input: MaterialInput) -> UnifiedNormalizerLLMResponse:
    """Generalized regex and table-lookup fallback covering all pipe sizes."""
    text = raw_input.material.lower()
    has_unit, detected_unit = detect_explicit_unit(f"{raw_input.material} {raw_input.quantity}")
    standard, pipe_class, steel_grade, is_erw = parse_specification_metadata(text)
    dn, od, wall, tech_ambiguities = extract_dimensions_and_bore(text, pipe_class)

    wall_amb = evaluate_wall_deviation(dn, wall)
    if wall_amb:
        tech_ambiguities.append(wall_amb)

    qty_desc, qty_assumption, qty_prompt = _build_fallback_quantity_notes(raw_input.quantity, has_unit)

    return UnifiedNormalizerLLMResponse(
        parsed_dn_mm=dn,
        parsed_od_mm=od,
        parsed_wall_thickness_mm=wall,
        parsed_standard=standard,
        parsed_class=pipe_class,
        parsed_steel_grade=steel_grade,
        is_erw=is_erw,
        has_quantity_unit=has_unit,
        detected_unit=detected_unit,
        quantity_ambiguity_description=qty_desc,
        quantity_stated_assumption=qty_assumption,
        quantity_clarification_prompt=qty_prompt,
        technical_ambiguities=tech_ambiguities,
    )
