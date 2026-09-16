# Methodology: Parameters, Confidence Model, and Procurement Reasoning

## 1. Input Parameter Design

The system accepts a minimal, standard 4-field contract representing real-world industrial procurement tenders:

| Field | Type | Description | Assessment Demonstration Example |
|---|---|---|---|
| `id` | String | Unique line-item identifier | `M-01`, `M-02`, `M-03` |
| `material` | String | Technical material description, standards, dimensions | `40 mm MS ERW, Class B pipe` |
| `quantity` | Number | Quantity required (intentionally unitless) | `500`, `1000`, `1200` |
| `location` | String | Delivery / procurement destination | `Ahmedabad, Gujarat, India` |

---

## 2. Technical Ambiguity Detection Logic

### 2.1 Unspecified Quantity Units
- **Industrial Context**: Procurement requisitions often omit units when piping contractors order by length, whereas steel mills trade by metric tonnage and stockists sell by 6-meter bundle pieces.
- **Handling**:
  1. The agent intercepts the unitless float/integer and emits a `WARNING` level ambiguity.
  2. Declares an explicit **Stated Assumption**: defaults to **linear meters** (the primary basis for piping BOQs in Indian engineering projects).
  3. Calculates the equivalent batch mass in Metric Tons using standard steel density:
     $$\text{Linear Mass (kg/m)} = (OD - t) \times t \times 0.02466$$
     $$\text{Total Batch Tonnage (MT)} = \frac{\text{Linear Mass} \times \text{Length (m)}}{1000}$$
  4. Calculates estimated piece count based on standard commercial pipe lengths:
     $$\text{Commercial 6m Pieces} \approx \text{round}\left(\frac{\text{Length}}{6.0}\right)$$
  5. Formulates a ready-to-send buyer clarification prompt for verification before issuing Purchase Orders.

### 2.2 Technical Ambiguity: Nominal Bore (NB) vs Outside Diameter (OD)
- **Scenario (M-02)**: `40 mm MS ERW, Class B pipe`.
- **Engineering Reality**:
  - In Indian and British piping standards (IS 1239 / BS 1387), pipe sizes are designated by **Nominal Bore (NB / DN)**.
  - A `40 mm NB` (DN 40 / 1.5 inch NB) pipe has a standardized outside diameter of **48.3 mm**, with Class B wall thickness of **3.25 mm**.
  - There is no 40 mm outside diameter pipe in IS 1239 Part 1.
- **Handling**:
  - The agent identifies the potential conflict between 40 mm OD and 40 mm NB.
  - Rather than silently altering the specification, it documents the ambiguity and evaluates suppliers against standard DN 40 NB Class B (OD 48.3 mm) while adding an explicit RFQ confirmation item.

### 2.3 Non-Standard Wall Thickness Discrepancy
- **Scenario (M-01)**: `ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239`.
- **Engineering Reality**:
  - IS 1239 (Part 1): 2004 defines three weight schedules for DN 50 (60.3 mm OD):
    - Class A (Light): 3.25 mm wall thickness
    - Class B (Medium): 3.65 mm wall thickness
    - Class C (Heavy): 4.50 mm wall thickness
  - A wall thickness of **5.5 mm** exceeds standard Class C Heavy schedules and falls outside routine commercial stock.
- **Handling**:
  - The agent flags this as a `NON_STANDARD_WALL_THICKNESS` exception.
  - Explains that fulfilling 5.5 mm requires either:
    1. Custom mill rolling batch from primary manufacturers (e.g. Jindal Pipes or Surya Roshni) subject to minimum order quantity (MOQ).
    2. Supplying equivalent heavy-wall pipe under ASTM A53 Schedule 80 (nominal wall 5.54 mm).
    3. Procuring under IS 3589 standard.
  - Downgrades off-the-shelf stockists to Category-Level Leads and prioritizes primary manufacturers capable of custom rolling.

### 2.4 Dimensional Tolerance Alignment
- **Scenario (M-03)**: `ERW pipe, DN 80, 89.5 x 4.8 mm, IS 1239`.
- **Engineering Reality**:
  - Under IS 1239 Part 1, DN 80 nominal outside diameter is 88.9 mm with a permissible upper tolerance of **89.5 mm** (+0.6 mm).
  - Standard Class C Heavy thickness is 4.85 mm; specified 4.8 mm is within standard commercial tolerance (-10%).
