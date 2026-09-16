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
from app.domain.models import MaterialInput, NormalizedSpecification, VendorTier


def tool_lookup_is1239_spec(dn_mm: int) -> Dict[str, Any]:
    """Look up official IS 1239 Part 1 specifications for a given Nominal Diameter (DN)."""
    spec = get_is1239_spec_by_dn(dn_mm)
    if not spec:
        return {
            "found": False,
            "error": f"DN {dn_mm} is not listed in IS 1239 Part 1 nominal size table (DN 15 to DN 150).",
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


def _format_matched_vendor_candidate(vendor: Dict[str, Any]) -> Dict[str, Any]:
    """Format matching vendor dictionary for tool response."""
    return {
        "id": vendor.get("id"),
        "vendor_name": vendor.get("vendor_name"),
        "tier": vendor.get("tier"),
        "vendor_type": vendor.get("vendor_type"),
        "location": vendor.get("location"),
        "supported_dn_range": vendor.get("supported_dn_range"),
        "supported_standards": vendor.get("supported_standards"),
    }


def tool_search_vendor_registry(
    tier: Optional[str] = None,
    target_dn_mm: Optional[int] = None,
    standard: Optional[str] = None,
) -> Dict[str, Any]:
    """Search verified industrial vendor registry with optional tier, DN, and standard filters."""
    from app.agents.searcher import SearchAgent

    searcher = SearchAgent()
    tier_enum = None
    if tier:
        try:
            tier_enum = VendorTier(tier.upper())
        except ValueError:
            pass

    dummy_input = MaterialInput(
        id="REACT-TOOL-01",
        material=f"DN {target_dn_mm or 50} steel pipe {standard or 'IS 1239'}",
        quantity=100.0,
    )
    spec = NormalizedSpecification(
        raw_input=dummy_input,
        parsed_dn_mm=target_dn_mm,
        parsed_standard=standard,
    )
    qualified, exclusions = searcher.retrieve_candidates_with_audit(spec, tier=tier_enum)
    return {
        "total_matched": len(qualified),
        "total_excluded": len(exclusions),
        "candidates": [_format_matched_vendor_candidate(vendor) for vendor in qualified],
        "exclusions": exclusions,
    }
