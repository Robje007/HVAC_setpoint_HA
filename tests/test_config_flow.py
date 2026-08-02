"""Config flow smoke tests.

These tests need the Home Assistant pytest plugin. They are skipped in minimal
Python environments but run in a normal custom-component CI setup.
"""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hvac_setpoint_curve.const import (
    CONF_COOLING_CLIMATE,
    CONF_COOLING_CURVE_POINTS,
    CONF_CURVE_POINTS,
    CONF_HEATING_CURVE_POINTS,
    CONF_SENSOR_ONLY,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_config_flow_requires_control_or_sensor_only(hass) -> None:
    """The initial flow rejects an empty control setup."""

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Living room",
            CONF_SENSOR_ONLY: False,
        },
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "missing_control_or_sensor_only"


async def test_config_flow_accepts_climate_entity(hass) -> None:
    """The happy path proceeds from linked entity selection to preset selection."""

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Living room",
            CONF_COOLING_CLIMATE: "climate.living_room",
            CONF_SENSOR_ONLY: False,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "preset"


async def test_options_flow_opens_configuration_menu(hass) -> None:
    """The Configure button opens the options menu on current Home Assistant versions."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={CONF_SENSOR_ONLY: True},
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "menu"
    assert result["step_id"] == "init"


async def test_options_custom_curve_is_saved_for_both_modes(hass) -> None:
    """The single custom editor writes one shared heating and cooling curve."""

    entry = MockConfigEntry(domain=DOMAIN, title="Living room", data={CONF_SENSOR_ONLY: True}, options={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "custom_curve"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "custom_curve"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "point_count": 3,
            "outdoor_temp_1": 0,
            "setpoint_1": 22,
            "outdoor_temp_2": 15,
            "setpoint_2": 21,
            "outdoor_temp_3": 30,
            "setpoint_3": 24,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_CURVE_POINTS] == result["data"][CONF_COOLING_CURVE_POINTS]
    assert result["data"][CONF_CURVE_POINTS] == result["data"][CONF_HEATING_CURVE_POINTS]


async def test_config_flow_rejects_climate_without_cooling_mode(hass) -> None:
    """A heating-only climate entity cannot be selected for cooling control."""

    hass.states.async_set("climate.heater", "off", {"hvac_modes": ["off", "heat"]})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Invalid cooling controller",
            CONF_COOLING_CLIMATE: "climate.heater",
            CONF_SENSOR_ONLY: False,
        },
    )

    assert result["type"] == "form"
    assert result["errors"][CONF_COOLING_CLIMATE] == "unsupported_cooling_mode"
