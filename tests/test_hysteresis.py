"""Tests for hysteresis decisions."""

from __future__ import annotations

from custom_components.hvac_setpoint_curve.hysteresis import decide_cooling, decide_heating


def test_cooling_turns_on_above_on_threshold() -> None:
    """Cooling activates above the outdoor on threshold."""

    result = decide_cooling(outdoor_temp=24.1, active=False, on_above=24.0, off_below=22.5)
    assert result.active is True
    assert result.changed is True


def test_cooling_stays_on_inside_deadband() -> None:
    """Cooling remains active inside the outdoor hysteresis band."""

    result = decide_cooling(outdoor_temp=23.0, active=True, on_above=24.0, off_below=22.5)
    assert result.active is True
    assert result.changed is False


def test_cooling_turns_off_below_off_threshold() -> None:
    """Cooling deactivates below the outdoor off threshold."""

    result = decide_cooling(outdoor_temp=22.4, active=True, on_above=24.0, off_below=22.5)
    assert result.active is False
    assert result.changed is True


def test_heating_turns_on_below_on_threshold() -> None:
    """Heating activates below the outdoor low threshold."""

    result = decide_heating(outdoor_temp=17.9, active=False, on_below=18.0, off_above=19.5)
    assert result.active is True
    assert result.changed is True


def test_heating_stays_on_inside_deadband() -> None:
    """Heating remains active inside the outdoor hysteresis band."""

    result = decide_heating(outdoor_temp=18.8, active=True, on_below=18.0, off_above=19.5)
    assert result.active is True
    assert result.changed is False


def test_heating_turns_off_above_off_threshold() -> None:
    """Heating deactivates above the outdoor high threshold."""

    result = decide_heating(outdoor_temp=19.6, active=True, on_below=18.0, off_above=19.5)
    assert result.active is False
    assert result.changed is True
