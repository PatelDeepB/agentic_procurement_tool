"""Integration tests for FastAPI endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_should_return_healthy_status_on_health_endpoint():
    """Verify /health returns HTTP 200 and indicates healthy system."""
    # Act
    response = client.get("/health")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["vendor_registry_entries"] > 0


def test_should_return_default_demonstration_materials():
    """Verify /api/v1/materials/defaults returns M-01, M-02, and M-03."""
    # Act
    response = client.get("/api/v1/materials/defaults")

    # Assert
    assert response.status_code == 200
    materials = response.json()
    assert len(materials) == 3
    ids = [m["id"] for m in materials]
    assert "M-01" in ids
    assert "M-02" in ids
    assert "M-03" in ids


def test_should_run_procurement_workflow_via_api():
    """Verify POST /api/v1/procure/run successfully executes workflow."""
    # Arrange
    payload = {
        "id": "M-02",
        "material": "40 mm MS ERW, Class B pipe",
        "quantity": 500.0,
        "location": "Ahmedabad, Gujarat, India",
    }

    # Act
    response = client.post("/api/v1/procure/run", json=payload)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["material_id"] == "M-02"
    assert len(data["specification"]["ambiguities"]) > 0
    assert len(data["ahmedabad_vendors"]) > 0
    assert len(data["india_vendors"]) > 0
    assert len(data["global_vendors"]) > 0


def test_should_return_400_on_invalid_quantity():
    """Verify POST /api/v1/procure/run rejects zero or negative quantity."""
    # Arrange
    payload = {
        "id": "M-ERR",
        "material": "ERW pipe",
        "quantity": -10.0,
        "location": "Ahmedabad",
    }

    # Act
    response = client.post("/api/v1/procure/run", json=payload)

    # Assert
    assert response.status_code == 400


def test_should_export_results_in_markdown_and_csv():
    """Verify export endpoints return formatted files."""
    # Arrange: first run evaluation
    client.post(
        "/api/v1/procure/run",
        json={
            "id": "M-03",
            "material": "ERW pipe, DN 80, 89.5 x 4.8 mm, IS 1239",
            "quantity": 1200.0,
            "location": "Ahmedabad, Gujarat, India",
        },
    )

    # Act: Export Markdown
    md_res = client.get("/api/v1/procure/M-03/export/md")
    # Act: Export CSV
    csv_res = client.get("/api/v1/procure/M-03/export/csv")

    # Assert
    assert md_res.status_code == 200
    assert "# Procurement Evaluation Report: M-03" in md_res.text
    assert csv_res.status_code == 200
    assert "vendor_name,location" in csv_res.text
