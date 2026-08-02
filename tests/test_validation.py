"""Tests for configuration validation."""

from __future__ import annotations

from custom_components.hvac_setpoint_curve.const import (
    CONF_COOLING_OFF_THRESHOLD,
    CONF_COOLING_ON_THRESHOLD,
    CONF_HEATING_OFF_THRESHOLD,
    CONF_HEATING_ON_THRESHOLD,
)
from custom_components.hvac_setpoint_curve.validation import threshold_error


def test_valid_heating_and_cooling_thresholds() -> None:
    """Separated hysteresis bands are valid."""

    assert threshold_error({}, cooling_enabled=True, heating_enabled=True) is None


def test_cooling_on_must_be_above_cooling_off() -> None:
    """Cooling needs a correctly ordered hysteresis band."""

    options = {CONF_COOLING_ON_THRESHOLD: 22, CONF_COOLING_OFF_THRESHOLD: 23}
    assert threshold_error(options, cooling_enabled=True, heating_enabled=False) == "invalid_cooling_hysteresis"


def test_heating_off_must_be_above_heating_on() -> None:
    """Heating needs a correctly ordered hysteresis band."""

    options = {CONF_HEATING_ON_THRESHOLD: 20, CONF_HEATING_OFF_THRESHOLD: 19}
    assert threshold_error(options, cooling_enabled=False, heating_enabled=True) == "invalid_heating_hysteresis"


def test_heating_and_cooling_ranges_must_not_overlap() -> None:
    """The controller requires a neutral band between heating and cooling."""

    options = {CONF_HEATING_OFF_THRESHOLD: 24, CONF_COOLING_ON_THRESHOLD: 23}
    assert threshold_error(options, cooling_enabled=True, heating_enabled=True) == "overlapping_heating_cooling"
