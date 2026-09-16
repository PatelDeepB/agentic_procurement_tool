# Changelog

All notable changes to the Agentic Procurement Tool will be documented in this file.

## [2.2.2] - 2026-09-16

### Enhanced & Aligned
- **Strict Output Specification Alignment (`app/services/export_service.py`, `app/domain/models.py`, `app/agents/evaluator.py`, `app/agents/scorer.py`)**:
  - Streamlined Markdown report to focus exclusively on the 10 core output requirements, eliminating internal debug logs and query lists.
  - Formatted each vendor card with 1:1 matching section headers: Vendor Name, Location, Country & Type, Product/Specification Match, Evidence Supporting Match (with [SOURCED], [ASSUMPTION], and [NEEDS_CONFIRMATION_RFQ]), Quantity/Capacity/Stock Relevance, Standard/Grade/Class/Certification Evidence, Delivery/Service-Area Evidence, Contact Details & Website, Source Links, Confidence & Verification Status, and Unresolved Issues & Recommended Next Step.
  - Aligned CSV output columns with the exact 10 core fields.
  - Added dedicated `stock_or_capacity_evidence` and `delivery_evidence` fields to `VendorEvidence` domain model.

## [2.2.1] - 2026-09-16

### Enhanced
- **Comprehensive Vendor Export Formatting (`app/services/export_service.py`)**:
  - Explicitly surfaced verified physical addresses, certifications, and unresolved issues in Markdown report vendor cards.
  - Added `address`, `certifications`, and `unresolved_issues` columns to standard CSV export, ensuring 100% compliance with CPO procurement reporting specifications.

## [2.2.0] - 2026-09-16

### Hardened & Refactored
- **Dedicated Executive Synthesizer Agent (`app/agents/synthesizer.py`, `app/agents/orchestrator.py`)**:
  - Replaced ad-hoc orchestrator helper with full-fledged `ExecutiveSynthesizerAgent` implementing CPO strategic sourcing frameworks.
  - Formulated 4-part executive reasoning structure: Executive Feasibility & Technical Viability, Strategic Dual-Sourcing Recommendation, Critical Commercial & Logistics Risk Matrix, and Actionable Buyer RFQ Execution Plan.
  - Injected rich multi-tier candidate context (top vendor names, intra-tier and global ranks, confidence scores, vendor types, locations, and batch tonnage metrics) into LLM prompts.
- **Intelligent Deterministic Fallback (`app/agents/synthesizer.py`, `app/llm/mock_client.py`)**:
  - Implemented context-aware offline CPO synthesis dynamically tailored to specific engineering requisitions (M-01 custom wall & mill rolling MOQs, M-02 40 mm NB vs OD clarification, and M-03 batch tonnage calculations).
  - Cites real top candidates with scores (e.g. Western Steel 89.0%, Jindal Pipes 99.0%, Baosteel 80.0%) and generates numbered purchasing execution plans.
- **Executive Synthesizer Test Suite (`tests/test_synthesizer.py`)**:
  - Added 6 comprehensive AAA unit tests covering active LLM execution, graceful error fallback, custom wall thickness advice, dimensional ambiguity resolution, tonnage risk metrics, and top vendor citation.
  - Test suite expanded to 69 passing tests in 0.53s with 100% compliance across all rules.

## [2.1.0] - 2026-09-16

### Hardened & Refactored
- **Strict Zero-Address Traceability Baseline (`app/agents/scorer.py`)**:
  - Eliminated legacy 1.0 base score for vendors with missing physical addresses. Suppliers without a physical address now receive exactly 0.0 address points.
  - Added dual lookup for `source_url` and `website` in digital footprint scoring.
- **Resilient Input & None-Safety Across Agents (`app/agents/scorer.py`, `app/agents/evaluator.py`)**:
  - Hardened `_build_evaluated_vendor` and `_deduplicate_candidates` in `ScorerAgent` to accept raw vendor dictionaries directly without requiring the `raw_vendor` wrapper.
  - Extracted `_synthesize_evidence` helper in `ScorerAgent`, keeping function length under 30 lines.
  - Protected `_score_certifications`, `_score_geography`, and `EvaluatorAgent` against explicit `None` values in JSON payloads for certifications, supported standards, supported classes, and delivery evidence.
- **Idiomatic Domain Property (`app/domain/models.py`, `app/services/export_service.py`)**:
  - Added `all_vendors` property to `ProcurementResult` for clean tier aggregation across exporters.
