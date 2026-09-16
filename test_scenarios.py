"""Manual scenario tester for the agentic procurement workflow.

Use this file to run custom material requirements against the real orchestration logic
without altering project code. It prints the normalized specification and highlights
ambiguities for review.
"""

from app.domain.models import MaterialInput
from app.agents.orchestrator import ProcurementOrchestrator


def run_scenario(label: str, material: str, quantity: float, location: str = "Ahmedabad, Gujarat, India") -> None:
    """Execute one procurement scenario and print the ambiguous requirement details."""
    req = MaterialInput(
        id=label,
        material=material,
        quantity=quantity,
        location=location,
    )

    result = ProcurementOrchestrator().run_procurement_workflow(req)

    print(f"\n{'=' * 80}")
    print(f"SCENARIO: {label}")
    print(f"Material: {material}")
    print(f"Quantity: {quantity}")
    print(f"Location: {location}")
    print(f"{'=' * 80}")
    print("Ambiguities detected:")

    if not result.specification.ambiguities:
        print("  - None")
    else:
        for amb in result.specification.ambiguities:
            print(f"  - Type: {amb.ambiguity_type.value}")
            print(f"    Severity: {amb.severity.value}")
            print(f"    Description: {amb.description}")
            print(f"    Assumption: {amb.stated_assumption}")
            print(f"    Clarification prompt: {amb.clarification_prompt}")
            if amb.unit_conversions:
                print(f"    Conversions: {amb.unit_conversions}")

    print("\nTier summary:")
    print(f"  Ahmedabad: {len(result.ahmedabad_vendors)}")
    print(f"  India-wide: {len(result.india_vendors)}")
    print(f"  Global: {len(result.global_vendors)}")

    print("\nExecutive synthesis:")
    print(result.llm_synthesis)


if __name__ == "__main__":
    scenarios = [
        (
            "SCENARIO-01",
            "ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239",
            1000.0,
        ),
        (
            "SCENARIO-02",
            "40 mm MS ERW, Class B pipe",
            500.0,
        ),
        (
            "SCENARIO-03",
            "ERW pipe, DN 80, 89.5 x 4.8 mm, IS 1239",
            1200.0,
        ),
        (
            "SCENARIO-04",
            "DN 50 ERW pipe, IS 1239",
            750.0,
        ),
        (
            "SCENARIO-05",
            "40 mm OD MS ERW pipe, Class B",
            300.0,
        ),
    ]

    for label, material, qty, *rest in scenarios:
        location = rest[0] if rest else "Ahmedabad, Gujarat, India"
        run_scenario(label, material, qty, location)
