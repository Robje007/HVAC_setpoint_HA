"""Single building-profile selector for HVAC Setpoint Curve."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HvacSetpointConfigEntry
from .const import (
    CONF_COOLING_CURVE_POINTS,
    CONF_COOLING_PRESET,
    CONF_HEATING_CURVE_POINTS,
    CONF_HEATING_PRESET,
    CONF_PRESET,
    DEFAULT_PRESET,
    DOMAIN,
    PRESET_CUSTOM,
    preset_curve,
    preset_name,
)
from .entity import HvacSetpointEntity

VISIBLE_PROFILES = ("comfort", "eco")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HvacSetpointConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one profile selector for the complete zone."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BuildingProfileSelect(coordinator)])


class BuildingProfileSelect(HvacSetpointEntity, SelectEntity):
    """Apply a coherent heating, neutral-zone and cooling profile."""

    _attr_translation_key = "building_profile"
    _attr_icon = "mdi:home-thermometer-outline"

    def __init__(self, coordinator) -> None:
        """Initialize the building profile selector."""

        super().__init__(coordinator, "building_profile")
        language = coordinator.hass.config.language
        self._names = {key: preset_name(key, language) for key in VISIBLE_PROFILES}
        self._custom_name = (
            "Aangepast — wijzigen via Configureren"
            if str(language).lower().startswith("nl")
            else "Custom — edit via Configure"
        )
        self._attr_options = [*self._names.values(), self._custom_name]

    @property
    def current_option(self) -> str:
        """Return the active building profile."""

        preset = self.coordinator.merged_options.get(CONF_PRESET, DEFAULT_PRESET)
        return self._names.get(preset, self._custom_name)

    async def async_select_option(self, option: str) -> None:
        """Apply both comfort curves."""

        preset = next((key for key, name in self._names.items() if name == option), PRESET_CUSTOM)
        new_options = {
            **self.coordinator.config_entry.options,
            CONF_PRESET: preset,
            CONF_COOLING_PRESET: preset,
            CONF_HEATING_PRESET: preset,
        }
        if preset != PRESET_CUSTOM:
            new_options.update(
                {
                    CONF_COOLING_CURVE_POINTS: preset_curve(preset, "cooling"),
                    CONF_HEATING_CURVE_POINTS: preset_curve(preset, "heating"),
                }
            )
        self.coordinator.hass.config_entries.async_update_entry(
            self.coordinator.config_entry,
            options=new_options,
        )
        await self.coordinator.async_request_refresh()
