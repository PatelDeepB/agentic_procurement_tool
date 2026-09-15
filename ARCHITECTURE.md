# Architecture Note: AI/ML Multi-Agent Procurement Harness

## 1. System Overview

The Agentic Procurement Tool is engineered as a production-grade **Multi-Agent LLM System** designed to solve complex industrial procurement problems.

Rather than relying on a single, unstructured prompt that suffers from hallucinations, arithmetic inaccuracies, and unreliable schema outputs, the system uses an orchestrated multi-agent harness combining:
- **LLM Reasoning Agents**: Natural language understanding, ambiguity detection, semantic retrieval strategy, and grounded evidence extraction.
- **Deterministic Engineering Tools (ReAct Pattern)**: Physical standards tables (IS 1239 Part 1:2004), exact tolerance calculations, and steel mass formulas ($W = (OD - t) \times t \times 0.02466$ kg/m).
- **Multi-Provider Architecture**: Plug-and-play support for **Google Gemini**, **OpenAI**, and an offline **Deterministic Mock LLM Client** that ensures 100% reproducible execution and zero-dependency grading.

```
+-----------------------------------------------------------------------------------+
|                            4-Field Input Contract                                 |
|            [id]              [material]           [quantity]         [location]   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 1: Spec Normalizer & Ambiguity Agent (LLM + ReAct Tools)                    |
| - Prompt: Senior Industrial Piping Procurement Engineer                           |
| - Tools Invoked:                                                                  |
|     * tool_lookup_is1239_spec(dn)                                                 |
|     * tool_evaluate_wall_thickness(dn, wall)                                      |
|     * tool_calculate_steel_tonnage(od, wall, qty)                                 |
| - Diagnostics:                                                                    |
|     * Unspecified Quantity Unit -> Computes Metric Tons & 6m piece counts         |
|     * Technical Ambiguity -> DN 40 NB (OD 48.3 mm) vs 40 mm OD                    |
|     * Non-Standard Thickness -> DN 50 with 5.5 mm wall (> 4.5 mm Class C max)     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 2: Procurement Search & Strategy Agent (LLM)                                |
| - Synthesizes precision queries tailored to 3 distinct geographic tiers:          |
|     1. Ahmedabad Local GIDC Industrial Estates (Odhav, Naroda, Vatva, Sanand)    |
|     2. India-wide Primary Pipe Mills (Jindal, Tata Steel, Surya, APL Apollo)      |
|     3. Global / International Export Suppliers (Baosteel, Tenaris, UAE Stockists) |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 3: Multi-Tier Candidate Retrieval (Tool)                                    |
| - Queries verified industrial supplier registry across target geographic scopes   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 4: Grounded Evidence Extraction & Verification Agent (LLM)                  |
| - Prompt: Procurement Technical Auditor                                           |
| - Anti-Hallucination Guardrail: Rejects fabricated prices, lead times, or stock   |
| - Strict Classification:                                                          |
|     * [SOURCED]: Verified catalog citations, plant addresses, BIS licenses       |
|     * [ASSUMPTION]: Engineering inferences (e.g. assuming linear meters, DN 40 NB)|
|     * [NEEDS_CONFIRMATION_RFQ]: Binding price quotes, MTC EN 10204 Type 3.1       |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 5: Geographic & Delivery Feasibility Engine                                 |
| - Local Ahmedabad warehouse dispatch (12-24 hrs)                                  |
| - Domestic rail/road freight corridor or Changodar/Sarkhej regional hub (2-3 days)|
| - Global container ocean shipping via Mundra / Kandla Port, Gujarat (15-30 days)  |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 6: Deterministic Confidence Scorer, Deduplicator & Ranker                   |
| - Multi-attribute scoring: Tech Fit (35%), Certifications (25%), Capacity (20%),  |
|   Logistics (15%), Traceability (5%)                                              |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 7: Executive Procurement Synthesis Agent (LLM)                              |
| - Prompt: Chief Procurement Officer                                               |
| - Generates procurement strategy, supplier risk balance, and RFQ action steps     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Delivery: RESTful API (/api/v1/), CLI Runner, Markdown / CSV / JSON Artifacts     |
+-----------------------------------------------------------------------------------+
```

---

## 2. Why Multi-Agent Decomposition over a Single Prompt?

1. **Failure Mode of Single Monolithic Prompts**:
   - Monolithic prompts attempt to perform parsing, math, search, scoring, and output formatting in one context.
   - When asked to perform arithmetic on pipe weights ($55.8 \times 4.5 \times 0.02466$), pure LLMs produce subtle calculation errors.
   - When asked to evaluate multiple suppliers simultaneously, models hallucinate plausible-sounding stock quantities, fake price quotes, or non-existent Indian Standard license numbers.

2. **The Multi-Agent Advantage**:
   - **Isolation of Concerns**: Each agent has a focused prompt and a specific cognitive task.
   - **Tool-Augmented Grounding (ReAct)**: Exact physical properties are queried from deterministic tools, grounding the LLM in real engineering data.
   - **Observable Auditability**: The system emits state transitions and reasoning traces, allowing human buyers to audit why a vendor was ranked or excluded.

---

## 3. Post-Submission Interview Talking Points

Be prepared to explain the following engineering decisions during the post-submission technical interview:

### Q1: Why did you decompose the problem into multiple agents instead of a single prompt?
> "In industrial engineering procurement, accuracy and physical grounding are paramount. Single-prompt architectures suffer from three critical failure modes: arithmetic hallucinations on steel mass calculations, conflating unverified assumptions with sourced facts, and formatting degradation on multi-tier vendor comparisons. By decomposing into specialized agents (Normalizer with ReAct tools, Multi-Tier Strategist, Grounded Auditor, and Executive Synthesizer), each agent operates with dedicated guardrails and typed Pydantic boundaries."

### Q2: How did you design the confidence scoring model?
> "The confidence scoring model is intentionally deterministic (0 to 100 points) across five verifiable dimensions: Technical Specification Fit (35%), Standards & Quality Certifications (25%), Large-Volume Capacity Feasibility (20%), Geographic Delivery Logistics (15%), and Evidence Traceability (5%). This prevents prompt drift and guarantees reproducible ranking across runs."

### Q3: How do you prevent hallucinations?
> "We enforce a three-tier tagging contract on all extracted vendor data:
> 1. `[SOURCED]`: Directly quoted from official company records, catalogs, or BIS ISI registries.
> 2. `[ASSUMPTION]`: Explicitly declared engineering deductions (e.g., interpreting unitless 1000 as linear meters or 40 mm as DN 40 NB).
> 3. `[NEEDS_CONFIRMATION_RFQ]`: Mandatory commercial verification items (live stock, binding pricing, MTC mill test certificates).
> Any attempt to hallucinate static prices or inventory numbers is blocked by policy."

### Q4: How are ambiguities in inputs handled?
> "The normalizer explicitly diagnoses ambiguities rather than silently modifying inputs. For missing quantity units, it assumes linear meters, computes conversion matrices (metric tons and 6-meter commercial lengths), and generates a buyer clarification prompt. For technical ambiguities like '40 mm MS ERW', it exposes that IS 1239 has no 40 mm OD pipe and that the standard commercial size is DN 40 NB (48.3 mm OD)."
