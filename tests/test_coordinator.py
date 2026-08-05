"""Tests for coordinator control behavior."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.climate import HVACMode
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hvac_setpoint_curve.const import (
    CONF_CONTROLLER_ENABLED,
    CONF_COOLING_CLIMATE,
    CONF_COOLING_CURVE_POINTS,
    CONF_COOLING_NIGHT_OFFSET,
    CONF_COOLING_OFF_THRESHOLD,
    CONF_COOLING_ON_THRESHOLD,
    CONF_HEATING_CLIMATE,
    CONF_HEATING_CURVE_POINTS,
    CONF_HEATING_NIGHT_OFFSET,
    CONF_INDOOR_SETTLING_HOURS,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_NIGHT_MODE,
    CONF_OPPOSITE_ENTITY_INTERLOCK,
    CONF_OUTDOOR_AVERAGING_HOURS,
    CONF_OUTDOOR_TEMP_SENSOR,
    DOMAIN,
)
from custom_components.hvac_setpoint_curve.coordinator import (
    HvacCurveData,
    HvacSetpointCoordinator,
    _time_weighted_average,
)

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


async def test_interlock_turns_off_separate_cooling_before_heating(hass) -> None:
    """An enabled interlock prevents separate equipment from opposing a heat demand."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: "climate.cooler",
            CONF_HEATING_CLIMATE: "climate.heater",
            CONF_OPPOSITE_ENTITY_INTERLOCK: True,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set("climate.cooler", HVACMode.COOL, {"temperature": 22.0})
    hass.states.async_set("climate.heater", HVACMode.OFF, {"temperature": 20.0})
    data = HvacCurveData(
        cooling_active=False,
        heating_active=True,
        cooling_target_setpoint=22.0,
        heating_target_setpoint=20.0,
    )

    calls = []
    _register_climate_services(hass, calls)
    await coordinator._apply_control_states(coordinator.merged_options, data)
    await hass.async_block_till_done()

    assert calls[0].data == {"entity_id": "climate.cooler", "hvac_mode": HVACMode.OFF}
    assert calls[1].data == {"entity_id": "climate.heater", "hvac_mode": HVACMode.HEAT}


async def test_disabled_interlock_never_turns_off_separate_entity(hass) -> None:
    """Existing installations retain setpoint-only behavior unless interlock is enabled."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: "climate.cooler",
            CONF_HEATING_CLIMATE: "climate.heater",
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set("climate.cooler", HVACMode.COOL, {"temperature": 22.0})
    hass.states.async_set("climate.heater", HVACMode.OFF, {"temperature": 20.0})
    data = HvacCurveData(
        cooling_active=False,
        heating_active=True,
        cooling_target_setpoint=22.0,
        heating_target_setpoint=20.0,
    )

    calls = []
    _register_climate_services(hass, calls)
    await coordinator._apply_control_states(coordinator.merged_options, data)
    await hass.async_block_till_done()

    assert all(call.data.get("hvac_mode") != HVACMode.OFF for call in calls)


@pytest.mark.parametrize(
    ("mode", "climate_key", "step", "calculated", "expected"),
    [
        (HVACMode.HEAT, CONF_HEATING_CLIMATE, 0.5, 20.3, 20.5),
        (HVACMode.COOL, CONF_COOLING_CLIMATE, 1.0, 23.6, 24.0),
    ],
)
async def test_target_matches_climate_temperature_step(hass, mode, climate_key, step, calculated, expected) -> None:
    """Heating and cooling targets use the linked entity's supported increment."""

    entity_id = "climate.test_unit"
    entry = MockConfigEntry(domain=DOMAIN, data={climate_key: entity_id})
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {
            "temperature": 19.0,
            "target_temp_step": step,
            "min_temp": 16.0,
            "max_temp": 30.0,
        },
    )

    calls = []
    _register_climate_services(hass, calls)
    await coordinator._apply_climate_control(entity_id, mode, True, calculated)
    await hass.async_block_till_done()

    assert calls[-1].data["temperature"] == expected


async def test_target_is_clamped_to_climate_temperature_range(hass) -> None:
    """A calculated target cannot exceed the linked climate entity's limits."""

    entity_id = "climate.test_unit"
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_COOLING_CLIMATE: entity_id})
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {"temperature": 19.0, "target_temp_step": 0.5, "min_temp": 16.0, "max_temp": 22.0},
    )

    calls = []
    _register_climate_services(hass, calls)
    await coordinator._apply_climate_control(entity_id, HVACMode.COOL, True, 24.3)
    await hass.async_block_till_done()

    assert calls[-1].data["temperature"] == 22.0


