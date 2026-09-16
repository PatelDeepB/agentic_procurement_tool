"""Unit tests for ExecutiveSynthesizerAgent Chief Procurement Officer reasoning."""

from unittest.mock import MagicMock

from app.agents.synthesizer import ExecutiveSynthesizerAgent
from app.domain.models import (
    AmbiguityItem,
    AmbiguitySeverity,
    AmbiguityType,
    EvaluatedVendor,
    MatchCategory,
    MaterialInput,
    NormalizedSpecification,
    VendorEvidence,
    VendorTier,
    VendorType,
)
from app.llm.client import MockLLMClient


def _build_test_evaluated_vendor(
    vendor_name: str,
    tier: VendorTier,
    vendor_type: VendorType,
    score: float,
    rank: int,
    global_rank: int,
) -> EvaluatedVendor:
    """Helper fixture to create typed EvaluatedVendor instances."""
    evidence = VendorEvidence(
        catalog_spec="Standard IS 1239 ERW pipe",
        source_url="https://testvendor.com",
        address="GIDC Estate, Ahmedabad",
        contact_email="sales@testvendor.com",
        contact_phone="+91-79-2287-4100",
        certifications=["IS 1239", "ISO 9001"],
    )
    return EvaluatedVendor(
        vendor_name=vendor_name,
        tier=tier,
        location="Ahmedabad, Gujarat" if tier == VendorTier.AHMEDABAD else "Ghaziabad, UP",
        country="India",
        vendor_type=vendor_type,
        match_category=MatchCategory.EXACT_MATCH,
        confidence_score=score,
        score_breakdown={},
        evidence=evidence,
        unresolved_issues=[],
        recommended_next_step="Issue RFQ",
        rank=rank,
        global_rank=global_rank,
    )


def test_should_generate_comprehensive_synthesis_with_llm_client():
    """Verify synthesizer produces CPO strategic reasoning using active LLM client."""
    # Arrange
    cloud_client = MagicMock()
    cloud_client.__class__.__name__ = "GeminiLLMClient"
    cloud_client.is_service_available = True
    cloud_client.generate_completion.return_value = (
        "Executive Procurement Recommendation:\n"
        "### 1. Executive Feasibility & Technical Viability\n"
        "Technical analysis complete.\n"
        "### 2. Strategic Dual-Sourcing Recommendation\n"
        "Dual sourcing recommended.\n"
        "### 3. Critical Commercial & Logistics Risk Matrix\n"
        "Risk matrix analyzed.\n"
        "### 4. Actionable Buyer RFQ Execution Plan\n"
        "1. Issue RFQ."
    )
    synthesizer = ExecutiveSynthesizerAgent(llm_client=cloud_client)
    raw_input = MaterialInput(id="M-01", material="ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239", quantity=1000.0)
    spec = NormalizedSpecification(raw_input=raw_input, parsed_dn_mm=50, parsed_wall_thickness_mm=5.5)

    vendor_local = _build_test_evaluated_vendor("Western Steel", VendorTier.AHMEDABAD, VendorType.STOCKIST_TRADER, 89.0, 1, 3)
    vendor_india = _build_test_evaluated_vendor("Jindal Pipes", VendorTier.INDIA_OUTSIDE_AHMEDABAD, VendorType.PRIMARY_MANUFACTURER, 99.0, 1, 1)
    vendor_global = _build_test_evaluated_vendor("Baosteel", VendorTier.GLOBAL, VendorType.PRIMARY_MANUFACTURER, 80.0, 1, 6)

    # Act
    synthesis = synthesizer.synthesize(spec, [vendor_local], [vendor_india], [vendor_global])

    # Assert
    assert cloud_client.generate_completion.called
    assert "Executive Procurement Recommendation:" in synthesis
    assert "Executive Feasibility & Technical Viability" in synthesis
    assert "Strategic Dual-Sourcing Recommendation" in synthesis
    assert "Actionable Buyer RFQ Execution Plan" in synthesis


