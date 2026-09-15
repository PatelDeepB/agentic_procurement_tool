"""Command-line interface (CLI) for running agentic procurement evaluations.

Supports batch execution of demonstration materials (M-01, M-02, M-03),
custom material input, and automated file exports (Markdown, CSV, JSON).
"""

import argparse
from pathlib import Path
import sys
from typing import List

from app.domain.models import MaterialInput, ProcurementResult
from app.services.export_service import ExportService
from app.services.procurement_service import ProcurementService


def parse_arguments() -> argparse.Namespace:
    """Parse terminal command-line options."""
    parser = argparse.ArgumentParser(
        description="Agentic Procurement Tool CLI - Evaluate industrial material vendors across geographic tiers."
    )
    parser.add_argument(
        "--material",
        choices=["M-01", "M-02", "M-03", "all"],
        help="Run preconfigured demonstration material (M-01, M-02, M-03, or 'all')",
    )
    parser.add_argument("--id", help="Custom material ID (e.g. C-01)")
    parser.add_argument("--desc", help="Custom material description (e.g. 'DN 50 ERW pipe')")
    parser.add_argument("--quantity", type=float, help="Custom quantity required")
    parser.add_argument("--location", default="Ahmedabad, Gujarat, India", help="Delivery destination")
    parser.add_argument(
        "--export",
        choices=["md", "csv", "json", "all"],
        help="Export generated evaluation results to files in output/ directory",
    )
    return parser.parse_args()


def display_result_summary(result: ProcurementResult) -> None:
    """Print clean terminal summary of evaluation and ambiguities."""
    spec = result.specification
    print("\n" + "=" * 70)
    print(f"PROCUREMENT EVALUATION: {result.material_id} - {spec.raw_input.material}")
    print("=" * 70)
    print(f"Location: {result.location} | Quantity: {spec.raw_input.quantity}")

    if spec.ambiguities:
        print("\n[!] DETECTED AMBIGUITIES & STATED ASSUMPTIONS:")
        for amb in spec.ambiguities:
            print(f"  * [{amb.severity.value}] {amb.ambiguity_type.value}: {amb.description}")
            print(f"    -> Stated Assumption: {amb.stated_assumption}")
            print(f"    -> Buyer Prompt: {amb.clarification_prompt}")

    print("\n[+] SHORTLISTED VENDORS BY TIER:")
    print(f"  1. Ahmedabad Local: {len(result.ahmedabad_vendors)} vendors")
    for v in result.ahmedabad_vendors:
        print(f"     - Rank {v.rank}: {v.vendor_name} | Score: {v.confidence_score}% | {v.match_category.value}")

    print(f"  2. India-wide: {len(result.india_vendors)} vendors")
    for v in result.india_vendors:
        print(f"     - Rank {v.rank}: {v.vendor_name} | Score: {v.confidence_score}% | {v.match_category.value}")

    print(f"  3. Global: {len(result.global_vendors)} vendors")
    for v in result.global_vendors:
        print(f"     - Rank {v.rank}: {v.vendor_name} | Score: {v.confidence_score}% | {v.match_category.value}")


def export_result_files(
    result: ProcurementResult,
    export_format: str,
    output_dir: Path,
    exporter: ExportService,
) -> None:
    """Save evaluation results to disk in specified formats."""
    output_dir.mkdir(parents=True, exist_ok=True)
    mat_id = result.material_id

    if export_format in ["md", "all"]:
        md_file = output_dir / f"{mat_id}_evaluation.md"
        md_file.write_text(exporter.to_markdown(result), encoding="utf-8")
        print(f"  -> Saved Markdown report: {md_file}")

    if export_format in ["csv", "all"]:
        csv_file = output_dir / f"{mat_id}_vendors.csv"
        csv_file.write_text(exporter.to_csv(result), encoding="utf-8")
        print(f"  -> Saved CSV export: {csv_file}")

    if export_format in ["json", "all"]:
        json_file = output_dir / f"{mat_id}_result.json"
        json_file.write_text(exporter.to_json(result), encoding="utf-8")
        print(f"  -> Saved JSON result: {json_file}")


def main() -> None:
    """CLI execution entrypoint."""
    args = parse_arguments()
    service = ProcurementService()
    exporter = ExportService()
    output_dir = Path("output")

    inputs_to_run: List[MaterialInput] = []

    if args.material == "all":
        inputs_to_run.extend(service.get_default_demonstrations())
    elif args.material:
        inputs_to_run = [d for d in service.get_default_demonstrations() if d.id == args.material]
    elif args.desc and args.quantity:
        inputs_to_run.append(
            MaterialInput(
                id=args.id or "CUSTOM-01",
                material=args.desc,
                quantity=args.quantity,
                location=args.location,
            )
        )
    else:
        print("Please provide --material [M-01|M-02|M-03|all] or custom inputs (--desc and --quantity).")
        sys.exit(1)

    for item in inputs_to_run:
        result = service.execute_procurement(item)
        display_result_summary(result)
        if args.export:
            print("\n[+] EXPORTING ARTIFACTS:")
            export_result_files(result, args.export, output_dir, exporter)

    print("\nProcurement evaluation completed successfully.")


if __name__ == "__main__":
    main()
