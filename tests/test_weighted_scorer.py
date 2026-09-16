"""Tests for the qualification-gated weighted scoring comparison agent."""

from app.agents.evaluator import EvaluatorAgent
from app.agents.normalizer import NormalizerAgent
from app.agents.weighted_scorer import WeightedScorerAgent
from app.domain.models import MaterialInput


def _candidate(vendor, spec):
    match_category, evidence, unresolved, next_step = EvaluatorAgent().evaluate_vendor(vendor, spec)
    return {
        "raw_vendor": vendor,
        "match_category": match_category,
        "evidence": evidence,
        "unresolved_issues": unresolved,
        "recommended_next_step": next_step,
    }


def test_weighted_scorer_returns_explainable_qualified_result():
    spec = NormalizerAgent().normalize(MaterialInput(
        id="W-01", material="ERW pipe, DN 50, 60.3 x 4.5 mm, IS 1239", quantity=1000,
    ))
    vendor = {
        "vendor_name": "Qualified Mill", "tier": "INDIA_OUTSIDE_AHMEDABAD",
        "vendor_type": "PRIMARY_MANUFACTURER", "supported_standards": ["IS 1239"],
        "supported_dn_range": [15, 350], "supported_classes": ["Class C"],
        "max_wall_thickness_mm": 10.0, "certifications": ["BIS ISI Mark IS 1239", "ISO 9001"],
        "delivery_evidence": "Ahmedabad depot", "stock_or_capacity_evidence": "250,000 MT capacity",
        "source_url": "https://example.com", "address": "Factory address",
        "contact_email": "sales@example.com", "contact_phone": "+91-0000000000",
    }

    result = WeightedScorerAgent().score_and_rank([_candidate(vendor, spec)], spec)[0]

    assert result.qualified is True
    assert result.weighted_score > 0
    assert sum(WeightedScorerAgent.WEIGHTS.values()) == 100
    assert set(result.criteria_scores) == set(WeightedScorerAgent.WEIGHTS)


def test_weighted_scorer_rejects_vendor_failing_mandatory_standard():
    spec = NormalizerAgent().normalize(MaterialInput(
        id="W-02", material="ERW pipe, DN 50, 60.3 x 4.5 mm, IS 1239", quantity=1000,
    ))
    vendor = {
        "vendor_name": "Unqualified Mill", "tier": "GLOBAL", "vendor_type": "PRIMARY_MANUFACTURER",
        "supported_standards": ["ASTM A53"], "supported_dn_range": [15, 350],
        "max_wall_thickness_mm": 10.0, "certifications": ["ISO 9001"],
        "delivery_evidence": "Mundra Port", "stock_or_capacity_evidence": "Large capacity",
        "source_url": "https://example.com", "address": "Factory address",
    }

    result = WeightedScorerAgent().score_and_rank([_candidate(vendor, spec)], spec)[0]

    assert result.qualified is False
    assert result.weighted_score == 0.0
    assert any("Required standard IS 1239" in failure for failure in result.qualification_failures)