- **Handling**:
  - The agent confirms this is an exact match for standard IS 1239 Heavy Class C ERW pipe.

---

## 3. Confidence Scoring Model

The confidence score is a deterministic, composite metric evaluated on a 100-point scale:

$$\text{Confidence Score} = S_{\text{tech}} + S_{\text{cert}} + S_{\text{capacity}} + S_{\text{logistics}} + S_{\text{trace}}$$

### Breakdown of Weights:

1. **Technical Fit ($S_{\text{tech}}$ - 35 points max)**:
   - `EXACT_MATCH`: 35 points (meets standard, dimensional range, and thickness capability).
   - `NEAR_MATCH`: 27 points (meets international equivalent standard or requires custom rolling).
   - `CATEGORY_LEVEL_LEAD`: 18 points (operates in ERW piping but cannot confirm exact gauge).
   - `UNVERIFIED_LEAD`: 8 points.

2. **Standards & Certifications ($S_{\text{cert}}$ - 25 points max)**:
   - BIS ISI mark for IS 1239 + ISO 9001: 25 points.
   - ISO 9001 + equivalent standard (ASTM A53 / API 5L / EN 10255): 20 points.
   - Verified single certification: 15 points.
   - Unverified: 5 points.

3. **Capacity & Bulk Feasibility ($S_{\text{capacity}}$ - 20 points max)**:
   - Primary integrated manufacturer (> 100,000 MT/year): 20 points.
   - Large authorized distributor (> 2,000 MT warehouse buffer): 17 points.
   - Regional stockist (500 to 2,000 MT): 14 points.
   - EPC Supplier: 12 points.
   - Small trader: 10 points.
   - Bulk Batch Feasibility Adjustment: Deducts 2.0 points from stockists/traders on bulk orders exceeding 50 Metric Tons to favor primary mills with continuous production.

4. **Geographic Coverage & Logistics ($S_{\text{logistics}}$ - 15 points max)**:
   - Ahmedabad local warehouse / same-day dispatch: 15 points.
   - Domestic manufacturer with dedicated Ahmedabad depot (Changodar/Sarkhej): 14 points.
   - Domestic manufacturer without local depot (2-3 days transit): 11 points.
   - Global exporter with established shipping corridor to Mundra Port: 8 points.

5. **Contact & Traceability ($S_{\text{trace}}$ - 5 points max)**:
   - Physical address: 2.0 points.
   - Verifiable domain URL: 1.5 points.
   - Direct communication channels:
     - Verified email and phone: 1.5 points.
     - Partial communication (email or phone only): 0.75 points.
     - Unverified/missing communication: 0.0 points.

### Dual Intra-Tier & Global Ranking Architecture

To deliver an intuitive and actionable procurement shortlist, vendors are assigned two complementary rankings:
- **Intra-Tier Rank (`rank`)**: Sequential standing (Rank 1 to N) within each geographic tier (Ahmedabad, India Domestic, Global Exporters), allowing buyers to immediately identify the top candidate in each logistics radius.
- **Global Rank (`global_rank`)**: Absolute cross-tier standing (1 to 10) sorted deterministically by confidence score descending, technical fit descending, certifications descending, and vendor name ascending for deterministic tie-breaking.

---

## 4. Evidence Grounding Rules

To ensure strict zero-hallucination compliance:
- **No Inferred Prices**: Spot prices for steel fluctuate daily with hot-rolled coil (HRC) indices; pricing must always be confirmed through formal RFQ.
- **No Inferred Ready Quantities**: Unless a vendor explicitly publishes live yard inventory, quantities are classified under `[NEEDS_CONFIRMATION_RFQ]`.
- **Labeling Standard**:
  - `[SOURCED]`: Verifiable company facts, plant locations, certificates, catalog lines.
  - `[ASSUMPTION]`: Explicit modeling deductions made by the system.
  - `[NEEDS_CONFIRMATION_RFQ]`: Action items for the procurement buyer.
