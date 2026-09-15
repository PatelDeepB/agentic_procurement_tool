"""Industrial standard specifications and calculation utilities for steel pipes.

This module encapsulates dimensional tables for IS 1239 (Part 1): 2004,
standard tolerance ranges, international equivalent standards, and
mass/weight calculations according to standard engineering formulas.
"""

from typing import Any, Dict, List, Optional

# Standard density factor for carbon steel pipes: (OD - t) * t * 0.02466 kg/m
STEEL_PIPE_MASS_FACTOR = 0.02466
STANDARD_PIPE_LENGTH_METERS = 6.0

# IS 1239 (Part 1): 2004 dimensional data table
# Key: Nominal Diameter (DN in mm)
IS1239_PART1_TABLE: Dict[int, Dict[str, Any]] = {
    15: {
        "nominal_bore_inch": "1/2",
        "nominal_od_mm": 21.3,
        "min_od_mm": 21.0,
        "max_od_mm": 21.8,
        "class_a_thickness_mm": 2.0,
        "class_b_thickness_mm": 2.6,
        "class_c_thickness_mm": 3.2,
    },
    20: {
        "nominal_bore_inch": "3/4",
        "nominal_od_mm": 26.9,
        "min_od_mm": 26.5,
        "max_od_mm": 27.3,
        "class_a_thickness_mm": 2.3,
        "class_b_thickness_mm": 2.6,
        "class_c_thickness_mm": 3.2,
    },
    25: {
        "nominal_bore_inch": "1",
        "nominal_od_mm": 33.7,
        "min_od_mm": 33.3,
        "max_od_mm": 34.2,
        "class_a_thickness_mm": 2.6,
        "class_b_thickness_mm": 3.2,
        "class_c_thickness_mm": 4.0,
    },
    32: {
        "nominal_bore_inch": "1-1/4",
        "nominal_od_mm": 42.4,
        "min_od_mm": 42.0,
        "max_od_mm": 42.9,
        "class_a_thickness_mm": 2.6,
        "class_b_thickness_mm": 3.2,
        "class_c_thickness_mm": 4.0,
    },
    40: {
        "nominal_bore_inch": "1-1/2",
        "nominal_od_mm": 48.3,
        "min_od_mm": 47.9,
        "max_od_mm": 48.8,
        "class_a_thickness_mm": 2.9,
        "class_b_thickness_mm": 3.25,
        "class_c_thickness_mm": 4.05,
    },
    50: {
        "nominal_bore_inch": "2",
        "nominal_od_mm": 60.3,
        "min_od_mm": 59.7,
        "max_od_mm": 60.8,
        "class_a_thickness_mm": 3.25,
        "class_b_thickness_mm": 3.65,
        "class_c_thickness_mm": 4.5,
    },
    65: {
        "nominal_bore_inch": "2-1/2",
        "nominal_od_mm": 76.1,
        "min_od_mm": 75.3,
        "max_od_mm": 76.6,
        "class_a_thickness_mm": 3.25,
        "class_b_thickness_mm": 3.65,
        "class_c_thickness_mm": 4.5,
    },
    80: {
        "nominal_bore_inch": "3",
        "nominal_od_mm": 88.9,
        "min_od_mm": 87.9,
        "max_od_mm": 89.5,
        "class_a_thickness_mm": 3.25,
        "class_b_thickness_mm": 4.05,
        "class_c_thickness_mm": 4.85,
    },
    100: {
        "nominal_bore_inch": "4",
        "nominal_od_mm": 114.3,
        "min_od_mm": 113.1,
        "max_od_mm": 115.0,
        "class_a_thickness_mm": 3.65,
        "class_b_thickness_mm": 4.5,
        "class_c_thickness_mm": 5.4,
    },
}

INTERNATIONAL_EQUIVALENTS: List[Dict[str, str]] = [
    {
        "standard": "ASTM A53",
        "jurisdiction": "USA / International",
        "scope": "Standard specification for pipe, steel, black and hot-dipped, zinc-coated, welded and seamless",
        "matching_classes": "Schedule 40 (similar to IS 1239 Medium/Class B), Schedule 80 (Heavy/Extra Heavy)",
    },
    {
        "standard": "BS 1387",
        "jurisdiction": "British / Commonwealth",
        "scope": "Specification for screwed and socketed steel tubes and tubulars",
        "matching_classes": "Light (Class A), Medium (Class B), Heavy (Class C)",
    },
    {
        "standard": "EN 10255",
        "jurisdiction": "European Union",
        "scope": "Non-alloy steel tubes suitable for welding and threading",
        "matching_classes": "Series L (Light), Series M (Medium), Series H (Heavy)",
    },
    {
        "standard": "IS 3589",
        "jurisdiction": "India",
        "scope": "Steel pipes for water and sewage (168.3 mm to 2540 mm OD, or heavy wall requirements)",
        "matching_classes": "Fe 330, Fe 410, Fe 450",
    },
]


