"""Unit tests for advanced and decoupled normalizer scenarios."""

from app.agents.normalizer import NormalizerAgent
from app.domain.models import MaterialInput


def test_should_resolve_wall_thickness_when_od_and_class_are_specified():
    """Verify that specifying OD does not bypass class wall thickness lookup."""
    # Arrange
    agent = NormalizerAgent()
    req = MaterialInput(
        id="T-DECOUPLED-01",
        material="DN 50, 60.3 mm MS ERW, Class B pipe",
        quantity=500.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    spec = agent.normalize(req)

    # Assert
    assert spec.parsed_dn_mm == 50
    assert spec.parsed_od_mm == 60.3
    assert spec.parsed_wall_thickness_mm == 3.65
    assert spec.estimated_linear_weight_kg_m is not None and spec.estimated_linear_weight_kg_m > 0
    assert spec.total_estimated_metric_tons is not None and spec.total_estimated_metric_tons > 0


def test_should_default_to_class_b_and_record_assumption_when_class_is_omitted():
    """Verify that omitting class defaults to Class B with stated ambiguity assumption."""
    # Arrange
    agent = NormalizerAgent()
    req = MaterialInput(
        id="T-DECOUPLED-02",
        material="DN 50 MS ERW pipe",
        quantity=1000.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    spec = agent.normalize(req)

    # Assert
    assert spec.parsed_dn_mm == 50
    assert spec.parsed_wall_thickness_mm == 3.65
    assert spec.estimated_linear_weight_kg_m is not None and spec.estimated_linear_weight_kg_m > 0
    class_ambiguities = [
        ambiguity
        for ambiguity in spec.ambiguities
        if "class" in ambiguity.description.lower() or "class" in ambiguity.stated_assumption.lower()
    ]
    assert len(class_ambiguities) > 0


def test_should_resolve_dn_when_actual_od_is_given_without_dn_prefix():
    """Verify reverse lookup finds DN 50 when given 60.3 mm OD directly."""
    # Arrange
    agent = NormalizerAgent()
    req = MaterialInput(
        id="T-OD-01",
        material="60.3 mm MS ERW pipe, Class B",
        quantity=600.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    spec = agent.normalize(req)

    # Assert
    assert spec.parsed_dn_mm == 50
    assert spec.parsed_od_mm == 60.3
    assert spec.parsed_wall_thickness_mm == 3.65


def test_should_detect_abbreviated_units_such_as_mtrs_and_pcs():
    """Verify detection of standard industrial unit abbreviations (mtr, mtrs, pcs, mt)."""
    # Arrange & Act
    has_meters, unit_meters = NormalizerAgent._detect_explicit_unit("1000 mtrs ERW pipe")
    has_pieces, unit_pieces = NormalizerAgent._detect_explicit_unit("500 pcs DN 50 pipe")
    has_metric_tons, unit_metric_tons = NormalizerAgent._detect_explicit_unit("50 MT MS pipe")

    # Assert
    assert has_meters is True and unit_meters == "meters"
    assert has_pieces is True and unit_pieces == "pieces"
    assert has_metric_tons is True and unit_metric_tons == "metric_tons"


def test_should_extract_steel_grade_when_specified():
    """Verify extraction of steel grade such as Fe 330 or Fe 410."""
    # Arrange
    agent = NormalizerAgent()
    req = MaterialInput(
        id="M-05",
        material="DN 50 MS ERW Pipe Fe 410 Class B",
        quantity=500.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    spec = agent.normalize(req)

    # Assert
    assert spec.parsed_steel_grade in ["FE 410", "FE410"]
