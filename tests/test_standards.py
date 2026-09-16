"""Unit tests for industrial standards specs and calculations."""

from app.core.standards import (
    calculate_linear_weight_kg_per_meter,
    calculate_piece_count_from_meters,
    calculate_total_weight_metric_tons,
    evaluate_thickness_compliance,
    find_is1239_dn_by_od,
    get_is1239_spec_by_dn,
)


def test_should_calculate_correct_linear_weight():
    """Verify linear mass calculation using formula (OD - t) * t * 0.02466."""
    # Arrange
    od_mm = 60.3
    wall_mm = 4.5

    # Act
    weight = calculate_linear_weight_kg_per_meter(od_mm, wall_mm)

    # Assert: (60.3 - 4.5) * 4.5 * 0.02466 = 55.8 * 4.5 * 0.02466 = 6.192
    assert abs(weight - 6.192) < 0.01


def test_should_calculate_batch_tonnage_correctly():
    """Verify conversion of linear weight and length to metric tons."""
    # Arrange
    linear_weight = 6.192
    meters = 1000.0

    # Act
    total_tons = calculate_total_weight_metric_tons(linear_weight, meters)

    # Assert
    assert total_tons == 6.192


def test_should_calculate_piece_count_for_standard_lengths():
    """Verify estimated piece count based on 6.0m commercial pipes."""
    # Arrange
    meters = 1200.0

    # Act
    pieces = calculate_piece_count_from_meters(meters)

    # Assert: 1200 / 6 = 200 pieces
    assert pieces == 200


def test_should_retrieve_is1239_spec_for_dn50():
    """Verify IS 1239 lookup returns correct standard dimensions for DN 50."""
    # Act
    spec = get_is1239_spec_by_dn(50)

    # Assert
    assert spec is not None
    assert spec["nominal_od_mm"] == 60.3
    assert spec["class_c_thickness_mm"] == 4.5


def test_should_find_dn_from_outside_diameter():
    """Verify tolerance matching from OD to DN."""
    # Act: 89.5 mm is within DN 80 tolerance (87.9 to 89.5)
    dn = find_is1239_dn_by_od(89.5)

    # Assert
    assert dn == 80


def test_should_flag_non_standard_thickness_for_dn50():
    """Verify that 5.5 mm wall thickness is flagged as non-standard for DN 50."""
    # Act
    compliance = evaluate_thickness_compliance(50, 5.5)

    # Assert
    assert compliance["is_standard"] is False
    assert "May require custom rolling" in compliance["deviation_note"]


def test_should_retrieve_is1239_spec_for_dn125_and_dn150():
    """Verify IS 1239 lookup returns correct dimensions for DN 125 and DN 150."""
    # Act
    spec_125 = get_is1239_spec_by_dn(125)
    spec_150 = get_is1239_spec_by_dn(150)

    # Assert
    assert spec_125 is not None
    assert spec_125["nominal_od_mm"] == 139.7
    assert spec_125["class_b_thickness_mm"] == 4.85
    assert spec_150 is not None
    assert spec_150["nominal_od_mm"] == 165.1
    assert spec_150["class_c_thickness_mm"] == 5.4


def test_should_find_dn_from_od_for_large_sizes():
    """Verify tolerance matching from OD to DN for DN 125 and DN 150."""
    # Act
    dn_125 = find_is1239_dn_by_od(140.0)
    dn_150 = find_is1239_dn_by_od(165.5)

    # Assert
    assert dn_125 == 125
    assert dn_150 == 150
