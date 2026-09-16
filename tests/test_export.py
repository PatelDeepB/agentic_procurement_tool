"""Unit tests for export service."""

import json

from app.agents.orchestrator import ProcurementOrchestrator
from app.domain.models import MaterialInput
from app.services.export_service import ExportService


def test_should_generate_comprehensive_markdown_report():
    """Verify Markdown report includes ambiguities, three tiers, and audit trail."""
    # Arrange
    orchestrator = ProcurementOrchestrator()
    exporter = ExportService()
    req = MaterialInput(
        id="M-01",
        material="ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239",
        quantity=1000.0,
        location="Ahmedabad, Gujarat, India",
    )
    result = orchestrator.run_procurement_workflow(req)

    # Act
    md_content = exporter.to_markdown(result)

    # Assert
    assert "# Procurement Evaluation Report: M-01" in md_content
    assert "## 2. Technical Ambiguities and Stated Assumptions" in md_content
    assert "### Tier 1: Ahmedabad Local Vendors" in md_content
    assert "### Tier 2: India-Based Vendors (Outside Ahmedabad)" in md_content
    assert "### Tier 3: International / Global Vendors" in md_content
    assert "[SOURCED]" in md_content
    assert "[ASSUMPTION]" in md_content
    assert "[NEEDS_CONFIRMATION_RFQ]" in md_content


def test_should_generate_valid_csv_export():
    """Verify CSV export contains column headers and vendor rows."""
    # Arrange
    orchestrator = ProcurementOrchestrator()
    exporter = ExportService()
    req = MaterialInput(
        id="M-02",
        material="40 mm MS ERW, Class B pipe",
        quantity=500.0,
        location="Ahmedabad, Gujarat, India",
    )
    result = orchestrator.run_procurement_workflow(req)

    # Act
    csv_content = exporter.to_csv(result)

    # Assert
    lines = csv_content.strip().split("\n")
    assert len(lines) > 1
    assert "material_id,tier,rank,vendor_name" in lines[0]


def test_should_generate_valid_json_export():
    """Verify JSON export is parseable and preserves result structure."""
    # Arrange
    orchestrator = ProcurementOrchestrator()
    exporter = ExportService()
    req = MaterialInput(
        id="M-03",
        material="ERW pipe, DN 80, 89.5 x 4.8 mm, IS 1239",
        quantity=1200.0,
        location="Ahmedabad, Gujarat, India",
    )
    result = orchestrator.run_procurement_workflow(req)

    # Act
    json_str = exporter.to_json(result)
    parsed = json.loads(json_str)

    # Assert
    assert parsed["material_id"] == "M-03"
    assert "specification" in parsed
    assert len(parsed["ahmedabad_vendors"]) > 0


def test_should_display_explicit_unit_in_markdown_export_when_specified():
    """Verify Markdown report displays explicit unit rather than claiming unspecified."""
    # Arrange
    orchestrator = ProcurementOrchestrator()
    exporter = ExportService()
    req = MaterialInput(
        id="M-EXPLICIT",
        material="DN 50 MS ERW pipe 1000 mtrs",
        quantity=1000.0,
        location="Ahmedabad, Gujarat, India",
    )
    result = orchestrator.run_procurement_workflow(req)

    # Act
    md_content = exporter.to_markdown(result)

    # Assert
    assert "- **Specified Quantity**: 1000.0 meters" in md_content
    assert "*(unit unspecified in input)*" not in md_content

