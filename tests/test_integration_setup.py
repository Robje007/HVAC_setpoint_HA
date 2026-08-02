"""End-to-end setup test for the custom integration."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hvac_setpoint_curve.const import (
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_SENSOR_ONLY,
    DOMAIN,
    SERVICE_SET_CURVE,
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
    integration_sensors = [
        state for state in hass.states.async_all("sensor") if state.attributes.get("config_entry_id") == entry.entry_id
    ]
    assert len(integration_sensors) == 1
    assert entity_registry.async_get(legacy_entity.entity_id) is None
