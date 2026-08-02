"""Pure hysteresis decisions for HVAC Setpoint Curve."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HysteresisResult:
    """Result of one hysteresis decision."""

    active: bool
    changed: bool


def decide_cooling(outdoor_temp: float, active: bool, on_above: float, off_below: float) -> HysteresisResult:
    """Cooling turns on above the outdoor high threshold and off below the outdoor low threshold."""

    if not active and outdoor_temp > on_above:
        return HysteresisResult(True, True)
    if active and outdoor_temp < off_below:
        return HysteresisResult(False, True)
    return HysteresisResult(active, False)


def decide_heating(outdoor_temp: float, active: bool, on_below: float, off_above: float) -> HysteresisResult:
    """Heating turns on below the outdoor low threshold and off above the outdoor high threshold."""

    if not active and outdoor_temp < on_below:
        return HysteresisResult(True, True)
    if active and outdoor_temp > off_above:
        return HysteresisResult(False, True)
    return HysteresisResult(active, False)
