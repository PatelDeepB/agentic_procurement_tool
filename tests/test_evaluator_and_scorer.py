"""Unit tests for evaluator and scorer agents."""

from app.agents.evaluator import EvaluatorAgent
from app.agents.normalizer import NormalizerAgent
from app.agents.scorer import ScorerAgent
from app.domain.models import (
    MatchCategory,
    MaterialInput,
    NormalizedSpecification,
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


def test_should_not_flag_custom_heavy_wall_assumption_for_standard_pipe_even_if_above_4_5mm():
    """Verify evaluator does not flag heavy gauge assumption for standard pipe above 4.5mm (fixes Flaw 4)."""
    # Arrange
    normalizer = NormalizerAgent()
    evaluator = EvaluatorAgent()
    # DN 100 Class C has 5.4 mm wall thickness, which is standard for DN 100 despite being > 4.5 mm
    spec_dn100 = normalizer.normalize(
        MaterialInput(
            id="T-DN100-STD",
            material="ERW pipe, DN 100, Class C, IS 1239",
            quantity=500.0,
            location="Ahmedabad, Gujarat, India",
        )
    )
    raw_vendor = {
        "vendor_name": "Jindal Pipes Limited",
        "tier": "INDIA_OUTSIDE_AHMEDABAD",
        "vendor_type": "PRIMARY_MANUFACTURER",
        "supported_standards": ["IS 1239"],
        "supported_classes": ["Class A", "Class B", "Class C"],
        "max_wall_thickness_mm": 6.0,
        "certifications": ["IS 1239", "ISO 9001"],
        "location": "Ghaziabad",
        "address": "Factory Road",
        "stock_or_capacity_evidence": "100k MT",
        "delivery_evidence": "Ahmedabad depot",
        "catalog_spec": "IS 1239 Class C",
        "source_url": "https://jindal.com",
    }

    # Act
    _, evidence, _, _ = evaluator.evaluate_vendor(raw_vendor, spec_dn100)

    # Assert: Should NOT assume custom rolling because 5.4 mm is standard for DN 100
    heavy_assumptions = [a for a in evidence.assumptions if "heavy gauge" in a.lower() or "schedule 80" in a.lower()]
    assert len(heavy_assumptions) == 0, "Standard DN 100 Class C pipe (5.4 mm) must not be flagged as custom heavy gauge"


def test_should_retrieve_all_tier_vendors_when_target_dn_is_none():
    """Verify searcher does not exclude vendors with magic number 40 when DN is None."""
    # Arrange
    from app.agents.searcher import SearchAgent
    searcher = SearchAgent()
    spec = NormalizedSpecification(
        raw_input=MaterialInput(id="T-ANY", material="Generic steel pipe", quantity=100.0, location="Ahmedabad"),
        parsed_dn_mm=None,
    )

    # Act
    candidates = searcher.retrieve_candidates(spec)

    # Assert: Should retrieve all 10 registered vendors across tiers
    assert len(candidates) == 10


def test_should_populate_evaluation_notes_on_vendor_evidence():
    """Verify evaluator attaches LLM evaluation trace notes to evidence model."""
    # Arrange
    normalizer = NormalizerAgent()
    evaluator = EvaluatorAgent()
    spec = normalizer.normalize(
        MaterialInput(
            id="T-NOTES",
            material="DN 50 MS ERW pipe",
            quantity=500.0,
            location="Ahmedabad, Gujarat, India",
        )
    )
    raw_vendor = {
        "vendor_name": "Western Steel Agency Ahmedabad",
        "tier": "AHMEDABAD",
        "vendor_type": "AUTHORIZED_DISTRIBUTOR",
        "supported_standards": ["IS 1239"],
        "supported_classes": ["Class A", "Class B", "Class C"],
        "max_wall_thickness_mm": 5.0,
        "certifications": ["ISO 9001:2015"],
        "location": "Ahmedabad",
        "address": "GIDC Odhav",
        "stock_or_capacity_evidence": "Ready stock",
        "delivery_evidence": "Same day",
        "catalog_spec": "IS 1239 ERW Pipes",
        "source_url": "https://westernsteel.in",
    }

    # Act
    _, evidence, _, _ = evaluator.evaluate_vendor(raw_vendor, spec)

    # Assert
    assert evidence.evaluation_notes is not None
    assert len(evidence.evaluation_notes) > 0


