"""Unit tests for AI/ML LLM agents, ReAct tools, and provider fallback."""

from app.agents.evaluator import EvaluatorAgent
from app.agents.normalizer import NormalizerAgent
from app.agents.orchestrator import ProcurementOrchestrator
from app.domain.models import MaterialInput
from app.llm.client import MockLLMClient, get_llm_client
from app.tools.procurement_tools import (
    tool_calculate_steel_tonnage,
    tool_evaluate_wall_thickness,
    tool_lookup_is1239_spec,
)


def test_should_instantiate_mock_llm_client_as_default_fallback():
    """Verify get_llm_client returns MockLLMClient when no cloud API key is configured."""
    # Act
    client = get_llm_client(force_provider="mock")

    # Assert
    assert isinstance(client, MockLLMClient)


def test_should_generate_structured_json_from_mock_client():
    """Verify MockLLMClient can generate parsed structured dictionary for unified normalizer."""
    # Arrange
    client = MockLLMClient()

    # Act
    data = client.generate_structured_json("System prompt", "normalize requisition for 40 mm pipe")

    # Assert
    assert "parsed_dn_mm" in data
    assert "technical_ambiguities" in data
    assert "has_quantity_unit" in data


def test_should_execute_is1239_lookup_tool_accurately():
    """Verify tool_lookup_is1239_spec returns dimensional bounds."""
    # Act
    result = tool_lookup_is1239_spec(40)

    # Assert
    assert result["found"] is True
    assert result["nominal_od_mm"] == 48.3
    assert result["class_b_medium_wall_mm"] == 3.25


def test_should_execute_steel_tonnage_tool_accurately():
    """Verify tool_calculate_steel_tonnage computes mass and 6m piece counts."""
    # Act: DN 50 OD 60.3, wall 4.5, 1000m
    result = tool_calculate_steel_tonnage(60.3, 4.5, 1000.0)

    # Assert
    assert result["linear_weight_kg_per_meter"] > 0
    assert result["total_metric_tons"] > 0
    assert result["estimated_pieces_6m"] == 167


def test_should_run_end_to_end_orchestrator_with_llm_synthesis():
    """Verify orchestrator runs multi-agent workflow and attaches executive LLM synthesis."""
    # Arrange
    client = MockLLMClient()
    orchestrator = ProcurementOrchestrator(llm_client=client)
    req = MaterialInput(
        id="M-01",
        material="ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239",
        quantity=1000.0,
        location="Ahmedabad, Gujarat, India",
    )

    # Act
    result = orchestrator.run_procurement_workflow(req)

    # Assert
    assert result.material_id == "M-01"
    assert result.llm_synthesis is not None
    assert "Executive Procurement Recommendation" in result.llm_synthesis
    assert result.model_provider == "mock"
