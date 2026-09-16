"""Export service generating Markdown, CSV, and JSON representations of procurement results."""

import csv
import io
import json
from typing import Any, Dict, List

from app.domain.models import (
    AmbiguityItem,
    AmbiguityType,
    EvaluatedVendor,
    NormalizedSpecification,
    ProcurementResult,
)


class ExportService:
    """Service to format and serialize ProcurementResult into standard artifacts."""

    def to_markdown(self, result: ProcurementResult) -> str:
        """Render result as an evidence-based, human-readable Markdown report."""
        spec = result.specification
        lines = self._format_requirement_summary(result, spec)
        lines.extend(self._format_ambiguities_markdown(spec.ambiguities))
        if result.search_queries:
            lines.extend(self._format_search_queries_markdown(result.search_queries))
        lines.extend(self._format_vendor_shortlist_markdown(result))
        if result.exclusion_log:
            lines.extend(self._format_exclusion_log_markdown(result.exclusion_log))

        if result.llm_synthesis:
            lines.extend([
                f"## 6. LLM Executive Procurement Reasoning (Provider: {result.model_provider or 'active'})",
                result.llm_synthesis,
                "",
            ])

        lines.extend([
            "## 7. Audit Trail and Agentic State Transitions",
            *(f"- `{entry}`" for entry in result.audit_trail),
        ])
        return "\n".join(lines)

    @staticmethod
    def _format_requirement_summary(result: ProcurementResult, spec: NormalizedSpecification) -> List[str]:
        """Format initial requirement summary block in markdown."""
        raw = spec.raw_input
        has_unit_ambiguity = any(
            ambiguity.ambiguity_type == AmbiguityType.UNSPECIFIED_QUANTITY_UNIT
            for ambiguity in spec.ambiguities
        )
        unit_suffix = " *(unit unspecified in input)*" if has_unit_ambiguity else f" {spec.assumed_quantity_unit}"
        return [
            f"# Procurement Evaluation Report: {raw.id}",
            "",
            "## 1. Requirement Summary",
            f"- **Material ID**: {raw.id}",
            f"- **Material Description**: {raw.material}",
            f"- **Specified Quantity**: {raw.quantity}{unit_suffix}",
            f"- **Procurement Location**: {raw.location}",
            f"- **Run ID**: `{result.run_id}`",
            f"- **Evaluation Timestamp**: {result.timestamp}",
            "",
            "## 2. Technical Ambiguities and Stated Assumptions",
        ]

    @staticmethod
    def _format_ambiguities_markdown(ambiguities: List[AmbiguityItem]) -> List[str]:
        """Format detected ambiguities into markdown bullet points."""
        if not ambiguities:
            return ["No technical ambiguities identified.", ""]

        lines: List[str] = []
        for item in ambiguities:
            lines.extend([
                f"### [{item.severity.value}] {item.ambiguity_type.value}",
                f"- **Issue**: {item.description}",
                f"- **Agent Assumption**: {item.stated_assumption}",
                f"- **Buyer Clarification Prompt**: `{item.clarification_prompt}`",
            ])
            if item.unit_conversions and "if_assumed_meters" in item.unit_conversions:
                conv = item.unit_conversions["if_assumed_meters"]
                lines.append(
                    f"- **Weight & Piece Conversion**: {conv['estimated_weight_metric_tons']} MT "
                    f"(~{conv['standard_6m_pieces']} standard 6-meter pieces)."
                )
            lines.append("")
        return lines

    @staticmethod
    def _format_search_queries_markdown(queries: Dict[str, List[str]]) -> List[str]:
        """Format synthesized multi-tier search queries into markdown."""
        lines: List[str] = [
            "## 3. Synthesized Multi-Tier Search Strategy",
            "",
        ]
        tier_titles = {
            "ahmedabad": "Ahmedabad Local Queries",
            "india_wide": "India-Wide Queries",
            "global": "Global / Import Queries",
        }
        for tier_key, title in tier_titles.items():
            tier_queries = queries.get(tier_key, [])
            if tier_queries:
                lines.append(f"### {title}")
                for query_item in tier_queries:
                    lines.append(f"- `{query_item}`")
                lines.append("")
        return lines

    @staticmethod
    def _format_exclusion_log_markdown(exclusion_log: List[Dict[str, str]]) -> List[str]:
        """Format candidate supplier exclusion audit log into markdown."""
        lines: List[str] = [
            "## 5. Candidate Supplier Disqualification Log",
            "",
        ]
        for exclusion in exclusion_log:
            vendor_name = exclusion.get("vendor_name", "Unknown Supplier")
            tier = exclusion.get("tier", "UNKNOWN")
            reason = exclusion.get("disqualification_reason", "Unspecified reason")
            lines.append(f"- **{vendor_name}** ({tier}): {reason}")
        lines.append("")
        return lines

    def _format_vendor_shortlist_markdown(self, result: ProcurementResult) -> List[str]:
        """Format 3-tier vendor shortlists."""
        return [
            "## 4. Evidence-Based Vendor Shortlist",
            "",
            "### Tier 1: Ahmedabad Local Vendors",
            *(self._format_vendor_markdown(vendor) for vendor in result.ahmedabad_vendors),
            "",
            "### Tier 2: India-Based Vendors (Outside Ahmedabad)",
            *(self._format_vendor_markdown(vendor) for vendor in result.india_vendors),
            "",
            "### Tier 3: International / Global Vendors",
            *(self._format_vendor_markdown(vendor) for vendor in result.global_vendors),
            "",
        ]

    @staticmethod
    def _format_vendor_markdown(vendor: EvaluatedVendor) -> str:
        """Helper to format a single vendor's evidence block in markdown."""
        ev = vendor.evidence
        facts = "\n".join(f"  - {fact}" for fact in ev.sourced_facts)
        assumptions = "\n".join(f"  - {assumption}" for assumption in ev.assumptions)
        rfq = "\n".join(f"  - {rfq_item}" for rfq_item in ev.needs_confirmation_rfq)
        notes_line = f"- **Technical Audit Notes**: {ev.evaluation_notes}\n" if ev.evaluation_notes else ""

        return (
            f"#### Rank {vendor.rank} (Overall #{vendor.global_rank}): {vendor.vendor_name} ({vendor.confidence_score}% Confidence)\n"
            f"- **Location**: {vendor.location}, {vendor.country}\n"
            f"- **Vendor Type**: {vendor.vendor_type.value}\n"
            f"- **Match Precision**: `{vendor.match_category.value}`\n"
            f"- **Website**: [{vendor.vendor_name}]({ev.source_url})\n"
            f"- **Contact**: Email: {ev.contact_email or 'N/A'}, Phone: {ev.contact_phone or 'N/A'}\n"
            f"{notes_line}"
            f"- **Sourced Evidence**:\n{facts}\n"
            f"- **Engineering Assumptions**:\n{assumptions}\n"
            f"- **RFQ Confirmation Items**:\n{rfq}\n"
            f"- **Recommended Next Step**: {vendor.recommended_next_step}\n"
        )

    @staticmethod
    def _build_csv_row_dict(material_id: str, vendor: EvaluatedVendor) -> Dict[str, Any]:
        """Construct dictionary representation of evaluated vendor for CSV export."""
        return {
            "material_id": material_id,
            "tier": vendor.tier.value,
            "rank": vendor.rank,
            "vendor_name": vendor.vendor_name,
            "location": vendor.location,
            "country": vendor.country,
            "vendor_type": vendor.vendor_type.value,
            "match_category": vendor.match_category.value,
            "confidence_score": vendor.confidence_score,
            "global_rank": vendor.global_rank,
            "contact_email": vendor.evidence.contact_email or "",
            "contact_phone": vendor.evidence.contact_phone or "",
            "source_url": vendor.evidence.source_url,
            "recommended_next_step": vendor.recommended_next_step,
        }

    def to_csv(self, result: ProcurementResult) -> str:
        """Format vendor evaluations across all three tiers into standard CSV."""
        output = io.StringIO()
        fieldnames = [
            "material_id", "tier", "rank", "vendor_name", "location", "country",
            "vendor_type", "match_category", "confidence_score", "global_rank",
            "contact_email", "contact_phone", "source_url", "recommended_next_step",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        all_vendors = result.ahmedabad_vendors + result.india_vendors + result.global_vendors
        for vendor in all_vendors:
            writer.writerow(self._build_csv_row_dict(result.material_id, vendor))

        return output.getvalue()

    def to_json(self, result: ProcurementResult) -> str:
        """Serialize complete ProcurementResult to indented JSON."""
        return json.dumps(result.model_dump(), indent=2)