def calculate_linear_weight_kg_per_meter(
    outside_diameter_mm: float,
    wall_thickness_mm: float,
) -> float:
    """Calculate theoretical linear mass of steel pipe in kg/meter.

    Uses standard formula: mass = (OD - t) * t * 0.02466
    """
    if outside_diameter_mm <= 0 or wall_thickness_mm <= 0:
        return 0.0
    if wall_thickness_mm >= outside_diameter_mm:
        return 0.0
    linear_weight = (
        (outside_diameter_mm - wall_thickness_mm)
        * wall_thickness_mm
        * STEEL_PIPE_MASS_FACTOR
    )
    return round(linear_weight, 3)


def calculate_total_weight_metric_tons(
    linear_weight_kg_m: float,
    length_in_meters: float,
) -> float:
    """Calculate total batch weight in metric tons."""
    if linear_weight_kg_m <= 0 or length_in_meters <= 0:
        return 0.0
    total_kg = linear_weight_kg_m * length_in_meters
    return round(total_kg / 1000.0, 3)


def calculate_piece_count_from_meters(
    length_in_meters: float,
    standard_length: float = STANDARD_PIPE_LENGTH_METERS,
) -> int:
    """Calculate the estimated number of standard 6m commercial pipes."""
    if length_in_meters <= 0 or standard_length <= 0:
        return 0
    return int(round(length_in_meters / standard_length))


def get_is1239_spec_by_dn(dn_mm: int) -> Optional[Dict[str, Any]]:
    """Retrieve standard IS 1239 Part 1 specifications for a given DN."""
    return IS1239_PART1_TABLE.get(dn_mm)


def find_is1239_dn_by_od(outside_diameter_mm: float) -> Optional[int]:
    """Find matching DN for an outside diameter within tolerance."""
    for dn, spec in IS1239_PART1_TABLE.items():
        if spec["min_od_mm"] <= outside_diameter_mm <= spec["max_od_mm"]:
            return dn
    return None


def evaluate_thickness_compliance(
    dn_mm: int,
    thickness_mm: float,
    specified_class: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate whether a wall thickness complies with standard IS 1239 classes."""
    spec = get_is1239_spec_by_dn(dn_mm)
    if not spec:
        return {
            "is_standard": False,
            "matched_class": None,
            "standard_thickness_mm": None,
            "deviation_note": f"DN {dn_mm} is not in standard IS 1239 Part 1 lookup table.",
        }

    class_a = spec["class_a_thickness_mm"]
    class_b = spec["class_b_thickness_mm"]
    class_c = spec["class_c_thickness_mm"]

    # Check matches with tolerance of 0.1 mm
    if abs(thickness_mm - class_a) <= 0.1:
        return {
            "is_standard": True,
            "matched_class": "Class A (Light)",
            "standard_thickness_mm": class_a,
            "deviation_note": "Standard IS 1239 Light class thickness.",
        }
    if abs(thickness_mm - class_b) <= 0.1:
        return {
            "is_standard": True,
            "matched_class": "Class B (Medium)",
            "standard_thickness_mm": class_b,
            "deviation_note": "Standard IS 1239 Medium class thickness.",
        }
    if abs(thickness_mm - class_c) <= 0.1:
        return {
            "is_standard": True,
            "matched_class": "Class C (Heavy)",
            "standard_thickness_mm": class_c,
            "deviation_note": "Standard IS 1239 Heavy class thickness.",
        }

    return {
        "is_standard": False,
        "matched_class": None,
        "standard_thickness_mm": class_c,
        "deviation_note": (
            f"Thickness {thickness_mm} mm deviates from standard IS 1239 Part 1 schedules "
            f"(Class A: {class_a} mm, Class B: {class_b} mm, Class C Heavy: {class_c} mm). "
            f"May require custom rolling, ASTM A53 Sch 80, or IS 3589 standard."
        ),
    }
