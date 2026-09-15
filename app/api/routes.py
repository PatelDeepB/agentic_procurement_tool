"""RESTful API routes for the Agentic Procurement Tool."""

from typing import List
from fastapi import APIRouter, HTTPException, Response, status

from app.domain.models import MaterialInput, ProcurementResult
from app.services.procurement_service import ProcurementService

router = APIRouter()
procurement_service = ProcurementService()


@router.get("/health", status_code=status.HTTP_200_OK, tags=["System"])
def health_check() -> dict:
    """Lightweight unauthenticated health check reflecting dependency status."""
    registry_count = len(procurement_service.orchestrator.searcher._vendors)
    is_ready = registry_count > 0
    return {
        "status": "healthy" if is_ready else "degraded",
        "service": "agentic-procurement-backend",
        "vendor_registry_entries": registry_count,
    }


@router.get(
    "/api/v1/materials/defaults",
    response_model=List[MaterialInput],
    status_code=status.HTTP_200_OK,
    tags=["Procurement"],
)
def get_default_materials() -> List[MaterialInput]:
    """Retrieve the three default candidate assessment demonstration materials."""
    return procurement_service.get_default_demonstrations()


@router.post(
    "/api/v1/procure/run",
    response_model=ProcurementResult,
    status_code=status.HTTP_200_OK,
    tags=["Procurement"],
)
def run_procurement_evaluation(material_input: MaterialInput) -> ProcurementResult:
    """Execute multi-tier agentic procurement evaluation for supplied material."""
    if not material_input.material.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Material description cannot be empty.",
        )
    if material_input.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be greater than zero.",
        )

    return procurement_service.execute_procurement(material_input)


@router.get(
    "/api/v1/procure/{run_or_material_id}/export/{format_type}",
    tags=["Procurement"],
)
def export_procurement_result(run_or_material_id: str, format_type: str) -> Response:
    """Download procurement evaluation report in markdown, csv, or json format."""
    fmt = format_type.lower()
    if fmt not in ["md", "markdown", "csv", "json"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported export format '{format_type}'. Supported: md, csv, json.",
        )

    content = procurement_service.export_result(run_or_material_id, fmt)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evaluation result found for identifier '{run_or_material_id}'. Run evaluation first.",
        )

    media_types = {
        "md": "text/markdown; charset=utf-8",
        "markdown": "text/markdown; charset=utf-8",
        "csv": "text/csv; charset=utf-8",
        "json": "application/json; charset=utf-8",
    }
    media_type = media_types[fmt]

    headers = {
        "Content-Disposition": f"attachment; filename=procurement_{run_or_material_id}.{fmt.replace('markdown', 'md')}"
    }

    return Response(content=content, media_type=media_type, headers=headers)
