"""Tests for curve math."""

from __future__ import annotations

import pytest

from custom_components.hvac_setpoint_curve.const import preset_changeovers, preset_curve
from custom_components.hvac_setpoint_curve.curve import (
    CurvePoint,
    computed_setpoint,
    humidity_offset,
    interpolate_setpoint,
    parse_curve_points,
)


def test_flat_before_first_point() -> None:
    """Temperatures below the first point use the first setpoint."""

    assert interpolate_setpoint([CurvePoint(0, 20), CurvePoint(10, 22), CurvePoint(20, 23)], -5) == 20


def test_flat_after_last_point() -> None:
    """Temperatures above the last point use the last setpoint."""

    assert interpolate_setpoint([CurvePoint(0, 20), CurvePoint(10, 22), CurvePoint(20, 23)], 25) == 23


def test_linear_interpolation_between_points() -> None:
    """Temperatures between points are interpolated linearly."""

    assert interpolate_setpoint([CurvePoint(0, 20), CurvePoint(10, 24), CurvePoint(20, 25)], 5) == 22


def test_points_are_sorted_before_interpolation() -> None:
    """Input order does not affect interpolation."""

    points = [
        {"outdoor_temp": 20, "setpoint": 25},
        {"outdoor_temp": 10, "setpoint": 24},
        {"outdoor_temp": 0, "setpoint": 20},
    ]
    assert interpolate_setpoint(points, 5) == 22


def test_duplicate_outdoor_temps_are_rejected() -> None:
    """Duplicate outdoor temperatures make the curve ambiguous."""

    with pytest.raises(ValueError, match="unique"):
        parse_curve_points([CurvePoint(0, 20), CurvePoint(0, 21), CurvePoint(10, 22)])


def test_too_few_points_are_rejected() -> None:
    """A valid curve needs at least three points."""

    with pytest.raises(ValueError, match="3-6"):
        parse_curve_points([CurvePoint(0, 20), CurvePoint(10, 21)])


def test_humidity_offset_is_conservative_and_capped() -> None:
    """Humidity adjustment only applies above 60% and is capped."""

    assert humidity_offset(None) == 0
    assert humidity_offset(60) == 0
    assert humidity_offset(70) == pytest.approx(0.2)
    assert humidity_offset(100) == pytest.approx(0.8)


def test_computed_setpoint_rounds_to_one_decimal() -> None:
    """Final setpoints are rounded for Home Assistant display."""

    points = [CurvePoint(0, 20), CurvePoint(3, 21), CurvePoint(6, 22)]
    assert computed_setpoint(points, 1, 65) == 20.4


def test_humidity_adjustment_can_cool_down_or_heat_up() -> None:
    """High humidity lowers cooling targets and raises heating targets."""

    points = [CurvePoint(0, 22), CurvePoint(10, 22), CurvePoint(20, 22)]
    assert computed_setpoint(points, 10, 70, humidity_direction=-1) == 21.8
    assert computed_setpoint(points, 10, 70, humidity_direction=1) == 22.2


def test_heating_profiles_decrease_toward_mild_weather() -> None:
    """Heating presets do not reuse cooling points at mild outdoor temperatures."""

    for preset in ("comfort", "eco"):
        points = preset_curve(preset, "heating")
        assert points[0]["setpoint"] > points[-1]["setpoint"]


def test_building_profiles_keep_a_realistic_neutral_zone() -> None:
    """Built-in profiles keep heating below cooling and separate seasonal modes."""

    for preset in ("comfort", "eco"):
        heating = preset_curve(preset, "heating")
        cooling = preset_curve(preset, "cooling")
        assert all(heat["setpoint"] < cool["setpoint"] for heat, cool in zip(heating, cooling, strict=True))
        heating_changeover, cooling_changeover = preset_changeovers(preset)
        assert heating_changeover < cooling_changeover
