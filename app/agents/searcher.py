"""Search and candidate retrieval agent for multi-tier procurement.

Generates targeted search criteria for Ahmedabad, India-wide, and Global
geographic scopes, and retrieves candidate suppliers capable of fulfilling
industrial piping specifications with complete exclusion audit logging.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.domain.models import AmbiguityType, NormalizedSpecification, VendorTier
from app.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


class SearchAgent:
    """Agent responsible for multi-tier query synthesis and candidate retrieval."""

    def __init__(
        self,
        registry_path: Optional[Path] = None,
        llm_client: Optional[BaseLLMClient] = None,
    ):
        """Initialize search agent with vendor registry and optional LLM client."""
        if registry_path is None:
            registry_path = Path(__file__).parent.parent / "data" / "vendor_registry.json"
        self.registry_path = registry_path
        self.llm = llm_client
        self._vendors: List[Dict[str, Any]] = self._load_registry()

    def _load_registry(self) -> List[Dict[str, Any]]:
        """Load vendor dataset from disk."""
        if not self.registry_path.exists():
            return []
        with open(self.registry_path, "r", encoding="utf-8") as registry_file:
            return json.load(registry_file)

    def generate_search_queries(self, spec: NormalizedSpecification) -> Dict[str, List[str]]:
        """Generate targeted search queries for each geographic tier."""
        if self.llm and hasattr(self.llm, "is_service_available") and self.llm.is_service_available:
            llm_queries = self._synthesize_queries_with_llm(spec)
            if llm_queries:
                return llm_queries

        return self._synthesize_queries_deterministic(spec)

    def _synthesize_queries_with_llm(
        self,
        spec: NormalizedSpecification,
    ) -> Optional[Dict[str, List[str]]]:
        """Use active LLM client to synthesize specialized industrial procurement search queries."""
        system_prompt = (
            "You are a Senior Industrial Procurement Specialist. Generate realistic B2B search queries "
            "for industrial steel pipe procurement across 3 geographic tiers: ahmedabad, india_wide, and global. "
            "Return ONLY a valid JSON object with keys 'ahmedabad', 'india_wide', and 'global', "
            "each containing a list of 2-3 precise search queries."
        )
        user_prompt = (
            f"Material: {spec.raw_input.material}\n"
            f"Nominal Bore: DN {spec.parsed_dn_mm or 'Unspecified'}\n"
            f"Outside Diameter: {spec.parsed_od_mm or 'Unspecified'} mm\n"
            f"Wall Thickness: {spec.parsed_wall_thickness_mm or 'Unspecified'} mm\n"
            f"Standard: {spec.parsed_standard or 'IS 1239'}\n"
            f"Class: {spec.parsed_class or 'Class B'}\n"
            f"Steel Grade: {spec.parsed_steel_grade or 'MS ERW'}\n"
            f"Identified Ambiguities: {[ambiguity.ambiguity_type.value for ambiguity in spec.ambiguities]}"
        )
        try:
            raw_response = self.llm.generate_completion(system_prompt, user_prompt, temperature=0.1)
            parsed_data = self.llm.extract_json(raw_response)
            if all(tier_key in parsed_data for tier_key in ["ahmedabad", "india_wide", "global"]):
                return {
                    tier_key: [str(query).strip() for query in parsed_data[tier_key]]
                    for tier_key in ["ahmedabad", "india_wide", "global"]
                }
        except Exception as query_err:
            logger.warning(f"LLM search query synthesis failed, falling back to deterministic generator: {query_err}")

        return None

    def _build_query_tokens(self, spec: NormalizedSpecification) -> Dict[str, str]:
        """Extract standardized tokens for deterministic search query generation."""
        dn_str = f"DN {spec.parsed_dn_mm}" if spec.parsed_dn_mm else "ERW steel pipe"
        od_str = f"{spec.parsed_od_mm} mm OD" if spec.parsed_od_mm else ""
        wall_str = f"{spec.parsed_wall_thickness_mm} mm wall" if spec.parsed_wall_thickness_mm else ""
        class_str = spec.parsed_class or "Class B"
        grade_str = spec.parsed_steel_grade or "MS ERW"
        std_str = spec.parsed_standard or "IS 1239"

        return {
            "dn": dn_str,
            "od": od_str,
            "wall": wall_str,
            "class_name": class_str,
            "grade": grade_str,
            "standard": std_str,
        }

    def _synthesize_queries_deterministic(
        self,
        spec: NormalizedSpecification,
    ) -> Dict[str, List[str]]:
        """Generate domain-rich search queries with technical dimensions and ambiguity handling."""
        tokens = self._build_query_tokens(spec)
        has_nb_od_ambiguity = any(
            ambiguity.ambiguity_type == AmbiguityType.NOMINAL_BORE_VS_OUTSIDE_DIAMETER
            for ambiguity in spec.ambiguities
        )
        has_non_standard_wall = any(
            ambiguity.ambiguity_type == AmbiguityType.NON_STANDARD_WALL_THICKNESS
            for ambiguity in spec.ambiguities
        )

        ahmedabad_queries = [
            f"Ahmedabad {tokens['dn']} {tokens['od']} {tokens['wall']} ERW pipe stockist distributor GIDC Odhav Vatva",
            f"{tokens['grade']} steel pipe supplier Ahmedabad ready stock {tokens['class_name']} {tokens['standard']}",
        ]
        if has_nb_od_ambiguity:
            ahmedabad_queries.append("40 mm NB vs 40 mm OD MS ERW pipe distributor Ahmedabad ready stock")

        india_queries = [
            f"India ERW steel pipe manufacturer {tokens['dn']} {tokens['wall']} {tokens['class_name']} IS 1239 BIS certified mill",
            f"Primary steel pipe mills India bulk dispatch Ahmedabad depot {tokens['grade']}",
        ]
        if has_non_standard_wall:
            india_queries.append(f"Heavy gauge ERW pipe custom rolling mill India {tokens['dn']} {tokens['wall']} ASTM A53 Schedule 80")

        global_queries = [
            f"Carbon steel ERW line pipe exporter {tokens['dn']} {tokens['od']} ASTM A53 BS 1387 EN 10255",
            f"Global tubular supplier CIF Mundra Port Gujarat India {tokens['dn']} {tokens['wall']}",
        ]

        return {
            "ahmedabad": [" ".join(query_text.split()) for query_text in ahmedabad_queries],
            "india_wide": [" ".join(query_text.split()) for query_text in india_queries],
            "global": [" ".join(query_text.split()) for query_text in global_queries],
        }

    def retrieve_candidates_with_audit(
        self,
        spec: NormalizedSpecification,
        tier: Optional[VendorTier] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """Retrieve matching candidate vendors and capture explicit disqualification rationales."""
        qualified_candidates: List[Dict[str, Any]] = []
        exclusion_log: List[Dict[str, str]] = []
        target_dn = spec.parsed_dn_mm

        for vendor in self._vendors:
            vendor_id = vendor.get("id", "UNKNOWN")
            vendor_name = vendor.get("vendor_name", "Unknown Supplier")
            vendor_tier = vendor.get("tier", "UNKNOWN")

            if tier and vendor_tier != tier.value:
                continue

            if target_dn is not None:
                dn_range = vendor.get("supported_dn_range", [15, 150])
                if not (dn_range[0] <= target_dn <= dn_range[1]):
                    exclusion_log.append({
                        "vendor_id": vendor_id,
                        "vendor_name": vendor_name,
                        "tier": vendor_tier,
                        "disqualification_reason": (
                            f"Nominal size DN {target_dn} is outside supplier certified "
                            f"production range [{dn_range[0]}, {dn_range[1]} mm]."
                        ),
                    })
                    continue

            qualified_candidates.append(vendor)

        return qualified_candidates, exclusion_log

    def retrieve_candidates(
        self,
        spec: NormalizedSpecification,
        tier: Optional[VendorTier] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve matching candidate vendors filtered by tier and preliminary capability."""
        qualified, _ = self.retrieve_candidates_with_audit(spec, tier)
        return qualified
