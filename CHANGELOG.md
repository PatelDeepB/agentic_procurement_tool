# Changelog

All notable changes to the Agentic Procurement Tool will be documented in this file.

## [1.6.0] - 2026-09-16

### Refactored & Hardened
- **System-Wide Clean Architecture and Rule Compliance (Rules 3 & 5)**:
  - Extracted deterministic fallback parsing into `app/agents/normalizer_fallback.py` and engineering prompts into `app/agents/normalizer_prompts.py`, bringing `normalizer.py` from 506 lines down to 266 lines.
  - Extracted `MockLLMClient` into `app/llm/mock_client.py` and base interfaces into `app/llm/base.py`, bringing `client.py` from 365 lines down to 119 lines.
  - Refactored all functions across `app/` so 100% of functions are under 40 lines and 100% of files are under 300 lines.
- **Audited LLM Trace Integration (`app/domain/models.py`, `app/agents/evaluator.py`, `app/services/export_service.py`)**:
  - Added `evaluation_notes` field to `VendorEvidence`, capturing the LLM technical audit trace instead of discarding the return value.
  - Rendered technical audit notes in generated Markdown and API export packages.
- **Dynamic Unit Formatting in Markdown Export (`app/services/export_service.py`)**:
  - Fixed hardcoded unit omission label in Markdown export: explicitly specified units (e.g. 1000 meters) now render cleanly without falsely stating unit was unspecified.
- **Magic Number Elimination in Searcher (`app/agents/searcher.py`)**:
  - Removed `target_dn = spec.parsed_dn_mm or 40` magic fallback. Candidate retrieval now dynamically matches all registered suppliers when DN is unspecified.
- **Strict Typing in Scorer (`app/agents/scorer.py`)**:
  - Converted confidence score return type annotation to `Tuple[float, Dict[str, float]]` and modularized scoring criteria into clean sub-methods.
- **Expanded Regression Test Suite (`tests/`)**:
  - Added regression tests for candidate retrieval without DN, evaluation notes attachment, and explicit unit export. Total test count expanded to 40 passing tests in 0.78s.

## [1.5.0] - 2026-09-16

### Fixed
- **Decoupled Outside Diameter and Wall Thickness Resolution (`app/agents/normalizer.py`)**:
  - Resolved outside diameter and wall thickness independently in `_determine_effective_dimensions`. Previously, providing outside diameter skipped wall thickness resolution, causing wall thickness to remain 0.0 mm and resulting in zero calculated tonnage.
- **Pipe Class Omission Default and Ambiguity Recording (`app/agents/normalizer.py`, `app/llm/client.py`)**:
  - When both pipe class and wall thickness are omitted from a requisition, defaulted effective wall thickness to standard IS 1239 Class B (Medium wall) per Indian commercial procurement conventions.
  - Automatically recorded an ambiguity item stating the Class B assumption and generating a buyer clarification prompt.
- **Reverse Outside Diameter Lookup (`app/agents/normalizer.py`, `app/llm/client.py`)**:
  - Integrated `find_is1239_dn_by_od` across deterministic fallback parsing and mock LLM parsing. Inputs specifying outside diameter directly (such as 60.3 mm or 48.3 mm) without a DN prefix now correctly resolve to nominal bores DN 50 or DN 40.
- **Evaluator Dynamic Wall Thickness Guardrail (`app/agents/evaluator.py`)**:
  - Replaced the hardcoded `> 4.5 mm` wall check with dynamic inspection of `AmbiguityType.NON_STANDARD_WALL_THICKNESS`. Standard thick-wall schedules such as DN 100 Class C (5.4 mm) are no longer falsely flagged as custom heavy rolling or ASTM A53 Schedule 80.
- **Comprehensive Regression Tests (`tests/test_normalizer.py`, `tests/test_evaluator_and_scorer.py`)**:
  - Added 4 new regression tests covering decoupled OD and wall resolution, default Class B ambiguity reporting, reverse OD lookup, and evaluator heavy-wall guardrail. All 37 tests pass.

