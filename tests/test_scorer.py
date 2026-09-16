"""Unit tests for ScorerAgent confidence scoring, ranking, and deduplication."""

from typing import Any, Dict, List

from app.agents.scorer import ScorerAgent
from app.domain.models import (
    MatchCategory,
    MaterialInput,
    NormalizedSpecification,
    VendorTier,
    VendorType,
)


def _build_test_vendor(
    vendor_name: str,
    tier: str,
    vendor_type: str,
    certifications: List[str],
    has_email: bool = True,
    has_phone: bool = True,
    has_url: bool = True,
) -> Dict[str, Any]:
    """Helper fixture to construct candidate vendor dictionaries."""
    return {
        "vendor_name": vendor_name,
        "tier": tier,
        "vendor_type": vendor_type,
        "supported_standards": ["IS 1239"],
        "supported_classes": ["Class A", "Class B", "Class C"],
        "max_wall_thickness_mm": 6.0,
        "certifications": certifications,
        "location": "Ahmedabad, Gujarat" if tier == "AHMEDABAD" else "Ghaziabad, UP",
        "address": "GIDC Industrial Estate",
        "stock_or_capacity_evidence": "100k MT ready stock",
        "delivery_evidence": "Ahmedabad depot dispatch",
        "catalog_spec": "IS 1239 compliant pipes",
        "source_url": "https://testvendor.com" if has_url else "",
        "contact_email": "sales@testvendor.com" if has_email else "",
        "contact_phone": "+91-79-2287-4100" if has_phone else "",
    }


def test_should_compute_valid_confidence_score_and_breakdown():
    """Verify scorer computes a score within [0, 100] and populates breakdown keys."""
    # Arrange
    scorer = ScorerAgent()
    spec = NormalizedSpecification(raw_input=MaterialInput(id="T-01", material="DN 50 pipe", quantity=100.0))
    raw_vendor = _build_test_vendor("Jindal Pipes", "INDIA_OUTSIDE_AHMEDABAD", "PRIMARY_MANUFACTURER", ["IS 1239", "ISO 9001"])
    candidate = {
        "raw_vendor": raw_vendor,
        "match_category": MatchCategory.EXACT_MATCH,
        "evidence": None,
        "unresolved_issues": [],
        "recommended_next_step": "Issue RFQ",
    }

    # Act
    ranked = scorer.score_and_rank([candidate], spec)

    # Assert
    assert len(ranked) == 1
    scored_vendor = ranked[0]
    assert 0.0 <= scored_vendor.confidence_score <= 100.0
    for key in ["technical_fit", "certifications", "capacity_feasibility", "geographic_logistics", "traceability"]:
        assert key in scored_vendor.score_breakdown


def test_should_deduplicate_identical_vendors():
    """Verify duplicate records for the same vendor are merged."""
    # Arrange
    scorer = ScorerAgent()
    spec = NormalizedSpecification(raw_input=MaterialInput(id="T-02", material="DN 50 pipe", quantity=100.0))
    raw_vendor = _build_test_vendor("Western Steel", "AHMEDABAD", "STOCKIST_TRADER", ["ISO 9001"])
    candidate = {
        "raw_vendor": raw_vendor,
        "match_category": MatchCategory.EXACT_MATCH,
        "evidence": None,
        "unresolved_issues": [],
        "recommended_next_step": "Issue RFQ",
    }

    # Act
    ranked = scorer.score_and_rank([candidate, candidate], spec)

    # Assert
    assert len(ranked) == 1