async def test_inactive_session_updates_target_without_turning_climate_off(hass) -> None:
    """An inactive curve session leaves mode control to the device thermostat."""

    entity_id = "climate.test_unit"
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_COOLING_CLIMATE: entity_id})
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set(entity_id, HVACMode.COOL, {"temperature": 21.0})

    calls = []
    _register_climate_services(hass, calls)
    await coordinator._apply_climate_control(entity_id, HVACMode.COOL, False, 24.0)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].service == "set_temperature"
    assert calls[0].data["temperature"] == 24.0
    assert all(call.data.get("hvac_mode") != HVACMode.OFF for call in calls)


async def test_disabled_controller_calculates_target_without_controlling_hvac(hass) -> None:
    """Pausing control keeps calculations but sends no HVAC commands."""

    entity_id = "climate.test_unit"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: entity_id,
            CONF_CONTROLLER_ENABLED: False,
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    coordinator.data = HvacCurveData(cooling_active=True)
    hass.states.async_set("sensor.outdoor_temperature", 30.0)
    hass.states.async_set(entity_id, HVACMode.COOL, {"temperature": 21.0})

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.target_setpoint is not None
    assert data.cooling_active is False
    assert data.heating_active is False
    assert calls == []


async def test_disabled_controller_skips_missing_outdoor_failsafe(hass) -> None:
    """A paused controller never turns equipment off through the outdoor fail-safe."""

    entity_id = "climate.test_unit"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: entity_id,
            CONF_CONTROLLER_ENABLED: False,
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    coordinator.data = HvacCurveData(cooling_active=True)
    hass.states.async_set("sensor.outdoor_temperature", "unavailable")
    hass.states.async_set(entity_id, HVACMode.COOL, {"temperature": 21.0})

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.cooling_active is False
    assert calls == []


async def test_cooling_stays_active_during_cold_night_until_indoor_target_is_reached(hass) -> None:
    """A sudden outdoor drop does not stop cooling while the building is still warm."""

    entity_id = "climate.air_conditioner"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: entity_id,
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            CONF_OUTDOOR_AVERAGING_HOURS: 0,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set("sensor.outdoor_temperature", 15.0)
    hass.states.async_set(entity_id, HVACMode.COOL, {"temperature": 22.0, "current_temperature": 25.0})

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.cooling_active is True
    assert data.cooling_indoor_temperature_used == 25.0
    assert data.cooling_indoor_temperature_source == entity_id
    assert all(call.data.get("hvac_mode") != HVACMode.OFF for call in calls)


async def test_cooling_waits_for_stability_and_resets_timer_after_rebound(hass, monkeypatch) -> None:
    """Residual heat resets settling before the curve session becomes inactive."""

    entity_id = "climate.air_conditioner"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: entity_id,
            CONF_COOLING_CURVE_POINTS: [
                {"outdoor_temp": -10.0, "setpoint": 22.0},
                {"outdoor_temp": 32.0, "setpoint": 22.0},
            ],
            CONF_COOLING_OFF_THRESHOLD: 16.0,
            CONF_COOLING_ON_THRESHOLD: 17.0,
            CONF_INDOOR_SETTLING_HOURS: 2.0,
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            CONF_OUTDOOR_AVERAGING_HOURS: 0,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    coordinator.data = HvacCurveData(cooling_active=True)
    now = [datetime(2026, 8, 3, 22, tzinfo=UTC)]
    monkeypatch.setattr(
        "custom_components.hvac_setpoint_curve.coordinator.dt_util.utcnow",
        lambda: now[0],
    )
    hass.states.async_set("sensor.outdoor_temperature", 15.0)
    hass.states.async_set(entity_id, HVACMode.COOL, {"temperature": 22.0, "current_temperature": 22.0})

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.cooling_active is True
    assert data.cooling_stabilizing is True

    coordinator.data = data
    now[0] += timedelta(hours=1)
    hass.states.async_set(entity_id, HVACMode.COOL, {"temperature": 22.0, "current_temperature": 24.0})
    data = await coordinator._async_update_data()

    assert data.cooling_active is True
    assert data.cooling_stabilizing is False

    coordinator.data = data
    now[0] += timedelta(minutes=5)
    hass.states.async_set(entity_id, HVACMode.COOL, {"temperature": 22.0, "current_temperature": 22.0})
    data = await coordinator._async_update_data()
    assert data.cooling_stabilizing is True

    coordinator.data = data
    now[0] += timedelta(hours=2)
    data = await coordinator._async_update_data()

    assert data.cooling_active is False
    assert data.cooling_stabilizing is False
    assert all(call.data.get("hvac_mode") != HVACMode.OFF for call in calls)