def test_should_fallback_to_rich_deterministic_synthesis_when_llm_fails():
    """Verify synthesizer gracefully recovers with deterministic CPO model if LLM raises exception."""
    # Arrange
    faulty_client = MagicMock()
    faulty_client.is_service_available = True
    faulty_client.generate_completion.side_effect = RuntimeError("Rate limit exceeded")

    synthesizer = ExecutiveSynthesizerAgent(llm_client=faulty_client)
    raw_input = MaterialInput(id="M-01", material="ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239", quantity=1000.0)
    spec = NormalizedSpecification(raw_input=raw_input, parsed_dn_mm=50, parsed_wall_thickness_mm=5.5)

    vendor_local = _build_test_evaluated_vendor("Western Steel", VendorTier.AHMEDABAD, VendorType.STOCKIST_TRADER, 89.0, 1, 3)
    vendor_india = _build_test_evaluated_vendor("Jindal Pipes", VendorTier.INDIA_OUTSIDE_AHMEDABAD, VendorType.PRIMARY_MANUFACTURER, 99.0, 1, 1)

    # Act
    synthesis = synthesizer.synthesize(spec, [vendor_local], [vendor_india], [])

    # Assert
    assert "Executive Procurement Recommendation:" in synthesis
    assert "Critical Commercial & Logistics Risk Matrix" in synthesis
    assert "Western Steel" in synthesis
    assert "Jindal Pipes" in synthesis


def test_should_tailor_recommendations_for_non_standard_wall_thickness_m01():
    """Verify deterministic synthesis highlights custom rolling MOQ and primary mill requirements for M-01."""
    # Arrange
    synthesizer = ExecutiveSynthesizerAgent(llm_client=None)
    ambiguity = AmbiguityItem(
        field="material",
        ambiguity_type=AmbiguityType.NON_STANDARD_WALL_THICKNESS,
        severity=AmbiguitySeverity.WARNING,
        description="5.5 mm wall exceeds standard IS 1239 Class C.",
        stated_assumption="Requires custom mill rolling.",
        clarification_prompt="Confirm 5.5 mm wall.",
    )
    raw_input = MaterialInput(id="M-01", material="ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239", quantity=1000.0)
    spec = NormalizedSpecification(
        raw_input=raw_input,
        parsed_dn_mm=50,
        parsed_wall_thickness_mm=5.5,
        ambiguities=[ambiguity],
    )

    vendor_local = _build_test_evaluated_vendor("Western Steel", VendorTier.AHMEDABAD, VendorType.STOCKIST_TRADER, 89.0, 1, 3)
    vendor_india = _build_test_evaluated_vendor("Jindal Pipes", VendorTier.INDIA_OUTSIDE_AHMEDABAD, VendorType.PRIMARY_MANUFACTURER, 99.0, 1, 1)

    # Act
    synthesis = synthesizer.synthesize(spec, [vendor_local], [vendor_india], [])

    # Assert
    assert "5.5 mm" in synthesis
    assert "exceeds standard" in synthesis.lower()
    assert "minimum order quantity" in synthesis.lower() or "moq" in synthesis.lower()
    assert "astm a53 schedule 80" in synthesis.lower()


def test_should_tailor_recommendations_for_nb_vs_od_ambiguity_m02():
    """Verify deterministic synthesis clarifies 40 mm NB vs OD discrepancy for M-02."""
    # Arrange
    synthesizer = ExecutiveSynthesizerAgent(llm_client=None)
    ambiguity = AmbiguityItem(
        field="material",
        ambiguity_type=AmbiguityType.NOMINAL_BORE_VS_OUTSIDE_DIAMETER,
        severity=AmbiguitySeverity.WARNING,
        description="40 mm can denote Nominal Bore (48.3 mm OD) or strict OD.",
        stated_assumption="Assumed DN 40 NB.",
        clarification_prompt="Confirm 40 mm NB vs OD.",
    )
    raw_input = MaterialInput(id="M-02", material="40 mm MS ERW, Class B pipe", quantity=500.0)
    spec = NormalizedSpecification(
        raw_input=raw_input,
        parsed_dn_mm=40,
        parsed_od_mm=48.3,
        ambiguities=[ambiguity],
    )

    vendor_local = _build_test_evaluated_vendor("Gujarat Infra Pipes", VendorTier.AHMEDABAD, VendorType.AUTHORIZED_DISTRIBUTOR, 97.0, 1, 5)
    vendor_india = _build_test_evaluated_vendor("APL Apollo", VendorTier.INDIA_OUTSIDE_AHMEDABAD, VendorType.PRIMARY_MANUFACTURER, 99.0, 1, 1)

    # Act
    synthesis = synthesizer.synthesize(spec, [vendor_local], [vendor_india], [])

    # Assert
    assert "40 mm" in synthesis
    assert "48.3 mm" in synthesis
    assert "Gujarat Infra Pipes" in synthesis
    assert "APL Apollo" in synthesis