- **Scorer Resilience Test Suite (`tests/test_scorer_resilience.py`)**:
  - Added 4 dedicated unit tests verifying zero-address traceability, raw vendor dictionary ingestion, None-value resilience, and website field recognition.
  - Expanded test suite to 63 passing tests in 0.51s with 100% compliance across all rules.

## [2.0.0] - 2026-09-16

### Hardened & Refactored
- **Dual Rank Architecture (`app/domain/models.py`, `app/agents/scorer.py`, `app/services/export_service.py`, `app/cli.py`)**:
  - Implemented dual ranking across `EvaluatedVendor`: `rank` for sequential intra-tier ranking (1..N within Ahmedabad, India, and Global scopes) and `global_rank` for cross-tier standing (1..10).
  - Resolved the ranking display discrepancy where Tier 1 previously started at "Rank 3" and Tier 3 at "Rank 7".
  - Updated Markdown reports, CSV exports, and CLI summaries to display both intra-tier rank and overall cross-tier position.
- **Traceability Scoring Logic Correction (`app/agents/scorer.py`)**:
  - Corrected communication channel scoring math: suppliers with zero contact channels receive 0.0 communication points, partial contact (email or phone) receives 0.75 points, and verified dual contact receives 1.5 points.
- **Safe Enum Parsing & Case-Insensitive Matching (`app/agents/scorer.py`)**:
  - Added `_parse_vendor_tier` and `_parse_vendor_type` static helpers with case-insensitive fallback, preventing `ValueError` crashes on lowercase inputs (e.g. "ahmedabad", "stockist_trader").
  - Fixed geography and capacity scoring to match case-insensitively, preventing local suppliers from being erroneously penalized with global distance scores.
  - Added explicit scoring support for `VendorType.EPC_SUPPLIER` (12.0 points).
- **Active Specification Capacity Integration (`app/agents/scorer.py`)**:
  - Connected `spec.total_estimated_metric_tons` to capacity feasibility evaluation, adjusting stockist scores when batch tonnage exceeds routine warehouse buffer capacity (> 50 MT).
- **Deterministic Multi-Key Sorting (`app/agents/scorer.py`)**:
  - Implemented composite tuple sorting by confidence score descending, technical fit descending, certifications descending, and vendor name ascending, ensuring 100% deterministic ranking for suppliers tied at 99.0%.
- **Dedicated Scorer Test Suite (`tests/test_scorer.py`)**:
  - Added 8 dedicated AAA unit tests covering dual ranking, traceability scoring math, case-insensitive tier parsing, deterministic tie-breaking, and batch order capacity adjustments.
  - Test suite expanded to 59 passing tests in 0.59s with 100% compliance across all rules.

## [1.9.0] - 2026-09-16

### Hardened & Refactored
- **Search Agent Dynamic Ambiguity Resolution (`app/agents/searcher.py`)**:
  - Eliminated hardcoded "40 mm" in ambiguous NB vs OD queries. Query generator now dynamically formats queries using the actual ambiguous size from the normalized specification (e.g. 25 mm, 40 mm, 50 mm).
- **Flexible Tier Representation (`app/agents/searcher.py`)**:
  - Enabled candidate retrieval to gracefully accept both `VendorTier` enum instances and string representations (e.g. "AHMEDABAD", "INDIA_OUTSIDE_AHMEDABAD", "GLOBAL"), preventing runtime `AttributeError` when queried from tools or API layers.
- **Outside Diameter (OD) to DN Candidate Deductive Auditing (`app/agents/searcher.py`)**:
  - Added fallback deductive lookup from `spec.parsed_od_mm` to standard DN via `find_is1239_dn_by_od` during candidate retrieval. Ensures suppliers with size constraints are properly audited and disqualified even when requisitions state dimensions in OD without explicit DN prefixes.
- **Comprehensive Global Heavy-Wall Query Synthesis (`app/agents/searcher.py`)**:
  - Injected specialized Schedule 80 and heavy-wall international queries into the Global search strategy when `NON_STANDARD_WALL_THICKNESS` ambiguity is present, matching primary exporter capabilities.
  - Refactored `_synthesize_queries_deterministic` into modular static helpers (`_build_ahmedabad_queries`, `_build_india_queries`, `_build_global_queries`) to strictly enforce the 40-line function length limit.