async def test_cooling_thermostat_retains_mode_when_room_is_below_target(hass) -> None:
    """The device thermostat, not this controller, cycles cooling around its target."""

    entity_id = "climate.air_conditioner"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: entity_id,
            CONF_COOLING_CURVE_POINTS: [
                {"outdoor_temp": -10.0, "setpoint": 24.0},
                {"outdoor_temp": 20.0, "setpoint": 24.0},
                {"outdoor_temp": 40.0, "setpoint": 24.0},
            ],
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            CONF_OUTDOOR_AVERAGING_HOURS: 0,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set("sensor.outdoor_temperature", 30.0)
    hass.states.async_set(entity_id, HVACMode.COOL, {"temperature": 24.0, "current_temperature": 22.9})

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.cooling_active is True
    assert data.cooling_stabilizing is False
    assert all(call.data.get("hvac_mode") != HVACMode.OFF for call in calls)


async def test_heating_thermostat_retains_mode_when_room_is_above_target(hass) -> None:
    """The device thermostat, not this controller, cycles heating around its target."""

    entity_id = "climate.heater"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HEATING_CLIMATE: entity_id,
            CONF_HEATING_CURVE_POINTS: [
                {"outdoor_temp": -10.0, "setpoint": 20.0},
                {"outdoor_temp": 10.0, "setpoint": 20.0},
                {"outdoor_temp": 30.0, "setpoint": 20.0},
            ],
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            CONF_OUTDOOR_AVERAGING_HOURS: 0,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set("sensor.outdoor_temperature", 10.0)
    hass.states.async_set(entity_id, HVACMode.HEAT, {"temperature": 20.0, "current_temperature": 21.1})

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.heating_active is True
    assert data.heating_stabilizing is False
    assert all(call.data.get("hvac_mode") != HVACMode.OFF for call in calls)


async def test_cooling_start_requires_outdoor_permission_and_indoor_demand(hass) -> None:
    """A new cooling cycle starts only when both outdoor and indoor conditions require it."""

    entity_id = "climate.air_conditioner"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: entity_id,
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            CONF_OUTDOOR_AVERAGING_HOURS: 0,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set("sensor.outdoor_temperature", 30.0)
    hass.states.async_set(entity_id, HVACMode.OFF, {"temperature": 24.0, "current_temperature": 26.0})

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.cooling_active is True


async def test_heating_stays_active_during_warm_afternoon_until_indoor_target_is_reached(hass) -> None:
    """A sudden outdoor rise does not stop heating while the building is still cold."""

    entity_id = "climate.heater"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HEATING_CLIMATE: entity_id,
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            CONF_OUTDOOR_AVERAGING_HOURS: 0,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    coordinator.data = HvacCurveData(heating_active=True)
    hass.states.async_set("sensor.outdoor_temperature", 25.0)
    hass.states.async_set(entity_id, HVACMode.HEAT, {"temperature": 18.0, "current_temperature": 17.0})

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.heating_active is True
    assert data.heating_indoor_temperature_used == 17.0
    assert data.heating_indoor_temperature_source == entity_id
    assert all(call.data.get("hvac_mode") != HVACMode.OFF for call in calls)


