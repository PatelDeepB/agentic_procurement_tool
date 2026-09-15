# Agentic Procurement Tool

An evidence-grounded agentic procurement tool engineered to find, evaluate, and shortlist vendors capable of supplying industrial materials in large quantities across three geographic tiers: **Ahmedabad Local**, **India-Wide**, and **Global**.

Built as a submission for the **Agentic Procurement Tool - Candidate Assessment**.

---

## Key Features

1. **4-Field Input Contract**: Seamlessly accepts `id`, `material`, `quantity`, and `location`.
2. **Dedicated Ambiguity Detection Engine**:
   - **Quantity Unit Ambiguity**: Detects missing units (1000, 500, 1200), computes equivalent metric tonnage and 6-meter pipe piece counts, states explicit assumptions (linear meters), and formulates buyer clarification prompts.
   - **Technical Dimension Ambiguity (NB vs OD)**: Identifies `40 mm MS ERW` as Nominal Bore (DN 40 / 1.5" NB, OD 48.3 mm, Class B wall 3.25 mm) vs non-standard 40 mm OD, exposing the discrepancy rather than silently altering requirements.
   - **Non-Standard Wall Thickness**: Compares requested thickness against IS 1239 Part 1 schedules (Class A/B/C) and flags non-standard gauges (such as 5.5 mm on DN 50) requiring custom rolling or ASTM A53 Schedule 80.
3. **Three-Tier Geographic Coverage**:
   - **Tier 1 (Ahmedabad Local)**: Local stockists, traders, and GIDC warehouses (Odhav, Naroda, Vatva, Sanand, Changodar).
   - **Tier 2 (India-Wide)**: Primary national manufacturers (Jindal Pipes, Tata Steel Tubes, Surya Roshni, APL Apollo) with regional hubs and freight corridors.
   - **Tier 3 (Global / International)**: Overseas manufacturers (Baosteel, Tenaris, UAE stockists) evaluated for export feasibility and delivery to Mundra/Kandla Port, Gujarat.
4. **Strict Zero-Hallucination Policy**:
   - All facts are explicitly tagged: `[SOURCED]`, `[ASSUMPTION]`, and `[NEEDS_CONFIRMATION_RFQ]`.
   - Never fabricates prices, inventory, lead times, or certifications.
5. **Execution Interfaces**:
   - High-performance versioned RESTful API (`/api/v1/`) with OpenAPI docs (`/docs`).
   - Command-line interface (`python -m app.cli`) for batch execution and grading.
   - Automated export to Markdown, CSV, and JSON.

---

## Quickstart & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.12.10)
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/agentic_procurement_tool.git
   cd agentic_procurement_tool
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Running the Demonstration

### 1. Running via CLI

Run all three assessment materials (M-01, M-02, M-03) and export outputs to `output/`:
```bash
python -m app.cli --material all --export all
```

Run a specific material:
```bash
python -m app.cli --material M-01 --export all
python -m app.cli --material M-02 --export all
python -m app.cli --material M-03 --export all
```

Run a custom procurement requirement:
```bash
python -m app.cli --id C-01 --desc "DN 50 ERW pipe, Class C, IS 1239" --quantity 750 --location "Ahmedabad, Gujarat, India" --export all
```

### 2. Running the FastAPI Server

Start the REST API server:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Interactive API Documentation**: Open `http://localhost:8000/docs` in your browser.
- **Health Check Endpoint**: Open `http://localhost:8000/health`.

#### API Endpoints Overview:
- `GET /health`: Lightweight unauthenticated health check.
- `GET /api/v1/materials/defaults`: Returns preconfigured M-01, M-02, and M-03 scenarios.
- `POST /api/v1/procure/run`: Executes multi-tier agentic procurement for any material input.
- `GET /api/v1/procure/{run_or_material_id}/export/{format}`: Downloads report as `md`, `csv`, or `json`.

---

## Assessment Demonstration Scenarios & Results

Pre-generated outputs are saved in the `output/` directory for immediate review:

| Material ID | Specification | Key Ambiguity Detected | Resulting Artifacts |
|---|---|---|---|
| **M-01** | `ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239` (Qty: 1000) | Missing quantity unit + 5.5mm wall exceeds IS 1239 Class C max (4.5mm) | [Markdown](output/M-01_evaluation.md), [CSV](output/M-01_vendors.csv), [JSON](output/M-01_result.json) |
| **M-02** | `40 mm MS ERW, Class B pipe` (Qty: 500) | Missing quantity unit + 40 mm NB (48.3 mm OD) vs 40 mm OD ambiguity | [Markdown](output/M-02_evaluation.md), [CSV](output/M-02_vendors.csv), [JSON](output/M-02_result.json) |
| **M-03** | `ERW pipe, DN 80, 89.5 x 4.8 mm, IS 1239` (Qty: 1200) | Missing quantity unit + OD 89.5 mm upper tolerance alignment | [Markdown](output/M-03_evaluation.md), [CSV](output/M-03_vendors.csv), [JSON](output/M-03_result.json) |

---

## Technical Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Deep-dive into the agentic harness, pipeline stages, state flow, and anti-hallucination guardrails.
- **[METHODOLOGY.md](METHODOLOGY.md)**: Input parameters, ambiguity detection rules, IS 1239 engineering formulas, and the 100-point confidence scoring model.
- **[LIMITATIONS.md](LIMITATIONS.md)**: Trade-offs (coverage vs speed vs accuracy), known system limitations, and planned future improvements.
- **[CHANGELOG.md](CHANGELOG.md)**: Audit log tracking code and design changes.

---

## Running Automated Tests

Run the complete test suite with `pytest`:
```bash
pytest -v
```

All 22 unit and integration tests execute in approximately 2 seconds:
- `tests/test_standards.py`: IS 1239 dimension tables, weight formulas, and tolerances.
- `tests/test_normalizer.py`: Ambiguity detection on M-01, M-02, and M-03.
- `tests/test_evaluator_and_scorer.py`: Evidence extraction, tagging, scoring, and deduplication.
- `tests/test_api.py`: FastAPI endpoints and error validation.
- `tests/test_export.py`: Markdown, CSV, and JSON report generation.

---

## Candidate Assessment Completion Checklist

- [x] GitHub repository with working code.
- [x] README includes setup and execution instructions.
- [x] All three materials (M-01, M-02, M-03) demonstrated with Ahmedabad destination.
- [x] Ahmedabad, India-wide, and Global vendor groups included and separated.
- [x] Sources, match status, confidence score, and unresolved issues visible for each vendor.
- [x] Quantity and technical ambiguities identified and exposed.
- [x] Large-quantity procurement and delivery feasibility considered.
- [x] No unsupported prices, stock, certifications, or dimensions presented as facts (`[SOURCED]` vs `[ASSUMPTION]`).
- [x] Architecture, parameters, assumptions, and limitations documented.
