"""Unit and integration tests for the multi-tier SearchAgent."""

from app.agents.normalizer import NormalizerAgent
from app.agents.searcher import SearchAgent
from app.domain.models import MaterialInput, VendorTier
from app.llm.mock_client import MockLLMClient
from app.tools.procurement_tools import tool_search_vendor_registry


def test_should_generate_rich_deterministic_queries_with_dimensions_and_grades():
    """Verify deterministic query generator produces queries with OD, wall, and grade."""
    # Arrange
    searcher = SearchAgent()
    normalizer = NormalizerAgent()
    spec = normalizer.normalize(
        MaterialInput(
            id="T-SEARCH-01",
            material="DN 50, 60.3 x 3.65 mm MS ERW Pipe Fe 410 Class B",
            quantity=500.0,
            location="Ahmedabad, Gujarat, India",
        )
    )

    # Act
    queries = searcher.generate_search_queries(spec)

    # Assert
    assert "ahmedabad" in queries and len(queries["ahmedabad"]) >= 2
    assert "india_wide" in queries and len(queries["india_wide"]) >= 2
    assert "global" in queries and len(queries["global"]) >= 2

    ahmedabad_text = " ".join(queries["ahmedabad"])
    assert "DN 50" in ahmedabad_text
    assert "60.3 mm OD" in ahmedabad_text
    assert "FE 410" in ahmedabad_text or "Fe 410" in ahmedabad_text


def test_should_synthesize_dual_queries_for_nominal_bore_vs_od_ambiguity():
    """Verify query synthesis adds clarifying queries when NB vs OD ambiguity is present."""
    # Arrange
    searcher = SearchAgent()
    normalizer = NormalizerAgent()
    spec = normalizer.normalize(
        MaterialInput(
            id="M-02",
            material="40 mm MS ERW, Class B pipe",
            quantity=500.0,
            location="Ahmedabad, Gujarat, India",
        )
    )

    # Act
    queries = searcher.generate_search_queries(spec)

    # Assert
    ahmedabad_text = " ".join(queries["ahmedabad"])
    assert "40 mm NB vs 40 mm OD" in ahmedabad_text


def test_should_synthesize_custom_rolling_queries_for_non_standard_wall():
    """Verify query generator incorporates custom rolling keywords for non-standard wall."""
    # Arrange
    searcher = SearchAgent()
    normalizer = NormalizerAgent()
    spec = normalizer.normalize(
        MaterialInput(
            id="M-01",
            material="ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239",
            quantity=1000.0,
            location="Ahmedabad, Gujarat, India",
        )
    )

    # Act
    queries = searcher.generate_search_queries(spec)

    # Assert
    india_text = " ".join(queries["india_wide"])
    assert "Heavy gauge" in india_text or "custom rolling" in india_text
    assert "Schedule 80" in india_text


def test_should_retrieve_candidates_and_populate_exclusion_log_when_dn_out_of_range():
    """Verify candidate retrieval correctly disqualifies suppliers outside DN range."""
    # Arrange
    searcher = SearchAgent()
    normalizer = NormalizerAgent()
    spec = normalizer.normalize(
        MaterialInput(
            id="T-DN15-TEST",
            material="DN 15 MS ERW pipe, Class B",
            quantity=200.0,
            location="Ahmedabad, Gujarat, India",
        )
    )

    # Act
    qualified, exclusions = searcher.retrieve_candidates_with_audit(spec)

    # Assert
    qualified_names = [vendor["vendor_name"] for vendor in qualified]
    excluded_names = [entry["vendor_name"] for entry in exclusions]

    assert "Gujarat Infra Pipes Pvt Ltd" in qualified_names
    assert "Western Steel Agency Ahmedabad" in excluded_names

    western_exclusion = next(
        entry for entry in exclusions if entry["vendor_name"] == "Western Steel Agency Ahmedabad"
    )
    assert "DN 15 is outside supplier certified production range" in western_exclusion["disqualification_reason"]


def test_should_filter_candidates_by_specific_tier():
    """Verify retrieval respects the requested geographic tier filter."""
    # Arrange
    searcher = SearchAgent()
    normalizer = NormalizerAgent()
    spec = normalizer.normalize(
        MaterialInput(
            id="T-TIER-TEST",
            material="DN 50 MS ERW pipe, Class B",
            quantity=500.0,
            location="Ahmedabad, Gujarat, India",
        )
    )

    # Act
    ahmedabad_candidates = searcher.retrieve_candidates(spec, tier=VendorTier.AHMEDABAD)

    # Assert
    assert len(ahmedabad_candidates) > 0
    for vendor in ahmedabad_candidates:
        assert vendor["tier"] == VendorTier.AHMEDABAD.value


def test_should_execute_search_vendor_registry_tool():
    """Verify ReAct search tool returns formatted candidates and exclusion summaries."""
    # Act
    tool_result = tool_search_vendor_registry(tier="AHMEDABAD", target_dn_mm=50)

    # Assert
    assert tool_result["total_matched"] > 0
    candidate = tool_result["candidates"][0]
    assert "vendor_name" in candidate
    assert "supported_dn_range" in candidate
    assert "supported_standards" in candidate


def test_should_support_llm_client_injection_with_graceful_fallback():
    """Verify SearchAgent handles mock LLM client without raising exceptions."""
    # Arrange
    mock_client = MockLLMClient()
    searcher = SearchAgent(llm_client=mock_client)
    normalizer = NormalizerAgent()
    spec = normalizer.normalize(
        MaterialInput(
            id="T-LLM-SEARCH",
            material="DN 80 MS ERW Pipe Class C",
            quantity=800.0,
            location="Ahmedabad, Gujarat, India",
        )
    )

    # Act
    queries = searcher.generate_search_queries(spec)

    # Assert
    assert isinstance(queries, dict)
    assert "ahmedabad" in queries and len(queries["ahmedabad"]) >= 2
