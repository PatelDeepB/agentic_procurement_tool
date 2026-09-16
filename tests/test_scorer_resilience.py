"""Resilience and edge case unit tests for ScorerAgent."""

from app.agents.scorer import ScorerAgent
from app.domain.models import (
    MatchCategory,
    MaterialInput,
    NormalizedSpecification,
)
from tests.test_scorer import _build_test_vendor


def test_should_score_traceability_zero_when_no_address_and_no_contact():
    """Verify traceability awards exactly 0.0 when vendor has no address and no contact."""
    # Arrange
    scorer = ScorerAgent()
    spec = NormalizedSpecification(raw_input=MaterialInput(id="T-ZERO", material="DN 50 pipe", quantity=100.0))
    raw_vendor = _build_test_vendor(
        "Ghost Vendor", "AHMEDABAD", "STOCKIST_TRADER", ["ISO 9001"],
        has_email=False, has_phone=False, has_url=False,
    )
    raw_vendor["address"] = ""

    # Act
    ranked = scorer.score_and_rank([{"raw_vendor": raw_vendor, "match_category": MatchCategory.EXACT_MATCH}], spec)

    # Assert
    assert ranked[0].score_breakdown["traceability"] == 0.0


def test_should_accept_raw_vendor_dictionary_directly():
    """Verify scorer safely accepts raw vendor dict without wrapper structure."""
    # Arrange
    scorer = ScorerAgent()
    spec = NormalizedSpecification(raw_input=MaterialInput(id="T-RAW", material="DN 50 pipe", quantity=100.0))
    raw_vendor = _build_test_vendor("Direct Vendor", "AHMEDABAD", "STOCKIST_TRADER", ["ISO 9001"])

    # Act
    ranked = scorer.score_and_rank([raw_vendor], spec)

    # Assert
    assert len(ranked) == 1
    assert ranked[0].vendor_name == "Direct Vendor"


def test_should_handle_none_certifications_and_none_delivery_evidence():
    """Verify scorer safely processes vendor with None certs and delivery evidence."""
    # Arrange
    scorer = ScorerAgent()
    spec = NormalizedSpecification(raw_input=MaterialInput(id="T-NONE", material="DN 50 pipe", quantity=100.0))
    raw_vendor = _build_test_vendor("None Vendor", "INDIA_OUTSIDE_AHMEDABAD", "STOCKIST_TRADER", [])
    raw_vendor["certifications"] = None
    raw_vendor["delivery_evidence"] = None

    # Act
    ranked = scorer.score_and_rank([raw_vendor], spec)

    # Assert
    assert len(ranked) == 1
    assert ranked[0].score_breakdown["certifications"] == 5.0
    assert ranked[0].score_breakdown["geographic_logistics"] == 11.0


def test_should_recognize_website_field_for_traceability():
    """Verify traceability awards 1.5 points when website is given without source_url."""
    # Arrange
    scorer = ScorerAgent()
    spec = NormalizedSpecification(raw_input=MaterialInput(id="T-WEB", material="DN 50 pipe", quantity=100.0))
    raw_vendor = _build_test_vendor("Web Vendor", "AHMEDABAD", "STOCKIST_TRADER", ["ISO 9001"], has_url=False)
    raw_vendor["website"] = "https://webvendor.com"

    # Act
    ranked = scorer.score_and_rank([raw_vendor], spec)

    # Assert
    # Address (2.0) + Website (1.5) + Email/Phone (1.5) = 5.0
    assert ranked[0].score_breakdown["traceability"] == 5.0
