"""Pure curve math for HVAC Setpoint Curve."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise

from .const import MAX_CURVE_POINTS, MIN_CURVE_POINTS


@dataclass(frozen=True, slots=True)
class CurvePoint:
    """A single outdoor-temperature to setpoint mapping."""

    outdoor_temp: float
    setpoint: float


def parse_curve_points(points: Iterable[dict[str, float] | CurvePoint]) -> list[CurvePoint]:
    """Parse and sort curve points from config-friendly dictionaries."""

    parsed: list[CurvePoint] = []
    for point in points:
        if isinstance(point, CurvePoint):
            parsed.append(point)
        else:
            parsed.append(
                CurvePoint(
                    outdoor_temp=float(point["outdoor_temp"]),
                    setpoint=float(point["setpoint"]),
                )
            )

    validate_curve_points(parsed)
    return sorted(parsed, key=lambda item: item.outdoor_temp)


def serialize_curve_points(points: Sequence[CurvePoint]) -> list[dict[str, float]]:
    """Serialize points for config entry storage."""

    return [
        {"outdoor_temp": point.outdoor_temp, "setpoint": point.setpoint}
        for point in sorted(points, key=lambda item: item.outdoor_temp)
    ]


def validate_curve_points(points: Sequence[CurvePoint]) -> None:
    """Validate point count and duplicate outdoor temperatures."""

    if not MIN_CURVE_POINTS <= len(points) <= MAX_CURVE_POINTS:
        raise ValueError(f"Curve must contain {MIN_CURVE_POINTS}-{MAX_CURVE_POINTS} points")

    outdoor_temps = [point.outdoor_temp for point in points]
    if len(outdoor_temps) != len(set(outdoor_temps)):
        raise ValueError("Curve points must have unique outdoor temperatures")


def interpolate_setpoint(points: Iterable[dict[str, float] | CurvePoint], outdoor_temp: float) -> float:
    """Return a setpoint using flat ends and linear interpolation between points."""

    parsed = parse_curve_points(points)
    temp = float(outdoor_temp)

    if temp <= parsed[0].outdoor_temp:
        return parsed[0].setpoint

    if temp >= parsed[-1].outdoor_temp:
        return parsed[-1].setpoint

    for lower, upper in pairwise(parsed):
        if lower.outdoor_temp <= temp <= upper.outdoor_temp:
            span = upper.outdoor_temp - lower.outdoor_temp
            ratio = (temp - lower.outdoor_temp) / span
            return lower.setpoint + ratio * (upper.setpoint - lower.setpoint)

    return parsed[-1].setpoint


def humidity_offset(humidity: float | None) -> float:
    """Apply a small comfort offset for high humidity.

    The first release intentionally keeps this conservative and transparent:
    no offset below 60%, then +0.1 C for each 5% RH above 60%, capped at +0.8 C.
    """

    if humidity is None or humidity <= 60:
        return 0.0
    return min(0.8, ((float(humidity) - 60.0) / 5.0) * 0.1)


def computed_setpoint(
    points: Iterable[dict[str, float] | CurvePoint],
    outdoor_temp: float,
    humidity: float | None = None,
) -> float:
    """Return the final setpoint with humidity adjustment."""

    return round(interpolate_setpoint(points, outdoor_temp) + humidity_offset(humidity), 1)
