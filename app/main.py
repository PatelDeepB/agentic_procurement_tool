"""FastAPI application entry point for the Agentic Procurement Tool backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(
    title="Agentic Procurement Tool API",
    description=(
        "Production-grade, evidence-grounded agentic procurement tool for industrial materials. "
        "Evaluates vendor capabilities across Ahmedabad, India-wide, and Global tiers with "
        "rigorous ambiguity detection and zero-hallucination guardrails."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for flexible integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)

# Mount static files and serve Web UI
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

static_directory = Path(__file__).parent / "static"
static_directory.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_directory)), name="static")


@app.get("/", include_in_schema=False)
def serve_index_page() -> FileResponse:
    """Serve the single-page web UI application."""
    index_file_path = static_directory / "index.html"
    return FileResponse(index_file_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
