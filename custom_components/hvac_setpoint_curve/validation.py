"""Validation helpers for HVAC Setpoint Curve configuration."""

from __future__ import annotations

from typing import Any

from .const import (
    CONF_COOLING_OFF_THRESHOLD,
    CONF_COOLING_ON_THRESHOLD,
    CONF_HEATING_OFF_THRESHOLD,
    CONF_HEATING_ON_THRESHOLD,
    DEFAULT_COOLING_OFF_THRESHOLD,
    DEFAULT_COOLING_ON_THRESHOLD,
    DEFAULT_HEATING_OFF_THRESHOLD,
    DEFAULT_HEATING_ON_THRESHOLD,
)


def threshold_error(
    options: dict[str, Any],
    *,
    cooling_enabled: bool,
    heating_enabled: bool,
) -> str | None:
    """Return an error key when hysteresis thresholds are inconsistent."""

    cooling_on = float(options.get(CONF_COOLING_ON_THRESHOLD, DEFAULT_COOLING_ON_THRESHOLD))
    cooling_off = float(options.get(CONF_COOLING_OFF_THRESHOLD, DEFAULT_COOLING_OFF_THRESHOLD))
    heating_on = float(options.get(CONF_HEATING_ON_THRESHOLD, DEFAULT_HEATING_ON_THRESHOLD))
    heating_off = float(options.get(CONF_HEATING_OFF_THRESHOLD, DEFAULT_HEATING_OFF_THRESHOLD))

    if cooling_enabled and cooling_on <= cooling_off:
        return "invalid_cooling_hysteresis"
    if heating_enabled and heating_off <= heating_on:
        return "invalid_heating_hysteresis"
    if cooling_enabled and heating_enabled and heating_off >= cooling_on:
        return "overlapping_heating_cooling"
    return None
