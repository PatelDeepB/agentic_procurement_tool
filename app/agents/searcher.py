"""Search and candidate retrieval agent for multi-tier procurement.

Generates targeted search criteria for Ahmedabad, India-wide, and Global
geographic scopes, and retrieves candidate suppliers capable of fulfilling
industrial piping specifications.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.domain.models import NormalizedSpecification, VendorTier


class SearchAgent:
    """Agent responsible for multi-tier query synthesis and candidate retrieval."""

    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize search agent with vendor registry."""
        if registry_path is None:
            registry_path = Path(__file__).parent.parent / "data" / "vendor_registry.json"
        self.registry_path = registry_path
        self._vendors: List[Dict[str, Any]] = self._load_registry()

    def _load_registry(self) -> List[Dict[str, Any]]:
        """Load vendor dataset from disk."""
        if not self.registry_path.exists():
            return []
        with open(self.registry_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def generate_search_queries(self, spec: NormalizedSpecification) -> Dict[str, List[str]]:
        """Generate targeted search queries for each geographic tier."""
        dn_term = f"DN {spec.parsed_dn_mm}" if spec.parsed_dn_mm else "ERW pipe"
        class_term = spec.parsed_class or "IS 1239"

        return {
            "ahmedabad": [
                f"Ahmedabad {dn_term} ERW steel pipe stockist distributor GIDC Odhav Vatva",
                f"MS ERW pipe stockist Ahmedabad {class_term} ready stock",
            ],
            "india_wide": [
                f"India ERW steel pipe manufacturer {dn_term} {class_term} IS 1239 BIS certified",
                f"Primary steel pipe mills India supply to Ahmedabad bulk quantity",
            ],
            "global": [
                f"International ERW carbon steel pipe manufacturer export ASTM A53 BS 1387",
                f"Global tubular steel supplier export to Mundra Port Gujarat India {dn_term}",
            ],
        }

    def retrieve_candidates(
        self,
        spec: NormalizedSpecification,
        tier: Optional[VendorTier] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve matching candidate vendors filtered by tier and preliminary capability."""
        results: List[Dict[str, Any]] = []
        target_dn = spec.parsed_dn_mm

        for vendor in self._vendors:
            if tier and vendor["tier"] != tier.value:
                continue

            if target_dn is not None:
                dn_range = vendor.get("supported_dn_range", [15, 150])
                if not (dn_range[0] <= target_dn <= dn_range[1]):
                    continue

            results.append(vendor)

        return results
