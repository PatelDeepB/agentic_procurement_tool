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
    types = [ambiguity.ambiguity_type for ambiguity in spec.ambiguities]
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
    qty_amb = next(
        ambiguity
        for ambiguity in spec.ambiguities
        if ambiguity.ambiguity_type == AmbiguityType.UNSPECIFIED_QUANTITY_UNIT
    )

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
    types = [ambiguity.ambiguity_type for ambiguity in spec.ambiguities]
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
    types = [ambiguity.ambiguity_type for ambiguity in spec.ambiguities]
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
    types = [ambiguity.ambiguity_type for ambiguity in spec.ambiguities]
    assert AmbiguityType.UNSPECIFIED_QUANTITY_UNIT not in types


def test_should_generalize_to_arbitrary_pipe_sizes_without_hardcoding():
    """Verify that normalizer dynamically resolves arbitrary pipe dimensions (e.g. DN 100, DN 25)."""
    # Arrange
    agent = NormalizerAgent()
    req_dn100 = MaterialInput(
        id="T-CUSTOM-01",
        material="DN 100 Class B MS ERW pipe",
        quantity=800.0,
        location="Ahmedabad, Gujarat, India",
    )
    req_dn25 = MaterialInput(
        id="T-CUSTOM-02",
        material="DN 25 Class A pipe",
        quantity=300.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    spec_100 = agent.normalize(req_dn100)
    spec_25 = agent.normalize(req_dn25)

    # Assert
    assert spec_100.parsed_dn_mm == 100
    assert spec_100.parsed_class == "Class B"
    assert spec_100.parsed_od_mm == 114.3
    assert spec_100.parsed_wall_thickness_mm == 4.5

    assert spec_25.parsed_dn_mm == 25
    assert spec_25.parsed_class == "Class A"
    assert spec_25.parsed_od_mm == 33.7
    assert spec_25.parsed_wall_thickness_mm == 2.6


def test_should_safely_parse_unrecognized_or_aliased_ambiguity_types():
    """Verify safe enum parsing handles synonyms, casing, and unknown strings gracefully."""
    # Arrange / Act
    t1 = NormalizerAgent._safe_parse_ambiguity_type("OD_VS_NB")
    t2 = NormalizerAgent._safe_parse_ambiguity_type("WALL_THICKNESS_DEVIATION")
    t3 = NormalizerAgent._safe_parse_ambiguity_type("UNKNOWN_CUSTOM_STRING")
    s1 = NormalizerAgent._safe_parse_severity("HIGH")
    s2 = NormalizerAgent._safe_parse_severity("LOW")

    # Assert
    assert t1 == AmbiguityType.NOMINAL_BORE_VS_OUTSIDE_DIAMETER
    assert t2 == AmbiguityType.NON_STANDARD_WALL_THICKNESS
    assert t3 == AmbiguityType.OTHER
    assert s1.value == "CRITICAL"
    assert s2.value == "INFO"


def test_should_correct_hallucinated_wall_thickness_ambiguity_via_tool():
    """Verify bidirectional validation removes false-positive non-standard wall ambiguity."""
    # Arrange
    from app.domain.models import AmbiguityItem, AmbiguitySeverity, UnifiedNormalizerLLMResponse

    agent = NormalizerAgent()
    llm_data = UnifiedNormalizerLLMResponse(
        parsed_dn_mm=40,
        parsed_od_mm=48.3,
        parsed_wall_thickness_mm=3.25,  # Standard Class B for DN 40
        has_quantity_unit=True,
        detected_unit="meters",
    )
    # Simulate LLM hallucinating a non-standard wall error
    ambiguities = [
        AmbiguityItem(
            field="material",
            ambiguity_type=AmbiguityType.NON_STANDARD_WALL_THICKNESS,
            severity=AmbiguitySeverity.WARNING,
            description="Hallucinated: 3.25 mm is non-standard",
            stated_assumption="Custom run",
            clarification_prompt="Confirm thickness",
        )
    ]

    # Act
    agent._verify_wall_thickness_via_tool(llm_data.parsed_dn_mm, llm_data.parsed_wall_thickness_mm, ambiguities)

    # Assert
    assert len(ambiguities) == 0, "Tool must remove false-positive hallucinated ambiguity"

