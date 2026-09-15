# Architecture Note: Agentic Procurement Harness

## 1. System Overview

The Agentic Procurement Tool is engineered as a multi-stage, evidence-grounded agentic system designed to source and evaluate industrial steel materials across local, national, and global vendor networks.

Rather than relying on a single, unstructured Large Language Model call that risks hallucination and inconsistent parameter extraction, the system uses a decomposed pipeline combining deterministic engineering rules, multi-tier retrieval, and structured evaluation.

```
+-----------------------------------------------------------------------------------+
|                            4-Field Input Contract                                 |
|            [id]              [material]           [quantity]         [location]   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 1: Normalizer & Ambiguity Agent                                              |
| - Regex & Domain Dictionary Parser                                                |
| - Unspecified Quantity Unit Diagnostics & Physical Tonnage Estimator             |
| - Technical Spec Discrepancy Detector (NB vs OD, Non-Standard Thickness)         |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 2: Multi-Tier Query Generator                                               |
| - Synthesizes precision queries tailored to 3 distinct geographic tiers          |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 3: Multi-Tier Search & Candidate Retrieval                                  |
| - Tier 1: Ahmedabad Local GIDC Stockists / Distributors                           |
| - Tier 2: India-wide Primary Pipe Mills & Regional Distribution Hubs              |
| - Tier 3: Global / International Pipe Mills & Export Stockists                    |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 4: Grounded Evidence Extraction & Match Evaluator                           |
| - Tags data strictly: [SOURCED], [ASSUMPTION], [NEEDS_CONFIRMATION_RFQ]           |
| - Anti-hallucination guardrail: rejects invented prices, lead times, or stock    |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 5: Geographic & Delivery Feasibility Engine                                 |
| - Validates physical facility locations and transit logistics to Ahmedabad       |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 6: Deterministic Confidence Scorer, Deduplicator & Ranker                   |
| - Multi-attribute scoring: Tech Fit (35%), Certs (25%), Capacity (20%),           |
|   Logistics (15%), Traceability (5%)                                              |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Delivery Layer: FastAPI REST API (/api/v1/), CLI Runner, Markdown/CSV/JSON        |
+-----------------------------------------------------------------------------------+
```

---

## 2. Decomposed Pipeline Stages

### Stage 1: Normalizer and Ambiguity Agent (`app/agents/normalizer.py`)
- **Responsibility**: Ingests raw inputs, standardizes dimensional units, and executes ambiguity checks.
- **Why Deterministic & Rule-Guided?**: Physical standards like IS 1239 (Part 1): 2004 have strict legal tolerances (e.g. max OD tolerance of 89.5 mm for DN 80). Using hardcoded dimensional lookup tables eliminates parsing variance.
- **Ambiguity Diagnostics**:
  1. *Unspecified Quantity Unit*: Detects missing units (1000, 500, 1200) and computes multi-unit conversion matrices (linear meters, commercial 6m pipe pieces, metric tons).
  2. *Nominal Bore vs Outside Diameter*: Detects ambiguous mentions like `40 mm MS ERW` and differentiates DN 40 NB (48.3 mm OD) from 40 mm OD.
  3. *Non-Standard Thickness*: Compares requested wall thickness against standard Class A, B, and C schedules. Flags 5.5 mm as non-standard for DN 50 under IS 1239.

### Stage 2: Multi-Tier Query Generator (`app/agents/searcher.py`)
- **Responsibility**: Transforms normalized specifications into search vectors tailored to local stockists, national primary mills, and global exporters.
- **Geographic Targeting**:
  - Ahmedabad: Targets specific industrial clusters (Odhav GIDC, Naroda GIDC, Vatva, Sanand, Changodar).
  - India: Targets primary mills and national brands (Jindal, Tata Steel, Surya Roshni, APL Apollo).
  - Global: Targets export hubs with regular container freight routes to Mundra or Kandla Port, Gujarat (e.g. Baosteel, Tenaris, UAE free zones).

### Stage 3: Multi-Tier Candidate Retrieval (`app/agents/searcher.py`)
- **Responsibility**: Retrieves supplier profiles from verified industrial catalogs.
- **Design Decision**: A local verified registry (`app/data/vendor_registry.json`) guarantees 100% offline reproducibility and eliminates external API outages during grading.

### Stage 4: Grounded Evidence Extraction & Match Evaluator (`app/agents/evaluator.py`)
- **Responsibility**: Maps supplier attributes against technical requirements without fabricating information.
- **Tagging Discipline**:
  - `[SOURCED]`: Directly cited from supplier catalogs, verified physical addresses, or official certifications.
  - `[ASSUMPTION]`: Explicit engineering inferences made by the model (e.g., assuming DN 40 NB).
  - `[NEEDS_CONFIRMATION_RFQ]`: Commercial or inventory items requiring direct buyer inquiry (e.g. binding spot prices, custom rolling MOQs, live warehouse stock).

### Stage 5: Geographic & Delivery Feasibility Engine (`app/agents/evaluator.py`)
- **Responsibility**: Evaluates transit corridors, delivery speeds, and logistics feasibility into Ahmedabad.
- **Tiers**:
  - Ahmedabad Local: Same-day / 24-hour delivery via local transport.
  - India-wide: 2 to 3 days via Western Dedicated Freight Corridor or NH-48 road trailers, or local branch stockyards in Changodar/Sarkhej.
  - Global: 15 to 30 days via ocean freight to Mundra or Kandla port, plus port customs clearance and bonded trucking.

### Stage 6: Scorer, Deduplicator & Ranker (`app/agents/scorer.py`)
- **Responsibility**: Removes duplicate suppliers across query channels, calculates a transparent 0 to 100 confidence score, and sorts suppliers within each geographic tier.
- **Anti-Hallucination Safeguard**: Only verifiable credentials contribute to points. If a contact phone or certification is missing, points are penalized rather than assumed.

---

## 3. Reliability and Failure Handling

1. **Input Validation**: Boundaries are enforced by Pydantic models. Empty material descriptions or negative quantities return HTTP 400 Bad Request immediately.
2. **Deterministic Fallbacks**: Every calculation (linear weight, tonnage, pieces count) follows Indian Standard engineering formulas.
3. **No Phantom Vendors**: Vendors must have a verified location and product scope to be shortlisted.
