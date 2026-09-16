"""Export service generating Markdown, CSV, and JSON representations of procurement results."""

import csv
import io
import json
from typing import List

from app.domain.models import (
    AmbiguityItem,
    AmbiguityType,
    EvaluatedVendor,
    ProcurementResult,
)


class ExportService:
    """Service to format and serialize ProcurementResult into standard artifacts."""

    def to_markdown(self, result: ProcurementResult) -> str:
        """Render result as an evidence-based, human-readable Markdown report."""
        spec = result.specification
        raw = spec.raw_input

        has_unit_ambiguity = any(
            a.ambiguity_type == AmbiguityType.UNSPECIFIED_QUANTITY_UNIT
            for a in spec.ambiguities
        )
        unit_suffix = " *(unit unspecified in input)*" if has_unit_ambiguity else f" {spec.assumed_quantity_unit}"

        lines: List[str] = [
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

        lines.extend(self._format_ambiguities_markdown(spec.ambiguities))
        lines.extend(self._format_vendor_shortlist_markdown(result))

        if result.llm_synthesis:
            lines.extend([
                f"## 4. LLM Executive Procurement Reasoning (Provider: {result.model_provider or 'active'})",
                result.llm_synthesis,
                "",
            ])

        lines.extend([
            "## 5. Audit Trail and Agentic State Transitions",
            *(f"- `{entry}`" for entry in result.audit_trail),
        ])
        return "\n".join(lines)

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

    def _format_vendor_shortlist_markdown(self, result: ProcurementResult) -> List[str]:
        """Format 3-tier vendor shortlists."""
        return [
            "## 3. Evidence-Based Vendor Shortlist",
            "",
            "### Tier 1: Ahmedabad Local Vendors",
            *(self._format_vendor_markdown(v) for v in result.ahmedabad_vendors),
            "",
            "### Tier 2: India-Based Vendors (Outside Ahmedabad)",
            *(self._format_vendor_markdown(v) for v in result.india_vendors),
            "",
            "### Tier 3: International / Global Vendors",
            *(self._format_vendor_markdown(v) for v in result.global_vendors),
            "",
        ]

    @staticmethod
    def _format_vendor_markdown(vendor: EvaluatedVendor) -> str:
        """Helper to format a single vendor's evidence block in markdown."""
        ev = vendor.evidence
        facts = "\n".join(f"  - {f}" for f in ev.sourced_facts)
        assumptions = "\n".join(f"  - {a}" for a in ev.assumptions)
        rfq = "\n".join(f"  - {r}" for r in ev.needs_confirmation_rfq)
        notes_line = f"- **Technical Audit Notes**: {ev.evaluation_notes}\n" if ev.evaluation_notes else ""

        return (
            f"#### Rank {vendor.rank}: {vendor.vendor_name} ({vendor.confidence_score}% Confidence)\n"
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

    def to_csv(self, result: ProcurementResult) -> str:
        """Format vendor evaluations across all three tiers into standard CSV."""
        output = io.StringIO()
        fieldnames = [
            "material_id",
            "tier",
            "rank",
            "vendor_name",
            "location",
            "country",
            "vendor_type",
            "match_category",
            "confidence_score",
            "contact_email",
            "contact_phone",
            "source_url",
            "recommended_next_step",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        all_vendors = result.ahmedabad_vendors + result.india_vendors + result.global_vendors
        for v in all_vendors:
            writer.writerow({
                "material_id": result.material_id,
                "tier": v.tier.value,
                "rank": v.rank,
                "vendor_name": v.vendor_name,
                "location": v.location,
                "country": v.country,
                "vendor_type": v.vendor_type.value,
                "match_category": v.match_category.value,
                "confidence_score": v.confidence_score,
                "contact_email": v.evidence.contact_email or "",
                "contact_phone": v.evidence.contact_phone or "",
                "source_url": v.evidence.source_url,
                "recommended_next_step": v.recommended_next_step,
            })

        return output.getvalue()

    def to_json(self, result: ProcurementResult) -> str:
        """Serialize complete ProcurementResult to indented JSON."""
        return json.dumps(result.model_dump(), indent=2)