def test_should_assign_intra_tier_rank_and_global_rank():
    """Verify rank is assigned 1..N within each tier and global_rank is assigned across all."""
    # Arrange
    scorer = ScorerAgent()
    spec = NormalizedSpecification(raw_input=MaterialInput(id="T-03", material="DN 50 pipe", quantity=100.0))

    vendor_india = _build_test_vendor("Primary Mill A", "INDIA_OUTSIDE_AHMEDABAD", "PRIMARY_MANUFACTURER", ["IS 1239", "ISO 9001"])
    vendor_ahmedabad = _build_test_vendor("Stockist A", "AHMEDABAD", "STOCKIST_TRADER", ["ISO 9001"])
    vendor_global = _build_test_vendor("Exporter A", "GLOBAL", "PRIMARY_MANUFACTURER", ["ASTM A53"])

    candidates = [
        {"raw_vendor": vendor_india, "match_category": MatchCategory.EXACT_MATCH, "evidence": None, "unresolved_issues": [], "recommended_next_step": "RFQ"},
        {"raw_vendor": vendor_ahmedabad, "match_category": MatchCategory.EXACT_MATCH, "evidence": None, "unresolved_issues": [], "recommended_next_step": "RFQ"},
        {"raw_vendor": vendor_global, "match_category": MatchCategory.NEAR_MATCH, "evidence": None, "unresolved_issues": [], "recommended_next_step": "RFQ"},
    ]

    # Act
    ranked = scorer.score_and_rank(candidates, spec)

    # Assert: Each tier top vendor must have intra-tier rank 1
    ranked_by_name = {vendor.vendor_name: vendor for vendor in ranked}
    assert ranked_by_name["Primary Mill A"].rank == 1
    assert ranked_by_name["Primary Mill A"].global_rank == 1

    assert ranked_by_name["Stockist A"].rank == 1
    assert ranked_by_name["Stockist A"].global_rank == 2

    assert ranked_by_name["Exporter A"].rank == 1
    assert ranked_by_name["Exporter A"].global_rank == 3


def test_should_award_zero_communication_points_when_no_email_and_no_phone():
    """Verify traceability awards 0.0 communication points when neither email nor phone exists."""
    # Arrange
    scorer = ScorerAgent()
    spec = NormalizedSpecification(raw_input=MaterialInput(id="T-04", material="DN 50 pipe", quantity=100.0))

    vendor_no_contact = _build_test_vendor("No Contact Vendor", "AHMEDABAD", "STOCKIST_TRADER", ["ISO 9001"], has_email=False, has_phone=False, has_url=False)
    vendor_with_email = _build_test_vendor("Email Vendor", "AHMEDABAD", "STOCKIST_TRADER", ["ISO 9001"], has_email=True, has_phone=False, has_url=False)

    candidate_no_contact = {"raw_vendor": vendor_no_contact, "match_category": MatchCategory.EXACT_MATCH, "evidence": None, "unresolved_issues": [], "recommended_next_step": "RFQ"}
    candidate_with_email = {"raw_vendor": vendor_with_email, "match_category": MatchCategory.EXACT_MATCH, "evidence": None, "unresolved_issues": [], "recommended_next_step": "RFQ"}

    # Act
    ranked = scorer.score_and_rank([candidate_no_contact, candidate_with_email], spec)
    ranked_by_name = {vendor.vendor_name: vendor for vendor in ranked}

    # Assert
    score_no_contact = ranked_by_name["No Contact Vendor"].score_breakdown["traceability"]
    score_with_email = ranked_by_name["Email Vendor"].score_breakdown["traceability"]
    assert score_no_contact == 2.0
    assert score_with_email == 2.75
    assert score_with_email > score_no_contact


def test_should_parse_lowercase_and_unknown_tier_and_type_safely():
    """Verify scorer does not crash on lowercase or non-standard tier/type inputs."""
    # Arrange
    scorer = ScorerAgent()
    spec = NormalizedSpecification(raw_input=MaterialInput(id="T-05", material="DN 50 pipe", quantity=100.0))
    raw_vendor = _build_test_vendor("Flexible Vendor", "ahmedabad", "stockist_trader", ["ISO 9001"])
    candidate = {"raw_vendor": raw_vendor, "match_category": MatchCategory.EXACT_MATCH, "evidence": None, "unresolved_issues": [], "recommended_next_step": "RFQ"}

    # Act
    ranked = scorer.score_and_rank([candidate], spec)

    # Assert
    assert len(ranked) == 1
    assert ranked[0].tier == VendorTier.AHMEDABAD
    assert ranked[0].vendor_type == VendorType.STOCKIST_TRADER


