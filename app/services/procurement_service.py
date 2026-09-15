"""Procurement service managing business workflows, demonstration datasets, and result caching."""

from typing import Dict, List, Optional

from app.agents.orchestrator import ProcurementOrchestrator
from app.domain.models import MaterialInput, ProcurementResult
from app.services.export_service import ExportService


class ProcurementService:
    """Service providing high-level procurement orchestration and result storage."""

    DEFAULT_DEMO_INPUTS: List[MaterialInput] = [
        MaterialInput(
            id="M-01",
            material="ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239",
            quantity=1000.0,
            location="Ahmedabad, Gujarat, India",
        ),
        MaterialInput(
            id="M-02",
            material="40 mm MS ERW, Class B pipe",
            quantity=500.0,
            location="Ahmedabad, Gujarat, India",
        ),
        MaterialInput(
            id="M-03",
            material="ERW pipe, DN 80, 89.5 x 4.8 mm, IS 1239",
            quantity=1200.0,
            location="Ahmedabad, Gujarat, India",
        ),
    ]

    def __init__(
        self,
        orchestrator: Optional[ProcurementOrchestrator] = None,
        exporter: Optional[ExportService] = None,
    ):
        """Initialize procurement service with orchestrator and export utility."""
        self.orchestrator = orchestrator or ProcurementOrchestrator()
        self.exporter = exporter or ExportService()
        self._cache: Dict[str, ProcurementResult] = {}

    def get_default_demonstrations(self) -> List[MaterialInput]:
        """Return the three assessment demonstration input scenarios."""
        return self.DEFAULT_DEMO_INPUTS

    def execute_procurement(self, material_input: MaterialInput) -> ProcurementResult:
        """Run multi-tier agentic procurement evaluation and cache the result."""
        result = self.orchestrator.run_procurement_workflow(material_input)
        self._cache[result.run_id] = result
        self._cache[material_input.id] = result
        return result

    def get_result_by_id(self, run_or_material_id: str) -> Optional[ProcurementResult]:
        """Retrieve previously executed procurement result from cache."""
        return self._cache.get(run_or_material_id)

    def export_result(self, run_or_material_id: str, format_type: str) -> Optional[str]:
        """Export cached procurement result in the specified format (markdown, csv, json)."""
        result = self.get_result_by_id(run_or_material_id)
        if not result:
            return None

        fmt = format_type.lower()
        if fmt in ["md", "markdown"]:
            return self.exporter.to_markdown(result)
        if fmt == "csv":
            return self.exporter.to_csv(result)
        if fmt == "json":
            return self.exporter.to_json(result)
        return None
