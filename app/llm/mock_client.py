"""Deterministic offline mock LLM client for zero-cost testing and offline execution."""

import json
import logging
from typing import Optional

from app.agents.normalizer_fallback import (
    detect_explicit_unit,
    evaluate_wall_deviation,
    extract_dimensions_and_bore,
    parse_specification_metadata,
)
from app.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


class MockLLMClient(BaseLLMClient):
    """Deterministic, high-fidelity offline LLM simulation client."""

    def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> str:
        """Generate simulated structured responses based on domain prompt patterns."""
        lower_prompt = user_prompt.lower()
        lower_sys = system_prompt.lower()

        if "executive" in lower_prompt or "synthesis" in lower_prompt or "chief procurement" in lower_sys:
            return self._mock_executive_response(user_prompt)

        if "search queries" in lower_sys or "industrial procurement specialist" in lower_sys:
            return self._mock_search_queries_response(user_prompt)

        if "normalize" in lower_prompt or "ambiguity" in lower_prompt:
            return self._mock_normalize_response(user_prompt)

        if "evaluate" in lower_prompt or "candidate" in lower_prompt:
            return self._mock_evaluator_response(user_prompt)

        return "Executive Procurement Recommendation: Evaluated candidate capabilities against tender specifications."

    def _mock_normalize_response(self, prompt: str) -> str:
        """Simulate unified single-call LLM response for specification normalization."""
        lower_prompt = prompt.lower()
        has_explicit_unit, detected_unit = detect_explicit_unit(lower_prompt)
        standard, pipe_class, steel_grade, is_erw = parse_specification_metadata(lower_prompt)
        dn, od, wall, technical_ambiguities = extract_dimensions_and_bore(lower_prompt, pipe_class)

        wall_amb = evaluate_wall_deviation(dn, wall)
        if wall_amb:
            technical_ambiguities.append(wall_amb)

        qty_desc = None if has_explicit_unit else (
            "Quantity value is provided without a physical unit of measure. "
            "In industrial steel piping, quantities are typically specified in linear meters, "
            "metric tons (MT), or commercial 6-meter pipe lengths/pieces."
        )
        qty_assumption = None if has_explicit_unit else (
            "Assumed quantity represents linear meters (standard Indian piping contract convention). "
            "Commercial lengths are assumed to be 6.0 meters."
        )
        qty_prompt = None if has_explicit_unit else (
            "Please confirm whether quantity is linear meters, metric tons, or standard 6m pipe pieces."
        )

        response = {
            "parsed_dn_mm": dn,
            "parsed_od_mm": od,
            "parsed_wall_thickness_mm": wall,
            "parsed_standard": standard,
            "parsed_class": pipe_class,
            "parsed_steel_grade": steel_grade,
            "is_erw": is_erw,
            "has_quantity_unit": has_explicit_unit,
            "detected_unit": detected_unit,
            "quantity_ambiguity_description": qty_desc,
            "quantity_stated_assumption": qty_assumption,
            "quantity_clarification_prompt": qty_prompt,
            "technical_ambiguities": technical_ambiguities,
        }
        return json.dumps(response, indent=2)

    @staticmethod
    def _mock_evaluator_response(prompt: str) -> str:
        """Simulate LLM response for vendor evidence evaluation."""
        return json.dumps({
            "thought_process": [
                "Cross-referenced vendor product catalog against normalized dimensions.",
                "Tagged verified credentials as [SOURCED].",
                "Flagged commercial and live stock verification items as [NEEDS_CONFIRMATION_RFQ].",
            ],
            "match_category": "EXACT_MATCH" if "IS 1239" in prompt else "NEAR_MATCH",
            "confidence_assessment": "High confidence based on verified BIS ISI mark and warehouse capacity.",
        }, indent=2)

    @staticmethod
    def _mock_search_queries_response(prompt: str) -> str:
        """Simulate LLM response for specialized multi-tier search queries."""
        return json.dumps({
            "ahmedabad": [
                "Ahmedabad GIDC ERW steel pipe distributor stockist ready inventory",
                "IS 1239 mild steel pipe supplier Odhav Vatva Ahmedabad",
            ],
            "india_wide": [
                "India primary ERW steel pipe manufacturers Jindal Surya Tata BIS mill",
                "IS 1239 heavy class steel tubes mill direct dispatch Changodar depot",
            ],
            "global": [
                "Carbon steel ERW line pipe exporter ASTM A53 BS 1387 CIF Mundra Port",
                "Global tubular industrial exporter heavy gauge Schedule 80",
            ],
        }, indent=2)

    @staticmethod
    def _mock_executive_response(prompt: str) -> str:
        """Simulate rich CPO executive procurement synthesis tailored to the prompt."""
        lower_prompt = prompt.lower()
        lines = [
            "Executive Procurement Recommendation:",
            "",
            "### 1. Executive Feasibility & Technical Viability",
        ]
        if "5.5 mm" in lower_prompt or "non_standard" in lower_prompt:
            lines.append("- Critical Finding: Specified 5.5 mm wall exceeds standard IS 1239 Class C (4.5 mm max). Requires custom mill rolling run from primary producers or ASTM A53 Schedule 80 equivalent.")
        elif "40 mm" in lower_prompt:
            lines.append("- Dimensional Clarification: Requirement denotes 40 mm NB (DN 40, actual OD 48.3 mm). Evaluated against standard Class B Medium schedule.")
        else:
            lines.append("- Material Compliance: Standard dimensions fully conform to IS 1239 Part 1 specifications.")

        lines.extend([
            "",
            "### 2. Strategic Dual-Sourcing Recommendation",
            "- Immediate / Emergency Buffer: Source initial requirement from qualified local Ahmedabad stockists for same-day/24h delivery.",
            "- Primary Volume Production: Contract primary domestic mills (Jindal Pipes / Surya Roshni) for factory dispatch with MTC EN 10204 Type 3.1.",
            "- International Hedge: Maintain global suppliers (Baosteel / Tenaris) for bulk marine freight via Mundra Port.",
            "",
            "### 3. Critical Commercial & Logistics Risk Matrix",
            "- Volume Exposure: Verify assumed quantity unit (linear meters vs metric tons vs pieces) to avoid commercial billing discrepancies.",
            "- Transit Corridors: Ahmedabad GIDC hubs (Changodar/Naroda) ensure local availability; inter-state transit requires 3 business days.",
            "",
            "### 4. Actionable Buyer RFQ Execution Plan",
            "1. Buyer Clarification: Issue formal acknowledgment confirming quantity unit and pipe schedule.",
            "2. Local Inquiry: Issue RFQ to top-ranked Ahmedabad stockist for urgent warehouse availability.",
            "3. Mill Negotiation: Request binding commercial quotation and production rolling slot from primary domestic mill.",
            "4. Quality Control: Mandate BIS ISI embossed marking verification prior to factory dispatch.",
        ])
        return "\n".join(lines)