## [1.4.0] - 2026-09-16

### Added
- **Hardened Ambiguity Detection & Generalized Normalizer (`app/agents/normalizer.py`, `app/domain/models.py`, `app/llm/client.py`)**:
  - Replaced hardcoded fallback checks with generalized regex and dynamic IS 1239 table lookups covering all nominal bores DN 15 to DN 150.
  - Injected domain engineering reference tables (IS 1239 schedules) directly into the LLM system prompt to prevent hallucination.
  - Implemented safe enum parsing helpers (`_safe_parse_ambiguity_type` and `_safe_parse_severity`) with synonym mapping to prevent runtime crashes.
  - Added bidirectional wall thickness verification: evaluates against deterministic ground truth, adding missed deviations and dismissing false-positive hallucinations.
  - Expanded unit abbreviation detection (`m`, `mtr`, `mtrs`, `pcs`, `mt`, `ft`, `bundle`) and steel tensile grade extraction (`parsed_steel_grade`).
  - Added 5 new edge-case tests in `tests/test_normalizer.py`, bringing total test count to 33 passing tests in 0.67s.

## [1.3.0] - 2026-09-16

### Added
- **Unified Single-Call Normalizer & Ambiguity Engine (`app/agents/normalizer.py`, `app/domain/models.py`)**:
  - Combined technical parameter extraction and ambiguity detection into a single structured LLM prompt (`UnifiedNormalizerLLMResponse`).
  - Reduced LLM latency and token costs by 50% by avoiding a separate second LLM call for ambiguity analysis.
  - Retained deterministic ReAct calculation tools (`lookup_is1239_spec`, `calculate_steel_linear_weight_and_tonnage`) to compute exact batch tonnage and commercial pipe piece counts.
  - Added dedicated test suite coverage (`tests/conftest.py` with mock LLM client) running 28 tests in 0.34s.

## [1.2.0] - 2026-09-15

### Added
- **Google Gemini Free Tier Engine (`app/llm/client.py`)**:
  - Configured `gemini-2.0-flash` (latest model on Google AI Studio Free Tier) as the primary LLM engine.
  - Added automatic fallback to `gemini-1.5-flash` for high stability and rate-limit resilience.
  - Implemented automatic local `.env` file discovery and variable loader.
  - Added `.env.example` template with instructions on generating a free API key at [Google AI Studio](https://aistudio.google.com/app/apikey).
  - Maintained offline deterministic mock fallback so testing never fails when no key is present.

## [1.1.0] - 2026-09-15

### Added
- **AI/ML Multi-Agent Harness (`app/llm/client.py`, `app/agents/`)**:
  - Implemented `BaseLLMClient` with `GeminiLLMClient`, `OpenAILLMClient`, and offline `MockLLMClient` with auto-fallback.
  - Upgraded `NormalizerAgent` to combine LLM prompt reasoning with ReAct tool calling.
  - Upgraded `EvaluatorAgent` with LLM-powered evidence extraction and anti-hallucination guardrail.
  - Added `_generate_executive_synthesis` in `ProcurementOrchestrator` to generate Chief Procurement Officer level executive summaries.
  - Added ReAct tools module (`app/tools/procurement_tools.py`) for standards lookup, tolerance checking, and mass calculations.
  - Added comprehensive test suite for LLM agents and tools (`tests/test_llm_agents.py`), bringing test count to 27 passing tests.
  - Added post-submission technical interview talking points in `ARCHITECTURE.md`.
  - Added LLM executive reasoning section to exported Markdown reports.

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
  - Automated unit and integration tests across standards, normalizer, evaluator, scorer, api, and exports (`pytest -v`).

- **Documentation & Demonstration Deliverables**:
  - Pre-generated demonstration outputs for M-01, M-02, and M-03 in `output/` (md, csv, json).
  - Created `README.md`, `ARCHITECTURE.md`, `METHODOLOGY.md`, and `LIMITATIONS.md`.
