"""Tests for coordinator control behavior."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.climate import HVACMode
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hvac_setpoint_curve.const import (
    CONF_COOLING_CLIMATE,
    CONF_HEATING_CLIMATE,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
    DOMAIN,
)
from custom_components.hvac_setpoint_curve.coordinator import HvacCurveData, HvacSetpointCoordinator

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _register_climate_services(hass, calls: list) -> None:
    """Register lightweight climate service handlers for coordinator tests."""

    async def _record(call) -> None:
        calls.append(call)

    hass.services.async_register("climate", "set_hvac_mode", _record)
    hass.services.async_register("climate", "set_temperature", _record)


async def test_shared_climate_gets_no_conflicting_off_command(hass) -> None:
    """One heat pump used for both modes receives only the active mode commands."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: "climate.heat_pump",
            CONF_HEATING_CLIMATE: "climate.heat_pump",
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set("climate.heat_pump", HVACMode.OFF, {"temperature": 22.0})
    data = HvacCurveData(
        cooling_active=True,
        heating_active=False,
        cooling_target_setpoint=21.0,
        heating_target_setpoint=21.0,
    )

    calls = []
    _register_climate_services(hass, calls)
    await coordinator._apply_control_states(coordinator.merged_options, data)
    await hass.async_block_till_done()

    modes = [call.data.get("hvac_mode") for call in calls]
    assert modes == [HVACMode.COOL, None]
    assert HVACMode.OFF not in modes


async def test_missing_explicit_outdoor_sensor_turns_control_off(hass) -> None:
    """An unavailable configured outdoor sensor fails safe instead of using indoor temperature."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: "climate.heat_pump",
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    coordinator.data = HvacCurveData(cooling_active=True)
    hass.states.async_set("climate.heat_pump", HVACMode.COOL, {"current_temperature": 25.0})
    hass.states.async_set("sensor.outdoor_temperature", "unavailable")

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.cooling_active is False
    assert len(calls) == 1
    assert calls[0].data["hvac_mode"] == HVACMode.OFF


async def test_missing_outdoor_sensor_can_leave_control_unchanged(hass) -> None:
    """The configurable fail-safe can leave the current HVAC state untouched."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: "climate.heat_pump",
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            CONF_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE: False,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    coordinator.data = HvacCurveData(cooling_active=True)
    hass.states.async_set("climate.heat_pump", HVACMode.COOL, {"current_temperature": 25.0})
    hass.states.async_set("sensor.outdoor_temperature", "unavailable")

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.cooling_active is True
    assert calls == []