def test_should_tailor_recommendations_for_heavy_batch_tonnage_m03():
    """Verify deterministic synthesis calculates volume exposure and piece count for M-03."""
    # Arrange
    synthesizer = ExecutiveSynthesizerAgent(llm_client=None)
    ambiguity = AmbiguityItem(
        field="quantity",
        ambiguity_type=AmbiguityType.UNSPECIFIED_QUANTITY_UNIT,
        severity=AmbiguitySeverity.WARNING,
        description="Quantity unit unspecified.",
        stated_assumption="Assumed linear meters.",
        clarification_prompt="Confirm unit.",
    )
    raw_input = MaterialInput(id="M-03", material="ERW pipe, DN 80, 89.5 x 4.8 mm, IS 1239", quantity=1200.0)
    spec = NormalizedSpecification(
        raw_input=raw_input,
        parsed_dn_mm=80,
        parsed_od_mm=89.5,
        parsed_wall_thickness_mm=4.8,
        total_estimated_metric_tons=12.5,
        total_estimated_pieces_6m=200,
        ambiguities=[ambiguity],
    )

    vendor_local = _build_test_evaluated_vendor("Gujarat Infra Pipes", VendorTier.AHMEDABAD, VendorType.AUTHORIZED_DISTRIBUTOR, 97.0, 1, 5)
    vendor_india = _build_test_evaluated_vendor("APL Apollo", VendorTier.INDIA_OUTSIDE_AHMEDABAD, VendorType.PRIMARY_MANUFACTURER, 99.0, 1, 1)

    # Act
    synthesis = synthesizer.synthesize(spec, [vendor_local], [vendor_india], [])

    # Assert
    assert "12.5 Metric Tons" in synthesis or "12.5" in synthesis
    assert "200" in synthesis
    assert "Standard Compliance" in synthesis


def test_should_cite_top_ranked_vendors_and_scores_in_executive_summary():
    """Verify deterministic synthesis includes top supplier names and confidence scores across all tiers."""
    # Arrange
    synthesizer = ExecutiveSynthesizerAgent(llm_client=None)
    raw_input = MaterialInput(id="T-01", material="DN 50 pipe", quantity=100.0)
    spec = NormalizedSpecification(raw_input=raw_input, parsed_dn_mm=50)

    vendor_local = _build_test_evaluated_vendor("Stockist Alfa", VendorTier.AHMEDABAD, VendorType.STOCKIST_TRADER, 91.5, 1, 2)
    vendor_india = _build_test_evaluated_vendor("Primary Mill Beta", VendorTier.INDIA_OUTSIDE_AHMEDABAD, VendorType.PRIMARY_MANUFACTURER, 98.5, 1, 1)
    vendor_global = _build_test_evaluated_vendor("Global Exporter Gamma", VendorTier.GLOBAL, VendorType.PRIMARY_MANUFACTURER, 84.0, 1, 3)

    # Act
    synthesis = synthesizer.synthesize(spec, [vendor_local], [vendor_india], [vendor_global])

    # Assert
    assert "Stockist Alfa (91.5%)" in synthesis
    assert "Primary Mill Beta (98.5%)" in synthesis
    assert "Global Exporter Gamma (84.0%)" in synthesis