- **Base LLM Client Standard JSON Extraction & Service State Tracking (`app/llm/base.py`, `app/llm/mock_client.py`)**:
  - Added `extract_json` static method and `is_service_available = True` default attribute to `BaseLLMClient`, harmonizing JSON extraction across all LLM subclasses.
  - Added specialized multi-tier search query simulation (`_mock_search_queries_response`) to `MockLLMClient`.
- **Search Agent Test Suite Expansion (`tests/test_searcher.py`)**:
  - Added unit tests for dynamic ambiguity query formatting across varied sizes, global heavy-wall query synthesis, OD-to-DN resolution candidate exclusion, string and enum tier filtering, active LLM query synthesis, and resilient fallback on LLM failure.
  - Test suite expanded to 51 passing tests in 0.73s with 100% compliance across all rules.

## [1.8.0] - 2026-09-16

### Added & Hardened
- **Searching Agent Architectural Overhaul (`app/agents/searcher.py`)**:
  - Connected `SearchAgent` with active LLM client for cognitive query synthesis with offline deterministic fallback.
  - Enriched search queries with complete dimensional depth: nominal diameter, outside diameter (OD), wall thickness, steel grade (e.g. Fe 410), and custom rolling schedules.
  - Added ambiguity-aware query generation: dynamically crafts dual queries for M-02 (40 mm NB vs 40 mm OD) and custom heavy-gauge mill inquiries for M-01 (5.5 mm wall).
  - Implemented `retrieve_candidates_with_audit` with structured disqualification logging (`exclusion_log`) replacing silent drops.
- **Pipeline and Reporting Integration (`app/domain/models.py`, `app/agents/orchestrator.py`, `app/services/export_service.py`, `app/cli.py`)**:
  - Added `search_queries` field to `ProcurementResult` and populated `exclusion_log`.
  - Rendered synthesized search strategy in Markdown reports (`## 3. Synthesized Multi-Tier Search Strategy`), JSON exports, and terminal output.
  - Rendered candidate supplier disqualification audit in Markdown and CLI outputs.
- **Agentic ReAct Search Tool (`app/tools/procurement_tools.py`)**:
  - Implemented `tool_search_vendor_registry` allowing autonomous agents to query verified vendor databases dynamically.
- **Dedicated Searcher Test Suite (`tests/test_searcher.py`)**:
  - Added 7 dedicated unit and integration tests covering query synthesis, ambiguity handling, candidate retrieval, exclusion logging, and tool execution.
  - Test suite expanded to 49 passing tests in 0.78s with 0 rule violations and 0 em-dashes.

## [1.7.0] - 2026-09-16

### Refactored & Hardened
- **Rule 2 Naming Conventions Enforcement (`app/`, `tests/`)**:
  - Eliminated all single-letter variables across production code and test suites, replacing them with descriptive names (`vendor`, `ambiguity`, `material_item`, `registry_file`, `env_file`, `standard_name`, `fact`, `assumption`, `rfq_item`).
- **Standards Catalog Expansion (`app/core/standards.py`, `app/tools/procurement_tools.py`)**:
  - Added full technical specifications for DN 125 (139.7 mm OD, 4.5/4.85/5.4 mm walls) and DN 150 (165.1 mm OD, 4.5/4.85/5.4 mm walls) into `IS1239_PART1_TABLE`.
  - Harmonized DN 50 Class A wall thickness from 3.25 mm to standard 2.9 mm per IS 1239 Part 1 Table 1.
  - Updated tool lookup error message to reflect full range from DN 15 to DN 150.
- **Fail-Fast Gemini Client Session Resilience (`app/llm/client.py`)**:
  - Added `is_service_available` session circuit breaker to `GeminiLLMClient` that detects HTTP 4xx authentication/endpoint errors and disables subsequent remote calls, eliminating repetitive retry timeouts.
- **Test Suite Modularization (Rules 3 & 5 Compliance)**:
  - Extracted advanced and decoupled tests into `tests/test_normalizer_advanced.py`, bringing `test_normalizer.py` from 303 lines down to 206 lines.
  - Extracted `_create_mock_vendor_dict` fixture in `tests/test_evaluator_and_scorer.py`, shortening all test functions to under 35 lines.
  - Added unit tests for DN 125 and DN 150 spec retrieval and reverse tolerance matching in `tests/test_standards.py`. Total test count reached 42 passing tests.

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
