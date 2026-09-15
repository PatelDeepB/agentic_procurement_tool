"""Unit tests for evaluator and scorer agents."""

from app.agents.evaluator import EvaluatorAgent
from app.agents.normalizer import NormalizerAgent
from app.agents.scorer import ScorerAgent
from app.domain.models import (
    MatchCategory,
    MaterialInput,
    VendorTier,
)


def test_should_classify_exact_match_for_is1239_certified_producer():
    """Verify evaluator assigns EXACT_MATCH to vendor meeting standard and dimensions."""
    # Arrange
    normalizer = NormalizerAgent()
    evaluator = EvaluatorAgent()
    spec = normalizer.normalize(
        MaterialInput(
            id="M-02",
            material="40 mm MS ERW, Class B pipe",
            quantity=500.0,
            location="Ahmedabad, Gujarat, India",
        )
    )
    raw_vendor = {
        "vendor_name": "Test Manufacturer",
        "tier": "INDIA_OUTSIDE_AHMEDABAD",
        "vendor_type": "PRIMARY_MANUFACTURER",
        "supported_standards": ["IS 1239", "ASTM A53"],
        "supported_classes": ["Class B", "Class C"],
        "max_wall_thickness_mm": 5.4,
        "certifications": ["IS 1239", "ISO 9001"],
        "location": "Ghaziabad",
        "address": "Factory Road",
        "stock_or_capacity_evidence": "100k MT",
        "delivery_evidence": "Changodar depot",
        "catalog_spec": "IS 1239 Class B",
        "source_url": "https://test.com",
    }

    # Act
    match_cat, evidence, _, _ = evaluator.evaluate_vendor(raw_vendor, spec)

    # Assert
    assert match_cat == MatchCategory.EXACT_MATCH
    assert any("[SOURCED]" in f for f in evidence.sourced_facts)
    assert any("[ASSUMPTION]" in a for a in evidence.assumptions)
    assert any("[NEEDS_CONFIRMATION_RFQ]" in r for r in evidence.needs_confirmation_rfq)


def test_should_compute_valid_confidence_score_and_breakdown():
    """Verify scorer computes a score within [0, 100] and populates breakdown keys."""
    # Arrange
    normalizer = NormalizerAgent()
    evaluator = EvaluatorAgent()
    scorer = ScorerAgent()

    spec = normalizer.normalize(
        MaterialInput(
            id="M-03",
            material="ERW pipe, DN 80, 89.5 x 4.8 mm, IS 1239",
            quantity=1200.0,
            location="Ahmedabad, Gujarat, India",
        )
    )
    raw_vendor = {
        "vendor_name": "Jindal Pipes Limited",
        "tier": "INDIA_OUTSIDE_AHMEDABAD",
        "vendor_type": "PRIMARY_MANUFACTURER",
        "supported_standards": ["IS 1239"],
        "supported_classes": ["Class C"],
        "max_wall_thickness_mm": 10.0,
        "certifications": ["IS 1239", "ISO 9001:2015"],
        "location": "Ghaziabad",
        "address": "Pipe House",
        "stock_or_capacity_evidence": "250,000 MT",
        "delivery_evidence": "Ahmedabad depot",
        "catalog_spec": "IS 1239 Class C",
        "source_url": "https://jindal.com",
        "contact_email": "sales@jindal.com",
        "contact_phone": "+91-11-4139-9999",
    }
    match_cat, evidence, unresolved, next_step = evaluator.evaluate_vendor(raw_vendor, spec)
    candidates = [{
        "raw_vendor": raw_vendor,
        "match_category": match_cat,
        "evidence": evidence,
        "unresolved_issues": unresolved,
        "recommended_next_step": next_step,
    }]

    # Act
    ranked = scorer.score_and_rank(candidates, spec)

    # Assert
    assert len(ranked) == 1
    vendor = ranked[0]
    assert 0.0 <= vendor.confidence_score <= 100.0
    assert "technical_fit" in vendor.score_breakdown
    assert "certifications" in vendor.score_breakdown
    assert "capacity_feasibility" in vendor.score_breakdown
    assert "geographic_logistics" in vendor.score_breakdown
    assert "traceability" in vendor.score_breakdown


def test_should_deduplicate_identical_vendors():
    """Verify that multiple records for the same vendor are merged into one."""
    # Arrange
    normalizer = NormalizerAgent()
    evaluator = EvaluatorAgent()
    scorer = ScorerAgent()

    spec = normalizer.normalize(
        MaterialInput(
            id="M-01",
            material="ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239",
            quantity=1000.0,
            location="Ahmedabad, Gujarat, India",
        )
    )
    raw_vendor = {
        "vendor_name": "Gujarat Infra Pipes Pvt Ltd",
        "tier": "AHMEDABAD",
        "vendor_type": "AUTHORIZED_DISTRIBUTOR",
        "supported_standards": ["IS 1239"],
        "supported_classes": ["Class A", "Class B", "Class C"],
        "max_wall_thickness_mm": 5.4,
        "certifications": ["ISO 9001"],
        "location": "Ahmedabad",
        "address": "Odhav GIDC",
        "stock_or_capacity_evidence": "2,500 MT",
        "delivery_evidence": "Same day",
        "catalog_spec": "ERW pipes",
        "source_url": "https://gujaratinfra.com",
    }
    match_cat, evidence, unresolved, next_step = evaluator.evaluate_vendor(raw_vendor, spec)
    duplicate_candidates = [
        {"raw_vendor": raw_vendor, "match_category": match_cat, "evidence": evidence, "unresolved_issues": unresolved, "recommended_next_step": next_step},
        {"raw_vendor": raw_vendor, "match_category": match_cat, "evidence": evidence, "unresolved_issues": unresolved, "recommended_next_step": next_step},
    ]

    # Act
    ranked = scorer.score_and_rank(duplicate_candidates, spec)

    # Assert
    assert len(ranked) == 1
