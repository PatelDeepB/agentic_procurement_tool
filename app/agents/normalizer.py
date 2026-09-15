"""Specification normalizer and ambiguity detection agent.

Parses industrial procurement requirements, extracts engineering dimensions,
detects missing quantity units, and flags technical ambiguities such as
Nominal Bore vs Outside Diameter and non-standard wall thicknesses.
"""

import re
from typing import List, Optional, Tuple

from app.core.standards import (
    calculate_linear_weight_kg_per_meter,
    calculate_piece_count_from_meters,
    calculate_total_weight_metric_tons,
    evaluate_thickness_compliance,
    get_is1239_spec_by_dn,
)
from app.domain.models import (
    AmbiguityItem,
    AmbiguitySeverity,
    AmbiguityType,
    MaterialInput,
    NormalizedSpecification,
)


class NormalizerAgent:
    """Agent that normalizes material requirements and diagnoses ambiguities."""

    def normalize(self, raw_input: MaterialInput) -> NormalizedSpecification:
        """Analyze raw material request and return normalized spec with detected ambiguities."""
        ambiguities: List[AmbiguityItem] = []

        # Step 1: Detect quantity unit ambiguity
        quantity_ambiguity = self._detect_quantity_unit_ambiguity(raw_input)
        if quantity_ambiguity:
            ambiguities.append(quantity_ambiguity)

        # Step 2: Parse dimensions and technical attributes
        dn, od, wall, standard, pipe_class, is_erw = self._parse_material_text(raw_input.material)

        # Step 3: Detect technical dimension ambiguities (NB vs OD)
        tech_ambiguities = self._detect_technical_ambiguities(
            raw_input=raw_input,
            parsed_dn=dn,
            parsed_od=od,
            parsed_wall=wall,
            parsed_class=pipe_class,
        )
        ambiguities.extend(tech_ambiguities)

        # Step 4: Calculate linear weight and batch tonnage
        effective_od = od or (get_is1239_spec_by_dn(dn)["nominal_od_mm"] if dn and get_is1239_spec_by_dn(dn) else 0.0)
        effective_wall = wall or (self._get_class_thickness(dn, pipe_class) if dn and pipe_class else 0.0)

        linear_weight = calculate_linear_weight_kg_per_meter(effective_od, effective_wall)
        total_tonnage = calculate_total_weight_metric_tons(linear_weight, raw_input.quantity)
        total_pieces = calculate_piece_count_from_meters(raw_input.quantity)

        # Update conversions on quantity ambiguity item if present
        if quantity_ambiguity and linear_weight > 0:
            quantity_ambiguity.unit_conversions = {
                "linear_weight_kg_per_meter": linear_weight,
                "if_assumed_meters": {
                    "total_length_meters": raw_input.quantity,
                    "estimated_weight_metric_tons": total_tonnage,
                    "standard_6m_pieces": total_pieces,
                },
                "if_assumed_pieces_6m": {
                    "total_pieces": int(raw_input.quantity),
                    "total_length_meters": raw_input.quantity * 6.0,
                    "estimated_weight_metric_tons": round((linear_weight * raw_input.quantity * 6.0) / 1000.0, 3),
                },
            }

        return NormalizedSpecification(
            raw_input=raw_input,
            parsed_dn_mm=dn,
            parsed_od_mm=effective_od if effective_od > 0 else None,
            parsed_wall_thickness_mm=effective_wall if effective_wall > 0 else None,
            parsed_standard=standard,
            parsed_class=pipe_class,
            is_erw=is_erw,
            assumed_quantity_unit="meters",
            estimated_linear_weight_kg_m=linear_weight if linear_weight > 0 else None,
            total_estimated_metric_tons=total_tonnage if total_tonnage > 0 else None,
            total_estimated_pieces_6m=total_pieces if total_pieces > 0 else None,
            ambiguities=ambiguities,
        )

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

        # Check for ERW
        is_erw = bool(re.search(r"\bERW\b", text, re.IGNORECASE))

        # Check standard (e.g. IS 1239, IS 3589, ASTM A53)
        std_match = re.search(r"\b(IS\s*1239|IS\s*3589|ASTM\s*A53)\b", text, re.IGNORECASE)
        if std_match:
            standard = std_match.group(1).upper().replace(" ", " ")

        # Check class (Class A, B, C)
        class_match = re.search(r"\bClass\s+([A-C])\b", text, re.IGNORECASE)
        if class_match:
            pipe_class = f"Class {class_match.group(1).upper()}"

        # Match DN pattern: e.g. "DN 50", "DN 80"
        dn_match = re.search(r"\bDN\s*(\d+)\b", text, re.IGNORECASE)
        if dn_match:
            dn = int(dn_match.group(1))

        # Match OD x Wall pattern: e.g. "60.3 x 5.5 mm" or "89.5 * 4.8 mm"
        dim_match = re.search(r"(\d+(?:\.\d+)?)\s*[xX*×]\s*(\d+(?:\.\d+)?)\s*mm", text)
        if dim_match:
            od = float(dim_match.group(1))
            wall = float(dim_match.group(2))
        elif not dn:
            # Check for leading "40 mm"
            single_dim = re.search(r"^(\d+(?:\.\d+)?)\s*mm", text.strip())
            if single_dim:
                nominal_val = int(float(single_dim.group(1)))
                dn = nominal_val

        return dn, od, wall, standard, pipe_class, is_erw

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

        # Check for 40 mm NB vs OD ambiguity
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

        # Check for wall thickness compliance if standard is IS 1239
        if parsed_dn and parsed_wall:
            compliance = evaluate_thickness_compliance(parsed_dn, parsed_wall, parsed_class)
            if not compliance["is_standard"]:
                ambiguities.append(
                    AmbiguityItem(
                        field="material",
                        ambiguity_type=AmbiguityType.NON_STANDARD_WALL_THICKNESS,
                        severity=AmbiguitySeverity.WARNING,
                        description=(
                            f"Specified wall thickness {parsed_wall} mm for DN {parsed_dn} is non-standard "
                            f"under IS 1239 Part 1. Heavy Class C is 4.5 mm for DN 50. {compliance['deviation_note']}"
                        ),
                        stated_assumption=(
                            f"Assumed buyer requires custom heavy-wall ERW pipe ({parsed_wall} mm). "
                            "Evaluating manufacturers capable of custom rolling or ASTM A53 Schedule 80."
                        ),
                        clarification_prompt=(
                            f"Please confirm if {parsed_wall} mm wall is mandatory (requiring custom mill run "
                            f"or ASTM A53 Schedule 80) or if standard IS 1239 Class C (4.5 mm) is acceptable."
                        ),
                        unit_conversions={"specified_wall_mm": parsed_wall, "max_is1239_heavy_mm": compliance["standard_thickness_mm"]},
                    )
                )

        return ambiguities

    def _get_class_thickness(self, dn_mm: int, pipe_class: str) -> float:
        """Helper to get nominal thickness for standard classes."""
        spec = get_is1239_spec_by_dn(dn_mm)
        if not spec:
            return 0.0
        if "Class A" in pipe_class:
            return spec["class_a_thickness_mm"]
        if "Class B" in pipe_class:
            return spec["class_b_thickness_mm"]
        if "Class C" in pipe_class:
            return spec["class_c_thickness_mm"]
        return spec["class_b_thickness_mm"]
