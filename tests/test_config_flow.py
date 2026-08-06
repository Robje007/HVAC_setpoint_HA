"""Config flow smoke tests.

These tests need the Home Assistant pytest plugin. They are skipped in minimal
Python environments but run in a normal custom-component CI setup.
"""

from __future__ import annotations

import pytest
import voluptuous as vol

pytest.importorskip("homeassistant")

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hvac_setpoint_curve.const import (
    CONF_COOLING_CLIMATE,
    CONF_COOLING_CURVE_POINTS,
    CONF_COOLING_PRESET,
    CONF_HEATING_CLIMATE,
    CONF_HEATING_CURVE_POINTS,
    CONF_HEATING_PRESET,
    CONF_INDOOR_SETTLING_HOURS,
    CONF_INDOOR_START_DELTA,
    CONF_INDOOR_STOP_DELTA,
    CONF_OUTDOOR_AVERAGING_HOURS,
    CONF_SENSOR_ONLY,
    DOMAIN,
    preset_curve,
    preset_name,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def test_aggressive_cooling_preset_has_clear_localized_name() -> None:
    """The aggressive preset has a clear name in both supported languages."""

    assert preset_name("rail_aggressive_cooling", "en") == "Aggressive cooling"
    assert preset_name("rail_aggressive_cooling", "nl-NL") == "Agressieve koeling"
    assert preset_name("eco", "nl") == "Eco / energiebesparing"
    assert preset_name("custom", "nl") == "Aangepast"


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


async def test_config_flow_creates_safe_comfort_profile_without_engineering_steps(hass) -> None:
    """Initial setup needs only equipment and one understandable profile."""

    hass.states.async_set("climate.living_room", "off", {"hvac_modes": ["off", "cool"]})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Living room",
            CONF_COOLING_CLIMATE: "climate.living_room",
            CONF_SENSOR_ONLY: False,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"preset": "comfort"},
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_OUTDOOR_AVERAGING_HOURS] == 3.0
    assert result["data"][CONF_HEATING_CURVE_POINTS] != result["data"][CONF_COOLING_CURVE_POINTS]


async def test_config_flow_filters_climate_entities_by_hvac_mode(hass) -> None:
    """Heating-only entities are not offered by the optional cooling selector."""

    hass.states.async_set("climate.heater", "off", {"hvac_modes": ["off", "heat"]})
    hass.states.async_set("climate.cooler", "off", {"hvac_modes": ["off", "cool"]})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    schema = result["data_schema"].schema
    fields = {marker.schema: value for marker, value in schema.items()}

    assert fields[CONF_COOLING_CLIMATE].config["exclude_entities"] == ["climate.heater"]
    assert fields[CONF_HEATING_CLIMATE].config["exclude_entities"] == ["climate.cooler"]


async def test_options_flow_uses_clearable_suggested_entity_values(hass) -> None:
    """An optional linked entity can be cleared instead of its old value being restored."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={CONF_HEATING_CLIMATE: "climate.heater"},
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "linked_entities"},
    )
    markers = {marker.schema: marker for marker in result["data_schema"].schema}
    heating_marker = markers[CONF_HEATING_CLIMATE]

    assert heating_marker.default is vol.UNDEFINED
    assert heating_marker.description == {"suggested_value": "climate.heater"}


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
    assert result["menu_options"] == ["linked_entities", "preset", "custom_curve", "control_behavior"]


async def test_options_flow_saves_thermal_inertia_settings(hass) -> None:
    """Outdoor averaging and indoor demand deltas are configurable in the UI."""

    entry = MockConfigEntry(domain=DOMAIN, title="Living room", data={CONF_SENSOR_ONLY: True}, options={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "control_behavior"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "control_behavior"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_OUTDOOR_AVERAGING_HOURS: 4.0,
            CONF_INDOOR_START_DELTA: 0.7,
            CONF_INDOOR_STOP_DELTA: 0.3,
            CONF_INDOOR_SETTLING_HOURS: 2.5,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_OUTDOOR_AVERAGING_HOURS] == 4.0
    assert result["data"][CONF_INDOOR_START_DELTA] == 0.7
    assert result["data"][CONF_INDOOR_STOP_DELTA] == 0.3
    assert result["data"][CONF_INDOOR_SETTLING_HOURS] == 2.5


async def test_options_custom_curve_saves_a_combined_comfort_band(hass) -> None:
    """The custom editor saves distinct heating and cooling limits together."""

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
            "heating_setpoint_1": 20,
            "cooling_setpoint_1": 24,
            "outdoor_temp_2": 15,
            "heating_setpoint_2": 20,
            "cooling_setpoint_2": 24,
            "outdoor_temp_3": 30,
            "heating_setpoint_3": 19,
            "cooling_setpoint_3": 25,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_HEATING_CURVE_POINTS] != result["data"][CONF_COOLING_CURVE_POINTS]
    assert result["data"][CONF_HEATING_CURVE_POINTS][0]["setpoint"] == 20
    assert result["data"][CONF_COOLING_CURVE_POINTS][0]["setpoint"] == 24


async def test_profile_flow_has_one_building_profile_field(hass) -> None:
    """Users choose one coherent profile instead of separate mode profiles."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Boiler",
        data={CONF_HEATING_CLIMATE: "climate.boiler"},
        options={},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "preset"},
    )
    fields = {marker.schema: value for marker, value in result["data_schema"].schema.items()}

    assert list(fields) == ["preset"]
    values = [item["value"] for item in fields["preset"].config["options"]]
    assert "comfort" in values
    assert "eco" in values
    assert "rail_aggressive_cooling" not in values


async def test_options_profile_updates_both_automatic_comfort_curves(hass) -> None:
    """One profile selection updates the complete automatic comfort band."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={
            CONF_COOLING_CLIMATE: "climate.airco",
            CONF_HEATING_CLIMATE: "climate.boiler",
        },
        options={},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "preset"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"preset": "eco"},
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_COOLING_PRESET] == "eco"
    assert result["data"][CONF_HEATING_PRESET] == "eco"
    assert result["data"][CONF_HEATING_CURVE_POINTS] == preset_curve("eco", "heating")
    assert result["data"][CONF_COOLING_CURVE_POINTS] != result["data"][CONF_HEATING_CURVE_POINTS]


async def test_config_flow_rejects_climate_without_cooling_mode(hass) -> None:
    """A heating-only climate entity cannot be selected for cooling control."""

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    # Simulate capabilities changing after the form was opened; submission validation
    # remains a second line of defense in addition to selector filtering.
    hass.states.async_set("climate.heater", "off", {"hvac_modes": ["off", "heat"]})
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
