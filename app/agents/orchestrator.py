"""Agentic harness orchestrator coordinating the multi-stage procurement pipeline.

Manages pipeline state transitions, invokes specialized agents, records an
audit trail, and assembles the comprehensive ProcurementResult payload.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List

from app.agents.evaluator import EvaluatorAgent
from app.agents.normalizer import NormalizerAgent
from app.agents.scorer import ScorerAgent
from app.agents.searcher import SearchAgent
from app.domain.models import (
    MaterialInput,
    ProcurementResult,
    VendorTier,
)


class ProcurementOrchestrator:
    """Multi-agent orchestrator managing the procurement evaluation workflow."""

    def __init__(
        self,
        normalizer: NormalizerAgent | None = None,
        searcher: SearchAgent | None = None,
        evaluator: EvaluatorAgent | None = None,
        scorer: ScorerAgent | None = None,
    ):
        """Initialize pipeline with agent instances."""
        self.normalizer = normalizer or NormalizerAgent()
        self.searcher = searcher or SearchAgent()
        self.evaluator = evaluator or EvaluatorAgent()
        self.scorer = scorer or ScorerAgent()

    def run_procurement_workflow(self, raw_input: MaterialInput) -> ProcurementResult:
        """Execute end-to-end multi-tier procurement evaluation for given material input."""
        audit_trail: List[str] = []
        run_id = f"RUN-{raw_input.id}-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        audit_trail.append(f"[{timestamp}] Stage 1: Received requirement '{raw_input.id}' for location '{raw_input.location}'.")

        # Stage 1: Normalization & Ambiguity Detection
        spec = self.normalizer.normalize(raw_input)
        audit_trail.append(
            f"Stage 1 Complete: Normalized specs. Detected {len(spec.ambiguities)} technical/quantity ambiguities."
        )

        # Stage 2: Query Generation
        queries = self.searcher.generate_search_queries(spec)
        audit_trail.append(f"Stage 2 Complete: Synthesized search queries across Ahmedabad, India, and Global scopes.")

        # Stage 3: Multi-Tier Search & Candidate Retrieval
        all_raw_candidates = self.searcher.retrieve_candidates(spec)
        audit_trail.append(f"Stage 3 Complete: Retrieved {len(all_raw_candidates)} candidate supplier profiles.")

        # Stage 4: Grounded Evidence Extraction & Evaluation
        evaluated_candidates: List[Dict[str, Any]] = []
        exclusion_log: List[Dict[str, str]] = []

        for cand in all_raw_candidates:
            match_cat, evidence, unresolved, next_step = self.evaluator.evaluate_vendor(cand, spec)
            evaluated_candidates.append({
                "raw_vendor": cand,
                "match_category": match_cat,
                "evidence": evidence,
                "unresolved_issues": unresolved,
                "recommended_next_step": next_step,
            })

        audit_trail.append(f"Stage 4 Complete: Evaluated technical fit and tagged [SOURCED]/[ASSUMPTION] evidence.")

        # Stage 5 & 6: Deduplication, Scoring, and Geographic Segregation
        all_scored = self.scorer.score_and_rank(evaluated_candidates, spec)

        ahmedabad_vendors = [v for v in all_scored if v.tier == VendorTier.AHMEDABAD]
        india_vendors = [v for v in all_scored if v.tier == VendorTier.INDIA_OUTSIDE_AHMEDABAD]
        global_vendors = [v for v in all_scored if v.tier == VendorTier.GLOBAL]

        audit_trail.append(
            f"Stage 6 Complete: Scored and ranked vendors. Shortlisted: "
            f"{len(ahmedabad_vendors)} Ahmedabad, {len(india_vendors)} India-wide, {len(global_vendors)} Global."
        )

        return ProcurementResult(
            material_id=raw_input.id,
            run_id=run_id,
            timestamp=timestamp,
            location=raw_input.location,
            specification=spec,
            ahmedabad_vendors=ahmedabad_vendors,
            india_vendors=india_vendors,
            global_vendors=global_vendors,
            exclusion_log=exclusion_log,
            audit_trail=audit_trail,
        )
