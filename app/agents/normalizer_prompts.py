"""Engineering prompts and safe enum parsing helpers for specification normalization."""

import re
from typing import Any

from app.domain.models import AmbiguityItem, AmbiguitySeverity, AmbiguityType

NORMALIZER_SYSTEM_PROMPT = (
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


def safe_parse_ambiguity_type(val: Any) -> AmbiguityType:
    """Safely parse ambiguity type string into AmbiguityType enum with synonym mapping."""
    if not val or not isinstance(val, str):
        return AmbiguityType.OTHER
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", val.upper().strip())
    try:
        return AmbiguityType(cleaned)
    except ValueError:
        pass

    if "UNIT" in cleaned or "QUANTITY" in cleaned:
        return AmbiguityType.UNSPECIFIED_QUANTITY_UNIT
    if "BORE" in cleaned or "OD" in cleaned or "NB" in cleaned or "DIAMETER" in cleaned:
        return AmbiguityType.NOMINAL_BORE_VS_OUTSIDE_DIAMETER
    if "WALL" in cleaned or "THICKNESS" in cleaned:
        return AmbiguityType.NON_STANDARD_WALL_THICKNESS
    if "GRADE" in cleaned or "STEEL" in cleaned:
        return AmbiguityType.UNSPECIFIED_STEEL_GRADE
    return AmbiguityType.OTHER


def safe_parse_severity(val: Any) -> AmbiguitySeverity:
    """Safely parse severity string into AmbiguitySeverity enum with fallback."""
    if not val or not isinstance(val, str):
        return AmbiguitySeverity.WARNING
    cleaned = str(val).upper().strip()
    if "CRIT" in cleaned or "ERR" in cleaned or "HIGH" in cleaned:
        return AmbiguitySeverity.CRITICAL
    if "INFO" in cleaned or "LOW" in cleaned:
        return AmbiguitySeverity.INFO
    return AmbiguitySeverity.WARNING


def create_quantity_ambiguity(llm_data: Any, raw_input: Any) -> AmbiguityItem:
    """Create typed AmbiguityItem for unspecified quantity units."""
    desc = getattr(llm_data, "quantity_ambiguity_description", None) or (
        f"Quantity '{raw_input.quantity}' lacks a physical unit of measure. "
        "In industrial steel piping, quantities are typically specified in linear meters, "
        "metric tons (MT), or commercial 6-meter pipe lengths/pieces."
    )
    assump = getattr(llm_data, "quantity_stated_assumption", None) or (
        "Assumed quantity represents linear meters (standard Indian piping contract convention). "
        "Commercial lengths are assumed to be 6.0 meters."
    )
    prompt = getattr(llm_data, "quantity_clarification_prompt", None) or (
        f"Please confirm whether {raw_input.quantity} is linear meters, metric tons, or pieces."
    )
    return AmbiguityItem(
        field="quantity",
        ambiguity_type=AmbiguityType.UNSPECIFIED_QUANTITY_UNIT,
        severity=AmbiguitySeverity.WARNING,
        description=desc,
        stated_assumption=assump,
        clarification_prompt=prompt,
        unit_conversions={},
    )


def build_quantity_conversions(raw_input: Any, calc: dict) -> dict:
    """Compute physical conversion dictionary for quantity ambiguities."""
    lin_wt = calc["linear_weight_kg_per_meter"]
    return {
        "linear_weight_kg_per_meter": lin_wt,
        "if_assumed_meters": {
            "total_length_meters": raw_input.quantity,
            "estimated_weight_metric_tons": calc["total_metric_tons"],
            "standard_6m_pieces": calc["estimated_pieces_6m"],
        },
        "if_assumed_pieces_6m": {
            "total_pieces": int(raw_input.quantity),
            "total_length_meters": raw_input.quantity * 6.0,
            "estimated_weight_metric_tons": round((lin_wt * raw_input.quantity * 6.0) / 1000.0, 3),
        },
    }

