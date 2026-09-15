"""Agentic harness orchestrator coordinating the multi-stage procurement pipeline.

Manages pipeline state transitions, invokes specialized agents, records an
audit trail, and assembles the comprehensive ProcurementResult payload.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.agents.evaluator import EvaluatorAgent
from app.agents.normalizer import NormalizerAgent
from app.agents.scorer import ScorerAgent
from app.agents.searcher import SearchAgent
from app.domain.models import (
    MaterialInput,
    ProcurementResult,
    VendorTier,
)
from app.llm.client import BaseLLMClient, get_llm_client


class ProcurementOrchestrator:
    """Multi-agent orchestrator managing the procurement evaluation workflow."""

    def __init__(
        self,
        normalizer: Optional[NormalizerAgent] = None,
        searcher: Optional[SearchAgent] = None,
        evaluator: Optional[EvaluatorAgent] = None,
        scorer: Optional[ScorerAgent] = None,
        llm_client: Optional[BaseLLMClient] = None,
    ):
        """Initialize pipeline with agent instances and LLM client."""
        self.llm = llm_client or get_llm_client()
        self.normalizer = normalizer or NormalizerAgent(llm_client=self.llm)
        self.searcher = searcher or SearchAgent()
        self.evaluator = evaluator or EvaluatorAgent(llm_client=self.llm)
        self.scorer = scorer or ScorerAgent()

    def run_procurement_workflow(self, raw_input: MaterialInput) -> ProcurementResult:
        """Execute end-to-end multi-tier procurement evaluation for given material input."""
        audit_trail: List[str] = []
        run_id = f"RUN-{raw_input.id}-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        audit_trail.append(f"[{timestamp}] Stage 1: Received requirement '{raw_input.id}' for location '{raw_input.location}'.")

        # Stage 1: Normalization & Ambiguity Detection (LLM + ReAct Tools)
        spec = self.normalizer.normalize(raw_input)
        audit_trail.append(
            f"Stage 1 Complete: Normalized specs via LLM + Tools. Detected {len(spec.ambiguities)} technical/quantity ambiguities."
        )

        # Stage 2: Query Generation
        queries = self.searcher.generate_search_queries(spec)
        audit_trail.append("Stage 2 Complete: Synthesized search queries across Ahmedabad, India, and Global scopes.")

        # Stage 3: Multi-Tier Search & Candidate Retrieval
        all_raw_candidates = self.searcher.retrieve_candidates(spec)
        audit_trail.append(f"Stage 3 Complete: Retrieved {len(all_raw_candidates)} candidate supplier profiles.")

        # Stage 4: Grounded Evidence Extraction & Evaluation (LLM + Strict Tagging)
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

        audit_trail.append("Stage 4 Complete: Evaluated technical fit and tagged [SOURCED]/[ASSUMPTION] evidence.")

        # Stage 5 & 6: Deduplication, Scoring, and Geographic Segregation
        all_scored = self.scorer.score_and_rank(evaluated_candidates, spec)

        ahmedabad_vendors = [v for v in all_scored if v.tier == VendorTier.AHMEDABAD]
        india_vendors = [v for v in all_scored if v.tier == VendorTier.INDIA_OUTSIDE_AHMEDABAD]
        global_vendors = [v for v in all_scored if v.tier == VendorTier.GLOBAL]

        # Stage 7: LLM Executive Procurement Synthesis
        synthesis = self._generate_executive_synthesis(spec, ahmedabad_vendors, india_vendors, global_vendors)
        audit_trail.append(
            f"Stage 6 Complete: Scored and ranked vendors. Shortlisted: "
            f"{len(ahmedabad_vendors)} Ahmedabad, {len(india_vendors)} India-wide, {len(global_vendors)} Global."
        )

        provider_name = type(self.llm).__name__.replace("LLMClient", "").lower()

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
            llm_synthesis=synthesis,
            model_provider=provider_name,
        )

    def _generate_executive_synthesis(
        self,
        spec: Any,
        ahmedabad: list,
        india: list,
        global_v: list,
    ) -> str:
        """Call LLM to generate high-level executive procurement reasoning."""
        prompt = (
            f"Provide executive procurement reasoning for {spec.raw_input.material}. "
            f"Candidate counts: Ahmedabad local={len(ahmedabad)}, India-wide={len(india)}, Global={len(global_v)}. "
            f"Identified ambiguities: {[a.description for a in spec.ambiguities]}."
        )
        return self.llm.generate_completion(
            system_prompt="You are a Chief Procurement Officer summarizing vendor options, logistics risks, and RFQ next steps.",
            user_prompt=prompt,
        )
