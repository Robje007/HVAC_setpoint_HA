"""End-to-end setup test for the custom integration."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hvac_setpoint_curve.const import (
    CONF_CONTROLLER_ENABLED,
    CONF_COOLING_CURVE_POINTS,
    CONF_COOLING_NIGHT_OFFSET,
    CONF_COOLING_PRESET,
    CONF_HEATING_NIGHT_OFFSET,
    CONF_HEATING_PRESET,
    CONF_NIGHT_MODE,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_SENSOR_ONLY,
    DOMAIN,
    PRESETS,
    SERVICE_SET_CURVE,
    SERVICE_SET_PROFILE,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_config_entry_loads_entities_and_service(hass) -> None:
    """A sensor-only entry loads completely on the current Home Assistant version."""

    hass.states.async_set("sensor.outdoor_temperature", 12.0)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={
            CONF_SENSOR_ONLY: True,
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor_temperature",
        },
    )
    entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    legacy_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_cooling_target_setpoint",
        suggested_object_id="living_room_cooling_target_setpoint",
        config_entry=entry,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(DOMAIN, SERVICE_SET_CURVE)
    assert hass.services.has_service(DOMAIN, SERVICE_SET_PROFILE)
    integration_sensors = [
        state for state in hass.states.async_all("sensor") if state.attributes.get("config_entry_id") == entry.entry_id
    ]
    assert len(integration_sensors) == 1
    assert integration_sensors[0].attributes["outdoor_temperature_average"] == 12.0
    assert entity_registry.async_get(legacy_entity.entity_id) is None

    controller_entity_id = entity_registry.async_get_entity_id(
        "switch",
        DOMAIN,
        f"{entry.entry_id}_controller_enabled",
    )
    assert controller_entity_id is not None
    assert hass.states.get(controller_entity_id).state == "on"

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": controller_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_CONTROLLER_ENABLED] is False
    assert hass.states.get(controller_entity_id).state == "off"

    night_mode_entity_id = entity_registry.async_get_entity_id(
        "switch",
        DOMAIN,
        f"{entry.entry_id}_night_mode",
    )
    assert night_mode_entity_id is not None
    assert hass.states.get(night_mode_entity_id).state == "off"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": night_mode_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_NIGHT_MODE] is True
    assert hass.states.get(night_mode_entity_id).state == "on"

    cooling_night_offset_id = entity_registry.async_get_entity_id(
        "number",
        DOMAIN,
        f"{entry.entry_id}_cooling_night_offset",
    )
    heating_night_offset_id = entity_registry.async_get_entity_id(
        "number",
        DOMAIN,
        f"{entry.entry_id}_heating_night_offset",
    )
    assert cooling_night_offset_id is not None
    assert heating_night_offset_id is not None
    assert hass.states.get(cooling_night_offset_id).state == "1.0"
    assert hass.states.get(heating_night_offset_id).state == "1.5"

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": cooling_night_offset_id, "value": 2.0},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": heating_night_offset_id, "value": 2.5},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_COOLING_NIGHT_OFFSET] == 2.0
    assert entry.options[CONF_HEATING_NIGHT_OFFSET] == -2.5

    heating_changeover_id = entity_registry.async_get_entity_id(
        "number",
        DOMAIN,
        f"{entry.entry_id}_heating_on_threshold",
    )
    assert heating_changeover_id is not None
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": heating_changeover_id, "value": 17.0},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert entry.options["heating_on_threshold"] == 17.0
    assert entry.options["heating_off_threshold"] == 18.5

    building_profile_id = entity_registry.async_get_entity_id(
        "select",
        DOMAIN,
        f"{entry.entry_id}_building_profile",
    )
    assert building_profile_id is not None

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": building_profile_id, "option": "Eco / energy saving"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_COOLING_PRESET] == "eco"
    assert entry.options[CONF_HEATING_PRESET] == "eco"
    assert entry.options[CONF_COOLING_CURVE_POINTS] == PRESETS["eco"]["points"]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PROFILE,
        {
            "entry_id": entry.entry_id,
            "heating_points": [
                {"outdoor_temp": 0, "setpoint": 21},
                {"outdoor_temp": 15, "setpoint": 20},
                {"outdoor_temp": 30, "setpoint": 19},
            ],
            "cooling_points": [
                {"outdoor_temp": 0, "setpoint": 24},
                {"outdoor_temp": 15, "setpoint": 24},
                {"outdoor_temp": 30, "setpoint": 25},
            ],
            "heating_changeover": 18,
            "cooling_changeover": 22,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options["preset"] == "custom"
    assert entry.options["heating_on_threshold"] == 18
    assert entry.options["cooling_on_threshold"] == 22
