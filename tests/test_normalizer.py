"""Unit tests for normalizer and ambiguity detection agent."""

from app.agents.normalizer import NormalizerAgent
from app.domain.models import AmbiguityType, MaterialInput


def test_should_detect_missing_quantity_unit_ambiguity():
    """Verify that unitless quantity triggers UNSPECIFIED_QUANTITY_UNIT ambiguity."""
    # Arrange
    agent = NormalizerAgent()
    req = MaterialInput(
        id="M-01",
        material="ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239",
        quantity=1000.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    spec = agent.normalize(req)

    # Assert
    types = [a.ambiguity_type for a in spec.ambiguities]
    assert AmbiguityType.UNSPECIFIED_QUANTITY_UNIT in types


def test_should_calculate_tonnage_and_pieces_conversions_for_quantity():
    """Verify unit conversions are computed on quantity ambiguity item."""
    # Arrange
    agent = NormalizerAgent()
    req = MaterialInput(
        id="M-01",
        material="ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239",
        quantity=1000.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    spec = agent.normalize(req)
    qty_amb = next(a for a in spec.ambiguities if a.ambiguity_type == AmbiguityType.UNSPECIFIED_QUANTITY_UNIT)

    # Assert
    conversions = qty_amb.unit_conversions
    assert "if_assumed_meters" in conversions
    assert conversions["if_assumed_meters"]["standard_6m_pieces"] == 167
    assert conversions["if_assumed_meters"]["estimated_weight_metric_tons"] > 0


def test_should_detect_nominal_bore_vs_outside_diameter_ambiguity_on_m02():
    """Verify that '40 mm' triggers NB vs OD technical ambiguity for M-02."""
    # Arrange
    agent = NormalizerAgent()
    req = MaterialInput(
        id="M-02",
        material="40 mm MS ERW, Class B pipe",
        quantity=500.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    spec = agent.normalize(req)

    # Assert
    types = [a.ambiguity_type for a in spec.ambiguities]
    assert AmbiguityType.NOMINAL_BORE_VS_OUTSIDE_DIAMETER in types


def test_should_detect_non_standard_wall_thickness_on_m01():
    """Verify that 5.5 mm wall thickness is flagged as non-standard for DN 50 on M-01."""
    # Arrange
    agent = NormalizerAgent()
    req = MaterialInput(
        id="M-01",
        material="ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239",
        quantity=1000.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    spec = agent.normalize(req)

    # Assert
    types = [a.ambiguity_type for a in spec.ambiguities]
    assert AmbiguityType.NON_STANDARD_WALL_THICKNESS in types


def test_should_parse_dimensions_accurately_for_m03():
    """Verify parsing of DN 80, OD 89.5 mm, and wall 4.8 mm for M-03."""
    # Arrange
    agent = NormalizerAgent()
    req = MaterialInput(
        id="M-03",
        material="ERW pipe, DN 80, 89.5 x 4.8 mm, IS 1239",
        quantity=1200.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    spec = agent.normalize(req)

    # Assert
    assert spec.parsed_dn_mm == 80
    assert spec.parsed_od_mm == 89.5
    assert spec.parsed_wall_thickness_mm == 4.8


def test_should_not_flag_ambiguity_when_unit_is_explicitly_specified():
    """Verify that input with explicit unit does not trigger UNSPECIFIED_QUANTITY_UNIT."""
    # Arrange
    agent = NormalizerAgent()
    req = MaterialInput(
        id="M-04",
        material="DN 50 ERW pipe, Class B, 500 meters length",
        quantity=500.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    spec = agent.normalize(req)

    # Assert
    types = [a.ambiguity_type for a in spec.ambiguities]
    assert AmbiguityType.UNSPECIFIED_QUANTITY_UNIT not in types

