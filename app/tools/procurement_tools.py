"""Domain tools callable by LLM agents for engineering standards and calculations.

Implements the tool-augmented reasoning (ReAct) layer, grounding LLM agents
with deterministic physical mathematics and Indian Standard specifications.
"""

from typing import Any, Dict, List, Optional

from app.core.standards import (
    calculate_linear_weight_kg_per_meter,
    calculate_piece_count_from_meters,
    calculate_total_weight_metric_tons,
    evaluate_thickness_compliance,
    find_is1239_dn_by_od,
    get_is1239_spec_by_dn,
)


def tool_lookup_is1239_spec(dn_mm: int) -> Dict[str, Any]:
    """Look up official IS 1239 Part 1 specifications for a given Nominal Diameter (DN)."""
    spec = get_is1239_spec_by_dn(dn_mm)
    if not spec:
        return {
            "found": False,
            "error": f"DN {dn_mm} is not listed in IS 1239 Part 1 nominal size table (DN 15 to DN 100).",
        }
    return {
        "found": True,
        "dn_mm": dn_mm,
        "nominal_bore_inch": spec["nominal_bore_inch"],
        "nominal_od_mm": spec["nominal_od_mm"],
        "od_tolerance_range_mm": [spec["min_od_mm"], spec["max_od_mm"]],
        "class_a_light_wall_mm": spec["class_a_thickness_mm"],
        "class_b_medium_wall_mm": spec["class_b_thickness_mm"],
        "class_c_heavy_wall_mm": spec["class_c_thickness_mm"],
    }


def tool_evaluate_wall_thickness(dn_mm: int, thickness_mm: float) -> Dict[str, Any]:
    """Evaluate whether a wall thickness is standard under IS 1239 Part 1."""
    return evaluate_thickness_compliance(dn_mm, thickness_mm)


def tool_calculate_steel_tonnage(
    outside_diameter_mm: float,
    wall_thickness_mm: float,
    length_in_meters: float,
) -> Dict[str, Any]:
    """Calculate linear weight (kg/m), total metric tons, and standard 6m piece count."""
    linear_weight = calculate_linear_weight_kg_per_meter(outside_diameter_mm, wall_thickness_mm)
    total_tons = calculate_total_weight_metric_tons(linear_weight, length_in_meters)
    pieces = calculate_piece_count_from_meters(length_in_meters)
    return {
        "linear_weight_kg_per_meter": linear_weight,
        "total_metric_tons": total_tons,
        "estimated_pieces_6m": pieces,
        "formula_used": "mass_kg_m = (OD - t) * t * 0.02466",
    }


def tool_match_dn_from_outside_diameter(outside_diameter_mm: float) -> Dict[str, Any]:
    """Determine the closest standard IS 1239 DN from a measured outside diameter."""
    matched_dn = find_is1239_dn_by_od(outside_diameter_mm)
    if matched_dn:
        return {"matched": True, "dn_mm": matched_dn}
    return {"matched": False, "note": f"Outside diameter {outside_diameter_mm} mm does not match standard IS 1239 tolerances."}
