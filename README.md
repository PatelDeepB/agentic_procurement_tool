# Agentic Procurement Tool: Quickstart & Testing Guide

This guide provides a step-by-step walkthrough for anyone to set up, run, and test the **Agentic Procurement Tool** locally in under two minutes.

---

## 1. 30-Second Quickstart (Zero Configuration)

If you have Python 3.10+ installed, you can start the application immediately without configuring any API keys:

```powershell
# 1. Clone or navigate to the repository
cd agentic_procurement_tool

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1    # On Windows PowerShell
# source venv/bin/activate     # On Linux / macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the interactive Web UI and API server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Once running, open your web browser and navigate to:
- **Interactive Web UI**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Interactive API Documentation (Swagger)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 2. Prerequisites & Environment Setup

### 2.1 System Requirements
- **Python**: Version 3.10, 3.11, or 3.12.
- **Operating System**: Windows 10/11, macOS, or Linux.
- **Network**: Internet connection (only if using Google Gemini or OpenAI; offline mode works completely without internet).

### 2.2 Installing Dependencies
Dependencies are listed in `requirements.txt`:
```powershell
pip install -r requirements.txt
```
Core packages installed:
- `fastapi` & `uvicorn`: Web framework and ASGI web server.
- `pydantic`: Strict data validation and schema serialization.
- `httpx`: High-performance HTTP client for API communication.
- `jinja2`: Template engine for markdown and report generation.
- `pytest`: Automated test harness.

---

## 3. LLM Configuration (Optional)

The system features a **Multi-Provider LLM Layer** with automatic graceful fallbacks:

### Option A: Offline Deterministic Engine (Default, Zero Cost)
- If no API key is provided, the tool automatically uses its built-in **Deterministic Mock LLM Engine**.
- All calculations, IS 1239 engineering table lookups, ambiguity detections, candidate retrievals, scoring, and executive synthesis execute locally in under **0.8 seconds**.
- 100% reproducible, zero cost, and zero external network dependencies.

### Option B: Free Google Gemini API (Recommended for Live LLM Reasoning)
Google AI Studio offers a free tier with 1,500 free requests per day:
1. Obtain a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Create or edit the `.env` file in the project root:
   ```env
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=AIzaSyYourFreeGeminiKeyHere
   ```
3. The tool automatically detects `.env` on startup and activates `gemini-2.0-flash` with automatic fallback to `gemini-1.5-flash`.

### Option C: OpenAI API
If you prefer OpenAI:
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-YourOpenAIKeyHere
```

---

## 4. How to Run the App (3 Modes)

