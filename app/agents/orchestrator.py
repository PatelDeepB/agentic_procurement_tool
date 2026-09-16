"""Main multi-agent orchestrator coordinating the procurement pipeline.

Executes sequential multi-agent workflow:
Stage 1: Normalization & Ambiguity Detection (LLM + ReAct Tools)
Stage 2: Search Strategy Query Synthesis (LLM)
Stage 3: Multi-Tier Candidate Retrieval
Stage 4: Grounded Technical Evaluation & Evidence Tagging (LLM)
Stage 5: Deterministic Scoring & Deduplication
Stage 6: Geographic Segregation (Ahmedabad, India, Global)
Stage 7: Executive Procurement Synthesis (LLM)
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.agents.evaluator import EvaluatorAgent
from app.agents.normalizer import NormalizerAgent
from app.agents.scorer import ScorerAgent
from app.agents.searcher import SearchAgent
from app.domain.models import (
    EvaluatedVendor,
    MaterialInput,
    NormalizedSpecification,
    ProcurementResult,
    VendorTier,
)
from app.llm.client import BaseLLMClient, get_llm_client

logger = logging.getLogger(__name__)


class ProcurementOrchestrator:
    """Coordinates agents to execute end-to-end evidence-based procurement workflows."""

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """Initialize pipeline agents with unified or dedicated LLM client."""
        self.llm = llm_client or get_llm_client()
        self.normalizer = NormalizerAgent(llm_client=self.llm)
        self.searcher = SearchAgent()
        self.evaluator = EvaluatorAgent(llm_client=self.llm)
        self.scorer = ScorerAgent()

    def run_procurement_workflow(self, raw_input: MaterialInput) -> ProcurementResult:
        """Execute end-to-end multi-tier procurement evaluation for given material input."""
        audit_trail: List[str] = []
        run_id = f"RUN-{raw_input.id}-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        audit_trail.append(f"[{timestamp}] Stage 1: Received requirement '{raw_input.id}' for location '{raw_input.location}'.")
        spec = self.normalizer.normalize(raw_input)
        audit_trail.append(f"Stage 1 Complete: Normalized specs. Detected {len(spec.ambiguities)} ambiguities.")

        ahmedabad_v, india_v, global_v = self._retrieve_and_score_vendors(spec, audit_trail)

        synthesis = self._generate_executive_synthesis(spec, ahmedabad_v, india_v, global_v)
        audit_trail.append(
            f"Stage 6 Complete: Scored and ranked vendors. Shortlisted: "
            f"{len(ahmedabad_v)} Ahmedabad, {len(india_v)} India-wide, {len(global_v)} Global."
        )

        provider_name = type(self.llm).__name__.replace("LLMClient", "").lower()
        return ProcurementResult(
            material_id=raw_input.id,
            run_id=run_id,
            timestamp=timestamp,
            location=raw_input.location,
            specification=spec,
            ahmedabad_vendors=ahmedabad_v,
            india_vendors=india_v,
            global_vendors=global_v,
            exclusion_log=[],
            audit_trail=audit_trail,
            llm_synthesis=synthesis,
            model_provider=provider_name,
        )

    def _retrieve_and_score_vendors(
        self,
        spec: NormalizedSpecification,
        audit_trail: List[str],
    ) -> Tuple[List[EvaluatedVendor], List[EvaluatedVendor], List[EvaluatedVendor]]:
        """Retrieve, evaluate, and segregate vendors across tiers with audit logging."""
        self.searcher.generate_search_queries(spec)
        audit_trail.append("Stage 2 Complete: Synthesized search queries across Ahmedabad, India, and Global scopes.")

        raw_candidates = self.searcher.retrieve_candidates(spec)
        audit_trail.append(f"Stage 3 Complete: Retrieved {len(raw_candidates)} candidate supplier profiles.")

        evaluated = self._evaluate_raw_candidates(raw_candidates, spec)
        audit_trail.append("Stage 4 Complete: Evaluated technical fit and tagged [SOURCED]/[ASSUMPTION] evidence.")

        scored = self.scorer.score_and_rank(evaluated, spec)
        return self._segregate_by_tier(scored)

    def _evaluate_raw_candidates(
        self,
        raw_candidates: List[Dict[str, Any]],
        spec: NormalizedSpecification,
    ) -> List[Dict[str, Any]]:
        """Evaluate raw vendor candidates against specification."""
        evaluated: List[Dict[str, Any]] = []
        for cand in raw_candidates:
            match_cat, evidence, unresolved, next_step = self.evaluator.evaluate_vendor(cand, spec)
            evaluated.append({
                "raw_vendor": cand,
                "match_category": match_cat,
                "evidence": evidence,
                "unresolved_issues": unresolved,
                "recommended_next_step": next_step,
            })
        return evaluated

    @staticmethod
    def _segregate_by_tier(
        all_scored: List[EvaluatedVendor],
    ) -> Tuple[List[EvaluatedVendor], List[EvaluatedVendor], List[EvaluatedVendor]]:
        """Segregate scored candidates into three geographic tiers."""
        ahmedabad = [v for v in all_scored if v.tier == VendorTier.AHMEDABAD]
        india = [v for v in all_scored if v.tier == VendorTier.INDIA_OUTSIDE_AHMEDABAD]
        global_v = [v for v in all_scored if v.tier == VendorTier.GLOBAL]
        return ahmedabad, india, global_v

    def _generate_executive_synthesis(
        self,
        spec: NormalizedSpecification,
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
