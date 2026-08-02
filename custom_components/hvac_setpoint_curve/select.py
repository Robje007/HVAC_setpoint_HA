"""Select platform for HVAC Setpoint Curve presets."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HvacSetpointConfigEntry
from .const import (
    CONF_COOLING_CURVE_POINTS,
    CONF_CURVE_POINTS,
    CONF_HEATING_CURVE_POINTS,
    CONF_PRESET,
    DEFAULT_HEATING_CURVE_POINTS,
    DOMAIN,
    PRESET_CUSTOM,
    PRESETS,
)
from .entity import HvacSetpointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HvacSetpointConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up preset select entity."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PresetSelect(coordinator)])


class PresetSelect(HvacSetpointEntity, SelectEntity):
    """Select entity for applying built-in presets."""

    _attr_translation_key = "preset"

    def __init__(self, coordinator) -> None:
        """Initialize the select."""

        super().__init__(coordinator, "preset")
        self._attr_options = [PRESETS[key]["name"] for key in PRESETS] + ["Custom"]

    @property
    def current_option(self) -> str | None:
        """Return current preset label."""

        preset = self.coordinator.merged_options.get(CONF_PRESET, PRESET_CUSTOM)
        if preset in PRESETS:
            return PRESETS[preset]["name"]
        return "Custom"

    async def async_select_option(self, option: str) -> None:
        """Apply a preset, overwriting curve points."""

        preset_key = next((key for key, preset in PRESETS.items() if preset["name"] == option), PRESET_CUSTOM)
        new_options = {**self.coordinator.config_entry.options, CONF_PRESET: preset_key}
        if preset_key in PRESETS:
            new_options[CONF_CURVE_POINTS] = PRESETS[preset_key]["points"]
            new_options[CONF_COOLING_CURVE_POINTS] = PRESETS[preset_key]["points"]
            new_options.setdefault(CONF_HEATING_CURVE_POINTS, DEFAULT_HEATING_CURVE_POINTS)
        else:
            shared_points = self.coordinator.merged_options.get(
                CONF_CURVE_POINTS,
                self.coordinator.merged_options.get(CONF_COOLING_CURVE_POINTS),
            )
            if shared_points:
                new_options[CONF_CURVE_POINTS] = shared_points
                new_options[CONF_COOLING_CURVE_POINTS] = shared_points
                new_options[CONF_HEATING_CURVE_POINTS] = shared_points
        self.coordinator.hass.config_entries.async_update_entry(
            self.coordinator.config_entry,
            options=new_options,
        )
        await self.coordinator.async_request_refresh()