### Mode 1: Interactive Web UI (Browser)
1. Start the server:
   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. Open your browser and go to [http://127.0.0.1:8000/](http://127.0.0.1:8000/).
3. What you can do in the Web UI:
   - Click **M-01**, **M-02**, or **M-03** to instantly load benchmark scenarios.
   - Click **Run Procurement Evaluation** to execute the multi-agent workflow.
   - Review normalized engineering specifications, mass tonnage calculations, and commercial 6-meter piece counts.
   - Inspect ambiguity diagnostics and buyer clarification prompts.
   - Browse shortlisted suppliers across three tabs: **Ahmedabad Local**, **India-Wide**, and **Global Exporters**.
   - Review disqualified suppliers with explicit exclusion audit reasons.
   - Read the Chief Procurement Officer (CPO) strategic executive synthesis.
   - Click **Download Markdown (.md)**, **Download CSV (.csv)**, or **Download JSON (.json)** to export reports with one click.

### Mode 2: Interactive Swagger API (`/docs`)
1. With the server running, visit [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
2. Key endpoints to explore:
   - `GET /health`: Check backend health and verify all 30 vendor entries are loaded.
   - `GET /api/v1/materials/defaults`: Retrieve default benchmark requisition scenarios (M-01, M-02, M-03).
   - `POST /api/v1/procure/run`: Submit a custom material requisition payload and receive the full evaluation JSON.
   - `GET /api/v1/procure/{id}/export/{format}`: Export results in `markdown`, `csv`, or `json`.

### Mode 3: Command-Line Runner (CLI)
You can execute the evaluation pipeline directly from your terminal:
```powershell
# Run evaluation for all three default benchmark materials and generate all export files
python -m app.cli --material all --export all

# Run evaluation for a specific material scenario
python -m app.cli --material M-01 --export md,csv

# Run evaluation for custom pipe specifications directly from the command line
python -m app.cli --custom "50 mm NB Class B MS ERW pipe" --quantity 1000 --export all
```
Output files are automatically written to the `output/` directory:
- `output/M-01_evaluation.md`, `output/M-01_vendors.csv`, `output/M-01_result.json`
- `output/M-02_evaluation.md`, `output/M-02_vendors.csv`, `output/M-02_result.json`
- `output/M-03_evaluation.md`, `output/M-03_vendors.csv`, `output/M-03_result.json`

---

## 5. How to Test the Application

### 5.1 Run Automated Unit & Integration Tests
Execute the complete test suite using `pytest`:
```powershell
python -m pytest -v
```
- **Result**: All **70 unit and integration tests** pass in approximately **0.84 seconds**.
- Test breakdown:
  - `tests/test_api.py`: Web UI serving, health endpoints, 400 validation error handling, and artifact exports.
  - `tests/test_normalizer.py` & `tests/test_normalizer_advanced.py`: Specification parsing, ambiguity detection, dimensional lookups, and steel grade extraction.
  - `tests/test_searcher.py`: Query synthesis across geographic tiers, candidate retrieval, and exclusion logging.
  - `tests/test_evaluator_and_scorer.py`: Evidence extraction, grounded tagging, deterministic scoring, and deduplication.
  - `tests/test_scorer.py` & `tests/test_scorer_resilience.py`: 100-point composite formula, zero-address baseline, and missing-attribute resilience.
  - `tests/test_synthesizer.py`: Strategic dual-sourcing reasoning, risk matrix generation, and prioritized action plans.
  - `tests/test_standards.py`: IS 1239 Part 1 engineering dimensional tables, mass calculations, and tolerance verification.
  - `tests/test_export.py`: Markdown, CSV, and JSON export structure and formatting.

### 5.2 Run Live Endpoint Verification Script
With the uvicorn server running, you can run the live test script in a second terminal:
```powershell
python -c "
import urllib.request, json
res = urllib.request.urlopen('http://127.0.0.1:8000/health')
data = json.loads(res.read())
print('Health Check Status:', data['status'])
print('Loaded Vendors:', data['vendor_registry_entries'])
assert data['status'] == 'healthy'
assert data['vendor_registry_entries'] == 30
print('PASS: Backend is running with 30 vendors!')
"
```

---

## 6. Understanding the Benchmark Scenarios

The system evaluates three distinct requisition scenarios designed to test engineering precision:

### Scenario M-01: Non-Standard Wall Thickness Discrepancy
- **Input**: `ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239` | Quantity: `1000` | Location: `Ahmedabad, Gujarat, India`.
- **Engineering Reality**: Under IS 1239 Part 1:2004, the maximum standard schedule for DN 50 is Class C Heavy (4.5 mm). A wall thickness of 5.5 mm is non-standard.
- **System Diagnosis**: Flags `NON_STANDARD_WALL_THICKNESS`. Advises that fulfilling 5.5 mm requires either custom rolling from primary mills (subject to MOQ), ASTM A53 Schedule 80 equivalent, or IS 3589 standard.
- **Top Vendors**:
  - Ahmedabad Local: **Western Steel Agency Ahmedabad** (89.0%, holds stock of thick-walled pipes up to 6.5 mm).
  - India-Wide: **Jindal Pipes Limited** (99.0%) & **Surya Roshni Limited** (99.0%), primary mills with custom rolling capability.
  - Global: **Baosteel** & **Tenaris** (80.0%) for ASTM A53 Schedule 80 heavy-wall packages.

### Scenario M-02: Nominal Bore (NB) vs Outside Diameter (OD) Discrepancy
- **Input**: `40 mm MS ERW, Class B pipe` | Quantity: `500` | Location: `Ahmedabad, Gujarat, India`.
- **Engineering Reality**: In IS 1239 Part 1, there is no pipe with a 40 mm outside diameter. Standard 40 mm NB (1.5 inch) has an actual outside diameter of 48.3 mm with a Class B wall of 3.25 mm.
- **System Diagnosis**: Flags `NOMINAL_BORE_VS_OUTSIDE_DIAMETER`. Synthesizes dual search queries (`"40 mm NB"` and `"40 mm OD"`) to ensure complete market coverage.
- **Top Vendors**:
  - Ahmedabad Local: **Gujarat Infra Pipes Pvt Ltd** (97.0%) & **Ashapura Steel Tube Corporation** (90.0%).
  - India-Wide: **APL Apollo, Jindal Pipes, Surya Roshni, Tata Steel** (99.0%).

### Scenario M-03: Standard Heavy Class C Batch with High Tonnage
- **Input**: `ERW pipe, DN 80, 89.5 x 4.8 mm, IS 1239` | Quantity: `1200` | Location: `Ahmedabad, Gujarat, India`.
- **Engineering Reality**: 89.5 mm OD is within the permissible upper tolerance for DN 80 (88.9 mm + 0.6 mm). Standard Class C wall is 4.85 mm (-10% tolerance matches 4.8 mm). Total batch tonnage is **14.63 Metric Tons** (~200 standard 6-meter pipe pieces).
- **System Diagnosis**: Confirms exact standard match. Diagnoses missing quantity unit and calculates tonnage and piece conversions.
- **Strategic Recommendation**: Recommends dual-sourcing: 20% local buffer from Gujarat Infra Pipes for immediate site needs, and 80% bulk dispatch directly from Jindal Pipes factory to capture mill pricing discounts.

---

## 7. Realistic Imperfect Vendor Dataset

The vendor database ([`app/data/vendor_registry.json`](file:///c:/Deep_Patel_Projects/OpenSourceProjects/agentic_procurement_tool/app/data/vendor_registry.json)) contains **30 verified industrial suppliers** (10 Ahmedabad, 11 India-Wide, 9 Global) with realistic missing attributes to simulate real-world procurement data:
- **8 vendors** with unlisted websites.
- **7 vendors** with missing commercial emails.
- **8 vendors** with missing phone numbers.
- **6 vendors** with unlisted physical addresses (strictly receiving 0.0 address points).
- **12 vendors** with empty certifications (receiving baseline 5.0 points instead of 25.0).
- **7 vendors** with unverified stock/capacity.
- **7 vendors** with unverified delivery logistics.
- **5 vendors** with narrow diameter ranges (e.g. DN 15-25 mm or DN 150-600 mm) that deterministically trigger entries in the candidate disqualification log.

---

## 8. Troubleshooting & FAQ

### Q: Port 8000 is already in use
If another application is using port 8000, start the server on a different port:
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```
Then visit [http://127.0.0.1:8080/](http://127.0.0.1:8080/) in your browser.

### Q: PermissionError on CSV export files on Windows
If an export file (e.g. `output/M-01_vendors.csv`) is open in Microsoft Excel, Windows locks the file. The system includes built-in protection: it logs a warning and proceeds without crashing. Close Excel and re-run the export to overwrite the file.

### Q: Gemini API returns 404 or Invalid Key
Verify that your API key is correct in `.env`. If using a corporate or restricted network that blocks external AI APIs, simply remove or comment out `GEMINI_API_KEY` in `.env`. The system will automatically run using its built-in deterministic engine without any external network calls.

---

## 9. Project File Layout

```
agentic_procurement_tool/
├── README.md                      # Comprehensive candidate assessment overview
├── README_2.md                    # Quickstart & testing guide (this file)
├── ARCHITECTURE.md                # Multi-agent architecture and interview defense
├── METHODOLOGY.md                 # 100-point confidence model and ambiguity rules
├── LIMITATIONS.md                 # Trade-offs, failure modes, and planned roadmap
├── CHANGELOG.md                   # Full version history (v1.0.0 to v2.3.0)
├── requirements.txt               # Production and testing dependencies
├── .env.example                   # Environment configuration template
│
├── app/
│   ├── main.py                    # FastAPI application entry point and Web UI mount
│   ├── cli.py                     # Command-line interface runner
│   ├── agents/                    # Specialized cognitive agents
│   │   ├── normalizer.py          # Specification normalization & ambiguity detection
│   │   ├── searcher.py            # Multi-tier search strategy & candidate retrieval
│   │   ├── evaluator.py           # Technical fit evaluation & grounded evidence extraction
│   │   ├── scorer.py              # 100-point deterministic confidence scoring & dual ranking
│   │   ├── synthesizer.py         # Executive CPO strategic synthesis
│   │   └── orchestrator.py        # End-to-end pipeline coordination
│   ├── core/                      # Engineering standards and formulas
│   │   └── standards.py           # IS 1239 Part 1 dimensional tables & steel tonnage math
│   ├── domain/                    # Pydantic data schemas
│   │   └── models.py              # Strict domain models for requisitions and vendors
│   ├── data/                      # Vendor database
│   │   └── vendor_registry.json   # 30 industrial suppliers across Ahmedabad, India, Global
│   ├── static/                    # Frontend Web UI
│   │   ├── index.html             # Responsive single-page application
│   │   ├── style.css              # Dark-mode styling with CSS variables
│   │   └── app.js                 # Interactive form handling and export downloads
│   └── services/                  # Business logic and export generators
│       ├── export_service.py      # Markdown, CSV, and JSON export formatters
│       └── procurement_service.py # High-level workflow execution service
│
├── output/                        # Pre-generated benchmark reports and data exports
│   ├── M-01_evaluation.md, M-01_vendors.csv, M-01_result.json
│   ├── M-02_evaluation.md, M-02_vendors.csv, M-02_result.json
│   └── M-03_evaluation.md, M-03_vendors.csv, M-03_result.json
│
└── tests/                         # Automated test suite (70 tests passing in 0.84s)
    ├── test_api.py                # Web UI & RESTful API endpoints
    ├── test_evaluator_and_scorer.py
    ├── test_export.py
    ├── test_llm_agents.py
    ├── test_normalizer.py
    ├── test_normalizer_advanced.py
    ├── test_scorer.py
    ├── test_scorer_resilience.py
    ├── test_searcher.py
    ├── test_standards.py
    └── test_synthesizer.py
```
