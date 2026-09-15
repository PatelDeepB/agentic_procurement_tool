"""Export service generating Markdown, CSV, and JSON representations of procurement results."""

import csv
import io
import json
from typing import List

from app.domain.models import EvaluatedVendor, ProcurementResult


class ExportService:
    """Service to format and serialize ProcurementResult into standard artifacts."""

    def to_markdown(self, result: ProcurementResult) -> str:
        """Render result as an evidence-based, human-readable Markdown report."""
        spec = result.specification
        raw = spec.raw_input

        lines: List[str] = [
            f"# Procurement Evaluation Report: {raw.id}",
            "",
            "## 1. Requirement Summary",
            f"- **Material ID**: {raw.id}",
            f"- **Material Description**: {raw.material}",
            f"- **Specified Quantity**: {raw.quantity} *(unit unspecified in input)*",
            f"- **Procurement Location**: {raw.location}",
            f"- **Run ID**: `{result.run_id}`",
            f"- **Evaluation Timestamp**: {result.timestamp}",
            "",
            "## 2. Technical Ambiguities and Stated Assumptions",
        ]

        if not spec.ambiguities:
            lines.append("No technical ambiguities identified.")
        else:
            for item in spec.ambiguities:
                lines.extend([
                    f"### [{item.severity.value}] {item.ambiguity_type.value}",
                    f"- **Issue**: {item.description}",
                    f"- **Agent Assumption**: {item.stated_assumption}",
                    f"- **Buyer Clarification Prompt**: `{item.clarification_prompt}`",
                ])
                if item.unit_conversions:
                    conv = item.unit_conversions
                    if "if_assumed_meters" in conv:
                        lines.append(
                            f"- **Weight & Piece Conversion**: {conv['if_assumed_meters']['estimated_weight_metric_tons']} MT "
                            f"(~{conv['if_assumed_meters']['standard_6m_pieces']} standard 6-meter pieces)."
                        )
                lines.append("")

        lines.extend([
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
            "## 4. Audit Trail and System Reasoning",
        ])
        for step in result.audit_trail:
            lines.append(f"- {step}")

        lines.append("")
        return "\n".join(lines)

    def _format_vendor_markdown(self, vendor: EvaluatedVendor) -> str:
        """Helper to format a single vendor's evidence block in markdown."""
        ev = vendor.evidence
        facts = "\n".join(f"  - {f}" for f in ev.sourced_facts)
        assumptions = "\n".join(f"  - {a}" for a in ev.assumptions)
        rfq = "\n".join(f"  - {r}" for r in ev.needs_confirmation_rfq)

        return (
            f"#### Rank {vendor.rank}: {vendor.vendor_name} ({vendor.confidence_score}% Confidence)\n"
            f"- **Location**: {vendor.location}, {vendor.country}\n"
            f"- **Vendor Type**: {vendor.vendor_type.value}\n"
            f"- **Match Precision**: `{vendor.match_category.value}`\n"
            f"- **Website**: [{vendor.vendor_name}]({ev.source_url})\n"
            f"- **Contact**: Email: {ev.contact_email or 'N/A'}, Phone: {ev.contact_phone or 'N/A'}\n"
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