async def test_heating_only_entry_exposes_heating_target_while_idle(hass) -> None:
    """A heating-only entry never displays the unrelated cooling target."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HEATING_CLIMATE: "climate.heater",
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            CONF_OUTDOOR_AVERAGING_HOURS: 0,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set("sensor.outdoor_temperature", 20.0)
    hass.states.async_set("climate.heater", HVACMode.OFF, {"current_temperature": 20.0})

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()

    assert data.heating_active is False
    assert data.target_setpoint == data.heating_target_setpoint
    assert data.target_setpoint != data.cooling_target_setpoint


async def test_night_mode_applies_independent_offsets_after_curve_calculation(hass) -> None:
    """Night mode adjusts effective targets without changing the underlying curves."""

    constant_curve = [
        {"outdoor_temp": 0.0, "setpoint": 22.0},
        {"outdoor_temp": 20.0, "setpoint": 22.0},
        {"outdoor_temp": 40.0, "setpoint": 22.0},
    ]
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: "climate.cooler",
            CONF_HEATING_CLIMATE: "climate.heater",
            CONF_COOLING_CURVE_POINTS: constant_curve,
            CONF_HEATING_CURVE_POINTS: constant_curve,
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            CONF_OUTDOOR_AVERAGING_HOURS: 0,
            CONF_NIGHT_MODE: True,
            CONF_COOLING_NIGHT_OFFSET: 1.0,
            CONF_HEATING_NIGHT_OFFSET: -1.5,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set("sensor.outdoor_temperature", 20.0)
    hass.states.async_set("climate.cooler", HVACMode.OFF, {"current_temperature": 22.0})
    hass.states.async_set("climate.heater", HVACMode.OFF, {"current_temperature": 22.0})

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()

    assert data.night_mode is True
    assert data.cooling_curve_setpoint == 22.0
    assert data.heating_curve_setpoint == 22.0
    assert data.cooling_target_setpoint == 23.0
    assert data.heating_target_setpoint == 20.5


async def test_shared_heat_pump_keeps_current_mode_when_sessions_overlap(hass) -> None:
    """A shared unit never receives conflicting heat and cool decisions."""

    constant_curve = [
        {"outdoor_temp": 0.0, "setpoint": 22.0},
        {"outdoor_temp": 20.0, "setpoint": 22.0},
        {"outdoor_temp": 40.0, "setpoint": 22.0},
    ]
    entity_id = "climate.heat_pump"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: entity_id,
            CONF_HEATING_CLIMATE: entity_id,
            CONF_COOLING_CURVE_POINTS: constant_curve,
            CONF_HEATING_CURVE_POINTS: constant_curve,
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            CONF_OUTDOOR_AVERAGING_HOURS: 0,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    coordinator.data = HvacCurveData(cooling_active=True, heating_active=True)
    hass.states.async_set("sensor.outdoor_temperature", 21.0)
    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {"temperature": 22.0, "current_temperature": 22.0},
    )

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.cooling_active is True
    assert data.heating_active is False
    assert all(call.data.get("hvac_mode") != HVACMode.HEAT for call in calls)


async def test_explicit_indoor_sensor_overrides_climate_temperature(hass) -> None:
    """A configured indoor sensor takes priority over climate current_temperature."""

    entity_id = "climate.air_conditioner"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: entity_id,
            CONF_INDOOR_TEMP_SENSOR: "sensor.room_temperature",
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            CONF_OUTDOOR_AVERAGING_HOURS: 0,
        },
    )
    entry.add_to_hass(hass)
    coordinator = HvacSetpointCoordinator(hass, entry)
    hass.states.async_set("sensor.outdoor_temperature", 30.0)
    hass.states.async_set("sensor.room_temperature", 26.0)
    hass.states.async_set(entity_id, HVACMode.OFF, {"temperature": 24.0, "current_temperature": 20.0})

    calls = []
    _register_climate_services(hass, calls)
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert data.cooling_active is True
    assert data.cooling_indoor_temperature_used == 26.0
    assert data.cooling_indoor_temperature_source == "sensor.room_temperature"


def test_outdoor_temperature_uses_time_weighted_moving_average() -> None:
    """Brief outdoor changes are smoothed without event-frequency bias."""

    samples = deque()
    start = datetime(2026, 8, 3, 18, tzinfo=UTC)

    assert _time_weighted_average(samples, 30.0, 3.0, start) == 30.0
    assert _time_weighted_average(samples, 15.0, 3.0, start + timedelta(hours=1)) == 30.0
    assert _time_weighted_average(samples, 15.0, 3.0, start + timedelta(hours=2)) == 22.5
    assert _time_weighted_average(samples, 15.0, 3.0, start + timedelta(hours=4)) == 15.0


async def test_missing_explicit_outdoor_sensor_leaves_control_unchanged(hass) -> None:
    """An unavailable outdoor sensor never causes an HVAC off command."""

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

    assert data.cooling_active is True
    assert calls == []


async def test_legacy_missing_outdoor_option_is_ignored_safely(hass) -> None:
    """A stored legacy fail-safe option cannot turn HVAC equipment off."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COOLING_CLIMATE: "climate.heat_pump",
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
            "turn_off_when_outdoor_unavailable": True,
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
