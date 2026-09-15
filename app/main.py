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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