def test_should_score_geography_correctly_with_lowercase_tier():
    """Verify geography scoring gives 15.0 points for lowercase 'ahmedabad' tier."""
    # Arrange
    scorer = ScorerAgent()
    spec = NormalizedSpecification(raw_input=MaterialInput(id="T-06", material="DN 50 pipe", quantity=100.0))
    raw_vendor = _build_test_vendor("Lower Tier Vendor", "ahmedabad", "STOCKIST_TRADER", ["ISO 9001"])
    candidate = {"raw_vendor": raw_vendor, "match_category": MatchCategory.EXACT_MATCH, "evidence": None, "unresolved_issues": [], "recommended_next_step": "RFQ"}

    # Act
    ranked = scorer.score_and_rank([candidate], spec)

    # Assert: Must receive local geography score of 15.0, not overseas score of 8.0
    assert ranked[0].score_breakdown["geographic_logistics"] == 15.0


def test_should_break_ties_deterministically_by_technical_fit_and_name():
    """Verify vendors with equal confidence scores are sorted deterministically."""
    # Arrange
    scorer = ScorerAgent()
    spec = NormalizedSpecification(raw_input=MaterialInput(id="T-07", material="DN 50 pipe", quantity=100.0))

    vendor_beta = _build_test_vendor("Beta Steel", "INDIA_OUTSIDE_AHMEDABAD", "PRIMARY_MANUFACTURER", ["IS 1239", "ISO 9001"])
    vendor_alpha = _build_test_vendor("Alpha Steel", "INDIA_OUTSIDE_AHMEDABAD", "PRIMARY_MANUFACTURER", ["IS 1239", "ISO 9001"])

    candidates_order_one = [
        {"raw_vendor": vendor_beta, "match_category": MatchCategory.EXACT_MATCH, "evidence": None, "unresolved_issues": [], "recommended_next_step": "RFQ"},
        {"raw_vendor": vendor_alpha, "match_category": MatchCategory.EXACT_MATCH, "evidence": None, "unresolved_issues": [], "recommended_next_step": "RFQ"},
    ]
    candidates_order_two = [
        {"raw_vendor": vendor_alpha, "match_category": MatchCategory.EXACT_MATCH, "evidence": None, "unresolved_issues": [], "recommended_next_step": "RFQ"},
        {"raw_vendor": vendor_beta, "match_category": MatchCategory.EXACT_MATCH, "evidence": None, "unresolved_issues": [], "recommended_next_step": "RFQ"},
    ]

    # Act
    ranked_one = scorer.score_and_rank(candidates_order_one, spec)
    ranked_two = scorer.score_and_rank(candidates_order_two, spec)

    # Assert: Output order must be identical (Alpha before Beta by alphabetical tie-breaker)
    assert ranked_one[0].vendor_name == "Alpha Steel"
    assert ranked_one[1].vendor_name == "Beta Steel"
    assert ranked_two[0].vendor_name == "Alpha Steel"
    assert ranked_two[1].vendor_name == "Beta Steel"


def test_should_adjust_capacity_score_for_bulk_tonnage_orders():
    """Verify stockist capacity score adjusts when order tonnage exceeds 50 MT."""
    # Arrange
    scorer = ScorerAgent()
    spec_normal = NormalizedSpecification(
        raw_input=MaterialInput(id="T-NORM", material="DN 50 pipe", quantity=100.0),
        total_estimated_metric_tons=5.0,
    )
    spec_bulk = NormalizedSpecification(
        raw_input=MaterialInput(id="T-BULK", material="DN 50 pipe", quantity=10000.0),
        total_estimated_metric_tons=120.0,
    )

    vendor_stockist = _build_test_vendor("Stockist Vendor", "AHMEDABAD", "STOCKIST_TRADER", ["ISO 9001"])
    candidate = {
        "raw_vendor": vendor_stockist,
        "match_category": MatchCategory.EXACT_MATCH,
        "evidence": None,
        "unresolved_issues": [],
        "recommended_next_step": "RFQ",
    }

    # Act
    ranked_normal = scorer.score_and_rank([candidate], spec_normal)
    ranked_bulk = scorer.score_and_rank([candidate], spec_bulk)

    # Assert
    capacity_normal = ranked_normal[0].score_breakdown["capacity_feasibility"]
    capacity_bulk = ranked_bulk[0].score_breakdown["capacity_feasibility"]
    assert capacity_normal == 14.0
    assert capacity_bulk == 12.0  # 14.0 - 2.0 capacity adjustment for bulk scale exceeding routine buffer

