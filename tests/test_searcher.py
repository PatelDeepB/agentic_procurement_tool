"""Unit and integration tests for the multi-tier SearchAgent."""

from app.agents.normalizer import NormalizerAgent
from app.agents.searcher import SearchAgent
from app.domain.models import MaterialInput, NormalizedSpecification, VendorTier
from app.llm.base import BaseLLMClient
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


def test_should_synthesize_dual_queries_for_nominal_bore_vs_od_ambiguity_dynamically():
    """Verify query synthesis dynamically formats NB vs OD query using the ambiguous size."""
    # Arrange
    searcher = SearchAgent()
    normalizer = NormalizerAgent()
    spec_m02 = normalizer.normalize(
        MaterialInput(
            id="M-02",
            material="40 mm MS ERW, Class B pipe",
            quantity=500.0,
            location="Ahmedabad, Gujarat, India",
        )
    )
    spec_dn25 = normalizer.normalize(
        MaterialInput(
            id="T-DN25",
            material="25 mm MS ERW, Class B pipe",
            quantity=300.0,
            location="Ahmedabad, Gujarat, India",
        )
    )

    # Act
    queries_m02 = searcher.generate_search_queries(spec_m02)
    queries_dn25 = searcher.generate_search_queries(spec_dn25)

    # Assert
    ahmedabad_m02 = " ".join(queries_m02["ahmedabad"])
    ahmedabad_dn25 = " ".join(queries_dn25["ahmedabad"])
    assert "40 mm NB vs 40 mm OD" in ahmedabad_m02
    assert "25 mm NB vs 25 mm OD" in ahmedabad_dn25


def test_should_synthesize_custom_rolling_and_global_heavy_wall_queries_for_non_standard_wall():
    """Verify query generator incorporates custom rolling for India and heavy-wall for Global."""
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
    global_text = " ".join(queries["global"])
    assert "Heavy gauge" in india_text or "custom rolling" in india_text
    assert "Schedule 80" in india_text
    assert "Heavy wall" in global_text and "Schedule 80" in global_text


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


def test_should_resolve_target_dn_from_outside_diameter_when_dn_is_none():
    """Verify candidate retrieval infers DN from OD and audits size restrictions."""
    # Arrange
    searcher = SearchAgent()
    spec = NormalizedSpecification(
        raw_input=MaterialInput(id="T-OD165", material="165.1 mm pipe", quantity=100.0),
        parsed_dn_mm=None,
        parsed_od_mm=165.1,
    )

    # Act
    qualified, exclusions = searcher.retrieve_candidates_with_audit(spec)

    # Assert
    excluded_names = [entry["vendor_name"] for entry in exclusions]
    assert "Ashapura Steel Tube Corporation" in excluded_names
    ashapura_exclusion = next(
        entry for entry in exclusions if entry["vendor_name"] == "Ashapura Steel Tube Corporation"
    )
    assert "DN 150 is outside supplier certified production range" in ashapura_exclusion["disqualification_reason"]


def test_should_filter_candidates_by_specific_tier_with_enum_and_string():
    """Verify retrieval respects the requested tier whether passed as enum or string."""
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
    candidates_from_enum = searcher.retrieve_candidates(spec, tier=VendorTier.AHMEDABAD)
    candidates_from_string = searcher.retrieve_candidates(spec, tier="AHMEDABAD")

    # Assert
    assert len(candidates_from_enum) > 0
    assert len(candidates_from_string) == len(candidates_from_enum)
    for vendor in candidates_from_string:
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


def test_should_synthesize_queries_with_llm_client_successfully():
    """Verify SearchAgent successfully uses active LLM client when available."""
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
    assert any("Ahmedabad GIDC ERW" in query for query in queries["ahmedabad"])


class FailingLLMClient(BaseLLMClient):
    """Failing LLM simulation client to test graceful fallback."""

    def generate_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        """Simulate unexpected API failure or corrupted output."""
        raise RuntimeError("Remote LLM connection timeout")


def test_should_fallback_to_deterministic_queries_when_llm_fails():
    """Verify SearchAgent cleanly falls back to deterministic queries upon LLM failure."""
    # Arrange
    failing_client = FailingLLMClient()
    searcher = SearchAgent(llm_client=failing_client)
    normalizer = NormalizerAgent()
    spec = normalizer.normalize(
        MaterialInput(
            id="T-FALLBACK",
            material="DN 50 MS ERW Pipe Class B",
            quantity=500.0,
            location="Ahmedabad, Gujarat, India",
        )
    )

    # Act
    queries = searcher.generate_search_queries(spec)

    # Assert
    assert isinstance(queries, dict)
    assert "ahmedabad" in queries and len(queries["ahmedabad"]) >= 2
    assert any("DN 50" in query for query in queries["ahmedabad"])

