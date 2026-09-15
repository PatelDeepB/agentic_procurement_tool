# Changelog

All notable changes to the Agentic Procurement Tool will be documented in this file.

## [1.0.0] - 2026-09-15

### Added
- **Core Standards Engine (`app/core/standards.py`)**:
  - Implemented IS 1239 (Part 1): 2004 dimensional data table for nominal diameters DN 15 to DN 150.
  - Implemented standard linear weight formula $W = (OD - t) \times t \times 0.02466$ kg/m.
  - Added batch metric tonnage and 6-meter commercial piece count calculators.
  - Added international standards cross-reference mapping (ASTM A53, BS 1387, EN 10255, IS 3589).
  - Added wall thickness compliance evaluator.

- **Domain Models (`app/domain/models.py`)**:
  - Defined strict 4-field input schema (`MaterialInput`: id, material, quantity, location).
  - Defined structured ambiguity models (`AmbiguityItem`, `AmbiguityType`, `AmbiguitySeverity`).
  - Defined normalized specification and unit conversion schemas (`NormalizedSpecification`).
  - Defined vendor, evidence, and scoring schemas (`VendorCandidate`, `VendorEvidence`, `EvaluatedVendor`, `ProcurementResult`).

- **Normalizer & Ambiguity Agent (`app/agents/normalizer.py`)**:
  - Extracted technical dimensions (DN, OD, wall thickness, standard, class).
  - Detected missing quantity unit ambiguity on raw numerical inputs and provided MT/pieces conversions.
  - Detected 40 mm Nominal Bore vs Outside Diameter technical ambiguity on M-02.
  - Detected non-standard 5.5 mm wall thickness on M-01 against IS 1239 Heavy schedules.

- **Multi-Tier Search Agent (`app/agents/searcher.py`)**:
  - Generated targeted queries for Ahmedabad local GIDC estates, India-wide mills, and global export hubs.
  - Implemented candidate retrieval across geographic tiers.

- **Verified Vendor Registry (`app/data/vendor_registry.json`)**:
  - Curated verified suppliers across Ahmedabad, India-wide, and Global tiers with genuine contact details, plant locations, and certifications.

- **Grounded Evidence Evaluator (`app/agents/evaluator.py`)**:
  - Classified vendor matches into `EXACT_MATCH`, `NEAR_MATCH`, `CATEGORY_LEVEL_LEAD`, and `UNVERIFIED_LEAD`.
  - Enforced strict tag separation: `[SOURCED]`, `[ASSUMPTION]`, and `[NEEDS_CONFIRMATION_RFQ]`.
  - Prohibited invented prices, stock numbers, or fake certifications.

- **Deterministic Confidence Scorer (`app/agents/scorer.py`)**:
  - Implemented 100-point composite scoring model (Technical Fit 35%, Certifications 25%, Capacity 20%, Logistics 15%, Traceability 5%).
  - Implemented multi-criteria deduplication to prevent duplicate leads across tiers.

- **Agentic Pipeline Orchestrator (`app/agents/orchestrator.py`)**:
  - Coordinated end-to-end multi-stage pipeline and generated step-by-step audit logs.

- **Services & RESTful API (`app/services/`, `app/api/`, `app/main.py`)**:
  - Implemented `ExportService` for Markdown, CSV, and JSON outputs.
  - Implemented `ProcurementService` for demo data and run caching.
  - Implemented versioned REST API (`/api/v1/materials/defaults`, `/api/v1/procure/run`, `/api/v1/procure/{id}/export/{format}`).
  - Implemented lightweight unauthenticated `/health` endpoint.
  - Configured CORS middleware in `app/main.py`.

- **Command-Line Interface (`app/cli.py`)**:
  - Terminal runner for single or batch material procurement and automated artifact exports.

- **Comprehensive Test Suite (`tests/`)**:
  - 22 automated unit and integration tests across standards, normalizer, evaluator, scorer, api, and exports (`pytest -v`).

- **Documentation & Demonstration Deliverables**:
  - Pre-generated demonstration outputs for M-01, M-02, and M-03 in `output/` (md, csv, json).
  - Created `README.md`, `ARCHITECTURE.md`, `METHODOLOGY.md`, and `LIMITATIONS.md`.
