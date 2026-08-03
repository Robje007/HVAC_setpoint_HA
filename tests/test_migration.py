"""Tests for config-entry migrations."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hvac_setpoint_curve import async_migrate_entry
from custom_components.hvac_setpoint_curve.const import (
    CONF_COOLING_CURVE_POINTS,
    CONF_COOLING_PRESET,
    CONF_CURVE_POINTS,
    CONF_HEATING_CURVE_POINTS,
    CONF_HEATING_PRESET,
    CONF_PRESET,
    DOMAIN,
    PRESET_CUSTOM,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_custom_curves_migrate_to_one_shared_curve(hass) -> None:
    """Version 2 custom entries use the legacy/shared curve for both modes."""

    shared = [
        {"outdoor_temp": 0.0, "setpoint": 22.0},
        {"outdoor_temp": 15.0, "setpoint": 21.0},
        {"outdoor_temp": 30.0, "setpoint": 24.0},
    ]
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={CONF_PRESET: PRESET_CUSTOM, CONF_CURVE_POINTS: shared},
        options={
            CONF_COOLING_CURVE_POINTS: shared,
            CONF_HEATING_CURVE_POINTS: list(reversed(shared)),
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 4
    assert entry.options[CONF_CURVE_POINTS] == shared
    assert entry.options[CONF_COOLING_CURVE_POINTS] == shared
    assert entry.options[CONF_HEATING_CURVE_POINTS] == shared
    assert entry.options[CONF_COOLING_PRESET] == PRESET_CUSTOM
    assert entry.options[CONF_HEATING_PRESET] == PRESET_CUSTOM


async def test_two_point_curve_migrates_to_three_points(hass) -> None:
    """Version 1 curves gain an interpolated midpoint before shared-curve migration."""

    points = [
        {"outdoor_temp": 0.0, "setpoint": 20.0},
        {"outdoor_temp": 20.0, "setpoint": 24.0},
    ]
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_PRESET: PRESET_CUSTOM, CONF_CURVE_POINTS: points},
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 4
    assert entry.options[CONF_CURVE_POINTS][1] == {"outdoor_temp": 10.0, "setpoint": 22.0}
    assert len(entry.options[CONF_CURVE_POINTS]) == 3
